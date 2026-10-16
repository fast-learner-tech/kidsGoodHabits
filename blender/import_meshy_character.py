"""Turn a Meshy (or any painted-face) GLB character into a show character: rig, lip-sync, blinks.

Run:
  blender -b --factory-startup --python blender/import_meshy_character.py -- \
      --glb assets/_downloads/meshy/pip.glb --name Pip --height 1.15 --save assets/characters/pip_meshy.blend

Options:
  --target-verts N    decimate heavier models down to about N vertices first (default 40000)
  --arms-locked       arms stay part of the body (e.g. hands in pockets): no arm bones
  --quadruped         four-legged pet: root, body, head and tail bones, blinks, no mouth
  --mouth X,Z,HW,HH   painted mouth box (world units after scaling) when it cannot be found automatically
  --eyes X0,X1,Z0,Z1;X0,X1,Z0,Z1   painted eye boxes (character's right eye first), same units
  --closed-mouth      the painted mouth is a closed smile: a dark mouth inside is added and the jaw drops

What it does
  1. Decimates very heavy models (textures and normal maps are kept).
  2. Finds the painted eyes (whites, or dark pupils for --quadruped) and mouth (teeth, else lips) with a flat,
     straight-on render of the head.
  3. Scales the model to --height (feet on the floor, centred), clears flat-shaded normals, smooths it, and
     subdivides around the eyes and mouth so they deform smoothly.
  4. Finds the body landmarks from the mesh (chin and neck from the face, hips from the gap between the legs,
     shoulders from the torso width, arms from the fingertips; works for T-pose and arms-down poses), builds an
     armature (root, torso, chest, neck, head, arm/forearm/hand, leg/shin/foot), skins it with region-safe
     distance weights and lowers the arms to a relaxed rest pose.
  5. Adds shape keys on the body: mouth_A ... mouth_H, mouth_X (the painted mouth squashes and stretches like a
     jaw) for blender/apply_lipsync.py, and blink_L / blink_R (the painted eyes close down to the lower lid).

Result: a collection <Name> with <Name>_rig and <Name>_Body. Rig custom properties: "mouth_object" (object with
the mouth_* keys; absent for pets), "blink" = "shape_keys", "arms" = "free" / "locked" / "none".
Characters face -Y; their left side is +X.
"""
import argparse
import math
import os
import sys
import tempfile

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

# mouth shapes as (width scale, opening scale) relative to the painted mouth, for Rhubarb's letters
MOUTH_SHAPES = {
    "A": (1.0, 0.12),   # closed (P B M)
    "B": (1.0, 0.55),   # slightly open (K S T)
    "C": (1.0, 1.0),    # open (E)  = as painted
    "D": (1.06, 1.45),  # wide open (A)
    "E": (0.82, 1.15),  # rounded (O)
    "F": (0.68, 0.7),   # puckered (U W)
    "G": (1.0, 0.42),   # teeth on lip (F V)
    "H": (1.0, 0.85),   # tongue up (L)
    "X": (1.0, 0.3),    # rest: a closed smile
}
# closed painted mouths: (width scale, how far the jaw opens, 0..1) per Rhubarb letter
CLOSED_MOUTH_OPEN = {
    "A": (1.0, 0.0), "B": (1.0, 0.35), "C": (1.0, 0.6), "D": (1.05, 1.0), "E": (0.8, 0.7),
    "F": (0.65, 0.4), "G": (1.0, 0.25), "H": (1.0, 0.5), "X": (1.0, 0.0),
}
HOLE_SCALE = 1e-4  # the mouth inside is stored collapsed to this size, hidden in the head


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--glb", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--height", type=float, required=True)
    p.add_argument("--save", required=True)
    p.add_argument("--target-verts", type=int, default=22000)  # collapse lands ~1.8x higher (UV seams)
    p.add_argument("--arms-locked", action="store_true")
    p.add_argument("--quadruped", action="store_true")
    p.add_argument("--mouth", default=None)
    p.add_argument("--eyes", default=None)
    p.add_argument("--closed-mouth", action="store_true")
    return p.parse_args(argv)


def overrides(a, eyes, mouth, closed_mouth):
    """Apply --eyes / --mouth / --closed-mouth on top of what was detected."""
    if a.eyes:
        eyes = [tuple(float(v) for v in e.split(",")) for e in a.eyes.split(";")]
    if a.mouth:
        x, z, w, h = (float(v) for v in a.mouth.split(","))
        mouth = (x - w, x + w, z - h, z + h)
    elif isinstance(mouth, tuple) and mouth and mouth[0] == "closed":
        closed_mouth, mouth = True, mouth[1]
    return eyes, mouth, closed_mouth or a.closed_mouth


def add_mouth_inside(body, mouth):
    """Join a dark mouth-inside blob into the body, collapsed and hidden in the head until the jaw opens."""
    co = verts(body)
    mx0, mx1, mz0, mz1 = mouth
    mcx, mcz, hw = (mx0 + mx1) / 2, (mz0 + mz1) / 2, (mx1 - mx0) / 2
    near = (np.abs(co[:, 0] - mcx) < hw * 0.3) & (np.abs(co[:, 2] - mcz) < (mz1 - mz0))
    y_front = float(co[near, 1].min())
    centre = Vector((mcx, y_front + hw * 0.5, mcz))
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=HOLE_SCALE)
    bmesh.ops.translate(bm, verts=bm.verts, vec=centre)
    me = bpy.data.meshes.new("MouthInside")
    bm.to_mesh(me)
    bm.free()
    hole = bpy.data.objects.new("MouthInside", me)
    bpy.context.scene.collection.objects.link(hole)
    hole.matrix_world = body.matrix_world
    inside = bpy.data.materials.new("M_MouthInside")
    inside.use_nodes = True
    inside.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.035, 0.003, 0.004, 1)
    inside.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
    inside.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.0  # reads dark, not grey
    me.materials.append(inside)
    for g in ("head", "mouth_inside"):
        hole.vertex_groups.new(name=g).add(list(range(len(me.vertices))), 1.0, "REPLACE")
    bpy.ops.object.select_all(action="DESELECT")
    hole.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body["mouth_inside_centre"] = list(centre)
    body["mouth_front_y"] = y_front


