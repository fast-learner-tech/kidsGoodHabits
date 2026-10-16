"""Staging for episode 1 ("Pip and the Sparkly Smile", script v2): set, cast, props, camera and actions per shot.

Built by blender/build_shot.py with the helpers in blender/shotlib.py. Lip-sync, talking nods, breathing and
blinks are added automatically. Frame 1 is the start of each shot; s.line(k) gives a dialogue clip's frames.

Layout notes
  Bedroom: bed along +Y at x=1.55 (mattress top z=0.48, pillow y=1.3), rug at (0.2, -0.2).
  Bathroom: counter top z=0.685 along the back wall (y=1.72), basin at x=0, step stool at (0, 1.2) (top z=0.2).
            Biscuit sits on the counter right of the basin; the sand timer stands on the counter left of it.
Characters face -Y (towards the camera) unless turned; facing + turns them towards screen right (+X).
"""
import math

from mathutils import Vector
from shotlib import sec

BEAT = 15                      # frames per beat at 96 BPM (habit song)
COUNTER = 0.685
STOOL = (0.0, 1.2, 0.2)
PIP_SPOT = (0.62, 1.0, 0.0)
NANA_SPOT = (-0.82, 0.98, 0.0)
BISCUIT_COUNTER = (0.4, 1.6, COUNTER)
TIMER_SPOT = (-0.42, 1.62, COUNTER)
BED_LIE = (1.55, 0.05, 0.55)   # Pip lying in bed (feet end), head sunk into the pillow
BED_SIT = (1.55, 1.05, 0.08)   # Pip sitting up in bed, legs under the quilt


# ---------------------------------------------------------------- helpers shared by several shots

def bedroom(s, mood="morning"):
    s.sets("Bedroom", "Bedroom_Night" if mood == "night" else "Bedroom_Day", mood=mood)


def bathroom(s):
    s.sets("Bathroom", mood="day")
    s.put("Bath_Cup", (0.58, 1.84, 0.75))  # make room for Biscuit on the counter
    for i in range(3):
        s.put(f"Bath_CupBrush{i}", (0.56 + i * 0.02, 1.84, 0.86), (0, -10 + i * 10, 0))


DUVET_TOP = 0.697


def duvet(s):
    """Plump the quilt up so it covers whoever is in bed, up to the chest (head and shoulders stay visible).
    The plush toy moves to the floor by the bed so it is not sitting on top of the sleeper."""
    q = s.obj("Bed_Quilt")
    q.location = (1.55, 0.25, 0.61)
    q.scale = (1.0, 0.846, 2.9)        # ends at y = 0.8; top at DUVET_TOP, deep enough to hide toes
    for name in ("Bed_PlushBody", "Bed_PlushHead", "Bed_PlushEar-0.06", "Bed_PlushEar+0.06"):
        o = s.obj(name)
        o.location = (o.location.x + 1.0, o.location.y + 1.4, o.location.z - 0.49)


def biscuit_on_counter(s, facing=-20):
    return s.char("Biscuit", BISCUIT_COUNTER, facing)


def tomo_on_stool(s, brush=True, facing=0):
    t = s.char("Tomo", STOOL, facing)
    if brush:
        t.hold("Toothbrush_Tomo", "L")
    return t


def pip_at_sink(s, brush=True, facing=-15, loc=PIP_SPOT):
    p = s.char("Pip", loc, facing)
    if brush:
        p.hold("Toothbrush_Pip", "R")
    return p


def nana(s, kneel=True, facing=22, loc=NANA_SPOT):
    n = s.char("NanaRue", loc, facing)
    if kneel:
        n.crouch(1, drop=0.3)
    return n


# ---------------------------------------------------------------- bedroom, morning

def shot_01(s):  # wide: Pip asleep, Biscuit curled on the rug
    bedroom(s)
    duvet(s)
    pip = s.char("Pip", BED_LIE)
    pip.lie_down(BED_LIE)
    pip.close_eyes(1, s.end)
    bis = s.char("Biscuit", (0.15, -0.25, 0), 25)
    bis.close_eyes(1, s.end)
    s.camera((0.0, -2.4, 1.85), (1.15, 0.75, 0.55), 24, end_loc=(0.25, -1.9, 1.75), end_lens=27)


