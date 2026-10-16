"""Toolkit for building animated shots from episode.json + a staging script (see blender/build_shot.py).

A staging function gets a Shot and places the set, characters, props and camera, then keys actions:

    def shot_06(s):
        s.sets("Bathroom")
        tomo = s.char("Tomo", (0, 1.2, 0.2))
        tomo.hold("ToothpasteTube", "L")
        s.camera((0, -2.4, 1.2), (0, 1.0, 0.75), 28)

Dialogue lip-sync, talking head nods, breathing and blinks are added automatically by Shot.finish().
Directions and positions given to a character are in its own space: +X is the character's left, -Y is
in front of it, +Z is up. Positions are in metres from the character's feet.
"""
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "blender"))
import lighting_rig  # noqa: E402

FPS = 24
CHAR_FILES = {"Pip": "pip_meshy", "Tomo": "tomo_meshy", "Zuri": "zuri_meshy",
              "NanaRue": "nana_rue_meshy", "Biscuit": "biscuit_meshy"}
VOICE_CHAR = {"pip": "Pip", "tomo": "Tomo", "zuri": "Zuri", "nana_rue": "NanaRue"}
SET_COLLECTIONS = ("Bedroom", "Bedroom_Day", "Bedroom_Night", "Bathroom")
Y = Vector((0, 1, 0))


def sec(t):
    """Seconds -> frame number (frame 1 is t = 0)."""
    return 1 + round(t * FPS)


