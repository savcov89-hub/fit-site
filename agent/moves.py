"""Схемы упражнений: скелет с мышцами в любой позе (лёжа, на четвереньках, стоя), вид сбоку.

Поза задаётся углами сегментов, как в svgkit.add: градусы от вертикали «вверх», по часовой — вперёд
(для человека, который смотрит вправо). Таз в начале координат, потом поза сама опускается на пол.
Ближние рука и нога рисуются ярко, дальние — бледнее, поэтому видно «противоположные рука и нога».

Картинка: заголовок-упражнение, 1–2 подсказки, начальная поза полупрозрачно, конечная ярко, стрелка движения,
внизу — какие мышцы работают. Весь текст переносится по ширине, ничего не вылезает за край.
"""
import math

import svgkit as K

W = 640
S = 2.3                 # условные сантиметры -> пиксели, как в svgkit
L = dict(shank=44, thigh=46, torso=52, upper=29, fore=26)

RU = {
    "abs": "прямая мышца живота", "tva": "поперечная мышца живота", "obliques": "косые мышцы живота",
    "glutes": "ягодичные", "hams": "задняя поверхность бедра", "quads": "квадрицепс", "calves": "икры",
    "back": "разгибатели спины", "traps": "трапеции", "delts": "дельты", "chest": "грудные",
    "lats": "широчайшие", "biceps": "бицепс", "triceps": "трицепс", "hipflex": "сгибатели бедра",
}
MUSCLES = list(RU)

STYLE = """<style>
.far{opacity:.5}.deep{stroke-dasharray:4 3;stroke-width:1.6}
.legend{font:600 19px system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;fill:#9c3412}
.cue{font:400 19px system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;fill:#55554f}
.ttl{font:700 25px system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;fill:#1d1d1b}
.lg{fill:#d2491d;fill-opacity:.82}.okc{fill:#2e8b57}.badc{fill:#c0392b}
.mark{stroke:#fff;stroke-width:3.5;fill:none;stroke-linecap:round}
.floor{stroke:#b9b5aa;stroke-width:3}.equip{fill:#d9d5ca;stroke:#8f8a7e;stroke-width:2}
.cable{stroke:#8f8a7e;stroke-width:2;stroke-dasharray:6 5}
.plate{fill:#3a3a37;fill-opacity:.1;stroke:#3a3a37;stroke-width:3}.barc{fill:#3a3a37}.ghostbar{opacity:.3}
@media (prefers-color-scheme:dark){.legend{fill:#f59b72}.cue{fill:#a9a8a1}.ttl{fill:#ecebe6}
.lg{fill:#f0703f}.floor{stroke:#55534d}.plate{fill:#ecebe6;fill-opacity:.12;stroke:#bdbbb3}.barc{fill:#bdbbb3}.equip{fill:#2c2c30;stroke:#77756d}.cable{stroke:#77756d}}
</style>"""


# ---------- геометрия ----------

def add(p, a, ln):
    r = math.radians(a)
    return (p[0] + ln * math.sin(r), p[1] + ln * math.cos(r))


def frame(p0, p1):
    """Система координат сегмента: t — доля длины от p0 к p1, s — смещение «вперёд» (живот, перед бедра).
    «Вперёд» всегда поворот направления по часовой, поэтому поза может быть любой: лёжа, вниз головой."""
    u = (p1[0] - p0[0], p1[1] - p0[1])
    ln = math.hypot(*u) or 1
    u = (u[0] / ln, u[1] / ln)
    a = (u[1], -u[0])
    return lambda t, s: (p0[0] + u[0] * t * ln + a[0] * s, p0[1] + u[1] * t * ln + a[1] * s)


def spine(hip, angle, flex, ln=L["torso"]):
    """Корпус дугой: направление поворачивается на flex градусов от таза к плечам.
    flex > 0 — сгибание вперёд (скручивание, позвоночник круглый), < 0 — прогиб назад.
    Возвращает T(t, s) как у frame и угол направления в точке t (для поворота позвонков)."""
    n = 40

    def ang(t):
        return angle + flex * min(t, 1.0)

    def T(t, s):
        x, y = hip
        steps = max(1, int(n * min(t, 1.0)))
        tt = min(t, 1.0)
        for i in range(steps):
            r = math.radians(ang((i + 0.5) / steps * tt))
            x += ln * tt / steps * math.sin(r)
            y += ln * tt / steps * math.cos(r)
        r = math.radians(ang(t))
        if t > 1:
            x += ln * (t - 1) * math.sin(r)
            y += ln * (t - 1) * math.cos(r)
        return (x + s * math.cos(r), y - s * math.sin(r))
    return T, ang