def shot_02(s):  # medium: Biscuit hops onto the bed, nuzzles; Pip giggles awake
    bedroom(s)
    duvet(s)
    pip = s.char("Pip", BED_LIE)
    pip.lie_down(BED_LIE)
    a, b = s.line()
    pip.close_eyes(1, a - 8)
    pip.open_eyes(a - 8)
    pip.look(a - 8, yaw=-25, hold=s.end)
    pip.grin(b + 2, s.end)
    bis = s.char("Biscuit", (0.95, 1.05, 0), 90)
    bis.hop(4, height=0.25, length=14, loc_to=(1.22, 1.12, 0.48))
    bis.look(20, tilt=0)
    bis.look(26, pitch=12, tilt=15)       # nuzzle
    bis.look(40, pitch=0, tilt=-10)
    bis.look(s.end, tilt=-10)
    s.camera((0.5, 0.2, 1.45), (1.42, 1.05, 0.62), 35)


def shot_03(s):  # close: Pip sits up, stretches, yawns, smacks lips, puzzled
    bedroom(s)
    duvet(s)
    pip = s.char("Pip", BED_SIT)
    pip.sit_legs_forward(1)
    a, b = s.line()
    pip.arms_down(1)
    pip.cheer(14)                          # big stretch
    pip.cheer(26)
    pip.arms_down(36)
    pip.mouth_hold("D", 6, 26)             # yawn
    pip.mouth_hold("A", 28, 30)            # lip smack
    pip.mouth_hold("B", 31, 33)
    pip.mouth_hold("X", 34, a - 1)
    pip.look(1, pitch=-8)
    pip.look(20, pitch=-14)
    pip.look(36, tilt=12, hold=s.end)      # puzzled tilt
    s.camera((1.15, 0.05, 1.15), (1.55, 1.05, 0.9), 38)


def shot_04(s):  # close: Biscuit tilts its head ("mew?")
    bedroom(s)
    duvet(s)
    bis = s.char("Biscuit", (1.3, 0.55, DUVET_TOP), -10)
    bis.look(1)
    bis.look(14, tilt=20, pitch=-6)
    bis.look(s.end, tilt=22, pitch=-8)
    s.camera((1.22, -0.25, 1.0), (1.3, 0.55, 0.86), 50, end_loc=(1.25, -0.08, 0.97))


def shot_05(s):  # wide: Pip springs up and strikes a pose; Biscuit bounces behind
    bedroom(s)
    pip = s.char("Pip", (0.2, -0.2, 0), 0)
    a, b = s.line()
    pip.crouch(1, drop=0.12)
    pip.stand(8)
    pip.hop(8, height=0.12, length=10)
    pip.arm_dir("R", (0.7, -0.4, 0.4), (0.3, -0.6, 0.8), 18)   # "I know!" finger up
    mid = a + (b - a) // 3
    pip.arms_down(mid)
    pip.cheer(mid + 8)                     # "It's Sparkly Smile time!"
    pip.cheer(s.end)
    pip.grin(b + 1, s.end)
    bis = s.char("Biscuit", (0.75, 0.45, 0), -30)
    bis.hop(12, height=0.12, length=10)
    bis.hop(mid + 6, height=0.15, length=10)
    s.camera((0.2, -2.6, 1.1), (0.35, 0.2, 0.72), 28)


# ---------------------------------------------------------------- bathroom

