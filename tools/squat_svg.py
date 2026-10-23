"""Рисует SVG-иллюстрации к статье про присед: скелет с мышцами, вид сбоку.

python3 tools/squat_svg.py  ->  static/img/squat/*.svg
"""
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "static" / "img" / "squat"

W, H = 640, 480
S = 2.3                     # масштаб: условные сантиметры -> пиксели
OX, OY = 200, 455            # голеностоп на экране
# руки в проекции сбоку короче: хват широкий, плечо и предплечье уходят в стороны
L = dict(shank=44, thigh=46, torso=52, upper=19, fore=17)

STYLE = """
<style>
.bone{fill:#efe9dc;stroke:#7d776b;stroke-width:2;stroke-linejoin:round}
.joint{fill:#efe9dc;stroke:#7d776b;stroke-width:2}
.vert{fill:#e2dccd;stroke:#7d776b;stroke-width:1.2}
.m{fill:#c7867a;fill-opacity:.42;stroke:#a9665a;stroke-opacity:.55;stroke-width:1}
.on{fill:#d2491d;fill-opacity:.82;stroke:#9c3412;stroke-opacity:.9}
.plate{fill:#3a3a37;fill-opacity:.1;stroke:#3a3a37;stroke-width:3}
.bar{fill:#3a3a37}
.ghost{opacity:.18}
.ground{stroke:#b9b5aa;stroke-width:3}
.guide{stroke:#3d7fb8;stroke-width:2.5;stroke-dasharray:8 7;fill:none}
.arrow{stroke:#d2491d;stroke-width:5;fill:none;stroke-linecap:round;marker-end:url(#ah)}
.ahead{fill:#d2491d}
.lead{stroke:#6b6b66;stroke-width:1.5;fill:none}
.t{font:600 21px system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;fill:#1d1d1b}
.s{font:400 18px system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;fill:#55554f}
.ok{fill:#2e8b57}.bad{fill:#c0392b}
.balloon{fill:#3d7fb8;fill-opacity:.25;stroke:#3d7fb8;stroke-width:2}
@media (prefers-color-scheme:dark){
.bone,.joint{fill:#d9d3c4;stroke:#3b3934}.vert{fill:#c9c2b2;stroke:#3b3934}
.plate{fill:#ecebe6;fill-opacity:.12;stroke:#bdbbb3}.bar{fill:#bdbbb3}
.t{fill:#ecebe6}.s{fill:#a9a8a1}.lead{stroke:#9a9993}.ground{stroke:#55534d}
.arrow{stroke:#f0703f}.ahead{fill:#f0703f}.on{fill:#f0703f}
}
</style>
<defs><marker id="ah" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="4" markerHeight="4" orient="auto">
<path class="ahead" d="M0 0L10 5L0 10z"/></marker></defs>
"""


def scr(p):
    return (OX + p[0] * S, OY - p[1] * S)


def add(p, a, ln):
    """Точка p + отрезок длиной ln под углом a (градусы от вертикали, по часовой — вперёд)."""
    r = math.radians(a)
    return (p[0] + ln * math.sin(r), p[1] + ln * math.cos(r))


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def norm(d):
    n = math.hypot(*d) or 1
    return (d[0] / n, d[1] / n)


def ccw(d):
    return (-d[1], d[0])



def frame(p0, p1):
    """Система координат сегмента: t — доля длины от p0 к p1, s — смещение вперёд (к животу)."""
    u = (p1[0] - p0[0], p1[1] - p0[1])
    ln = math.hypot(*u)
    u = (u[0] / ln, u[1] / ln)
    a = (u[1], -u[0]) if u[1] >= 0 else (-u[1], u[0])
    return lambda t, s: (p0[0] + u[0] * t * ln + a[0] * s, p0[1] + u[1] * t * ln + a[1] * s)