def verts(obj):
    co = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


# ---------------------------------------------------------------- 1. decimate

def decimate(body, target):
    n = len(body.data.vertices)
    if n <= target * 1.3:
        return
    mod = body.modifiers.new("Decimate", "DECIMATE")
    mod.decimate_type, mod.ratio = "COLLAPSE", target / n
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier=mod.name)
    print(f"decimated {n} -> {len(body.data.vertices)} vertices")


# ---------------------------------------------------------------- 2. face landmarks

def blobs(mask):
    seen = np.zeros_like(mask)
    found = []
    h, w = mask.shape
    for r0, c0 in zip(*np.nonzero(mask)):
        if seen[r0, c0]:
            continue
        stack, rows, cols = [(r0, c0)], [], []
        seen[r0, c0] = True
        while stack:
            rr, cc = stack.pop()
            rows.append(rr)
            cols.append(cc)
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nr, nc = rr + dr, cc + dc
                if 0 <= nr < h and 0 <= nc < w and mask[nr, nc] and not seen[nr, nc]:
                    seen[nr, nc] = True
                    stack.append((nr, nc))
        found.append((len(rows), np.array(rows), np.array(cols)))
    return sorted(found, key=lambda b: -b[0])


def find_face(body, quadruped):
    """Flat-colour orthographic render of the head -> eye boxes and mouth box (x0, x1, z0, z1), world units."""
    co = verts(body) @ np.array(body.matrix_world)[:3, :3].T + np.array(body.matrix_world)[:3, 3]
    top, bot = co[:, 2].max(), co[:, 2].min()
    H = top - bot
    sc = bpy.context.scene
    sc.world = bpy.data.worlds.new("FaceFindWorld")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.0, 0.6, 0.0, 1)  # green screen
    cam = bpy.data.objects.new("FaceFindCam", bpy.data.cameras.new("FaceFindCam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    size = H * (0.6 if quadruped else 0.45)  # tall hair (puffs, buns) pushes the face down the window
    cz = top - size / 2 - H * 0.02
    cx = (co[:, 0].min() + co[:, 0].max()) / 2
    cam.data.type, cam.data.ortho_scale = "ORTHO", size
    cam.location = (cx, co[:, 1].min() - 2, cz)
    cam.rotation_euler = (math.radians(90), 0, 0)
    r = sc.render
    r.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "FLAT"
    sc.display.shading.color_type = "TEXTURE"
    sc.view_settings.view_transform = "Standard"
    res = 800
    r.resolution_x = r.resolution_y = res
    r.resolution_percentage = 100
    path = os.path.join(tempfile.mkdtemp(), "face.png")
    r.filepath = path
    bpy.ops.render.render(write_still=True)
    if os.environ.get("FACE_DEBUG"):  # keep the face render for inspection
        import shutil
        shutil.copy(path, os.environ["FACE_DEBUG"])
    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:]).reshape(res, res, 4)[::-1, :, :3]
    bpy.data.images.remove(img)
    bpy.data.objects.remove(cam, do_unlink=True)
    lum, sat = px.mean(axis=2), px.max(axis=2) - px.min(axis=2)
    green = (px[:, :, 1] > 0.45) & (px[:, :, 0] < 0.2) & (px[:, :, 2] < 0.2)

    def world(row, col):
        return cx + (col + 0.5 - res / 2) / res * size, cz + (res / 2 - row - 0.5) / res * size

    def box(rows, cols):
        x0, z1 = world(rows.min(), cols.min())
        x1, z0 = world(rows.max(), cols.max())
        return x0, x1, z0, z1

    min_px = 150
    if quadruped:  # big dark eyes, no whites
        cand = [b for b in blobs((lum < 0.14) & ~green) if b[0] > min_px]
    else:
        cand = [b for b in blobs((lum > 0.7) & (sat < 0.14) & ~green) if b[0] > min_px]  # eye whites can be soft grey
    # the two eyes: the largest pair of blobs side by side at about the same height
    best = None
    for i in range(min(len(cand), 6)):
        for j in range(i + 1, min(len(cand), 6)):
            bi, bj = box(cand[i][1], cand[i][2]), box(cand[j][1], cand[j][2])
            dz = abs((bi[2] + bi[3]) - (bj[2] + bj[3])) / 2
            hgt = max(bi[3] - bi[2], bj[3] - bj[2])
            tilt = 1.4 if quadruped else 0.8  # pets often tilt their heads a lot
            if dz < hgt * tilt and (bi[0] > bj[1] or bj[0] > bi[1]):
                score = cand[i][0] + cand[j][0]
                if best is None or score > best[0]:
                    best = (score, sorted((bi, bj), key=lambda b: b[0]))
    if not best:
        raise SystemExit("Could not find two painted eyes")
    eyes = best[1]
    if quadruped:  # the dark blobs are the pupils: grow them to the whole eye (iris ring included)
        grow = lambda b, k: (b[0] - (b[1] - b[0]) * k, b[1] + (b[1] - b[0]) * k, b[2] - (b[3] - b[2]) * k, b[3] + (b[3] - b[2]) * k)
        return [grow(e, 0.3) for e in eyes], None
    eye_bottom = min(e[2] for e in eyes)
    ex0, ex1 = eyes[0][0], eyes[1][1]
    eye_h = max(e[3] - e[2] for e in eyes)
    lowest = eye_bottom - eye_h * 2.6  # teeth sit just under the nose, never down at a white collar
    teeth = [box(r_, c_) for n, r_, c_ in cand if n > 60 and lowest < box(r_, c_)[3] < eye_bottom and box(r_, c_)[2] > lowest]
    if teeth:
        m = [min(b[0] for b in teeth), max(b[1] for b in teeth), min(b[2] for b in teeth), max(b[3] for b in teeth)]
        # grow the box over the dark mouth opening around the teeth (lips, tongue, shadow)
        redness = px[:, :, 0] - np.maximum(px[:, :, 1], px[:, :, 2])
        inside = (lum < 0.5) & (redness > 0.08) & ~green
        w, h = m[1] - m[0], m[3] - m[2]
        t0 = list(m)
        small_teeth = w < (ex1 - ex0) * 0.3  # only a few teeth show: the mouth opening is bigger than they are
        for _, r_, c_ in (blobs(inside) if small_teeth else []):
            b = box(r_, c_)
            touches = b[0] < t0[1] + w * 0.3 and b[1] > t0[0] - w * 0.3 and b[2] < t0[3] + h * 1.5 and b[3] > t0[2] - h * 1.5
            if touches and b[3] < eye_bottom and (b[1] - b[0]) < w * 2.5:
                m = [min(m[0], b[0]), max(m[1], b[1]), min(m[2], b[2]), max(m[3], b[3])]
        return eyes, tuple(m)
    # closed painted mouth: the largest reddish-dark blob below the eyes, between them
    redness = px[:, :, 0] - np.maximum(px[:, :, 1], px[:, :, 2])
    lips = [b for b in blobs((redness > 0.1) & (lum < 0.6) & ~green) if b[0] > 60]
    lips = [box(r_, c_) for _, r_, c_ in lips]
    lips = [b for b in lips if b[3] < eye_bottom - (eyes[0][3] - eyes[0][2]) * 0.6 and b[0] > ex0 and b[1] < ex1]
    return eyes, ("closed", lips[0]) if lips else None