def shot_06(s):  # wide: Tomo on the stool hugging the tube; Nana Rue folding towels
    bathroom(s)
    tomo = tomo_on_stool(s, brush=False)
    tomo.hold("ToothpasteTube", "L")
    tomo.hug_front(1)
    tomo.hop(sec(0.6), height=0.04, length=8)  # "Me first!" bounce
    n = nana(s, kneel=False, facing=35, loc=(-1.0, 1.05, 0))
    towel = s.copy("Bath_Towel0", "FoldedTowel")
    towel.scale = (0.4, 0.35, 0.22)  # a small folded towel
    towel.rotation_euler = (1.5708, 0, 0)
    n.hold("FoldedTowel", "L")
    n.hug_front(1)
    for f in range(10, s.end, 24):
        n.lean(f, pitch=8)
        n.lean(f + 12, pitch=2)
    n.look(1, yaw=-25, pitch=10, hold=s.end)
    biscuit_on_counter(s)
    s.camera((0.0, -2.1, 1.2), (-0.1, 1.0, 0.75), 28)


def shot_07(s):  # close: Tomo squeezes a huge toothpaste mountain that flops over
    bathroom(s)
    tomo = tomo_on_stool(s)
    tomo.hold("ToothpasteTube", "R")
    tomo.hold_up("L", 1)
    tomo.arm_dir("R", (0.3, -0.5, -0.5), (-0.6, -0.6, 0.3), 1)
    s.on_bristles("ToothpasteBlob", "Toothbrush_Tomo")
    blob = s.obj("ToothpasteBlob")
    s.scale_keys(blob, [(1, 0.05), (10, 0.05), (34, 1.6), (40, (1.75, 1.75, 1.45)), (46, 1.6), (52, (1.55, 1.55, 1.7))])
    blob.rotation_euler = (0, 0, 0)
    blob.keyframe_insert("rotation_euler", frame=56)
    blob.rotation_euler = (0, 1.4, 0)      # flop!
    blob.keyframe_insert("rotation_euler", frame=64)
    tube = s.obj("ToothpasteTube")
    s.scale_keys(tube, [(10, 1.0), (16, (1.0, 0.55, 1.0)), (34, (1.0, 0.5, 1.0))])
    a, b = s.line()
    tomo.look(1, pitch=18)
    tomo.look(a, pitch=4, tilt=10, hold=s.end)
    bis = biscuit_on_counter(s)
    bis.look(56, pitch=0)
    bis.look(62, pitch=-14)                # startled lean back
    bis.look(s.end, pitch=-10, tilt=8)
    s.camera((0.12, 0.1, 1.02), (0.15, 1.35, 0.92), 38)


def shot_08(s):  # medium: Pip speed-brushes
    bathroom(s)
    pip = pip_at_sink(s)
    pip.brush("R", 4, s.end - 14, speed=3)
    pip.hold_up("R", s.end - 8)
    pip.grin(s.line()[1] + 1, s.end)
    s.camera((0.42, -0.45, 1.0), (0.6, 1.0, 0.86), 40)


def shot_09(s):  # medium: Nana Rue kneels down with a warm laugh
    bathroom(s)
    n = nana(s, kneel=False)
    n.stand(1)
    n.crouch(20, drop=0.3)
    n.look(1)
    n.look(20, pitch=8, tilt=-8, hold=s.end)
    n.open_arms(24, sides=("R",))
    n.arms_down(48, sides=("R",))
    tomo_on_stool(s)
    pip_at_sink(s)
    s.camera((-0.25, -0.75, 1.05), (-0.25, 1.0, 0.82), 32)


def shot_10(s):  # close: Nana Rue's gentle sweeping gesture
    bathroom(s)
    n = nana(s)
    a, b = s.line()
    n.arm_dir("R", (0.35, -0.6, -0.4), (0.2, -0.8, 0.2), a)
    n.arm_dir("R", (0.85, -0.25, -0.3), (0.9, -0.35, 0.1), b - 4)   # sweep outwards
    n.arms_down(b + 14, sides=("R",))
    n.look(1, pitch=6, tilt=-6, hold=s.end)
    s.camera((-0.68, -0.25, 1.0), (-0.8, 0.98, 0.93), 45)