def smooth(pts):
    """Замкнутая сглаженная кривая через точки (Catmull-Rom -> Безье)."""
    P = [scr(p) for p in pts]
    n = len(P)
    d = f"M{P[0][0]:.1f} {P[0][1]:.1f}"
    for i in range(n):
        p0, p1, p2, p3 = P[i - 1], P[i], P[(i + 1) % n], P[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return d + "Z"


def shape(f, pts, cls):
    return f'<path class="{cls}" d="{smooth([f(t, s) for t, s in pts])}"/>'


def pose(shank, thigh, bar_x=6.0):
    """shank: наклон голени вперёд; thigh: угол бедра назад от вертикали (90 — параллель полу).
    Наклон корпуса подбирается так, чтобы гриф стоял над серединой стопы."""
    ankle = (0.0, 8.0)
    knee = add(ankle, shank, L["shank"])
    hip = add(knee, -thigh, L["thigh"])
    best = None
    for i in range(0, 900):
        tb = i / 10
        T = frame(hip, add(hip, tb, L["torso"]))
        barp = T(1.03, -10.5)
        err = abs(barp[0] - bar_x)
        if best is None or err < best[0]:
            best = (err, tb, barp)
    _, tb, barp = best
    sh_end = add(hip, tb, L["torso"])
    T = frame(hip, sh_end)
    joint = T(0.94, -2)
    hand = (barp[0] + 2.5, barp[1] + 1)
    # локоть смотрит вниз и чуть назад, кисть держит гриф
    elbow = add(joint, 180 + 25, L["upper"])
    return dict(ankle=ankle, knee=knee, hip=hip, top=sh_end, joint=joint, tb=tb,
                bar=barp, hand=hand, elbow=elbow, heel=(-7, 1), toe=(20, 1))


def figure(P, on=(), ghost=False):
    on = set(on)
    m = lambda k: "m on" if k in on else "m"
    g = []
    an, k, hp = P["ankle"], P["knee"], P["hip"]
    S_ = frame(an, k)
    F = frame(k, hp)
    T = frame(hp, P["top"])
    # стопа
    g.append(shape(lambda t, s: (an[0] + t, an[1] + s - 8),
                   [(-7, 1), (-7, 5), (-2, 9.5), (3, 9), (12, 4.5), (20, 2.2), (21, 0.6), (8, 0.2), (-5, 0.3)], "bone"))
    # голень
    g.append(shape(S_, [(0.2, -1.6), (0.45, -5.2), (0.68, -6.8), (0.86, -5), (0.97, -2.2), (0.85, -1.4), (0.5, -1.6)], m("calves")))
    g.append(shape(S_, [(0.15, 1.8), (0.5, 3.6), (0.85, 3.2), (0.86, 1.9), (0.5, 2.1)], "m"))
    g.append(shape(S_, [(0.02, 1.8), (0.1, 1.3), (0.88, 1.5), (0.98, 3.4), (1.03, 0.5), (0.98, -2.8), (0.88, -1.2), (0.1, -0.6), (0.02, -1.6)], "bone"))
    # бедро
    g.append(shape(F, [(0.1, -1.4), (0.35, -5.6), (0.7, -6.6), (0.95, -4.2), (0.92, -1.6), (0.5, -1.8)], m("hams")))
    g.append(shape(F, [(-0.02, 3.6), (0.15, 6.4), (0.5, 8.2), (0.82, 7), (0.98, 3.6), (0.85, 1.6), (0.5, 1.8), (0.12, 2)], m("quads")))
    g.append(shape(F, [(-0.02, 2.8), (0.04, 3.6), (0.1, 1.6), (0.86, 1.3), (0.97, 2.4), (1.02, 0.6), (0.99, -1.8), (0.88, -1.4), (0.1, -1.6), (0.0, -2.6)], "bone"))
    g.append(f'<circle class="joint" cx="{scr(k)[0]:.1f}" cy="{scr(k)[1]:.1f}" r="5"/>')
    # ягодичные — от таза к бедру
    gl = [T(0.27, -8.6), T(0.16, -12.4), T(0.0, -12.8), F(0.8, -6.4), F(0.62, -3.6), F(0.8, -1.4), T(0.06, -6.2)]
    g.append(f'<path class="{m("glutes")}" d="{smooth(gl)}"/>')
    # таз
    g.append(shape(T, [(-0.04, -2.5), (0.05, -8.5), (0.27, -10), (0.32, -5.5), (0.3, 1.5), (0.17, 5.5), (0.05, 4.5), (0.0, 2)], "bone"))
    g.append(f'<circle class="joint" cx="{scr(hp)[0]:.1f}" cy="{scr(hp)[1]:.1f}" r="5.5"/>')
    # пресс и разгибатели
    g.append(shape(T, [(0.1, 3.8), (0.3, 6.6), (0.55, 7.2), (0.72, 6.4), (0.7, 4.4), (0.4, 4.6), (0.15, 2.8)], m("abs")))
    g.append(shape(T, [(0.15, -8.6), (0.4, -10.6), (0.7, -11.2), (0.92, -10), (0.95, -8.6), (0.7, -8.8), (0.4, -8.2)], m("back")))
    # грудная клетка и рёбра
    g.append(shape(T, [(0.42, -6.8), (0.6, -8.6), (0.86, -8.2), (0.98, -5), (0.97, 2.6), (0.82, 6.8), (0.55, 7), (0.42, 4.2)], "bone rib"))
    for t in (0.5, 0.6, 0.7, 0.8, 0.9):
        a, b2, c = scr(T(t + 0.02, -7.6)), scr(T(t - 0.05, 0)), scr(T(t - 0.02, 5.8))
        g.append(f'<path class="lead" style="stroke:#7d776b" d="M{a[0]:.1f} {a[1]:.1f}Q{b2[0]:.1f} {b2[1]:.1f} {c[0]:.1f} {c[1]:.1f}"/>')
    # позвоночник с изгибами
    for i in range(18):
        t = 0.06 + i * 0.056
        s = -6.6 + 1.6 * math.cos((t - 0.3) * 2 * math.pi / 0.9)
        x, y = scr(T(t, s))
        g.append(f'<rect class="vert" x="{x - 3.6:.1f}" y="{y - 3.2:.1f}" width="7.2" height="6.4" rx="1.8" '
                 f'transform="rotate({P["tb"]:.1f} {x:.1f} {y:.1f})"/>')
    # трапеция и верх спины, дельта
    g.append(shape(T, [(0.72, -9.2), (0.92, -11.4), (1.06, -10), (1.14, -5.8), (1.04, -5.2), (0.86, -7.6)], m("traps")))
    # голова
    hc = scr(T(1.3, -3.5))
    g.append(f'<circle class="bone" cx="{hc[0]:.1f}" cy="{hc[1]:.1f}" r="20"/>')
    jw = [T(1.22, 1), T(1.18, 7), T(1.25, 9.5), T(1.31, 8)]
    g.append('<path class="bone" d="M' + "L".join(f"{scr(p)[0]:.1f} {scr(p)[1]:.1f}" for p in jw) + 'Z"/>')
    eye = scr(T(1.33, 2.5))
    g.append(f'<circle cx="{eye[0]:.1f}" cy="{eye[1]:.1f}" r="4.5" fill="#7d776b"/>')
    # рука: дельта, плечо, предплечье
    J, E, Hd = P["joint"], P["elbow"], P["hand"]
    UA = frame(E, J)
    g.append(shape(UA, [(0.5, -3.6), (0.85, -5.4), (1.08, -2.5), (1.08, 3.5), (0.75, 4.2), (0.55, 2.2)], "m"))
    g.append(shape(UA, [(0.0, -1.8), (0.05, 2), (0.95, 1.4), (1.02, 0), (0.95, -1.4)], "bone"))
    FA = frame(E, Hd)
    g.append(shape(FA, [(0.0, -1.6), (0.05, 1.6), (0.95, 1.2), (1.0, 0), (0.95, -1.2)], "bone"))
    for p in (J, E):
        x, y = scr(p)
        g.append(f'<circle class="joint" cx="{x:.1f}" cy="{y:.1f}" r="4.2"/>')
    # штанга: диск и гриф
    b = scr(P["bar"])
    g.append(f'<circle class="plate" cx="{b[0]:.1f}" cy="{b[1]:.1f}" r="40"/>')
    g.append(f'<circle class="bar" cx="{b[0]:.1f}" cy="{b[1]:.1f}" r="6"/>')
    hx, hy = scr(Hd)
    g.append(f'<circle class="joint" cx="{hx:.1f}" cy="{hy:.1f}" r="5"/>')
    cls = ' class="ghost"' if ghost else ""
    return f"<g{cls}>" + "".join(g) + "</g>"


def ground():
    y = OY - 0 * S
    return f'<line class="ground" x1="40" y1="{y + 4:.0f}" x2="{W - 40}" y2="{y + 4:.0f}"/>'


def label(x, y, title, sub=None, to=None, anchor="start"):
    s = []
    if to:
        # линия-выноска от края заголовка, а не через текст
        ox = x + len(title) * 11 + 6 if to[0] > x else x - 8
        s.append(f'<path class="lead" d="M{ox:.0f} {y - 7:.0f}L{to[0]:.0f} {to[1]:.0f}"/>'
                 f'<circle cx="{to[0]:.0f}" cy="{to[1]:.0f}" r="4" fill="#6b6b66"/>')
    s.append(f'<text class="t" x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}">{title}</text>')
    if sub:
        for i, line in enumerate(sub if isinstance(sub, list) else [sub]):
            s.append(f'<text class="s" x="{x:.0f}" y="{y + 24 + i * 22:.0f}" text-anchor="{anchor}">{line}</text>')
    return "".join(s)


def arrow(a, b, curve=None):
    if curve:
        return f'<path class="arrow" d="M{a[0]:.0f} {a[1]:.0f}Q{curve[0]:.0f} {curve[1]:.0f} {b[0]:.0f} {b[1]:.0f}"/>'
    return f'<path class="arrow" d="M{a[0]:.0f} {a[1]:.0f}L{b[0]:.0f} {b[1]:.0f}"/>'


def svg(name, title, body):
    OUT.mkdir(parents=True, exist_ok=True)
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{title}">'
           f"<title>{title}</title>{STYLE}{body}</svg>\n")
    (OUT / f"{name}.svg").write_text(doc, encoding="utf-8")