def torso(P):
    return spine(P["hip"], P["tb"], P.get("flex", 0))


def rot(v, a):
    """Поворот вектора по часовой на a градусов (носок вниз — положительный угол)."""
    r = math.radians(a)
    return (v[0] * math.cos(r) + v[1] * math.sin(r), -v[0] * math.sin(r) + v[1] * math.cos(r))


def ik(j, target, l1=L["upper"], l2=L["fore"], bend=1):
    """Углы плеча и предплечья, чтобы кисть дошла до точки (или потянулась к ней)."""
    dx, dy = target[0] - j[0], target[1] - j[1]
    d = min(math.hypot(dx, dy), l1 + l2 - 0.01)
    base = math.degrees(math.atan2(dx, dy))
    c = max(-1, min(1, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)))
    a1 = base + bend * math.degrees(math.acos(c))
    e = add(j, a1, l1)
    a2 = math.degrees(math.atan2(target[0] - e[0], target[1] - e[1]))
    return a1, a2


FOOT = [(-7, 1), (-7, 5), (-2, 9.5), (3, 9), (12, 4.5), (20, 2.2), (21, 0.6), (8, 0.2), (-5, 0.3)]


def leg(hip, thigh, shank, foot):
    knee = add(hip, thigh, L["thigh"])
    ankle = add(knee, shank, L["shank"])
    pts = [(ankle[0] + v[0], ankle[1] + v[1]) for v in (rot((x, y - 8), foot) for x, y in FOOT)]
    heel = (ankle[0] + rot((-7, -7), foot)[0], ankle[1] + rot((-7, -7), foot)[1])
    toe = (ankle[0] + rot((20, -7), foot)[0], ankle[1] + rot((20, -7), foot)[1])
    return dict(knee=knee, ankle=ankle, foot=pts, heel=heel, toe=toe)


def build(spec):
    """spec: torso (наклон корпуса у таза), flex (изгиб позвоночника), thigh, shank, foot, upper, fore
    (+ thigh2… для дальних рук и ног), opt. hand/hand2 — цель кисти."""
    g = lambda k, d=0: spec.get(k, d)  # noqa: E731
    hip = (0.0, 0.0)
    T, _ = spine(hip, g("torso"), g("flex"))
    top = T(1, 0)
    P = dict(hip=hip, top=top, tb=g("torso"), flex=g("flex"), joint=T(0.94, -2), head=T(1.3, -3.5), belly=T(0.35, 7.5),
             low_back=T(0.3, -11), chest=T(0.8, 8))
    P["near"] = leg(hip, g("thigh"), g("shank"), g("foot"))
    P["far"] = leg(hip, g("thigh2", g("thigh")), g("shank2", g("shank")), g("foot2", g("foot")))
    for side, sfx in (("arm", ""), ("arm2", "2")):
        if "hand" + sfx in spec:
            up, fo = ik(P["joint"], spec["hand" + sfx], bend=spec.get("bend" + sfx, 1))
        else:
            up, fo = g("upper" + sfx, g("upper", 180)), g("fore" + sfx, g("fore", 180))
        e = add(P["joint"], up, L["upper"])
        P[side] = dict(elbow=e, hand=add(e, fo, L["fore"]))
    for k in ("knee", "ankle", "heel", "toe"):
        P[k] = P["near"][k]
    P["elbow"], P["hand"] = P["arm"]["elbow"], P["arm"]["hand"]
    P["knee2"], P["heel2"], P["hand2"] = P["far"]["knee"], P["far"]["heel"], P["arm2"]["hand"]
    return P