def look_rot(loc, target):
    return (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def fix_quaternion_flips(obj):
    """q and -q are the same rotation, but blending from one to the other passes through nonsense (a near-zero
    quaternion). Walk each bone's rotation keys in time order and flip any key that points the other way."""
    ad = obj.animation_data
    if not (ad and ad.action):
        return
    curves = {}
    for fc in ad.action.fcurves:
        if fc.data_path.endswith("rotation_quaternion"):
            curves.setdefault(fc.data_path, {})[fc.array_index] = fc
    for chans in curves.values():
        if len(chans) != 4:
            continue
        frames = sorted({kp.co.x for fc in chans.values() for kp in fc.keyframe_points})
        prev = None
        for f in frames:
            kps = [next((kp for kp in chans[i].keyframe_points if abs(kp.co.x - f) < 1e-3), None) for i in range(4)]
            if any(k is None for k in kps):
                continue
            q = [k.co.y for k in kps]
            if prev is not None and sum(a * b for a, b in zip(prev, q)) < 0:
                q = [-v for v in q]
                for k, v in zip(kps, q):
                    k.co.y = v
                    k.handle_left.y = v
                    k.handle_right.y = v
            prev = q
        for fc in chans.values():
            fc.update()


def attach_to_bone(obj, rig, bone, world):
    """Parent obj to a pose bone so that it sits at `world` (a 4x4 matrix) right now.
    The local offset is computed directly: Blender places bone children at the bone's tail."""
    bpy.context.view_layer.update()
    pb = rig.pose.bones[bone]
    parent_world = rig.matrix_world @ pb.matrix @ Matrix.Translation((0, pb.length, 0))
    obj.parent, obj.parent_type, obj.parent_bone = rig, "BONE", bone
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = parent_world.inverted() @ world


# ---------------------------------------------------------------- characters

class Char:
    def __init__(self, shot, name, loc, facing=0.0):
        self.shot, self.name = shot, name
        lib = ROOT / "assets" / "characters" / f"{CHAR_FILES[name]}.blend"
        with bpy.data.libraries.load(str(lib)) as (_, dst):
            dst.collections = [name]
        coll = dst.collections[0]
        bpy.context.scene.collection.children.link(coll)
        self.rig = bpy.data.objects[f"{name}_rig"]
        self.body = bpy.data.objects[f"{name}_Body"]
        self.pet = name == "Biscuit"
        self.rig.location = loc
        self.rig.rotation_mode = "XYZ"  # glTF imports use quaternions, which would ignore these angles
        self.rig.rotation_euler = (0, 0, math.radians(facing))
        self.rig.animation_data_create()
        if self.rig.animation_data.action:
            self.rig.animation_data.action = None
        for pb in self.rig.pose.bones:
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.location = (0, 0, 0)
        self.keys = self.body.data.shape_keys.key_blocks
        self.scale = self.rig.scale[0]
        self.eyes_closed = []      # (start, end) frame ranges with closed eyes (no blinks there)
        self.no_breath = False
        self.look_state = {}       # frame -> (yaw, pitch, tilt) for the head
        self.held = {}             # side -> (prop, wrist-to-centre, centre-to-bristles) in metres
        self.brushing = []         # (start, end) frames spent brushing
        bpy.context.view_layer.update()
        self.mouth = self._feature("mouth_D") if not self.pet else None
        self.eye = {s: self._feature(f"blink_{s}") for s in ("L", "R")}
        if not self.pet:
            self.arm_len = {s: (self.rig.data.bones[f"arm.{s}"].length,
                                self.rig.data.bones[f"forearm.{s}"].length + self.rig.data.bones[f"hand.{s}"].length * 0.4)
                            for s in ("L", "R")}
            self.arms_down(1)
            self.shape("mouth_X", 1.0, 1)  # resting face: a closed smile

    # -- landmarks: where the mouth and eyes are, found from the shape keys that move them
    def _feature(self, key):
        kb, basis = self.keys.get(key), self.keys["Basis"]
        if kb is None:
            return None
        n = len(basis.data)
        import numpy as np
        a, b = np.empty(n * 3), np.empty(n * 3)
        basis.data.foreach_get("co", a)
        kb.data.foreach_get("co", b)
        a, b = a.reshape(-1, 3), b.reshape(-1, 3)
        d = np.linalg.norm(b - a, axis=1)
        sel = d > d.max() * 0.5
        local = Vector(a[sel].mean(axis=0))
        world = self.body.matrix_world @ local
        return self.rig.matrix_world.inverted() @ world  # armature space

    def to_arm(self, p):
        """Character-space metres -> armature space (the rig is scaled)."""
        return Vector(p) / self.scale

    # -- generic bone rotation keys
    def _key_q(self, bone, q, frame):
        pb = self.rig.pose.bones[bone]
        pb.rotation_quaternion = q
        pb.keyframe_insert("rotation_quaternion", frame=frame)

    def _aim(self, bone, direction, parent_rot):
        """Local rotation that points `bone` along `direction` (armature space), given the parent's posed rotation."""
        rest = self.rig.data.bones[bone].matrix_local.to_3x3()
        want = rest.inverted() @ (parent_rot.inverted() @ Vector(direction).normalized())
        q = Y.rotation_difference(want)
        posed = parent_rot @ (rest @ q.to_matrix() @ rest.inverted())
        return q, posed

    # -- arms: two-bone IK to a target point, elbow pushed towards a pole direction
    def reach(self, side, target, frame, pole=None, from_mouth=False, hand_rot=None):
        """Put the hand of `side` at `target` (character-space metres, or offset from the mouth).
        hand_rot: optional armature-space 3x3 orientation for the hand (aims whatever it holds)."""
        bones = self.rig.data.bones
        S = bones[f"arm.{side}"].head_local
        T = (self.mouth + self.to_arm(target)) if from_mouth else self.to_arm(target)
        L1, L2 = self.arm_len[side]
        if hand_rot is not None:  # aiming a held prop: the target is the wrist itself, not the palm
            L2 = self.rig.data.bones[f"forearm.{side}"].length
        d = T - S
        dist = min(max(d.length, abs(L1 - L2) + 1e-4), (L1 + L2) * 0.999)
        dn = d.normalized()
        x = 1 if side == "L" else -1
        pole = Vector(pole) if pole else Vector((x * 0.6, 0.3, -1.0))
        pn = (pole - dn * pole.dot(dn)).normalized()
        cos_a = (L1 * L1 + dist * dist - L2 * L2) / (2 * L1 * dist)
        sin_a = math.sqrt(max(0.0, 1 - cos_a * cos_a))
        E = S + L1 * (dn * cos_a + pn * sin_a)
        if callable(hand_rot):  # orientation that depends on where the wrist really ends up
            hand_rot = hand_rot(S + dn * dist)
        self.pose_arm(side, E - S, (S + dn * dist) - E, frame, hand_rot)
        return S + dn * dist

    def reach_world(self, side, world_point, frame, pole=None):
        """Put a hand at a point in the room (e.g. another character's hand)."""
        local = self.rig.matrix_world.inverted() @ Vector(world_point)
        self.reach(side, local * self.scale, frame, pole=pole)

    def mouth_world(self):
        return self.rig.matrix_world @ self.mouth

    def pose_arm(self, side, upper, fore, frame, hand_rot=None):
        ident = Matrix.Identity(3)
        q1, p1 = self._aim(f"arm.{side}", upper, ident)
        q2, p2 = self._aim(f"forearm.{side}", fore, p1)
        self._key_q(f"arm.{side}", q1, frame)
        self._key_q(f"forearm.{side}", q2, frame)
        qh = Quaternion()
        if hand_rot is not None:  # posed hand = forearm delta @ rest @ local  ->  solve for the local rotation
            rest = self.rig.data.bones[f"hand.{side}"].matrix_local.to_3x3()
            qh = (rest.inverted() @ p2.inverted() @ hand_rot).to_quaternion()
        self._key_q(f"hand.{side}", qh, frame)

    def arm_dir(self, side, upper, fore, frame):
        """Pose by directions given for the LEFT arm; the right arm is mirrored automatically."""
        x = 1 if side == "L" else -1
        self.pose_arm(side, Vector((x * upper[0], upper[1], upper[2])), Vector((x * fore[0], fore[1], fore[2])), frame)

    def arms_down(self, frame, sides=("L", "R")):
        for s in sides:
            self.arm_dir(s, (0.16, 0.06, -1), (0.1, -0.2, -1), frame)

    def cheer(self, frame, sides=("L", "R")):
        for s in sides:
            self.arm_dir(s, (0.35, 0.05, 1), (0.2, 0, 1), frame)

    def open_arms(self, frame, sides=("L", "R")):
        for s in sides:
            self.arm_dir(s, (0.85, -0.3, -0.35), (0.85, -0.5, 0.1), frame)

    def wave(self, side, start, end, period=10):
        self.arm_dir(side, (0.85, 0, 0.55), (0.25, 0, 1), start)
        f, k = start + period // 2, 0
        while f < end:
            self.arm_dir(side, (0.85, 0, 0.55), ((0.55, 0, 1) if k % 2 else (-0.1, 0, 1)), f)
            f += period // 2
            k += 1

    def brush(self, side, start, end, speed=8, area="front"):
        """Really brush the teeth: the hand beside the face, the brush across the mouth with its bristles on the
        teeth, little scrubbing strokes. area: "front", "side" (the backs) or "top" (the chewing tops)."""
        x = 1 if side == "L" else -1
        held = self.held.get(side)
        reach_len = (held[1] + held[2]) if held else 0.12          # wrist -> bristles, metres
        tip = self.mouth + self.to_arm((0, -0.016, -0.004))         # just in front of the teeth
        if area == "side":
            tip = self.mouth + self.to_arm((x * 0.025, -0.01, -0.004))
        # brush direction (wrist -> bristles): mostly from the side, elbow out, like real brushing; children's
        # arms are short, so the hand stays close beside the face and the handle sits in front of the cheek
        d = {"front": Vector((-x * 0.9, 0.42, -0.1)), "side": Vector((-x * 0.55, 0.8, -0.1)),
             "top": Vector((-x * 0.85, 0.4, 0.35))}[area].normalized()
        face = Vector((0, 1, 0)) if area != "top" else Vector((0, 0.35, -1))

        def aim_from(target):
            def rot(wrist):  # point the brush at the teeth from wherever the wrist really is
                yy = (target - wrist).normalized()
                zz = (face - yy * face.dot(yy)).normalized()
                return Matrix((yy.cross(zz), yy, zz)).transposed()  # columns: X, Y (brush length), Z (bristles)
            return rot

        f, k = start, 0
        while f <= end:
            stroke = 0.011 if k % 2 else -0.011                     # scrub in and out along the teeth
            wob = 0.004 if k % 4 < 2 else -0.004                    # and a little up and down: small circles
            target = tip + self.to_arm((x * stroke, 0, wob))
            wrist = target - d * (reach_len / self.scale)
            self.reach(side, wrist * self.scale, f, pole=(x * 0.9, 0.2, -0.6), hand_rot=aim_from(target))
            f += max(2, speed // 4)
            k += 1
        self.brushing.append((start, end))

    def hold_up(self, side, frame):
        """Hold something up proudly in front of the face."""
        self.arm_dir(side, (0.35, -0.6, -0.35), (0.05, -0.35, 1), frame)

    def hug_front(self, frame):
        """Both hands together in front of the chest (hugging a tube, holding a towel)."""
        for s in ("L", "R"):
            self.arm_dir(s, (0.3, -0.45, -0.75), (-0.75, -0.55, 0.25), frame)

    # -- head, neck, torso
    def _rot_world(self, bone, axis, deg):
        rest = self.rig.data.bones[bone].matrix_local.to_3x3()
        return Quaternion((rest.inverted() @ Vector(axis)).normalized(), math.radians(deg))

    def look(self, frame, yaw=0.0, pitch=0.0, tilt=0.0, hold=None):
        """Turn the head: yaw + = to the character's left, pitch + = down, tilt + = towards its left shoulder."""
        if self.pet:
            q = self._rot_world("head", (0, 0, 1), yaw) @ self._rot_world("head", (1, 0, 0), -pitch) @ \
                self._rot_world("head", (0, 1, 0), tilt)
            self._key_q("head", q, frame)
            return
        for bone, share in (("neck", 0.4), ("head", 0.6)):
            q = self._rot_world(bone, (0, 0, 1), yaw * share) @ self._rot_world(bone, (1, 0, 0), -pitch * share) @ \
                self._rot_world(bone, (0, 1, 0), tilt * share)
            self._key_q(bone, q, frame)
        self.look_state[frame] = (yaw, pitch, tilt)
        if hold:
            self.look(hold, yaw, pitch, tilt)

    def head_at(self, frame):
        prev = [f for f in self.look_state if f <= frame]
        return self.look_state[max(prev)] if prev else (0.0, 0.0, 0.0)

    def lean(self, frame, pitch=0.0, roll=0.0, bone="torso"):
        """Bend the body: pitch + = forward, roll + = towards its left."""
        q = self._rot_world(bone, (1, 0, 0), pitch) @ self._rot_world(bone, (0, 1, 0), -roll)
        self._key_q(bone, q, frame)

    def sway(self, start, end, beat_frames=15, amount=6):
        """Rock side to side on the beat (song)."""
        f, k = start, 0
        while f <= end:
            self.lean(f, roll=amount if k % 2 else -amount, bone="spine")
            f += beat_frames
            k += 1

    def nod_yes(self, start, times=2, period=8):
        y, p, t = self.head_at(start)
        for k in range(times * 2 + 1):
            self.look(start + k * period // 2, y, p + (10 if k % 2 else 0), t)

    # -- whole body
    def place(self, frame, loc=None, facing=None):
        if loc is not None:
            self.rig.location = loc
            self.rig.keyframe_insert("location", frame=frame)
        if facing is not None:
            self.rig.rotation_euler = (self.rig.rotation_euler[0], self.rig.rotation_euler[1], math.radians(facing))
            self.rig.keyframe_insert("rotation_euler", frame=frame)

    def hop(self, start, height=0.08, length=10, loc_to=None):
        base = Vector(self.rig.location)
        end = Vector(loc_to) if loc_to else base
        self.place(start, base)
        mid = (base + end) / 2 + Vector((0, 0, height))
        self.place(start + length // 2, mid)
        self.place(start + length, end)

    def spin(self, start, length=18):
        z0 = math.degrees(self.rig.rotation_euler[2])
        self.place(start, facing=z0)
        self.place(start + length, facing=z0 + 360)

    def lie_down(self, loc, frame=1):
        """Lie on the back (head towards +Y), e.g. in bed."""
        self.rig.location = loc
        self.rig.rotation_euler = (math.radians(-90), 0, 0)
        self.rig.keyframe_insert("location", frame=frame)
        self.rig.keyframe_insert("rotation_euler", frame=frame)

    def sit_legs_forward(self, frame):
        for s in ("L", "R"):
            x = 1 if s == "L" else -1
            ident = Matrix.Identity(3)
            q1, p1 = self._aim(f"leg.{s}", Vector((x * 0.08, -1, 0.02)), ident)
            q2, _ = self._aim(f"shin.{s}", Vector((x * 0.04, -1, -0.08)), p1)
            self._key_q(f"leg.{s}", q1, frame)
            self._key_q(f"shin.{s}", q2, frame)

    def crouch(self, frame, drop=0.25):
        """Bend the knees and lower the hips by `drop` metres (feet stay on the floor)."""
        bones = self.rig.data.bones
        root = self.rig.pose.bones["root"]
        root.location = (0, -drop / self.scale, 0)  # root bone points up: its local Y is the character's up
        root.keyframe_insert("location", frame=frame)
        for s in ("L", "R"):
            x = 1 if s == "L" else -1
            hip = bones[f"leg.{s}"].head_local - Vector((0, 0, drop / self.scale))
            ankle = bones[f"shin.{s}"].tail_local
            L1, L2 = bones[f"leg.{s}"].length, bones[f"shin.{s}"].length
            d = ankle - hip
            dist = min(d.length, (L1 + L2) * 0.999)
            dn = d.normalized()
            pole = Vector((x * 0.2, -1, 0))
            pn = (pole - dn * pole.dot(dn)).normalized()
            cos_a = (L1 * L1 + dist * dist - L2 * L2) / (2 * L1 * dist)
            knee = hip + L1 * (dn * cos_a + pn * math.sqrt(max(0.0, 1 - cos_a * cos_a)))
            ident = Matrix.Identity(3)
            q1, p1 = self._aim(f"leg.{s}", knee - hip, ident)
            q2, _ = self._aim(f"shin.{s}", ankle - knee, p1)
            self._key_q(f"leg.{s}", q1, frame)
            self._key_q(f"shin.{s}", q2, frame)
        self.lean(frame, pitch=12)

    def stand(self, frame):
        root = self.rig.pose.bones["root"]
        root.location = (0, 0, 0)
        root.keyframe_insert("location", frame=frame)
        for b in ("leg.L", "shin.L", "leg.R", "shin.R"):
            self._key_q(b, Quaternion(), frame)
        self.lean(frame)

    # -- face
    def shape(self, name, value, frame):
        kb = self.keys[name]
        kb.value = value
        kb.keyframe_insert("value", frame=frame)

    def mouth_hold(self, letter, start, end):
        """Hold one mouth shape (yawns, big smiles) outside dialogue."""
        names = [k.name for k in self.keys if k.name.startswith("mouth_")]
        for f in (start, end):
            for n in names:
                self.shape(n, 1.0 if n == f"mouth_{letter}" else 0.0, f)

    def grin(self, start, end):
        """The painted open smile (all mouth shapes off)."""
        for f in (start, end):
            for k in self.keys:
                if k.name.startswith("mouth_"):
                    self.shape(k.name, 0.0, f)

    def close_eyes(self, start, end):
        for s in ("L", "R"):
            self.shape(f"blink_{s}", 1.0, start)
            self.shape(f"blink_{s}", 1.0, end)
        self.eyes_closed.append((start, end))

    def open_eyes(self, frame, over=6):
        for s in ("L", "R"):
            self.shape(f"blink_{s}", 1.0, frame)
            self.shape(f"blink_{s}", 0.0, frame + over)

    def wink(self, frame, side="R", hold=10):
        self.shape(f"blink_{side}", 0.0, frame)
        self.shape(f"blink_{side}", 1.0, frame + 3)
        self.shape(f"blink_{side}", 1.0, frame + 3 + hold)
        self.shape(f"blink_{side}", 0.0, frame + 6 + hold)
        self.eyes_closed.append((frame, frame + 8 + hold))

    # -- props
    def hold(self, prop, side, along=None):
        """Attach a prop (toothbrush, tube) to a hand; it points along the hand.
        Long props are gripped near one end so they stick out past the fingers and stay visible."""
        obj = bpy.data.objects[prop]
        if prop.startswith("Toothbrush") and not self.pet:
            obj.scale = (0.85, 0.85, 0.85)  # a child's toothbrush (~15 cm)
            bpy.context.view_layer.update()
        length = obj.dimensions.z
        hand_len = self.rig.data.bones[f"hand.{side}"].length * self.scale
        if along is None:  # wrist -> prop centre: held near the end of the handle, so the (open) fingers stop
            along = (hand_len * 0.6 + length * 0.5 - 0.015) if length > 0.1 else hand_len * 0.5  # short of the face
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        pb = self.rig.pose.bones[f"hand.{side}"]
        m = self.rig.matrix_world @ pb.matrix
        rot = m.to_3x3().normalized()
        bx, by, bz = rot.col[0], rot.col[1], rot.col[2]
        r = Matrix((bx, -bz, by)).transposed()  # prop Z (its length) along the hand bone
        loc = m.translation + by * along
        attach_to_bone(obj, self.rig, f"hand.{side}", Matrix.Translation(loc) @ r.to_4x4())
        self.held[side] = (obj, along, length * 0.5 - 0.005)
        return obj

    # -- automatic life
    def lip_sync(self, line_id, at):
        names = [k.name for k in self.keys if k.name.startswith("mouth_")]
        cues = json.loads((self.shot.audio_dir / f"{line_id}.json").read_text())["mouthCues"]
        s0 = sec(at)
        prev = None
        for cue in cues:
            fr = s0 + round(cue["start"] * FPS)
            if prev is not None:
                for n in names:
                    self.shape(n, 1.0 if n == f"mouth_{prev}" else 0.0, fr - 1)
            for n in names:
                self.shape(n, 1.0 if n == f"mouth_{cue['value']}" else 0.0, fr)
            prev = cue["value"]
        end = s0 + round(cues[-1]["end"] * FPS)
        if not self.pet:  # gentle nods while talking, around wherever the head is looking
            f, k = s0, 0
            while f < end:
                y, p, t = self.head_at(f)
                self.look(f, y, p + (3 if k % 2 else -2), t + (2 if k % 3 == 0 else -1))
                f += 10
                k += 1
            y, p, t = self.head_at(end)
            self.look(end + 6, y, p, t)
        return s0, end

    def life(self, end):
        rnd = random.Random(hash(self.name) & 0xFFFF)
        if not self.no_breath and not self.pet:
            chest = self.rig.pose.bones["chest"]
            for f in range(1, end + 1, 40):
                chest.scale = (1, 1, 1)
                chest.keyframe_insert("scale", frame=f)
                chest.scale = (1.015, 1.0, 1.015)
                chest.keyframe_insert("scale", frame=f + 20)
        f = rnd.randint(15, 50)
        while f < end - 6:
            if not any(a - 4 <= f <= b + 4 for a, b in self.eyes_closed):
                for s in ("L", "R"):
                    self.shape(f"blink_{s}", 0.0, f)
                    self.shape(f"blink_{s}", 1.0, f + 2)
                    self.shape(f"blink_{s}", 0.0, f + 5)
            f += rnd.randint(60, 105)
        if self.pet and "tail" in self.rig.pose.bones:
            for f in range(1, end + 1, 30):
                self._key_q("tail", self._rot_world("tail", (0, 0, 1), 20), f)
                self._key_q("tail", self._rot_world("tail", (0, 0, 1), -20), f + 15)


# ---------------------------------------------------------------- shots

class Shot:
    def __init__(self, episode, n):
        self.ep = episode
        self.data = next(s for s in episode["shots"] if s["n"] == n)
        self.n = n
        self.end = self.data["frames"][1]
        self.audio_dir = ROOT / "audio" / episode["id"]
        self.chars = {}
        sc = bpy.context.scene
        sc.frame_start, sc.frame_end = 1, self.end
        sc.render.fps = FPS
        self.cam = None

    def sets(self, *names, mood="day"):
        for c in bpy.context.scene.collection.children:
            if c.name in SET_COLLECTIONS:
                c.hide_render = c.hide_viewport = c.name not in names
        lighting_rig.apply(mood)

    def char(self, name, loc, facing=0.0):
        c = Char(self, name, loc, facing)
        self.chars[name] = c
        return c

    def obj(self, name):
        return bpy.data.objects[name]

    def put(self, name, loc, rot=(0, 0, 0), frame=None):
        o = bpy.data.objects[name]
        o.location = loc
        o.rotation_euler = [math.radians(a) for a in rot]
        if frame is not None:
            o.keyframe_insert("location", frame=frame)
            o.keyframe_insert("rotation_euler", frame=frame)
        return o

    def camera(self, loc, target, lens=35, end_loc=None, end_target=None, end_lens=None):
        cam = bpy.data.objects.new("ShotCam", bpy.data.cameras.new("ShotCam"))
        bpy.context.scene.collection.objects.link(cam)
        bpy.context.scene.camera = cam
        cam.data.sensor_width = 36
        for f, l, t, ln in ((1, loc, target, lens), (self.end, end_loc or loc, end_target or target, end_lens or lens)):
            cam.location = l
            cam.rotation_euler = look_rot(l, t)
            cam.data.lens = ln
            cam.keyframe_insert("location", frame=f)
            cam.keyframe_insert("rotation_euler", frame=f)
            cam.data.keyframe_insert("lens", frame=f)
        self.cam = cam
        return cam

    def copy(self, name, new_name):
        src = bpy.data.objects[name]
        o = src.copy()
        o.name = new_name
        for c in src.users_collection:
            c.objects.link(o)
        return o

    def material(self, name, rgb, emit=0.0, rough=0.4):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*rgb, 1)
        b.inputs["Roughness"].default_value = rough
        if emit:
            b.inputs["Emission Color"].default_value = (*rgb, 1)
            b.inputs["Emission Strength"].default_value = emit
        return m

    def blob(self, name, world, radius, mat):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=radius, location=world)
        o = bpy.context.active_object
        o.name = name
        bpy.ops.object.shade_smooth()
        o.data.materials.append(mat)
        return o

    def stick_to(self, obj, parent, local=(0, 0, 0)):
        """Parent obj to another object at a position in that object's own space."""
        obj.parent = parent
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.location = local
        obj.rotation_euler = (0, 0, 0)
        return obj

    def on_bristles(self, paste, brush, height=0.0):
        """Toothpaste (dot or blob) sitting on a brush's bristles (bristles face the brush's -Y)."""
        return self.stick_to(bpy.data.objects[paste], bpy.data.objects[brush], (0, -0.032 - height, 0.075))

    def brush_flat(self, name, loc):
        """A toothbrush lying on the counter along X, bristles up."""
        o = bpy.data.objects[name]
        o.parent = None
        o.matrix_world = Matrix.Translation(loc) @ Matrix(((0, 0, 1), (-1, 0, 0), (0, -1, 0))).to_4x4()
        return o

    def scale_keys(self, obj, keys):
        o = bpy.data.objects[obj] if isinstance(obj, str) else obj
        for f, v in keys:
            o.scale = (v, v, v) if isinstance(v, (int, float)) else v
            o.keyframe_insert("scale", frame=f)

    def timer(self, loc, sand_top=0.0):
        """Place the sand timer; sand_top is how much sand is still in the top bulb (0..1)."""
        t = bpy.data.objects["SandTimer"]
        t.location = loc
        bpy.context.view_layer.update()
        top = bpy.data.objects.get("SandTop") or self.copy("SandTimer_SandBottom", "SandTop")
        top.parent = None
        top.matrix_world = t.matrix_world @ Matrix.Translation((0, 0, 0.125)) @ Matrix.Rotation(math.pi, 4, "X")
        top.parent = t
        top.matrix_parent_inverse = t.matrix_world.inverted()
        self.sand(sand_top, 1)
        return t

    def sand(self, top_amount, frame):
        """Key how much sand is in the top bulb (the bottom gets the rest)."""
        for name, v in (("SandTop", top_amount), ("SandTimer_SandBottom", 1 - top_amount)):
            o = bpy.data.objects[name]
            o.scale = (1, 1, max(v, 0.02))
            o.keyframe_insert("scale", frame=frame)

    def flip_timer(self, start, length=12):
        t = bpy.data.objects["SandTimer"]
        z0 = t.location.z
        t.rotation_euler = (0, 0, 0)
        t.keyframe_insert("rotation_euler", frame=start)
        t.keyframe_insert("location", frame=start)
        t.location.z = z0 + 0.06
        t.keyframe_insert("location", frame=start + length // 2)
        t.rotation_euler = (math.pi, 0, 0)
        t.location.z = z0 + 0.185  # upside down, resting on what was its top cap
        t.keyframe_insert("rotation_euler", frame=start + length)
        t.keyframe_insert("location", frame=start + length)

    def light_patch(self, start_loc, end_loc, energy=150):
        """A soft patch of 'window' light gliding across the floor (time passing)."""
        data = bpy.data.lights.new("LightPatch", "SPOT")
        data.energy, data.spot_size, data.spot_blend, data.color = energy, math.radians(35), 0.8, (1.0, 0.92, 0.75)
        o = bpy.data.objects.new("LightPatch", data)
        bpy.context.scene.collection.objects.link(o)
        for f, loc in ((1, start_loc), (self.end, end_loc)):
            o.location = loc
            o.rotation_euler = look_rot(loc, (loc[0] + 0.3, loc[1] + 0.8, 0))
            o.keyframe_insert("location", frame=f)
            o.keyframe_insert("rotation_euler", frame=f)
        return o

    def foam(self, char, n=6, radius=0.012):
        """Little toothpaste foam blobs round a character's mouth (they follow the head)."""
        mat = self.material("M_Foam", (0.95, 0.98, 1.0), rough=0.6)
        m = char.mouth_world()
        rnd = random.Random(7)
        head = char.rig.pose.bones["head"]
        out = []
        for i in range(n):
            a = 2 * math.pi * i / n
            p = m + char.rig.matrix_world.to_3x3().normalized() @ Vector((0.035 * math.cos(a), -0.02, 0.018 * math.sin(a) - 0.005))
            o = self.blob(f"Foam{i}", p, radius * rnd.uniform(0.7, 1.3), mat)
            attach_to_bone(o, char.rig, head.name, o.matrix_world.copy())
            out.append(o)
        return out

    def sparkles(self, char, start, end, n=4):
        """Soft gleams by the teeth that swell and fade (no flashing)."""
        mat = self.material("M_Sparkle", (1.0, 1.0, 0.92), emit=6.0)
        m = char.mouth_world()
        for i in range(n):
            p = m + char.rig.matrix_world.to_3x3().normalized() @ Vector(((i - n / 2) * 0.02, -0.03, 0.005 * (i % 2)))
            o = self.blob(f"Sparkle{i}", p, 0.006, mat)
            mid = start + (end - start) * (i + 1) // (n + 1)
            self.scale_keys(o, [(start, 0.0), (mid, 1.4), (min(end, mid + 18), 0.0)])

    def fill_light(self, loc, target, energy=40, size=0.6, color=(1.0, 0.97, 0.92)):
        """Extra soft light for a shot (e.g. a mirror light on a face)."""
        data = bpy.data.lights.new("ShotFill", "AREA")
        data.energy, data.size, data.color = energy, size, color
        o = bpy.data.objects.new("ShotFill", data)
        bpy.context.scene.collection.objects.link(o)
        o.location = loc
        o.rotation_euler = look_rot(loc, target)
        return o

    def line(self, k=0):
        """(start, end) frames of the k-th dialogue clip of this shot."""
        d = self.data["dialogue"][k]
        cues = json.loads((self.audio_dir / f"{d['id']}.json").read_text())["mouthCues"]
        return sec(d["at"]), sec(d["at"]) + round(cues[-1]["end"] * FPS)

    def finish(self):
        for d in self.data["dialogue"]:
            who = VOICE_CHAR.get(d["voice"])
            if who in self.chars:
                self.chars[who].lip_sync(d["id"], d["at"])
        speakers = {VOICE_CHAR.get(d["voice"]) for d in self.data["dialogue"]}
        for c in self.chars.values():
            if not c.pet and c.name not in speakers:
                for a0, a1 in c.brushing:
                    c.mouth_hold("B", a0, a1)  # teeth showing round the brush
            c.life(self.end)
        for c in self.chars.values():
            fix_quaternion_flips(c.rig)
        for ob in bpy.data.objects:
            for owner in (ob, getattr(ob.data, "shape_keys", None) if ob.type == "MESH" else None, ob.data if ob.type == "CAMERA" else None):
                ad = getattr(owner, "animation_data", None) if owner else None
                if not (ad and ad.action):
                    continue
                for fc in ad.action.fcurves:
                    snap = "mouth_" in fc.data_path
                    for kp in fc.keyframe_points:
                        kp.interpolation = "CONSTANT" if snap else "BEZIER"
