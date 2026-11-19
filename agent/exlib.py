"""База схем упражнений: анимированные SVG «скелет с мышцами», которые проверяет Михаил.

exercises/exercises.csv — манифест: id, название, раздел, мышцы, статус (draft / approved / fix), замечание.
exercises/poses.json    — позы: start и end углами суставов (как в moves.py), опорная точка, снаряд, подсказки.
static/ex/<id>.svg      — готовая картинка: поза плавно переходит start -> end -> start (SMIL, работает и в <img>).

Агент статей берёт только схемы со статусом approved (см. approved() и figures.add_moves).

    python agent/exlib.py            # перерисовать все схемы
    python agent/exlib.py squat lunge  # только эти
"""
import copy
import csv
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import moves as M  # noqa: E402
import svgkit as K  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "exercises"
OUT = ROOT / "static" / "ex"
URL = "/ex"
STATUSES = ("draft", "fix", "approved")

FRAMES = 5          # поз на половину движения (start -> end), включая крайние
HOLD = 0.12         # доля цикла, которую поза держится в начале и в конце
DUR = 3.6           # секунд на цикл туда-обратно

SVGNS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVGNS)


# ---------- манифест ----------

def manifest():
    with (LIB / "exercises.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_manifest(rows):
    with (LIB / "exercises.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "section", "muscles", "status", "comment"])
        w.writeheader()
        w.writerows(rows)


def poses():
    return json.loads((LIB / "poses.json").read_text(encoding="utf-8"))


def save_poses(P):
    """Одна строка на позу, чтобы правки в истории git было легко читать."""
    lines = []
    for k, ex in P.items():
        parts = [f'  "{k}": {{']
        items = list(ex.items())
        for i, (f, v) in enumerate(items):
            comma = "," if i < len(items) - 1 else ""
            parts.append(f'    "{f}": {json.dumps(v, ensure_ascii=False)}{comma}')
        lines.append("\n".join(parts) + "\n  }")
    (LIB / "poses.json").write_text("{\n" + ",\n".join(lines) + "\n}\n", encoding="utf-8")


def approved():
    """Одобренные схемы для агента: [{id, name, muscles, url}]."""
    return [dict(r, url=f"{URL}/{r['id']}.svg") for r in manifest() if r["status"] == "approved"]


# ---------- позы ----------

def lerp_spec(a, b, t):
    """Углы суставов идут кратчайшим путём: нога из 180 в -88 уходит назад через 270, а не вперёд."""
    out = dict(b)
    for k, v in b.items():
        if isinstance(v, (int, float)) and isinstance(a.get(k), (int, float)):
            d = v - a[k] if k in ("flex", "flex0", "flex1", "rear", "rear_h", "kneel", "upper_len", "fore_len", "lift", "bar_y", "bar_x") else (v - a[k] + 180) % 360 - 180
            out[k] = a[k] + d * t
        elif isinstance(v, (list, tuple)) and isinstance(a.get(k), (list, tuple)):     # цель кисти [x, y] от таза
            out[k] = tuple(x + (y - x) * t for x, y in zip(a[k], v))
    return out


def full(spec):
    """Дальние рука и нога по умолчанию повторяют ближние — нужно, чтобы их тоже можно было плавно двигать."""
    s = dict(spec)
    if "hand" in s:
        s["hand"] = tuple(s["hand"])
        s.setdefault("hand2", s["hand"])
        s.setdefault("bend2", s.get("bend", 1))
    for k in ("thigh", "shank", "foot", "upper", "fore"):
        s.setdefault(k + "2", s.get(k, 180 if k in ("upper", "fore") else 0))
    s.setdefault("upper", 180)
    s.setdefault("fore", 180)
    return s


def pose(spec):
    """Поза по углам. upper_len / fore_len — видимая длина плеча и предплечья, когда рука уходит в сторону
    от зрителя (жим лёжа: локоть внизу сбоку, в проекции плечо почти точка)."""
    P = M.build(spec)
    if spec.get("rear"):
        # задняя нога на носке (выпады): носок стоит на полу на rear см позади передней пятки,
        # колено сгибается само (ik), поэтому стопа не скользит и не висит в воздухе
        floor = min(p[1] for p in P["near"]["foot"])
        f = spec.get("foot2", 60)
        if spec.get("rear_h"):
            # болгарский выпад: подъём задней стопы лежит на скамье высотой rear_h, голеностоп — у её края
            ankle = (P["near"]["heel"][0] - spec["rear"], floor + spec["rear_h"] + 0.5)
            P["benchpts"] = dict(a=(ankle[0] - 34, floor + spec["rear_h"]), b=(ankle[0] + 4, floor))
        else:
            tip = M.rot((21, -7.4), f)
            ankle = (P["near"]["heel"][0] - spec["rear"] - tip[0], floor - tip[1])
        th, sh = M.ik(P["hip"], ankle, M.L["thigh"], M.L["shank"], bend=-1)
        P["far"] = M.leg(P["hip"], th, sh, f)
        P["knee2"], P["heel2"] = P["far"]["knee"], P["far"]["heel"]
    if spec.get("kneel"):
        # на колене (растяжка сгибателей бедра): колено и голень задней ноги лежат на полу, таз стоит на её
        # бедре (угол thigh2), передняя стопа стоит на полу в kneel см впереди колена, нога дотягивается через ik
        P["far"] = M.leg(P["hip"], spec["thigh2"], -90, spec.get("foot2", 180))
        floor = min(p[1] for p in leg_pts(P, P["far"]))
        ankle = (P["far"]["knee"][0] + spec["kneel"], floor + 7.8)
        th, sh = M.ik(P["hip"], ankle, M.L["thigh"], M.L["shank"], bend=-1)
        P["near"] = M.leg(P["hip"], th, sh, spec.get("foot", 0))
        for k in ("knee", "ankle", "heel", "toe"):
            P[k] = P["near"][k]
        P["knee2"], P["heel2"] = P["far"]["knee"], P["far"]["heel"]
    P["toe2"] = P["far"]["toe"]
    if "upper_len" in spec or "fore_len" in spec:
        for side, sfx in (("arm", ""), ("arm2", "2")):
            e = M.add(P["joint"], spec["upper" + sfx], spec.get("upper_len", M.L["upper"]))
            P[side] = dict(elbow=e, hand=M.add(e, spec["fore" + sfx], spec.get("fore_len", M.L["fore"])))
        P["elbow"], P["hand"], P["hand2"] = P["arm"]["elbow"], P["arm"]["hand"], P["arm2"]["hand"]
    return P


def leg_pts(P, lg):
    """Точки контура ноги (как в moves.samples): по ним ставим на пол колено и голень."""
    F, Sg = M.frame(lg["knee"], P["hip"]), M.frame(lg["ankle"], lg["knee"])
    return ([F(t / 4, s) for t in range(5) for s in (-6, 7.5)] + [Sg(t / 4, s) for t in range(5) for s in (-6, 3)]
            + list(lg["foot"]))


def _nil(P):
    return dict(elbow=P["joint"], hand=P["joint"])


def set_arms(P, target, bend=1, l1=M.L["upper"], sides=("arm", "arm2")):
    """Кисти в точку target (штанга, пол, голень), локти сгибаются сами (ik).
    l1 — видимая длина плеча: когда локти разведены в стороны, сбоку плечо кажется короче (жим стоя).
    bend: front / back / up — из двух решений ik берём то, где локоть впереди, сзади или выше."""
    if bend in ("front", "back", "up"):
        elbow = lambda b: M.add(P["joint"], M.ik(P["joint"], target, l1=l1, bend=b)[0], l1)  # noqa: E731
        pick = {"front": lambda e: e[0], "back": lambda e: -e[0], "up": lambda e: e[1]}[bend]
        bend = max((1, -1), key=lambda b: pick(elbow(b)))
    for side in sides:
        up, fo = M.ik(P["joint"], target, l1=l1, bend=bend)
        e = M.add(P["joint"], up, l1)
        P[side] = dict(elbow=e, hand=M.add(e, fo, M.L["fore"]))
    P["elbow"], P["hand"], P["hand2"] = P["arm"]["elbow"], P["arm"]["hand"], P["arm2"]["hand"]


GRIP = 6.0                                   # гриф лежит в кулаке, на 6 см дальше запястья
REACH = M.L["upper"] + M.L["fore"] - 0.4 + GRIP


def bar_arms(P, ex, spec):
    """bar_line: штанга идёт строго по вертикали на bar_line см впереди голеностопа (над серединой стопы).
    bar_y — высота грифа над плечевым суставом (жим стоя); без него руки висят прямо (становая)."""
    if "bar_line" not in ex:
        return
    x = P["near"]["ankle"][0] + ex["bar_line"]
    j = P["joint"]
    if "bar_y" in spec:     # жим: гриф лежит на ладони, чуть выше запястья
        y = j[1] + spec["bar_y"]
        set_arms(P, (x, y - 4), ex.get("bend", 1), spec.get("upper_len", M.L["upper"]))
    else:                   # руки висят прямо, гриф в кулаке
        y = j[1] - math.sqrt(max(0.0, REACH ** 2 - (x - j[0]) ** 2))
        d = math.hypot(x - j[0], y - j[1]) or 1
        k = max(0.0, d - GRIP) / d
        set_arms(P, (j[0] + (x - j[0]) * k, j[1] + (y - j[1]) * k), ex.get("bend", 1))
    P["grip"] = (x, y)


def mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def com_x(P, ex):
    """Центр масс по горизонтали: доли сегментов по Демпстеру, плюс вес снаряда (load — доля веса тела)."""
    T = M.torso(P)[0]
    parts = [(P["head"], .081), (T(0.5, -2), .497)]
    for a in (P["arm"], P["arm2"]):
        parts += [(mid(P["joint"], a["elbow"]), .028), (mid(a["elbow"], a["hand"]), .022)]
    for lg in (P["near"], P["far"]):
        parts += [(mid(P["hip"], lg["knee"]), .1), (mid(lg["knee"], lg["ankle"]), .0465),
                  ((lg["ankle"][0] + 6, 0), .0145)]
    load = ex.get("load", 0)
    if load and ex.get("bar") in ("back", "hands"):
        parts.append((bar_point(P, ex["bar"]), load))
    elif load and ex.get("bar") == "dumbbell":
        parts.append((mid(P["hand"], P["hand2"]), load))
    return sum(p[0] * m for p, m in parts) / sum(m for _, m in parts)


def balance(spec, ex):
    """Таз уходит назад или вперёд, пока центр масс (с весом штанги) не встанет над серединой стопы:
    так человек не падает вперёд в наклонах и отклоняется назад в жиме стоя. Подбирается угол бедра."""
    key = ex["balance"] if ex["balance"] in ("thigh", "torso") else "thigh"   # что подбирать: бедро или наклон корпуса
    best = None
    for i in range(-120, 121):
        s = dict(spec, **{key: spec[key] + i * 0.5})
        if not ex.get("single"):        # на одной ноге (тяга на одной ноге) дальняя нога своя
            s["thigh2"] = s["thigh"]
        P = pose(s)
        bar_arms(P, ex, s)
        err = abs(com_x(P, ex) - (P["near"]["ankle"][0] + 6))
        if best is None or err < best[0]:
            best = (err, s)
    return best[1]


def bridge(spec, ex, ref):
    """Мостик: лопатки и стопы всё время на полу, таз поднимается на lift см. Корпус поворачивается так,
    чтобы верх спины лежал на полу, ноги дотягиваются до стоп через ik, голова лежит (шея сгибается)."""
    H = ref["hip_y"] + spec.get("lift", 0)
    best = None
    for i in range(0, 141):
        a = -90 - i * 0.5
        s = dict(spec, torso=a, flex=-90 - a, flex0=0.85)
        T = M.spine((0, 0), a, s["flex"], flex0=0.85)[0]
        bottom = min(T(t / 20, -11.5)[1] for t in range(12, 21))
        err = abs(H + bottom)
        if best is None or err < best[0]:
            best = (err, s)
    s = best[1]
    P = M.build(s)
    # плечо стоит на месте: таз смещается, стопа (голеностоп) тоже стоит на месте
    hip_w = (ref["joint_x"] - P["joint"][0], H)
    ankle = (ref["ankle"][0] - hip_w[0], ref["ankle"][1] - hip_w[1])
    th, sh = M.ik((0, 0), ankle, M.L["thigh"], M.L["shank"], bend=-1)
    P["near"] = M.leg((0, 0), th, sh, spec.get("foot", 0))
    if not ex.get("single"):
        P["far"] = P["near"]
    for k in ("knee", "ankle", "heel", "toe"):
        P[k] = P["near"][k]
    P["knee2"], P["heel2"], P["toe2"] = P["far"]["knee"], P["far"]["heel"], P["far"]["toe"]
    # руки лежат на полу вдоль тела, кисти не двигаются
    set_arms(P, (ref["joint_x"] + 53 - hip_w[0], 2.2 - hip_w[1]), bend=-1)
    return P


def bridge_ref(ex):
    """Лёжа (lift 0): высота таза над полом, плечо и голеностоп — их держим на месте.
    Пол — по спине и стопам: руки сюда не входят, иначе тело зависает над полом."""
    P = pose(full(dict(ex["start"], torso=-90, flex=0)))
    T = M.torso(P)[0]
    floor = min(min(T(t / 10, -11.5)[1] for t in range(11)), lowest(P, "feet"))
    P = M.moved(P, 0, -floor)
    return dict(hip_y=P["hip"][1], joint_x=P["joint"][0] - P["hip"][0],
                ankle=(P["near"]["ankle"][0] - P["hip"][0], P["near"]["ankle"][1]))


def thrust(spec, ex, ref=None):
    """Ягодичный мостик с упором в скамью: лопатки лежат на краю скамьи высотой bench_h — край не двигается,
    корпус поворачивается вокруг него. Голеностоп (ref) стоит на месте, ноги дотягиваются через ik.
    Штанга лежит на тазу (bar: hip), руки её придерживают."""
    hb = ex["bench_h"]
    P = M.build(spec)
    c = M.torso(P)[0](0.78, -11.5)
    P = M.moved(P, -c[0], hb - c[1])
    if ref:
        th, sh = M.ik(P["hip"], ref, M.L["thigh"], M.L["shank"], bend=-1)
        P["near"] = P["far"] = M.leg(P["hip"], th, sh, spec.get("foot", 0))
        for k in ("knee", "ankle", "heel", "toe"):
            P[k] = P["near"][k]
        P["knee2"], P["heel2"] = P["far"]["knee"], P["far"]["heel"]
    P["toe2"] = P["far"]["toe"]
    if ex.get("bar") == "hip":
        g = M.torso(P)[0](0.04, 16)
        P["grip"] = g
        set_arms(P, (g[0], g[1] - 3), "up")
    P["benchpts"] = dict(a=(-50.0, hb), b=(1.0, 0.0))
    return P


def hang(spec, ex):
    """Вис на перекладине: перекладина в (bar_x, bar_y) см от плечевого сустава, кисти под ней.
    Всё тело поворачивается, пока центр масс не окажется точно под перекладиной — как висит живой человек."""
    keys = ("torso", "thigh", "shank", "foot", "thigh2", "shank2", "foot2")
    best = None
    for i in range(-80, 81):
        s = dict(spec, **{k: spec[k] + i * 0.25 for k in keys if k in spec})
        P = pose(s)
        j = P["joint"]
        g = (j[0] + s.get("bar_x", 0), j[1] + s["bar_y"])
        set_arms(P, (g[0], g[1] - 5), ex.get("bend", 1), s.get("upper_len", M.L["upper"]))
        P["grip"] = g
        err = abs(com_x(P, ex) - g[0])
        if best is None or err < best[0]:
            best = (err, P)
    return best[1]


def grab(P, what):
    """Куда кладутся кисти: shin — голень под коленом, ankle — подъём стопы, thigh — бедро над коленом."""
    lg = P["near"]
    Sg, F = M.frame(lg["ankle"], lg["knee"]), M.frame(lg["knee"], P["hip"])
    return {"shin": Sg(0.8, 5), "ankle": Sg(0.02, 6), "thigh": F(0.18, 9)}[what]


def solve(spec, ex, ref=None):
    if ex.get("bridge"):
        return bridge(spec, ex, ref)
    if ex.get("thrust"):
        return thrust(spec, ex, ref)
    if ex.get("hang"):
        return hang(spec, ex)
    if ex.get("balance"):
        spec = balance(spec, ex)
    P = pose(spec)
    bar_arms(P, ex, spec)
    if ex.get("hold"):      # штанга на спине: руки держат гриф как в приседе (локти вниз-назад от корпуса)
        for side in ("arm", "arm2"):
            e = M.add(P["joint"], P["tb"] + 200, M.L["upper"])
            P[side] = dict(elbow=e, hand=M.add(e, P["tb"] + 20, M.L["fore"]))
        P["elbow"], P["hand"], P["hand2"] = P["arm"]["elbow"], P["arm"]["hand"], P["arm2"]["hand"]
    if ex.get("hands_to"):  # кисти держат ногу: колено к груди, стопу в растяжке бедра
        set_arms(P, grab(P, ex["hands_to"]), ex.get("bend", 1), sides=("arm",) if ex.get("one_hand") else ("arm", "arm2"))
    return P


def frames(ex):
    """Список поз P от start к end (если start нет — одна поза)."""
    ref = bridge_ref(ex) if ex.get("bridge") else None
    if ex.get("thrust"):    # стопы стоят там, где они в верхней точке
        ref = thrust(full(ex["end"]), ex)["near"]["ankle"]
    end = full(ex["end"])
    if not ex.get("start"):
        return [solve(end, ex, ref)]
    start = full(ex["start"])
    out = []
    for i in range(FRAMES):
        t = (1 - math.cos(math.pi * i / (FRAMES - 1))) / 2      # плавный разгон и торможение
        out.append(solve(lerp_spec(start, end, t), ex, ref))
    return out


def lowest(P, part):
    if part == "feet":
        return min(p[1] for lg in (P["near"], P["far"]) for p in lg["foot"])
    if part == "toe":
        return P["toe"][1]
    if part == "far":       # опорная нога — дальняя (скалолаз: ближняя нога в воздухе)
        return min(p[1] for p in P["far"]["foot"])
    if part == "pelvis":    # на полу таз и живот («супермен»: грудь и ноги поднимаются)
        T = M.torso(P)[0]
        return min(T(t / 10, s)[1] for t in range(0, 5) for s in (-11.5, 7.5))
    if part == "legs":      # на полу колени и голени (отжимания с колен)
        return min(p[1] for lg in (P["near"], P["far"]) for p in leg_pts(P, lg))
    if part == "body":      # всё, кроме рук: руки потом сами встанут на пол (plant)
        return min(p[1] for p in M.samples(dict(P, arm=_nil(P), arm2=_nil(P))))
    return M.bbox(P)[1]


def place(Ps, ex):
    """Каждую позу ставим на пол, опорную точку (стопа, колено, таз) держим на месте по горизонтали.
    floor: feet — пол по стопам (мостик, отжимания: остальное тело само ложится на пол), toe — носок стоит
    на ступеньке высотой step см (подъём на носки, пятка свисает).
    plant: hand — кисть стоит на полу в одной точке во всех позах (отжимания), рука сгибается сама через ik;
    точка — под плечом в последней позе, сдвинутая назад на plant_back см.
    legs — на полу колени и голени (отжимания с колен), body — всё, кроме рук («кобра»).
    hang — вис: перекладина на высоте hang см, пол только для масштаба."""
    if ex.get("hang"):      # перекладина на высоте hang см и не двигается
        return [M.moved(P, -P["grip"][0], ex["hang"] - P["grip"][1]) for P in Ps]
    anchor, plant = ex.get("anchor", "hip"), ex.get("plant")
    part = ex.get("floor", "feet" if plant == "hand" else "all")
    lift = ex.get("step", 0)
    Ps = [M.moved(P, 0, lift - lowest(P, part)) for P in Ps]
    ref = Ps[0][anchor][0]
    Ps = [M.moved(P, ref - P[anchor][0], 0) for P in Ps]
    if plant == "hand":
        hand = (Ps[-1]["joint"][0] - ex.get("plant_back", 0), 2.2)
        for P in Ps:
            set_arms(P, hand)
    return Ps


# ---------- снаряды ----------

BARS = ("back", "hands", "hip")


def bar_point(P, bar):
    if bar == "back":
        return M.torso(P)[0](0.97, -9)
    return P.get("grip", P["hand"])


def equipment(pen, P, ex):
    """Снаряд в руках: штанга (диск и гриф сбоку) или гантель."""
    bar = ex.get("bar", "none")
    if bar in BARS:
        x, y = pen.p(bar_point(P, bar))
        return (f'<circle class="plate" cx="{x:.1f}" cy="{y:.1f}" r="40"/>'
                f'<circle class="barc" cx="{x:.1f}" cy="{y:.1f}" r="6"/>')
    if bar == "dumbbell":
        out = []
        for h in (P["hand2"], P["hand"]):
            x, y = pen.p(h)
            out.append(f'<rect class="db" x="{x - 13:.1f}" y="{y - 13:.1f}" width="26" height="26" rx="5"/>'
                       f'<circle class="barc" cx="{x:.1f}" cy="{y:.1f}" r="4.5"/>')
        return '<g class="far">' + out[0] + "</g>" + out[1]
    if bar == "kettlebell":     # гиря висит из кистей по направлению предплечья
        h, e = P["hand"], P["elbow"]
        d = math.hypot(h[0] - e[0], h[1] - e[1]) or 1
        u = ((h[0] - e[0]) / d, (h[1] - e[1]) / d)
        c, r = pen.p((h[0] + u[0] * 12, h[1] + u[1] * 12)), pen.p((h[0] + u[0] * 3.5, h[1] + u[1] * 3.5))
        return (f'<circle class="kbh" cx="{r[0]:.1f}" cy="{r[1]:.1f}" r="9"/>'
                f'<circle class="db" cx="{c[0]:.1f}" cy="{c[1]:.1f}" r="19"/>')
    if bar == "pullbar":        # перекладина сбоку — кружок на кронштейне
        x, y = pen.p(P["grip"])
        return (f'<path class="equip" style="fill:none;stroke-width:5" d="M{x:.1f} {y:.1f}V{y - 34:.1f}"/>'
                f'<circle class="barc" cx="{x:.1f}" cy="{y:.1f}" r="7"/>')
    if bar == "band":           # резинка от кистей к стопам
        out = []
        for h, lg in ((P["hand2"], P["far"]), (P["hand"], P["near"])):
            a, b = pen.p(h), pen.p(lg["foot"][7])
            out.append(f'<path class="band" d="M{a[0]:.1f} {a[1]:.1f}L{b[0]:.1f} {b[1]:.1f}"/>')
        return '<g class="far">' + out[0] + "</g>" + out[1]
    return ""


def step_svg(pen, P, h):
    """Ступенька под передней частью стопы: пятка свисает за край (подъём на носки)."""
    x = P["toe"][0]
    a, c = pen.p((x - 18, h)), pen.p((x + 22, 0))
    return f'<rect class="equip" x="{a[0]:.1f}" y="{a[1]:.1f}" width="{c[0] - a[0]:.1f}" height="{c[1] - a[1] + 3:.1f}" rx="3"/>'


def bench_svg(pen, ex, P):
    """Скамья под корпусом (жимы, тяга на скамье): высота в условных см, ставится до тела."""
    b = ex.get("bench")
    if not b:
        return ""
    x0, x1 = b["x"]
    h = b["h"]
    a, c = pen.p((x0, h)), pen.p((x1, 0))
    leg1, leg2 = pen.p((x0 + 6, 0)), pen.p((x1 - 6, 0))
    return (f'<rect class="equip" x="{a[0]:.1f}" y="{a[1]:.1f}" width="{c[0] - a[0]:.1f}" height="10" rx="4"/>'
            f'<path class="equip" style="fill:none;stroke-width:6" d="M{leg1[0]:.1f} {a[1] + 10:.1f}V{c[1]:.1f}'
            f'M{leg2[0]:.1f} {a[1] + 10:.1f}V{c[1]:.1f}"/>')


# ---------- анимация ----------

def parse(frag):
    return ET.fromstring(f'<g xmlns="{SVGNS}">{frag}</g>')


MATRIX = re.compile(r"matrix\(([^)]*)\)")


def tr_parts(t):
    """transform -> список (тип, значения) для animateTransform."""
    m = MATRIX.fullmatch(t.strip())
    if m:
        a, b, c, d, e, f = map(float, m.group(1).split())
        rot = math.degrees(math.atan2(b, a))
        r = math.radians(rot)
        flip = 1 if abs(c + math.sin(r)) + abs(d - math.cos(r)) < 0.2 else -1
        return [("translate", f"{e:.1f} {f:.1f}"), ("rotate", f"{rot:.1f}"), ("scale", f"1 {flip}")]
    m = re.fullmatch(r"rotate\(([^)]*)\)", t.strip())
    if m:
        return [("rotate", " ".join(m.group(1).split()))]
    raise ValueError(f"не умею анимировать transform {t}")


NUM = re.compile(r"-?\d+\.\d+")


def coarse(v):
    """В анимации хватает целых пикселей: файл в 2–3 раза легче, на глаз разницы нет."""
    return NUM.sub(lambda m: str(round(float(m.group()))), v)


def merge(trees, key_times, dur):
    """Деревья одинаковой структуры -> одно дерево с <animate> там, где атрибуты меняются."""
    base = copy.deepcopy(trees[0])

    def walk(node, others):
        for attr, v in list(node.attrib.items()):
            vals = [o.attrib.get(attr) for o in others]
            if len(set(vals)) == 1:
                continue
            if attr == "transform":
                parts = [tr_parts(x) for x in vals]
                for i, (typ, _) in enumerate(parts[0]):
                    seq = [p[i][1] for p in parts]
                    ET.SubElement(node, f"{{{SVGNS}}}animateTransform", attributeName="transform", type=typ,
                                  values=";".join(seq), keyTimes=key_times, dur=dur, repeatCount="indefinite",
                                  additive="replace" if i == 0 else "sum")
                node.set("transform", " ".join(f"{t}({x})" for t, x in parts[0]))
            else:
                ET.SubElement(node, f"{{{SVGNS}}}animate", attributeName=attr, values=";".join(map(coarse, vals)),
                              keyTimes=key_times, dur=dur, repeatCount="indefinite")
        kids = [list(o) for o in others]
        if len({len(k) for k in kids}) != 1:
            raise ValueError("у кадров разная структура")
        for i, ch in enumerate(list(node)):
            if ch.tag.endswith("animate") or ch.tag.endswith("animateTransform"):
                continue
            walk(ch, [k[i] for k in kids])

    walk(base, trees)
    return "".join(ET.tostring(ch, encoding="unicode") for ch in base)


def timeline(n):
    """Кадры 0..n-1 туда, держим, обратно, держим. Возвращает индексы кадров и keyTimes."""
    if n == 1:
        return [0], None
    idx = list(range(n)) + list(range(n - 1, -1, -1)) + [0]
    move = (1 - 2 * HOLD) / 2
    times = []
    for i in range(n):                               # туда
        times.append(move * i / (n - 1))
    for i in range(n):                               # пауза в конечной позе и обратно
        times.append(move + HOLD + move * i / (n - 1))
    times.append(1.0)
    return idx, ";".join(f"{t:.4f}" for t in times)


# ---------- картинка ----------

STYLE_EXTRA = """<style>
.db{fill:#3a3a37;fill-opacity:.85}.kbh{fill:none;stroke:#3a3a37;stroke-width:4.5}
.band{fill:none;stroke:#5f5d55;stroke-width:3.5;stroke-linecap:round}
@media (prefers-color-scheme:dark){.db{fill:#bdbbb3}.kbh{stroke:#bdbbb3}.band{stroke:#a9a8a1}}
</style>"""


def render(row, ex):
    Ps = place(frames(ex), ex)
    if "benchpts" in Ps[0]:     # скамья под лопатками (мостик от скамьи) или под задней стопой (болгарский выпад)
        a, b = Ps[0]["benchpts"]["a"], Ps[0]["benchpts"]["b"]
        ex = dict(ex, bench=dict(x=(a[0], b[0]), h=a[1]))
    elif ex.get("bench"):
        # скамья под спиной: верх — по нижнему краю корпуса в первой позе, от таза до плеч с запасом
        T = M.torso(Ps[0])[0]
        back = [T(t / 10, -11.5) for t in range(11)]
        xs = [p[0] for p in back]
        ex = dict(ex, bench=dict(x=(min(xs) - 6, max(xs) + 4), h=min(p[1] for p in back)))
    on = row["muscles"].split()
    pts = [p for P in Ps for p in M.samples(P)]
    if ex.get("bar") in BARS:
        for P in Ps:
            c = bar_point(P, ex["bar"])
            pts += [(c[0] - 17.5, c[1] - 17.5), (c[0] + 17.5, c[1] + 17.5)]
    if ex.get("bar") == "pullbar":
        pts += [(Ps[0]["grip"][0], Ps[0]["grip"][1] + 16)]
    if ex.get("bar") == "kettlebell":
        for P in Ps:
            h, e = P["hand"], P["elbow"]
            pts += [(h[0] + (h[0] - e[0]) * 0.8 + s, h[1] + (h[1] - e[1]) * 0.8 + s) for s in (-9, 9)]
    if ex.get("step"):
        x = Ps[0]["toe"][0]
        pts += [(x - 18, 0), (x + 22, ex["step"])]
    if ex.get("bench"):
        pts += [(ex["bench"]["x"][0], 0), (ex["bench"]["x"][1], ex["bench"]["h"])]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y1 = max(p[1] for p in pts)

    out, y = [], 46
    for line in M.wrap(row["name"], 36)[:2]:
        out.append(M.txt(32, y, line, "ttl"))
        y += 32
    for cue in ex.get("cues", [])[:2]:
        for line in M.wrap(cue, 52)[:2]:
            out.append(M.txt(32, y, line, "cue"))
            y += 25
    y += 14
    floor_y = y + (y1 + 4) * M.S
    pen = M.Pen(M.W / 2 - (x0 + x1) / 2 * M.S, floor_y)
    out.append(f'<line class="floor" x1="32" y1="{floor_y + 3:.0f}" x2="{M.W - 32}" y2="{floor_y + 3:.0f}"/>')
    out.append(bench_svg(pen, ex, Ps[0]))
    if ex.get("step"):
        out.append(step_svg(pen, Ps[0], ex["step"]))
    figs = [M.draw_body(pen, P, on=on) + equipment(pen, P, ex) for P in Ps]
    idx, kt = timeline(len(figs))
    if kt:
        body = merge([parse(figs[i]) for i in idx], kt, f"{DUR}s")
        out.append(f"<g>{body}</g>")
    else:
        out.append(figs[0])
    y = floor_y + 40
    lines = M.wrap("Работают: " + ", ".join(M.RU[k] for k in on if k in M.RU), 50)
    out.append(f'<circle class="lg" cx="42" cy="{y - 7}" r="8"/>')
    for i, line in enumerate(lines[:3]):
        out.append(M.txt(58, y + i * 25, line, "legend"))
    y += 25 * min(len(lines), 3)
    return M.STYLE + STYLE_EXTRA + "".join(out), int(y + 6)


def build(ids=None):
    rows, P = manifest(), poses()
    n = 0
    for row in rows:
        if ids and row["id"] not in ids:
            continue
        if row["id"] not in P:
            print(f"{row['id']}: нет позы в poses.json")
            continue
        body, h = render(row, P[row["id"]])
        K.svg(OUT / f"{row['id']}.svg", row["name"], body, h=h)
        n += 1
    print(f"Схем нарисовано: {n}")


if __name__ == "__main__":
    build(set(sys.argv[1:]) or None)