def samples(P):
    """Точки контура тела, чтобы поставить позу на пол и посчитать размеры."""
    T, _ = torso(P)
    out = [T(t / 10, s) for t in range(0, 11) for s in (-11.5, 7.5)]
    hx, hy = P["head"]
    out += [(hx + 8.7 * math.cos(a / 4 * math.pi), hy + 8.7 * math.sin(a / 4 * math.pi)) for a in range(8)]
    for lg in (P["near"], P["far"]):
        F, Sg = frame(lg["knee"], P["hip"]), frame(lg["ankle"], lg["knee"])
        out += [F(t / 4, s) for t in range(5) for s in (-6, 7.5)]
        out += [Sg(t / 4, s) for t in range(5) for s in (-6, 3)]
        out += lg["foot"]
    for a in (P["arm"], P["arm2"]):
        out += [P["joint"], a["elbow"], (a["hand"][0], a["hand"][1] - 2.2)]
    return out


def bbox(P):
    pts = samples(P)
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def moved(P, dx, dy):
    def mv(v):
        if isinstance(v, tuple):
            return (v[0] + dx, v[1] + dy)
        if isinstance(v, dict):
            return {k: mv(x) for k, x in v.items()}
        if isinstance(v, list):
            return [mv(x) for x in v]
        return v
    return {k: (mv(v) if k not in ("tb", "flex") else v) for k, v in P.items()}


def on_floor(P, floor=0.0):
    return moved(P, 0, floor - bbox(P)[1])


# ---------- рисование ----------

class Pen:
    def __init__(self, ox, oy):
        self.ox, self.oy = ox, oy

    def p(self, v):
        return (self.ox + v[0] * S, self.oy - v[1] * S)

    def smooth(self, pts):
        P = [self.p(v) for v in pts]
        n = len(P)
        d = f"M{P[0][0]:.1f} {P[0][1]:.1f}"
        for i in range(n):
            p0, p1, p2, p3 = P[i - 1], P[i], P[(i + 1) % n], P[(i + 2) % n]
            c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
            c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
            d += f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
        return d + "Z"

    def shape(self, f, pts, cls):
        return f'<path class="{cls}" d="{self.smooth([f(t, s) for t, s in pts])}"/>'

    def joint(self, v, r=5):
        x, y = self.p(v)
        return f'<circle class="joint" cx="{x:.1f}" cy="{y:.1f}" r="{r}"/>'


def draw_leg(pen, P, lg, m):
    g = []
    an, k, hp = lg["ankle"], lg["knee"], P["hip"]
    Sg, F = frame(an, k), frame(k, hp)
    g.append(f'<path class="bone" d="{pen.smooth(lg["foot"])}"/>')
    g.append(pen.shape(Sg, [(0.2, -1.6), (0.45, -5.2), (0.68, -6.8), (0.86, -5), (0.97, -2.2), (0.85, -1.4), (0.5, -1.6)], m("calves")))
    g.append(pen.shape(Sg, [(0.15, 1.8), (0.5, 3.6), (0.85, 3.2), (0.86, 1.9), (0.5, 2.1)], "m"))
    g.append(pen.shape(Sg, [(0.02, 1.8), (0.1, 1.3), (0.88, 1.5), (0.98, 3.4), (1.03, 0.5), (0.98, -2.8), (0.88, -1.2), (0.1, -0.6), (0.02, -1.6)], "bone"))
    g.append(pen.shape(F, [(0.1, -1.4), (0.35, -5.6), (0.7, -6.6), (0.95, -4.2), (0.92, -1.6), (0.5, -1.8)], m("hams")))
    g.append(pen.shape(F, [(-0.02, 3.6), (0.15, 6.4), (0.5, 8.2), (0.82, 7), (0.98, 3.6), (0.85, 1.6), (0.5, 1.8), (0.12, 2)], m("quads")))
    if "hipflex" in m.on:
        g.append(pen.shape(F, [(0.72, 2.5), (0.85, 5.5), (1.02, 6), (1.08, 3), (0.95, 1.8)], m("hipflex")))
    g.append(pen.shape(F, [(-0.02, 2.8), (0.04, 3.6), (0.1, 1.6), (0.86, 1.3), (0.97, 2.4), (1.02, 0.6), (0.99, -1.8), (0.88, -1.4), (0.1, -1.6), (0.0, -2.6)], "bone"))
    g.append(pen.joint(k))
    return g