# ---------------------------------------------------------------- 3. normalise, smooth, subdivide face

def normalise(body, height):
    co = verts(body) @ np.array(body.matrix_world)[:3, :3].T + np.array(body.matrix_world)[:3, 3]
    lo, hi = co.min(axis=0), co.max(axis=0)
    s = height / (hi[2] - lo[2])
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    m = Matrix.Scale(s, 4) @ Matrix.Translation(Vector((-cx, -cy, -lo[2])))
    body.data.transform(m @ body.matrix_world)
    body.matrix_world = Matrix.Identity(4)
    return lambda x, z: (s * (x - cx), s * (z - lo[2]))


def subdivide_regions(body, boxes, cuts=2):
    bm = bmesh.new()
    bm.from_mesh(body.data)
    edges = set()
    for x0, x1, z0, z1 in boxes:
        for f in bm.faces:
            c = f.calc_center_median()
            if x0 <= c.x <= x1 and z0 <= c.z <= z1 and f.normal.y < 0.3:
                edges.update(f.edges)
    bmesh.ops.subdivide_edges(bm, edges=list(edges), cuts=cuts, use_grid_fill=True)
    bm.to_mesh(body.data)
    bm.free()


# ---------------------------------------------------------------- 4. body landmarks and rig

def triangles(obj):
    me = obj.data
    me.calc_loop_triangles()
    idx = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", idx)
    return verts(obj)[idx.reshape(-1, 3)]


def slice_points(tri, z, step):
    """Points every `step` along the outline where the plane at height z cuts the surface.
    (Vertices of a decimated mesh are too sparse to judge gaps; the cut outline is not.)"""
    zs = tri[:, :, 2]
    t3 = tri[(zs.min(axis=1) <= z) & (zs.max(axis=1) > z)]
    out = []
    for tr in t3:
        hits = []
        for a, b in ((tr[0], tr[1]), (tr[1], tr[2]), (tr[2], tr[0])):
            if (a[2] - z) * (b[2] - z) <= 0 and abs(b[2] - a[2]) > 1e-12:
                hits.append(a + (b - a) * (z - a[2]) / (b[2] - a[2]))
        if len(hits) >= 2:
            n = max(2, int(np.linalg.norm(hits[1] - hits[0]) / step) + 2)
            out.append(np.linspace(hits[0], hits[1], n))
    return np.vstack(out) if out else np.zeros((0, 3))


def outer_cluster(xs, gap):
    """Given |x| values of one z-slice, return the threshold beyond which points are separate (the arm), or None."""
    if len(xs) < 4:
        return None
    s = np.sort(xs)
    d = np.diff(s)
    i = np.nonzero(d > gap)[0]
    return s[i[0] + 1] if len(i) else None