def shot_11(s):  # close: Nana Rue taps her own smile
    bathroom(s)
    n = nana(s)
    a, b = s.line()
    mid = (a + b) // 2
    n.reach("L", (0.03, -0.05, 0.0), mid, from_mouth=True)
    n.reach("L", (0.03, -0.09, 0.0), mid + 5, from_mouth=True)
    n.reach("L", (0.03, -0.05, 0.0), mid + 10, from_mouth=True)
    n.arms_down(b + 12, sides=("L",))
    n.look(1, pitch=6, tilt=-6, hold=s.end)
    s.camera((-0.68, -0.25, 1.0), (-0.8, 0.98, 0.93), 45)


def shot_12(s):  # medium: Pip and Tomo nod eagerly, brushes held up
    bathroom(s)
    pip = pip_at_sink(s)
    tomo = tomo_on_stool(s)
    pip.hold_up("R", 1)
    tomo.hold_up("L", 1)
    pip.nod_yes(4, times=2)
    tomo.nod_yes(6, times=3, period=7)
    pip.look(30, yaw=25, hold=s.end)       # towards Nana Rue
    tomo.look(30, yaw=20, hold=s.end)
    s.camera((0.3, -0.75, 1.02), (0.3, 1.1, 0.9), 35)


def shot_13(s):  # close-up: a pea-sized dot on a brush
    bathroom(s)
    s.brush_flat("Toothbrush_Nana", (0.12, 1.52, COUNTER + 0.012))
    s.on_bristles("ToothpasteDot", "Toothbrush_Nana")
    a, b = s.line()
    dot_frame = a + (b - a) // 2
    s.scale_keys("ToothpasteDot", [(1, 0.0), (dot_frame - 4, 0.0), (dot_frame + 6, 1.0)])
    tube = s.obj("ToothpasteTube")
    tube.parent = None
    tube.rotation_euler = (3.1416, 0, 0)   # cap down
    for f, loc in ((1, (0.34, 1.5, 1.0)), (dot_frame - 12, (0.2, 1.52, 0.8)), (dot_frame + 8, (0.2, 1.52, 0.8)),
                   (dot_frame + 24, (0.36, 1.5, 1.02))):
        tube.location = loc
        tube.keyframe_insert("location", frame=f)
    s.scale_keys(tube, [(dot_frame - 4, 1.0), (dot_frame + 4, (1.0, 0.7, 1.0)), (dot_frame + 10, 1.0)])
    s.camera((0.02, 1.2, 0.9), (0.14, 1.52, 0.71), 60)


def shot_14(s):  # medium: Tomo (helped by Nana Rue) and Pip each add a tiny dot, hold brushes up
    bathroom(s)
    pip = pip_at_sink(s)
    tomo = tomo_on_stool(s)
    n = nana(s, loc=(-0.45, 0.95, 0), facing=30)
    s.on_bristles("ToothpasteDot", "Toothbrush_Tomo")
    s.copy("ToothpasteDot", "DotPip")
    s.on_bristles("DotPip", "Toothbrush_Pip")
    (ta, tb), (pa, pb) = s.line(0), s.line(1)
    s.scale_keys("ToothpasteDot", [(1, 0.0), (6, 0.0), (14, 1.0)])
    s.scale_keys("DotPip", [(1, 0.0), (10, 0.0), (18, 1.0)])
    tomo.arm_dir("L", (0.3, -0.5, -0.6), (-0.4, -0.8, 0.3), 1)
    n.reach_world("R", tomo.mouth_world() + tomo.rig.matrix_world.to_3x3().normalized() @ Vector((0.06, -0.2, -0.15)), 1)
    tomo.hold_up("L", ta)
    n.arms_down(ta + 6, sides=("R",))
    pip.arm_dir("R", (0.3, -0.5, -0.6), (-0.4, -0.8, 0.3), 1)
    pip.hold_up("R", pa)
    tomo.grin(tb + 1, s.end)
    pip.grin(pb + 1, s.end)
    s.camera((0.1, -0.7, 1.0), (0.1, 1.1, 0.88), 34)