def draw_arm(pen, a, J, m):
    g = []
    E, Hd = a["elbow"], a["hand"]
    UA, FA = frame(E, J), frame(E, Hd)
    g.append(pen.shape(UA, [(0.15, 1.5), (0.45, 3.4), (0.75, 3), (0.8, 1.4)], m("biceps")))
    g.append(pen.shape(UA, [(0.1, -1.5), (0.4, -3.6), (0.75, -3.4), (0.8, -1.4)], m("triceps")))
    g.append(pen.shape(UA, [(0.62, -3.4), (0.85, -5), (1.08, -2.5), (1.08, 3.5), (0.8, 4), (0.66, 2)], m("delts")))
    g.append(pen.shape(UA, [(0.0, -1.5), (0.04, 1.6), (0.96, 1.2), (1.02, 0), (0.96, -1.2)], "bone"))
    g.append(pen.shape(FA, [(0.0, -1.4), (0.05, 1.4), (0.95, 1.1), (1.0, 0), (0.95, -1.1)], "bone"))
    g += [pen.joint(J, 4.2), pen.joint(E, 4.2), pen.joint(Hd, 5)]
    return g


def draw_trunk(pen, P, m):
    g = []
    hp, lg = P["hip"], P["near"]
    (T, ang), F = torso(P), frame(lg["knee"], hp)
    gl = [T(0.27, -8.6), T(0.16, -12.4), T(0.0, -12.8), F(0.8, -6.4), F(0.62, -3.6), F(0.8, -1.4), T(0.06, -6.2)]
    g.append(f'<path class="{m("glutes")}" d="{pen.smooth(gl)}"/>')
    g.append(pen.shape(T, [(-0.04, -2.5), (0.05, -8.5), (0.27, -10), (0.32, -5.5), (0.3, 1.5), (0.17, 5.5), (0.05, 4.5), (0.0, 2)], "bone"))
    g.append(pen.joint(hp, 5.5))
    g.append(pen.shape(T, [(0.42, -8.2), (0.6, -9.8), (0.84, -9.4), (0.86, -6), (0.6, -4.6), (0.45, -5.6)], m("lats")))
    g.append(pen.shape(T, [(0.12, -3.5), (0.3, -6.2), (0.55, -5), (0.6, 2.8), (0.35, 4.4), (0.15, 2.4)], m("obliques")))
    g.append(pen.shape(T, [(0.1, 3.8), (0.3, 6.6), (0.55, 7.2), (0.72, 6.4), (0.7, 4.4), (0.4, 4.6), (0.15, 2.8)], m("abs")))
    if "tva" in m.on:
        g.append(pen.shape(T, [(0.08, 2.4), (0.3, 5.4), (0.5, 5.6), (0.52, -6.8), (0.3, -7.6), (0.1, -5.5)], m("tva") + " deep"))
    g.append(pen.shape(T, [(0.15, -8.6), (0.4, -10.6), (0.7, -11.2), (0.92, -10), (0.95, -8.6), (0.7, -8.8), (0.4, -8.2)], m("back")))
    g.append(pen.shape(T, [(0.42, -6.8), (0.6, -8.6), (0.86, -8.2), (0.98, -5), (0.97, 2.6), (0.82, 6.8), (0.55, 7), (0.42, 4.2)], "bone"))
    for t in (0.5, 0.6, 0.7, 0.8, 0.9):
        a, b, c = pen.p(T(t + 0.02, -7.6)), pen.p(T(t - 0.05, 0)), pen.p(T(t - 0.02, 5.8))
        g.append(f'<path class="lead" style="stroke:#7d776b" d="M{a[0]:.1f} {a[1]:.1f}Q{b[0]:.1f} {b[1]:.1f} {c[0]:.1f} {c[1]:.1f}"/>')
    g.append(pen.shape(T, [(0.72, 4.6), (0.82, 7.8), (0.95, 7.4), (0.97, 3.6), (0.86, 2.6)], m("chest")))
    for i in range(18):
        t = 0.06 + i * 0.056
        s = -6.6 + 1.6 * math.cos((t - 0.3) * 2 * math.pi / 0.9)
        x, y = pen.p(T(t, s))
        g.append(f'<rect class="vert" x="{x - 3.6:.1f}" y="{y - 3.2:.1f}" width="7.2" height="6.4" rx="1.8" '
                 f'transform="rotate({ang(t):.1f} {x:.1f} {y:.1f})"/>')
    g.append(pen.shape(T, [(0.72, -9.2), (0.92, -11.4), (1.06, -10), (1.14, -5.8), (1.04, -5.2), (0.86, -7.6)], m("traps")))
    g.append(head_at(pen, T))
    return g