def landmarks(co, tri, H, eyes, mouth):
    j = {}
    eye_z = np.mean([(e[2] + e[3]) / 2 for e in eyes])
    mouth_z = (mouth[2] + mouth[3]) / 2
    j["chin_z"] = mouth[2] - (eye_z - mouth_z) * 0.55
    j["neck_z"] = j["chin_z"] - H * 0.03
    # crotch: lowest height (above the feet) with geometry on the centre line
    centre = co[np.abs(co[:, 0]) < H * 0.012]
    zs = np.sort(centre[:, 2])
    zs = zs[zs > H * 0.12]
    j["crotch_z"] = float(zs[0]) if len(zs) else H * 0.38
    j["hip_z"] = j["crotch_z"] + H * 0.04
    j["ankle_z"] = H * 0.06
    j["knee_z"] = (j["hip_z"] + j["ankle_z"]) / 2
    low = co[(co[:, 2] < j["crotch_z"] * 0.6) & (co[:, 2] > H * 0.1)]
    j["leg_x"] = float(np.median(np.abs(low[:, 0])))
    # torso half-width at the waist (between hips and neck), ignoring arms beyond a gap
    zw = j["hip_z"] + (j["neck_z"] - j["hip_z"]) * 0.3
    xs = np.abs(slice_points(tri, zw, H * 0.002)[:, 0])
    cut = outer_cluster(xs, H * 0.015)
    j["torso_half"] = float(np.percentile(xs[xs < cut], 98) if cut is not None else np.percentile(xs, 80))
    j["shoulder_z"] = j["neck_z"] - (j["neck_z"] - j["hip_z"]) * 0.14
    # shoulder joints sit at the outer edge of the chest, measured just below the armpits
    zc = j["shoulder_z"] - H * 0.07
    xs = np.abs(slice_points(tri, zc, H * 0.002)[:, 0])
    cut = outer_cluster(xs, H * 0.015)
    chest_half = float(np.percentile(xs[xs < cut], 98) if cut is not None else np.percentile(xs, 80))
    j["shoulder_x"] = max(chest_half, j["torso_half"]) * 1.35
    return j


def arm_chain(co, H, j, side):
    """Shoulder, elbow, wrist, fingertip for one arm (works for T-pose and arms-down poses)."""
    sgn = 1 if side == "L" else -1
    band = (co[:, 2] > j["crotch_z"] - H * 0.12) & (co[:, 2] < j["shoulder_z"] + H * 0.06) & (sgn * co[:, 0] > 0)
    pts = co[band]
    tip = pts[np.argmax(sgn * pts[:, 0])]
    near_tip = pts[np.linalg.norm(pts - tip, axis=1) < H * 0.06]
    y = float(np.median(near_tip[:, 1]))
    horizontal = tip[2] > j["shoulder_z"] - H * 0.06
    s = Vector((sgn * j["shoulder_x"], y, float(tip[2]) if horizontal else j["shoulder_z"]))
    t = Vector((float(tip[0]), y, float(tip[2])))
    return s, s + (t - s) * 0.42, s + (t - s) * 0.76, t