def shot_15(s):  # medium: Nana Rue guides Pip's hand in little circles
    bathroom(s)
    pip = pip_at_sink(s, loc=(0.35, 0.95, 0), facing=-10)
    n = nana(s, loc=(-0.05, 0.85, 0), facing=40)
    pip.brush("R", 1, s.end, speed=12)
    target = pip.mouth_world() + pip.rig.matrix_world.to_3x3().normalized() @ Vector((-0.03, -0.16, -0.08))
    n.reach_world("L", target, 1)
    n.reach_world("L", target, s.end)
    n.look(1, yaw=-20, pitch=12, hold=s.end)
    s.camera((0.15, -0.55, 1.0), (0.15, 1.0, 0.9), 38)


def shot_16(s):  # close: Pip brushes the fronts, the backs, the chewing tops
    bathroom(s)
    pip = pip_at_sink(s, facing=0)
    third = s.end // 3
    pip.brush("R", 1, third, speed=10, area="front")
    pip.brush("R", third + 1, 2 * third, speed=10, area="side")   # the backs
    pip.brush("R", 2 * third + 1, s.end, speed=10, area="top")   # the chewing tops
    pip.look(1, pitch=4, hold=s.end)
    s.camera((0.58, 0.02, 0.93), (0.62, 1.0, 0.86), 42)  # face, hand and brush in frame


def shot_17(s):  # medium: Nana Rue turns over the sand timer
    bathroom(s)
    s.timer(TIMER_SPOT, sand_top=0.0)
    n = nana(s, kneel=False, loc=(-0.78, 1.25, 0), facing=55)
    n.look(1, yaw=-20, pitch=20, hold=s.end)
    a, b = s.line()
    flip = a + (b - a) // 2
    top = (TIMER_SPOT[0], TIMER_SPOT[1], COUNTER + 0.2)
    n.reach_world("L", top, flip - 8)
    n.reach_world("L", (top[0], top[1], top[2] + 0.06), flip + 6)
    n.arms_down(flip + 22, sides=("L",))
    s.flip_timer(flip, 12)
    s.camera((-0.3, -0.25, 1.15), (-0.6, 1.4, 0.95), 35)


def shot_18(s):  # close: sand trickles (music only)
    bathroom(s)
    s.timer(TIMER_SPOT, sand_top=1.0)
    s.sand(1.0, 1)
    s.sand(0.8, s.end)
    s.camera((-0.3, 1.02, 0.86), (-0.42, 1.62, COUNTER + 0.09), 50)


def shot_19(s):  # close: Pip to camera, brushing the air (hold 3 s for the viewer)
    bathroom(s)
    pip = pip_at_sink(s, facing=0)
    f, k = 1, 0
    while f < s.end:
        a = k * math.pi / 2
        pip.reach("R", (0.04 + 0.04 * math.cos(a), -0.24, -0.08 + 0.04 * math.sin(a)), f, from_mouth=True)
        f += 6
        k += 1
    pip.grin(s.line()[1] + 1, s.end)
    s.camera((0.62, 0.0, 0.97), (0.62, 1.0, 0.9), 42)


def shot_20(s):  # wide: everyone brushing; Nana Rue helps Tomo; time passes
    bathroom(s)
    pip = pip_at_sink(s)
    tomo = tomo_on_stool(s)
    n = nana(s, loc=(-0.45, 0.95, 0), facing=30)
    pip.brush("R", 1, s.end, speed=12)
    tomo.brush("L", 1, s.end, speed=14)
    tgt = tomo.mouth_world() + tomo.rig.matrix_world.to_3x3().normalized() @ Vector((0.05, -0.15, -0.1))
    n.reach_world("R", tgt, 1)
    n.reach_world("R", tgt, s.end)
    n.look(1, yaw=-25, pitch=10, hold=s.end)
    biscuit_on_counter(s)
    s.light_patch((-2.2, -1.5, 2.6), (1.6, -1.2, 2.6))
    s.camera((0.0, -2.1, 1.2), (-0.05, 1.0, 0.75), 28)