def head_at(pen, T):
    c, a, b = pen.p(T(1.3, -3.5)), pen.p(T(1.3, 0)), pen.p(T(1.3, 1))
    o = pen.p(T(1.2, 0))
    up = K.norm((a[0] - o[0], a[1] - o[1]))
    fwd = K.norm((b[0] - a[0], b[1] - a[1]))
    return K.head(c, fwd, up)


def draw_body(pen, P, on=(), ghost=False):
    on = set(on)

    def m(k):
        return "m on" if k in on else "m"
    m.on = on
    far = draw_arm(pen, P["arm2"], P["joint"], m) + draw_leg(pen, P, P["far"], m)
    near = draw_leg(pen, P, P["near"], m) + draw_trunk(pen, P, m) + draw_arm(pen, P["arm"], P["joint"], m)
    body = '<g class="far">' + "".join(far) + "</g>" + "".join(near)
    return f'<g class="ghost">{body}</g>' if ghost else f"<g>{body}</g>"


# ---------- текст ----------

def wrap(text, width):
    lines, cur = [], ""
    for w in str(text).split():
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def txt(x, y, s, cls, anchor="start"):
    return f'<text class="{cls}" x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}">{K.esc(s)}</text>'


def badge(x, y, ok):
    c = f'<circle class="{"okc" if ok else "badc"}" cx="{x}" cy="{y}" r="16"/>'
    mark = (f'<path class="mark" d="M{x - 7} {y}l5 5 9 -10"/>' if ok else
            f'<path class="mark" d="M{x - 6} {y - 6}l12 12M{x + 6} {y - 6}l-12 12"/>')
    return c + mark


# ---------- упражнения ----------
# Супин: голова слева (корпус -90). На животе и на четвереньках: голова справа (корпус 90).

ARMS_FLOOR = dict(upper=101, fore=93)          # лёжа на спине: руки вдоль тела на полу
HOOK = dict(torso=-90, thigh=44, shank=150, foot=0, **ARMS_FLOOR)
TABLE = dict(torso=-90, thigh=2, shank=92, foot=-88, **ARMS_FLOOR)
QUAD = dict(torso=90, thigh=180, shank=-90, foot=180, upper=180, fore=180)


def _crunch(lift, flex):
    """Скручивание: поясница почти на полу, позвоночник сгибается дугой, руки тянутся к коленям."""
    return dict(HOOK, torso=-90 + lift, flex=flex, upper=104 - lift * 0.3, fore=98 - lift * 0.3)


EXERCISES = {
    # имя: (начальная поза или None, конечная поза, мышцы, опорная точка, стрелки)
    "breathing": (None, HOOK, ["tva"], "hip", [("belly_out", "belly")]),
    "heel_slide": (HOOK, dict(HOOK, thigh=91, shank=91, foot=-70), ["tva", "abs"], "hip", [("heel", "heel")]),
    "leg_lower": (TABLE, dict(TABLE, thigh=42, shank=148, foot=-10), ["tva", "abs"], "hip", [("toe", "toe")]),
    "head_lift": (HOOK, _crunch(2, 34), ["abs", "tva"], "hip", [("head", "head")]),
    "self_test": (None, dict(_crunch(2, 28), hand=None), ["abs"], "hip", []),
    "full_crunch": (HOOK, _crunch(22, 58), ["abs", "hipflex"], "hip", [("head", "head")]),
    "glute_bridge": (HOOK, dict(torso=-112, thigh=66, shank=167, foot=0, upper=101, fore=93),
                     ["glutes", "hams", "tva"], "joint", [("hip", "hip")]),
    "dead_bug_legs": (TABLE, dict(TABLE, thigh=74, shank=74, foot=-30), ["abs", "tva"], "hip", [("heel", "heel")]),
    "bird_dog": (QUAD, dict(QUAD, thigh=-88, shank=-92, foot=90, upper2=90, fore2=90),
                 ["glutes", "back", "abs"], "knee2", [("heel", "heel")]),
    "plank": (None, dict(torso=82, thigh=-98, shank=-98, foot=70, upper=180, fore=90),
              ["abs", "tva", "delts", "quads"], "hip", []),
    "side_plank_knees": (None, "front", ["obliques", "glutes", "delts"], "hip", []),
}