def make_armature(name):
    arm = bpy.data.armatures.new(f"{name}_rig")
    rig = bpy.data.objects.new(f"{name}_rig", arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    return rig, arm.edit_bones


def add_bone(eb, n, head, tail, parent=None, deform=True):
    b = eb.new(n)
    b.head, b.tail = Vector(head), Vector(tail)
    b.use_deform = deform
    if parent:
        b.parent = eb[parent]
        b.use_connect = (Vector(head) - eb[parent].tail).length < 1e-4
    return b


def build_humanoid_rig(name, body, H, eyes, mouth, arms_locked):
    co = verts(body)
    tri = triangles(body)
    j = landmarks(co, tri, H, eyes, mouth)
    chains = {} if arms_locked else {s: arm_chain(co, H, j, s) for s in ("L", "R")}
    rig, eb = make_armature(name)
    add_bone(eb, "root", (0, 0, 0), (0, 0, H * 0.1), deform=False)
    mid = j["hip_z"] + (j["neck_z"] - j["hip_z"]) * 0.5
    add_bone(eb, "torso", (0, 0, j["hip_z"]), (0, 0, mid), "root")
    add_bone(eb, "chest", (0, 0, mid), (0, 0, j["neck_z"]), "torso")
    add_bone(eb, "neck", (0, 0, j["neck_z"]), (0, 0, j["chin_z"]), "chest")
    add_bone(eb, "head", (0, 0, j["chin_z"]), (0, 0, H), "neck")
    for s, x in (("L", 1), ("R", -1)):
        if s in chains:
            sh, el, wr, tip = chains[s]
            add_bone(eb, f"arm.{s}", sh, el, "chest")
            add_bone(eb, f"forearm.{s}", el, wr, f"arm.{s}")
            add_bone(eb, f"hand.{s}", wr, tip, f"forearm.{s}")
        lx = x * j["leg_x"]
        add_bone(eb, f"leg.{s}", (lx, 0, j["hip_z"]), (lx, 0, j["knee_z"]), "torso")
        add_bone(eb, f"shin.{s}", (lx, 0, j["knee_z"]), (lx, 0, j["ankle_z"]), f"leg.{s}")
        add_bone(eb, f"foot.{s}", (lx, 0, j["ankle_z"]), (lx, -H * 0.08, H * 0.02), f"shin.{s}")
    bpy.ops.object.mode_set(mode="OBJECT")

    # which vertices are arm: per height slice, points beyond a gap from the body
    is_arm = np.zeros(len(co), bool)
    if chains:
        step = H * 0.01
        for z in np.arange(j["crotch_z"] - H * 0.15, j["shoulder_z"] + step, step):
            sl = np.nonzero(np.abs(co[:, 2] - z) < step / 2)[0]
            outline = slice_points(tri, z, H * 0.002)
            for sgn in (1, -1):
                part = sl[sgn * co[sl, 0] > 0]
                cut = outer_cluster(np.abs(outline[sgn * outline[:, 0] > 0][:, 0]), H * 0.015)
                if cut is not None:
                    is_arm[part[np.abs(co[part, 0]) >= cut]] = True
        for s in chains:  # everything clearly past the shoulder is arm too (T-pose)
            sgn = 1 if s == "L" else -1
            is_arm |= (sgn * co[:, 0] > j["torso_half"] * 1.15) & (co[:, 2] > j["shoulder_z"] - H * 0.12) & (co[:, 2] < j["chin_z"])

    def allowed(names):
        bones = [b.name for b in rig.data.bones if b.use_deform]
        m = np.zeros((len(co), len(bones)), bool)
        idx = {n: i for i, n in enumerate(bones)}
        z, x = co[:, 2], co[:, 0]
        head = z >= j["chin_z"]
        neck = (z >= j["neck_z"]) & ~head
        body_ = ~head & ~neck
        m[head, idx["head"]] = True
        for n in ("neck", "head", "chest"):
            m[neck, idx[n]] = True
        # torso bones may influence the whole body, so shoulders blend smoothly into the arms
        for n in ("torso", "chest", "neck"):
            m[body_, idx[n]] = True
        for s, sgn in (("L", 1), ("R", -1)):
            side = sgn * x > 0
            # legs never move hands that hang beside the thighs ...
            legs = body_ & ~is_arm & side & (z < j["hip_z"] + H * 0.05)
            for n in (f"leg.{s}", f"shin.{s}", f"foot.{s}"):
                m[legs, idx[n]] = True
            if s in chains:
                # ... and arms never move the thighs: below the hips only true arm points follow them
                armv = side & body_ & ((np.abs(x) > j["shoulder_x"] * 0.75) & (z > j["hip_z"] + H * 0.05) | is_arm)
                for n in (f"arm.{s}", f"forearm.{s}", f"hand.{s}"):
                    m[armv, idx[n]] = True
        return bones, m

    skin(body, rig, *allowed(None))
    print("landmarks", {k: round(v, 3) for k, v in j.items()}, "arms", "locked" if arms_locked else "free")
    return rig


def build_pet_rig(name, body, H, eyes):
    co = verts(body)
    eye_z = np.mean([(e[2] + e[3]) / 2 for e in eyes])
    neck_z = eye_z - (H - eye_z) * 0.5
    back_y = np.percentile(co[:, 1], 70)
    tail = (co[:, 1] > back_y) & (co[:, 2] < neck_z) & (co[:, 2] > H * 0.05)
    # the tail is the part of the back that sticks out furthest
    if np.any(tail):
        tail_pts = co[tail]
        base = tail_pts[np.argmin(tail_pts[:, 2])]
        tip = tail_pts[np.argmax(tail_pts[:, 2] + (tail_pts[:, 1] - back_y))]
    rig, eb = make_armature(name)
    add_bone(eb, "root", (0, 0, 0), (0, 0, H * 0.1), deform=False)
    add_bone(eb, "body", (0, 0, H * 0.1), (0, 0, neck_z), "root")
    add_bone(eb, "head", (0, 0, neck_z), (0, 0, H), "body")
    if np.any(tail):
        add_bone(eb, "tail", tuple(base), tuple(tip), "body")
    bpy.ops.object.mode_set(mode="OBJECT")
    bones = [b.name for b in rig.data.bones if b.use_deform]
    idx = {n: i for i, n in enumerate(bones)}
    m = np.zeros((len(co), len(bones)), bool)
    head = co[:, 2] >= neck_z
    m[head, idx["head"]] = True
    m[~head, idx["body"]] = True
    near_neck = np.abs(co[:, 2] - neck_z) < H * 0.05
    m[near_neck, idx["head"]] = m[near_neck, idx["body"]] = True
    if "tail" in idx:
        m[tail & (co[:, 1] > back_y + (co[:, 1].max() - back_y) * 0.35), idx["tail"]] = True
    skin(body, rig, bones, m)
    return rig


def skin(body, rig, bones, allowed):
    """Two nearest allowed bones per vertex, weighted by inverse distance^4 to the bone segment."""
    co = verts(body)
    segs = [(np.array(rig.data.bones[n].head_local), np.array(rig.data.bones[n].tail_local)) for n in bones]
    dist = np.empty((len(co), len(bones)))
    for k, (a, b) in enumerate(segs):
        ab = b - a
        t = np.clip(((co - a) @ ab) / max(ab @ ab, 1e-9), 0, 1)
        dist[:, k] = np.linalg.norm(co - (a + t[:, None] * ab), axis=1)
    dist[~allowed] = np.inf
    order = np.argsort(dist, axis=1)[:, :2]
    d1 = dist[np.arange(len(co)), order[:, 0]]
    d2 = dist[np.arange(len(co)), order[:, 1]]
    w1 = 1 / np.maximum(d1, 1e-4) ** 4
    w2 = np.where(np.isfinite(d2), 1 / np.maximum(d2, 1e-4) ** 4, 0.0)
    tot = w1 + w2
    groups = [body.vertex_groups.new(name=n) for n in bones]
    for vi in range(len(co)):
        groups[order[vi, 0]].add([vi], float(w1[vi] / tot[vi]), "REPLACE")
        if w2[vi] > 0:
            groups[order[vi, 1]].add([vi], float(w2[vi] / tot[vi]), "REPLACE")
    body.parent = rig
    body.modifiers.new("Armature", "ARMATURE").object = rig


def relax_arms(body, rig, target_from_vertical=12):
    """Lower the arms to hang relaxed and make that the rest pose (before any shape keys exist)."""
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    for s, x in (("L", 1), ("R", -1)):
        bone = rig.data.bones[f"arm.{s}"]
        tip = rig.data.bones[f"hand.{s}"].tail_local
        v = tip - bone.head_local
        current = math.degrees(math.atan2(abs(v.x), -v.z))  # 0 = hanging straight down, 90 = T-pose
        pb = rig.pose.bones[f"arm.{s}"]
        local_axis = (bone.matrix_local.to_3x3().inverted() @ (Vector((0, 1, 0)) * x)).normalized()
        pb.rotation_mode = "AXIS_ANGLE"
        pb.rotation_axis_angle = (math.radians(max(0.0, current - target_from_vertical)), *local_axis)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = body
    mod = next(m for m in body.modifiers if m.type == "ARMATURE")
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply(selected=False)
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
    bpy.ops.object.mode_set(mode="OBJECT")
    body.modifiers.new("Armature", "ARMATURE").object = rig


# ---------------------------------------------------------------- 5. face shape keys

def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def face_keys(body, eyes, mouth, closed_mouth):
    co = verts(body)
    front = co[:, 1] < np.percentile(co[:, 1], 40)  # front half only (not the back of the head)
    body.shape_key_add(name="Basis", from_mix=False)

    def add(name, newco):
        kb = body.shape_key_add(name=name, from_mix=False)
        kb.data.foreach_set("co", newco.ravel())

    if mouth and closed_mouth:
        mx0, mx1, mz0, mz1 = mouth
        mcx, pivot, hw, hh = (mx0 + mx1) / 2, (mz0 + mz1) / 2, (mx1 - mx0) / 2, (mz1 - mz0) / 2
        g = body.vertex_groups["mouth_inside"].index
        hole = np.array([any(e.group == g for e in v.groups) for v in body.data.vertices])
        centre = np.array(body["mouth_inside_centre"])
        unit = (co[hole] - centre) / HOLE_SCALE
        y_front = body["mouth_front_y"]
        lower = (co[:, 2] < pivot) & ~hole
        reach = np.sqrt(((co[:, 0] - mcx) / (hw * 1.5)) ** 2 + ((pivot - co[:, 2]) / (hw * 1.6)) ** 2)
        f = smoothstep(1 - reach) * front * lower
        for letter, (sx, amount) in CLOSED_MOUTH_OPEN.items():
            new = co.copy()
            drop = amount * hw * 0.5
            new[:, 0] = mcx + (co[:, 0] - mcx) * (1 + (sx - 1) * f)
            new[:, 2] = co[:, 2] - drop * f  # lower lip and chin drop like a jaw
            if amount > 0:  # the dark inside fills the gap between the lips, just in front of the face
                # fill only the gap between the upper lip and the dropped lower lip
                top, bottom = pivot - hh * 0.25, pivot - hh * 0.25 - drop * 0.85
                radii = np.array([hw * 0.48 * sx, hw * 0.1, (top - bottom) / 2])
                c = np.array([mcx, y_front + radii[1] * 0.75, (top + bottom) / 2])  # set back: lips frame it
                new[hole] = c + unit * radii
            add(f"mouth_{letter}", new)
    elif mouth:
        mx0, mx1, mz0, mz1 = mouth
        mcx, hw, hh = (mx0 + mx1) / 2, (mx1 - mx0) / 2, max((mz1 - mz0) / 2, (mx1 - mx0) * 0.08)
        pivot = mz1 + hh * 0.15
        dx = (co[:, 0] - mcx) / (hw * 1.5)
        below = co[:, 2] < pivot
        dz_low = (pivot - co[:, 2]) / (hh * 2 * 2.6)
        dz_up = (co[:, 2] - pivot) / (hh * 0.6)
        reach = np.where(below, np.sqrt(dx ** 2 + dz_low ** 2), np.sqrt(dx ** 2 + dz_up ** 2))
        f = smoothstep(1 - reach) * front
        for letter, (sx, sz) in (CLOSED_MOUTH_SHAPES if closed_mouth else MOUTH_SHAPES).items():
            new = co.copy()
            new[:, 0] = mcx + (co[:, 0] - mcx) * (1 + (sx - 1) * f)
            new[:, 2] = np.where(below, pivot + (co[:, 2] - pivot) * (1 + (sz - 1) * f), co[:, 2])
            add(f"mouth_{letter}", new)

    for side, (ex0, ex1, ez0, ez1) in zip(("R", "L"), eyes):  # eyes[0] is on -X = character's right
        ecx, ew, eh = (ex0 + ex1) / 2, (ex1 - ex0) / 2, (ez1 - ez0)
        epivot = ez0 + eh * 0.22
        ecz = (ez0 + ez1) / 2
        # fade out sooner above the eye so the brow, and glasses frames painted round the eye, stay put
        up = np.where(co[:, 2] > ecz, eh * 0.85, eh * 1.25)
        reach = np.sqrt(((co[:, 0] - ecx) / (ew * 1.45)) ** 2 + ((co[:, 2] - ecz) / up) ** 2)
        f = smoothstep((1 - reach) * 1.7) * front
        # leave anything standing out in front of the skin alone (glasses frames, lenses)
        near = (reach < 1.2) & front
        if near.any():
            skin_y = np.percentile(co[near, 1], 60)
            f = f * (co[:, 1] > skin_y - eh * 0.35)
        new = co.copy()
        new[:, 2] = epivot + (co[:, 2] - epivot) * (1 - 0.92 * f)
        add(f"blink_{side}", new)


# ---------------------------------------------------------------- already-rigged GLBs (Meshy "Rigged" exports)

# Meshy's Mixamo-style bones -> the names the show's animation scripts use
BONE_NAMES = {
    "Hips": "hips", "Spine": "torso", "Spine1": "spine", "Spine2": "chest", "Neck": "neck", "Head": "head",
    "LeftShoulder": "shoulder.L", "LeftArm": "arm.L", "LeftForeArm": "forearm.L", "LeftHand": "hand.L",
    "RightShoulder": "shoulder.R", "RightArm": "arm.R", "RightForeArm": "forearm.R", "RightHand": "hand.R",
    "LeftUpLeg": "leg.L", "LeftLeg": "shin.L", "LeftFoot": "foot.L", "LeftToeBase": "toe.L",
    "RightUpLeg": "leg.R", "RightLeg": "shin.R", "RightFoot": "foot.R", "RightToeBase": "toe.R",
}


def import_rigged(a, rig, body):
    """Keep Meshy's skeleton, weights and animations; rename bones, scale, and add the face shape keys."""
    for o in [o for o in bpy.data.objects if o not in (rig, body)]:
        bpy.data.objects.remove(o, do_unlink=True)  # helper objects (e.g. Meshy's icosphere)
    rig.name, rig.data.name = f"{a.name}_rig", f"{a.name}_rig"
    body.name = body.data.name = f"{a.name}_Body"
    for b in rig.data.bones:  # renaming also renames the vertex groups and the actions' channels
        short = b.name.split(":")[-1]
        if short in BONE_NAMES:
            b.name = BONE_NAMES[short]
    # a non-deforming root bone at the floor, parent of the hips (bounces, whole-body moves)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = rig.data.edit_bones
    # glTF only stores joints, so the imported bones get huge guessed lengths. Give every bone its real
    # length (the distance to its next joint), keeping its direction: skinning and the walk/run cycles depend
    # only on direction, while tools that use lengths (props at the hand, arm reach) need real ones.
    seg = {}
    for bone in eb:
        dists = [(c.head - bone.head).length for c in bone.children if (c.head - bone.head).length > 1e-6]
        if dists:
            seg[bone.name] = min(dists)
    for bone in eb:
        if bone.name in seg:
            length = seg[bone.name]
        elif bone.parent is not None and bone.parent.name in seg:
            length = seg[bone.parent.name] * (2.5 if bone.name == "head" else 0.5)
        else:
            continue
        bone.tail = bone.head + (bone.tail - bone.head).normalized() * length
    hips = eb["hips"]
    root = eb.new("root")
    root.head, root.tail, root.use_deform = Vector((0, 0, 0)), Vector((0, 0, hips.length * 0.5)), False
    hips.parent = root
    bpy.ops.object.mode_set(mode="OBJECT")
    # keep Meshy's walk/run cycles in the file, rest pose by default
    if rig.animation_data:
        rig.animation_data.action = None
    for act in list(bpy.data.actions):
        if "baselayer" in act.name:
            bpy.data.actions.remove(act)
        else:
            act.use_fake_user = True
    for pb in rig.pose.bones:
        pb.location, pb.rotation_quaternion, pb.scale = (0, 0, 0), (1, 0, 0, 0), (1, 1, 1)
    bpy.context.view_layer.update()
    # Meshy's rigged export makes the material fully metallic and feeds the colour into emission
    # (characters glow and look washed out): make it a plain, softly matte surface
    for m in body.data.materials:
        if not (m and m.use_nodes):
            continue
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        for name in ("Emission Color", "Metallic", "Roughness"):
            for link in list(bsdf.inputs[name].links):
                if name != "Roughness" or link.from_node.type == "TEX_IMAGE" and "rough" not in link.from_node.image.name.lower():
                    nt.links.remove(link)
        bsdf.inputs["Emission Strength"].default_value = 0.0
        bsdf.inputs["Metallic"].default_value = 0.0
        bsdf.inputs["Specular Tint"].default_value = (1.0, 1.0, 1.0, 1.0)  # exported as 2.0: a white haze
        m.blend_method = "OPAQUE"
        if not bsdf.inputs["Roughness"].is_linked:
            bsdf.inputs["Roughness"].default_value = 0.9  # matte, like Meshy's own roughness maps
        bsdf.inputs["Specular IOR Level"].default_value = 0.3  # softer highlights keep the colours rich

    # scale to the show height, feet on the floor, centred
    def world_co():
        mw = np.array(body.matrix_world)
        return verts(body) @ mw[:3, :3].T + mw[:3, 3]
    co = world_co()
    s = a.height / (co[:, 2].max() - co[:, 2].min())
    rig.scale = rig.scale * s
    bpy.context.view_layer.update()
    co = world_co()
    rig.location -= Vector(((co[:, 0].min() + co[:, 0].max()) / 2, (co[:, 1].min() + co[:, 1].max()) / 2, co[:, 2].min()))
    bpy.context.view_layer.update()

    eyes, mouth = find_face(body, a.quadruped)
    eyes, mouth, closed_mouth = overrides(a, eyes, mouth, False)
    if not a.quadruped and not mouth:
        raise SystemExit("No painted mouth found: pass --mouth x,z,half_w,half_h")
    print("eyes", eyes, "mouth", mouth, "closed" if closed_mouth else "")

    # face work happens in the mesh's own (centimetre) space: convert the boxes
    inv = body.matrix_world.inverted()
    def to_local(b):
        p0, p1 = inv @ Vector((b[0], 0, b[2])), inv @ Vector((b[1], 0, b[3]))
        return (p0.x, p1.x, p0.z, p1.z)
    eyes_l = [to_local(e) for e in eyes]
    mouth_l = to_local(mouth) if mouth else None

    bpy.context.view_layer.objects.active = body
    body.select_set(True)
    if body.data.has_custom_normals:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    bpy.ops.object.shade_smooth()
    pad = lambda b, k: (b[0] - (b[1] - b[0]) * k, b[1] + (b[1] - b[0]) * k, b[2] - (b[3] - b[2]) * k, b[3] + (b[3] - b[2]) * k)
    subdivide_regions(body, [pad(e, 0.4) for e in eyes_l] + ([pad(mouth_l, 0.5)] if mouth_l else []))
    subdivide_regions(body, [pad(e, 0.9) for e in eyes_l], cuts=1)  # extra detail round the eyes for clean blinks
    if closed_mouth:
        add_mouth_inside(body, mouth_l)
    face_keys(body, eyes_l, mouth_l, closed_mouth)
    unweighted = sum(1 for v in body.data.vertices if not any(g.weight > 1e-4 for g in v.groups))
    print(f"rigged import: {len(body.data.vertices)} vertices, {unweighted} without weights, "
          f"actions {[act.name for act in bpy.data.actions]}")
    return rig


# ---------------------------------------------------------------- main

def main():
    a = parse()
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=a.glb)
    rigs = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    skinned = [o for o in bpy.data.objects if o.type == "MESH" and o.parent in rigs]
    if rigs and skinned:
        rig, body = rigs[0], max(skinned, key=lambda o: len(o.data.vertices))
        import_rigged(a, rig, body)
        rig["arms"] = "free"
        rig["mouth_object"] = body.name
        rig["blink"] = "shape_keys"
        rig["source"] = "meshy_rigged"
        coll = bpy.data.collections.new(a.name)
        bpy.context.scene.collection.children.link(coll)
        for o in (rig, body):
            for c in o.users_collection:
                c.objects.unlink(o)
            coll.objects.link(o)
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=bpy.path.abspath(a.save))
        print(f"saved {a.name} (rigged): bones {[b.name for b in rig.data.bones]}")
        return
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if len(meshes) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for o in meshes:
            o.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.join()
    body = meshes[0]
    for o in [o for o in bpy.data.objects if o != body]:
        bpy.data.objects.remove(o, do_unlink=True)
    body.name = body.data.name = f"{a.name}_Body"
    bpy.context.view_layer.update()
    decimate(body, a.target_verts)

    eyes, mouth = find_face(body, a.quadruped)
    closed_mouth = isinstance(mouth, tuple) and bool(mouth) and mouth[0] == "closed"
    if closed_mouth:
        mouth = mouth[1]

    to_new = normalise(body, a.height)
    def conv(b):
        x0, z0 = to_new(b[0], b[2])
        x1, z1 = to_new(b[1], b[3])
        return (x0, x1, z0, z1)
    eyes = [conv(e) for e in eyes]
    mouth = conv(mouth) if mouth else None
    eyes, mouth, closed_mouth = overrides(a, eyes, mouth, closed_mouth)  # overrides are in scaled units
    if not a.quadruped and not mouth:
        raise SystemExit("No painted mouth found: pass --mouth x,z,half_w,half_h")
    print("eyes", eyes, "mouth", mouth, "closed" if closed_mouth else "")

    bpy.context.view_layer.objects.active = body
    body.select_set(True)
    if body.data.has_custom_normals:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    bpy.ops.object.shade_smooth()
    pad = lambda b, k: (b[0] - (b[1] - b[0]) * k, b[1] + (b[1] - b[0]) * k, b[2] - (b[3] - b[2]) * k, b[3] + (b[3] - b[2]) * k)
    subdivide_regions(body, [pad(e, 0.4) for e in eyes] + ([pad(mouth, 0.5)] if mouth else []))

    if a.quadruped:
        rig = build_pet_rig(a.name, body, a.height, eyes)
        rig["arms"] = "none"
    else:
        rig = build_humanoid_rig(a.name, body, a.height, eyes, mouth, a.arms_locked)
        rig["arms"] = "locked" if a.arms_locked else "free"
        if not a.arms_locked:
            relax_arms(body, rig)
    if mouth and closed_mouth:
        add_mouth_inside(body, mouth)
    face_keys(body, eyes, mouth, closed_mouth)
    if mouth:
        rig["mouth_object"] = body.name
    rig["blink"] = "shape_keys"

    coll = bpy.data.collections.new(a.name)
    bpy.context.scene.collection.children.link(coll)
    for o in (rig, body):
        for c in o.users_collection:
            c.objects.unlink(o)
        coll.objects.link(o)
    bpy.ops.file.pack_all()  # keep the textures inside the .blend
    bpy.ops.wm.save_as_mainfile(filepath=bpy.path.abspath(a.save))
    print(f"saved {a.name}: {len(body.data.vertices)} vertices, bones {[b.name for b in rig.data.bones]}")


main()