def shot_21(s):  # close: Tomo's foamy smile; a bubble pops on Biscuit's nose; tiny sneeze
    bathroom(s)
    tomo = tomo_on_stool(s, facing=15)
    tomo.hold_up("L", 1)
    s.foam(tomo)
    tomo.grin(1, s.line()[0] - 1)
    bis = biscuit_on_counter(s, facing=-35)
    bubble = s.obj("Bath_Bubble1")
    start = tomo.mouth_world() + Vector((0.05, -0.06, 0.02))
    nose = bis.rig.matrix_world @ (bis.eye["L"] + bis.eye["R"]) / 2
    nose = nose + Vector((0, -0.05, -0.04))
    for f, loc, sc in ((1, start, 0.2), (8, start, 0.5), (34, (start + nose) / 2 + Vector((0, 0, 0.06)), 0.6),
                       (52, nose, 0.6)):
        bubble.location = loc
        bubble.keyframe_insert("location", frame=f)
        s.scale_keys(bubble, [(f, sc)])
    s.scale_keys(bubble, [(55, 0.0)])      # pop
    bis.look(50, pitch=0)
    bis.look(56, pitch=14)                 # tiny sneeze
    bis.look(62, pitch=-4)
    bis.close_eyes(55, 60)
    tomo.look(1, yaw=-30, pitch=-4, hold=s.end)
    s.camera((0.22, 0.35, 1.0), (0.22, 1.45, 0.94), 38)


def shot_22(s):  # medium: the timer runs out with a soft chime
    bathroom(s)
    s.timer(TIMER_SPOT, sand_top=0.0)
    n = nana(s, kneel=False, loc=(-0.78, 1.15, 0), facing=40)
    a, b = s.line()
    n.look(1, yaw=-25, pitch=18)
    n.look(a, yaw=0, pitch=0, hold=s.end)
    n.open_arms(a + 10, sides=("L",))      # "now spit it in the sink"
    n.arms_down(b + 10, sides=("L",))
    s.camera((-0.45, -0.2, 1.15), (-0.62, 1.35, 0.95), 35)


def shot_23(s):  # medium (side): Pip, then Tomo, spit in the sink
    bathroom(s)
    tomo = tomo_on_stool(s, facing=180)
    pip = pip_at_sink(s, loc=(0.42, 1.18, 0), facing=165)
    (pa, pb), (ta, tb) = s.line(0), s.line(1)
    pip.lean(pa - 4, pitch=0)
    pip.lean(pa + 2, pitch=28)
    pip.lean(pb + 10, pitch=0)
    tomo.lean(ta - 4, pitch=0)
    tomo.lean(ta + 2, pitch=26)
    tomo.lean(tb + 10, pitch=0)
    bis = biscuit_on_counter(s, facing=-60)
    bis.look(pa + 2, tilt=18)
    bis.look(ta + 2, tilt=-18)
    bis.look(s.end, tilt=0)
    s.camera((1.75, 0.85, 1.05), (0.15, 1.45, 0.82), 35)


def shot_24(s):  # mirror close-up: not fuzzy anymore!
    bathroom(s)
    pip = s.char("Pip", STOOL, 180)
    a, b = s.line()
    pip.mouth_hold("H", 4, 18)             # tongue over the teeth
    pip.grin(20, a - 1)
    pip.grin(b + 1, s.end)
    s.sparkles(pip, b - 6, s.end)
    s.fill_light((0.0, 1.75, 1.75), (0.0, 1.1, 1.15), energy=35)  # mirror light on Pip's face
    # beside Pip's head, looking past it into the mirror at his reflection
    s.camera((-0.45, 0.6, 1.35), (-0.08, 1.98, 1.24), 45)


def shot_25(s):  # close: Pip's biggest sparkly smile (hold 3 s for the viewer)
    bathroom(s)
    pip = pip_at_sink(s, facing=0)
    pip.hold_up("R", 1)
    a, b = s.line()
    pip.grin(1, a - 1)
    pip.grin(b + 1, s.end)
    pip.look(b + 4, tilt=8, hold=s.end)
    s.camera((0.62, 0.05, 0.98), (0.62, 1.0, 0.92), 48)