def resolve(spec, P0=None):
    spec = dict(spec)
    if spec == "front":
        return None
    if spec.get("hand", 0) is None:
        # кисть на живот, пальцы на средней линии
        P = build({k: v for k, v in spec.items() if k != "hand"})
        spec["hand"] = torso(P)[0](0.45, 9)
        spec["bend"] = -1
    return build(spec)


def side_plank(pen, on, xform=None):
    """Боковая планка с колен, вид спереди: скелетный профиль тут не подходит, рисуем фронтально."""
    m = lambda k: "m on" if k in on else "m"  # noqa: E731
    knee = (0.0, 4.0)
    ang = 66
    F = frame(knee, add(knee, ang, 100))
    g = []
    # дальняя рука на бедре, ноги, таз
    for sgn in (-1, 1):
        g.append(pen.shape(F, [(-0.02, 2 * sgn), (0.0, 6 * sgn), (0.44, 11 * sgn), (0.47, 7 * sgn), (0.44, 5 * sgn)], "bone"))
        g.append(pen.shape(F, [(0.05, 2.5 * sgn), (0.25, 9 * sgn), (0.42, 13 * sgn), (0.44, 7 * sgn)], m("quads")))
        g.append(pen.joint(F(0, 4 * sgn)))
        g.append(pen.shape(F, [(0.6, 7 * sgn), (0.66, 15 * sgn), (0.75, 13 * sgn), (0.74, 6 * sgn)], m("obliques")))
    g.append(pen.shape(F, [(0.43, -6), (0.5, -15), (0.57, -14), (0.55, -4), (0.53, 0), (0.55, 4), (0.57, 14), (0.5, 15), (0.43, 6), (0.46, 0)], "bone"))
    g.append(pen.shape(F, [(0.49, 10), (0.53, 16.5), (0.59, 15), (0.56, 9)], m("glutes")))
    g.append(pen.shape(F, [(0.58, -5), (0.62, 5), (0.76, 6.5), (0.76, -6.5)], m("abs")))
    for i in range(14):
        x, y = pen.p(F(0.56 + i * 0.03, 0))
        g.append(f'<rect class="vert" x="{x - 3.6:.1f}" y="{y - 3.2:.1f}" width="7.2" height="6.4" rx="1.8" '
                 f'transform="rotate({ang:.1f} {x:.1f} {y:.1f})"/>')
    g.append(pen.shape(F, [(0.74, -6), (0.8, -13), (0.92, -14), (0.99, -9), (0.99, 9), (0.92, 14), (0.8, 13), (0.74, 6), (0.77, 0)], "bone"))
    for t in (0.8, 0.85, 0.9, 0.95):
        a, b, c = pen.p(F(t, -12.5)), pen.p(F(t - 0.03, 0)), pen.p(F(t, 12.5))
        g.append(f'<path class="lead" style="stroke:#7d776b" d="M{a[0]:.1f} {a[1]:.1f}Q{b[0]:.1f} {b[1]:.1f} {c[0]:.1f} {c[1]:.1f}"/>')
    hc, h0 = pen.p(F(1.12, 0)), pen.p(F(1.0, 0))
    g.append(K.head_front(hc, K.norm((hc[0] - h0[0], hc[1] - h0[1]))))
    sh_lo, sh_hi = F(1.0, 17), F(1.0, -17)
    g.append(f'<path class="bone" d="M{pen.p(sh_hi)[0]:.1f} {pen.p(sh_hi)[1]:.1f}L{pen.p(sh_lo)[0]:.1f} {pen.p(sh_lo)[1]:.1f}" style="stroke-width:5"/>')
    elbow = (sh_lo[0], 3.0)
    hand = (sh_lo[0] + 24, 2.6)
    up = {"elbow": elbow, "hand": hand}
    mm = lambda k: m(k)  # noqa: E731
    mm.on = on
    g += draw_arm(pen, up, sh_lo, mm)
    top = {"elbow": F(0.78, -24), "hand": F(0.56, -17)}
    g += draw_arm(pen, top, sh_hi, mm)
    pts = [knee, F(1.2, 0), F(1.0, -20), sh_lo, hand, F(0.0, 8), F(0.0, -8)]
    return "<g>" + "".join(g) + "</g>", pts