STAND = pose(4, 3)
MID = pose(24, 52)
BOTTOM = pose(33, 96)


def main():
    # 1. Гриф на спине
    P = STAND
    b = scr(P["bar"])
    svg("shag-1-grif", "Гриф лежит на трапециях, лопатки сведены",
        ground() + figure(P, on={"traps"}) +
        label(330, 70, "Гриф на трапециях", "не на шейных позвонках", to=(b[0] + 8, b[1] - 10)) +
        label(330, 170, "Лопатки сведены", ["верх спины плотный:", "получается «полка»"], to=scr(lerp(P["hip"], P["top"], 0.78))) +
        label(330, 290, "Хват узкий,", ["насколько позволяют", "плечи и запястья"]))

    # 2. Стопы: вид сбоку + вид сверху
    P = STAND
    he, to = scr(P["heel"]), scr(P["toe"])
    feet = []
    cx, cy = 500, 300
    for sgn in (-1, 1):
        ang = sgn * 20
        x = cx + sgn * 48
        feet.append(f'<g transform="translate({x} {cy}) rotate({ang})">'
                    f'<path class="bone" d="M-13 30q-3 -40 0 -58q13 -14 26 0q3 18 0 58q-13 9 -26 0z"/></g>')
    top = ("".join(feet) +
           f'<line class="guide" x1="{cx - 48}" y1="{cy + 52}" x2="{cx + 48}" y2="{cy + 52}"/>'
           f'<text class="s" x="{cx}" y="{cy + 80}" text-anchor="middle">≈ ширина плеч</text>'
           f'<text class="s" x="{cx}" y="{cy - 64}" text-anchor="middle">вид сверху</text>'
           f'<text class="s" x="{cx}" y="{cy - 42}" text-anchor="middle">носки чуть наружу</text>')
    svg("shag-2-stopy", "Стопы на ширине плеч, носки слегка наружу, вес на всей стопе",
        ground() + figure(P, on={"calves"}) +
        arrow((he[0] + 8, he[1] - 70), (he[0] + 8, he[1] - 14)) +
        arrow((to[0] - 6, to[1] - 70), (to[0] - 6, to[1] - 14)) +
        label(310, 70, "Вес на всей стопе", ["пятка и носок", "прижаты к полу"], to=(to[0] - 6, to[1] - 74)) +
        top)

    # 3. Вдох и напряжённый корпус
    P = STAND
    belly = scr(lerp(P["hip"], P["top"], 0.3))
    svg("shag-3-vdoh", "Вдох в живот и напряжённый пресс держат поясницу",
        ground() + figure(P, on={"abs", "back"}) +
        f'<ellipse class="balloon" cx="{belly[0] + 4:.0f}" cy="{belly[1]:.0f}" rx="20" ry="30"/>' +
        arrow((belly[0] + 30, belly[1]), (belly[0] + 62, belly[1])) +
        arrow((belly[0] - 24, belly[1]), (belly[0] - 54, belly[1])) +
        label(330, 120, "Вдох в живот", ["давление внутри живота", "работает как мяч"], to=(belly[0] + 66, belly[1] - 8)) +
        label(330, 260, "Пресс и спина", ["напряжены, как будто", "сейчас ткнут кулаком"], to=scr(lerp(P["hip"], P["top"], 0.55))))

    # 4. Опускание
    P = MID
    k, hp = scr(P["knee"]), scr(P["hip"])
    to = scr(P["toe"])
    bx = scr(P["bar"])[0]
    svg("shag-4-opuskanie", "Опускание: таз и колени двигаются одновременно, гриф над серединой стопы",
        ground() + figure(STAND, ghost=True) + figure(P, on={"quads", "glutes"}) +
        f'<line class="guide" x1="{bx:.0f}" y1="40" x2="{bx:.0f}" y2="{OY:.0f}"/>' +
        arrow((k[0] + 14, k[1] - 6), (k[0] + 50, k[1] + 4)) +
        arrow((hp[0] - 20, hp[1] - 10), (hp[0] - 44, hp[1] + 30)) +
        label(400, 70, "Гриф над серединой", "стопы весь повтор", to=(bx + 4, 80)) +
        label(400, 190, "Колени вперёд", "по линии носков", to=(k[0] + 54, k[1] + 4)) +
        label(36, 140, "Таз вниз", "и немного назад") +
        label(400, 320, "Вниз под контролем,", "без падения в яму"))

    # 5. Подъём
    P = MID
    sh, hp = scr(P["top"]), scr(P["hip"])
    he, to = scr(P["heel"]), scr(P["toe"])
    svg("shag-5-podyom", "Подъём: толкай пол всей стопой, грудь и таз поднимаются вместе",
        ground() + figure(BOTTOM, ghost=True) + figure(P, on={"quads", "glutes", "back"}) +
        arrow((sh[0] - 70, sh[1] + 30), (sh[0] - 70, sh[1] - 30)) +
        arrow((hp[0] - 40, hp[1] + 20), (hp[0] - 40, hp[1] - 40)) +
        arrow(((he[0] + to[0]) / 2, OY - 50), ((he[0] + to[0]) / 2, OY - 6)) +
        label(36, 60, "Грудь и таз вверх", "одновременно") +
        label(400, 270, "Толкай пол", "всей стопой", to=((he[0] + to[0]) / 2 + 8, OY - 30)) +
        label(372, 90, "Таз не обгоняет плечи,", ["иначе нагрузка уходит", "в поясницу"]))

    # 6. Колени за носками
    P = BOTTOM
    to, k, he = scr(P["toe"]), scr(P["knee"]), scr(P["heel"])
    svg("koleni-za-noski", "В нижней точке колени выходят за носки, и это нормально",
        ground() + figure(P, on={"quads"}) +
        f'<line class="guide" x1="{to[0]:.0f}" y1="{k[1] - 60:.0f}" x2="{to[0]:.0f}" y2="{OY:.0f}"/>' +
        label(400, 120, "Колени за носками —", ["нормально, если пятки", "на полу и спина ровная"], to=(k[0] + 10, k[1])) +
        label(400, 330, "Пятки на полу", None, to=(he[0] + 4, he[1] - 4)))


if __name__ == "__main__":
    main()