# ---------------------------------------------------------------- the habit song (cut on bar lines)

def song_cast(s, nana_loc=(-0.8, 1.0, 0)):
    pip = pip_at_sink(s)
    tomo = tomo_on_stool(s)
    n = nana(s, kneel=False, loc=nana_loc)
    for c in (pip, tomo, n):
        c.sway(1, s.end, BEAT, amount=6)
    return pip, tomo, n


def shot_26(s):  # wide: song begins, everyone sways; Pip leads
    bathroom(s)
    pip, tomo, n = song_cast(s)
    pip.hold_up("R", 1)
    tomo.hold_up("L", 1)
    biscuit_on_counter(s)
    s.camera((0.0, -2.1, 1.2), (-0.05, 1.0, 0.78), 28, end_loc=(0.0, -1.8, 1.15))


def shot_27(s):  # medium: Pip and Tomo brush in time (Tomo sings)
    bathroom(s)
    pip = pip_at_sink(s)
    tomo = tomo_on_stool(s)
    for c in (pip, tomo):
        c.sway(1, s.end, BEAT, amount=5)
    pip.brush("R", 1, s.end, speed=BEAT)
    tomo.brush("L", 1, s.end, speed=BEAT)
    s.camera((0.3, -0.75, 1.02), (0.3, 1.1, 0.9), 35)


def shot_28(s):  # close: timer flips; Biscuit spins (Nana Rue sings)
    bathroom(s)
    s.timer(TIMER_SPOT, sand_top=0.0)
    s.flip_timer(BEAT * 2, 12)
    bis = biscuit_on_counter(s)
    bis.spin(BEAT * 4, length=BEAT * 2)
    s.camera((0.0, 0.55, 0.98), (0.0, 1.62, 0.8), 30)


def shot_29(s):  # wide: everyone's sparkly smile pose on the last word (Pip sings)
    bathroom(s)
    pip, tomo, n = song_cast(s)
    a, b = s.line()
    for c in (pip, tomo, n):
        c.arms_down(b - 10)
        c.cheer(b - 2)
        c.cheer(s.end)
        c.grin(b, s.end)
    biscuit_on_counter(s).hop(b - 4, height=0.06, length=8)
    s.camera((0.0, -2.1, 1.2), (-0.05, 1.0, 0.8), 28)


# ---------------------------------------------------------------- bedroom, night

def shot_30(s):  # medium: Pip in bed holds up a clean toothbrush and winks
    bedroom(s, "night")
    duvet(s)
    pip = s.char("Pip", BED_SIT)
    pip.sit_legs_forward(1)
    pip.hold("Toothbrush_Pip", "R")
    a, b = s.line()
    pip.hold_up("R", 6)
    pip.wink(b - 4, "R", hold=8)
    pip.grin(b + 1, s.end)
    s.camera((1.15, 0.05, 1.15), (1.5, 1.05, 0.9), 38)


def shot_31(s):  # wide: Pip snuggles in, Biscuit curls up, the lamp dims (fade out in the edit)
    bedroom(s, "night")
    duvet(s)
    pip = s.char("Pip", BED_LIE)
    pip.lie_down(BED_LIE)
    pip.mouth_hold("D", 4, 26)             # one last yawn
    pip.mouth_hold("X", 30, s.end)
    pip.close_eyes(34, s.end)
    bis = s.char("Biscuit", (1.6, -0.05, DUVET_TOP), 30)
    bis.close_eyes(20, s.end)
    lamp = s.obj("Bed_LampGlow")
    for f, e in ((1, 60.0), (s.end, 18.0)):
        lamp.data.energy = e
        lamp.data.keyframe_insert("energy", frame=f)
    s.camera((0.0, -2.4, 1.85), (1.15, 0.75, 0.55), 24, end_loc=(0.3, -1.85, 1.7), end_lens=27)