def point(P, name):
    if name == "belly_out":
        return torso(P)[0](0.35, 22)
    return P[name]


def draw_exercise(f):
    """f: exercise, title, cues (список), highlight (необязательно), verdict ok|bad|none;
    для custom ещё start (или None), end — словари углов, arrow — точка для стрелки;
    bar: back — штанга на спине (присед), hands — в руках (тяги), none или нет поля — без штанги."""
    if f["exercise"] == "custom":
        pt = f.get("arrow", "none")
        start, end, muscles, anchor = f.get("start"), f["end"], [], "hip"
        arrows = [(pt, pt)] if pt != "none" and start else []
    else:
        start, end, muscles, anchor, arrows = EXERCISES[f["exercise"]]
    on = f.get("highlight") or muscles
    if end == "front":
        _, pts = side_plank(Pen(0, 0), set())
        B, A = None, None
        boxes = [(min(p[0] for p in pts) - 9, 0, max(p[0] for p in pts) + 9, max(p[1] for p in pts) + 9)]
    else:
        B = on_floor(resolve(end))
        A = on_floor(resolve(start)) if start else None
        if A:
            A = moved(A, B[anchor][0] - A[anchor][0], 0)
        boxes = [bbox(B)] + ([bbox(A)] if A else [])
    x0, x1 = min(b[0] for b in boxes), max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)

    out, y = [], 46
    verdict = f.get("verdict", "none")
    tx = 72 if verdict in ("ok", "bad") else 32
    if tx > 32:
        out.append(badge(48, 38, verdict == "ok"))
    for line in wrap(f["title"], 34 if tx > 32 else 36)[:2]:
        out.append(txt(tx, y, line, "ttl"))
        y += 32
    for cue in [c for c in f.get("cues", []) if c][:2]:
        for line in wrap(cue, 52)[:2]:
            out.append(txt(32, y, line, "cue"))
            y += 25
    y += 14
    fig_h = (y1 + 4) * S
    floor_y = y + fig_h
    pen = Pen(W / 2 - (x0 + x1) / 2 * S, floor_y)
    out.append(f'<line class="floor" x1="32" y1="{floor_y + 3:.0f}" x2="{W - 32}" y2="{floor_y + 3:.0f}"/>')
    if B is None:
        out.append(side_plank(pen, set(on))[0])
        out.append(txt(W - 32, floor_y - 8, "вид спереди", "cue", "end"))
    else:
        if A:
            out.append(draw_body(pen, A, ghost=True))
        out.append(draw_body(pen, B, on=on))
        bar = f.get("bar", "none")
        if bar in ("back", "hands"):
            for P, ghost in ([(A, True)] if A else []) + [(B, False)]:
                # гриф на трапециях чуть позади плеча или в кистях
                x, y_ = pen.p(torso(P)[0](0.97, -9) if bar == "back" else P["hand"])
                out.append(f'<g{" class=\"ghostbar\"" if ghost else ""}>'
                           f'<circle class="plate" cx="{x:.1f}" cy="{y_:.1f}" r="40"/>'
                           f'<circle class="barc" cx="{x:.1f}" cy="{y_:.1f}" r="6"/></g>')
    for a, b in arrows:
        p0 = pen.p(point(A or B, a))
        p1 = pen.p(point(B, b))
        if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) > 18:
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            nx, ny = -(p1[1] - p0[1]) * 0.18, (p1[0] - p0[0]) * 0.18
            out.append(K.arrow(p0, p1, curve=(mx + nx, my + ny) if a != "belly_out" else None))
    y = floor_y + 40
    names = [RU[k] for k in on if k in RU]
    lines = wrap("Работают: " + ", ".join(names), 50)
    out.append(f'<circle class="lg" cx="42" cy="{y - 7}" r="8"/>')
    for i, line in enumerate(lines[:3]):
        out.append(txt(58, y + i * 25, line, "legend"))
    y += 25 * min(len(lines), 3)
    return STYLE + "".join(out), y + 6
