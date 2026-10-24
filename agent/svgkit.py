"""Общий набор для SVG-картинок статей: скелет с мышцами (вид сбоку), подписи, стрелки, стиль.

Стиль один на все картинки сайта, тёмная тема через prefers-color-scheme внутри SVG.
"""
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

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
    # «вперёд» — всегда поворот по часовой; раньше знак менялся, и в глубоком приседе квадрицепс уезжал под бедро
    a = (u[1], -u[0])
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


def pose(shank, thigh, bar_x=6.0, torso=None, bar=True, arms="down"):
    """shank: наклон голени вперёд; thigh: угол бедра назад от вертикали (90 — параллель полу).
    Наклон корпуса подбирается так, чтобы гриф стоял над серединой стопы."""
    ankle = (0.0, 8.0)
    knee = add(ankle, shank, L["shank"])
    hip = add(knee, -thigh, L["thigh"])
    best = None
    for i in ([round(torso * 10)] if torso is not None else range(0, 900)):
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
    if bar:
        # локоть смотрит вниз и чуть назад, кисть держит гриф
        elbow = add(joint, 180 + 25, L["upper"])
    elif arms == "forward":
        # присед без веса: руки вытянуты вперёд для баланса
        elbow = add(joint, 84, 29)
        hand = add(elbow, 88, 26)
    else:
        # без штанги руки висят вдоль корпуса, в проекции сбоку они полной длины
        elbow = add(joint, 180 + 4, 29)
        hand = add(elbow, 180 - 6, 26)
    return dict(ankle=ankle, knee=knee, hip=hip, top=sh_end, joint=joint, tb=tb,
                bar=barp if bar else None, hand=hand, elbow=elbow, heel=(-7, 1), toe=(20, 1))


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
    a, o, b = scr(T(1.3, 0)), scr(T(1.2, 0)), scr(T(1.3, 1))
    g.append(head(scr(T(1.3, -3.5)), norm((b[0] - a[0], b[1] - a[1])), norm((a[0] - o[0], a[1] - o[1]))))
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
    if P["bar"]:
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
    s.append(f'<text class="t" x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}">{esc(title)}</text>')
    if sub:
        for i, line in enumerate(sub if isinstance(sub, list) else [sub]):
            s.append(f'<text class="s" x="{x:.0f}" y="{y + 24 + i * 22:.0f}" text-anchor="{anchor}">{esc(line)}</text>')
    return "".join(s)


def arrow(a, b, curve=None):
    if curve:
        return f'<path class="arrow" d="M{a[0]:.0f} {a[1]:.0f}Q{curve[0]:.0f} {curve[1]:.0f} {b[0]:.0f} {b[1]:.0f}"/>'
    return f'<path class="arrow" d="M{a[0]:.0f} {a[1]:.0f}L{b[0]:.0f} {b[1]:.0f}"/>'


def svg(path, title, body, h=H):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" role="img" aria-label="{esc(title)}">'
           f"<title>{esc(title)}</title>{STYLE}{body}</svg>\n")
    path.write_text(doc, encoding="utf-8")


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# Голова сбоку. Координаты головы: x — вперёд (к лицу), y — вниз, радиус черепа около 20 px.
HEADS = {
    # череп: гладкий свод, скула и аккуратная нижняя челюсть одним контуром
    "skull": ('<path class="bone" d="M-18 6C-23 -6 -16 -21 0 -21C14 -21 21 -12 20 -1C20 2 21 4 22 6'
              'C22 8 20 9 19 9C19 12 17 14 14 14C11 17 6 18 2 16C-3 15 -6 12 -8 9C-13 9 -16 8 -18 6Z"/>'
              '<ellipse cx="9" cy="-1" rx="4.6" ry="5.2" fill="#7d776b"/>'
              '<path class="lead" style="stroke:#7d776b" d="M-1 9Q6 12 14 10M5 12.5v3M9 12v3"/>'),
    # голова-манекен: ровное «яйцо», лёгкий нос, ухо, без лица
    "mannequin": ('<path class="bone" d="M-17 4C-20 -10 -11 -21 2 -21C14 -21 20 -12 19 -3L22 3L19 5'
                  'C19 11 15 17 6 18C-4 19 -14 14 -17 4Z"/>'
                  '<ellipse class="lead" style="stroke:#7d776b;fill:none" cx="-3" cy="0" rx="3.4" ry="5"/>'
                  '<circle cx="11" cy="-4" r="2.2" fill="#7d776b"/>'),
    # мультяшная: круглая, большой глаз и улыбка
    "cartoon": ('<circle class="bone" cx="0" cy="-1" r="19.5"/>'
                '<circle cx="9" cy="-5" r="5.2" fill="#fff" stroke="#7d776b" stroke-width="1.5"/>'
                '<circle cx="10.5" cy="-5" r="2.6" fill="#3b3934"/>'
                '<path class="lead" style="stroke:#7d776b;stroke-width:2;stroke-linecap:round" d="M8 8Q13 11 17 6"/>'
                '<circle cx="3" cy="5" r="3.2" fill="#d2491d" fill-opacity=".25"/>'),
}
HEAD = "muscle"


def head(c, fwd, up, variant=None):
    """Голова в точке c (экран), fwd и up — единичные векторы «к лицу» и «к макушке» на экране."""
    a, b, cc, d = fwd[0], fwd[1], -up[0], -up[1]
    return (f'<g class="head" transform="matrix({a:.3f} {b:.3f} {cc:.3f} {d:.3f} {c[0]:.1f} {c[1]:.1f})">'
            f'{HEADS[variant or HEAD]}</g>')


# Голова спереди (боковая планка): та же манера, без профиля
HEADS_FRONT = {
    "skull": ('<path class="bone" d="M-17 2C-19 -12 -10 -21 0 -21C10 -21 19 -12 17 2C16 8 13 11 10 13'
              'C9 17 5 19 0 19C-5 19 -9 17 -10 13C-13 11 -16 8 -17 2Z"/>'
              '<ellipse cx="-6.5" cy="0" rx="4.4" ry="5" fill="#7d776b"/><ellipse cx="6.5" cy="0" rx="4.4" ry="5" fill="#7d776b"/>'
              '<path class="lead" style="stroke:#7d776b" d="M-5 13H5M-2 11v4M2 11v4"/>'),
    "mannequin": '<ellipse class="bone" cx="0" cy="-1" rx="16" ry="20"/>',
    "cartoon": ('<circle class="bone" cx="0" cy="-1" r="19.5"/><circle cx="-6" cy="-4" r="2.6" fill="#3b3934"/>'
                '<circle cx="6" cy="-4" r="2.6" fill="#3b3934"/>'
                '<path class="lead" style="stroke:#7d776b;stroke-width:2;stroke-linecap:round" d="M-6 7Q0 11 6 7"/>'),
}

HEADS.update({
    # подробный череп: свод, глазница, нос, скула, нижняя челюсть с углом и зубы
    "skull2": ('<path class="bone" d="M-19 3C-22 -10 -13 -21 1 -21C13 -21 20 -13 20 -4C20 -1 21 1 22 3L19 4'
               'C19 6 18 7 17 7L17 9H6C3 9 -1 8 -4 7C-8 8 -13 8 -16 7C-18 6 -19 5 -19 3Z"/>'
               '<path class="bone" d="M-7 6C-9 10 -7 14 -4 15.5C1 17.5 9 16.5 14.5 14.5C16.5 13.5 16.5 11 15.5 9.5H6C2 9.5 -3 8 -7 6Z"/>'
               '<circle cx="10" cy="-3" r="4.6" fill="#7d776b"/>'
               '<path d="M18.5 1.5L16 5.5H19Z" fill="#7d776b"/>'
               '<path class="lead" style="stroke:#7d776b" d="M2 3Q7 2 12 4M7 7v5M10 7v5M13 7v5"/>'
               '<circle cx="-7" cy="3" r="1.8" fill="#7d776b"/>'),
    # профиль человека: лоб, нос, губы, подбородок, без черт лица
    "profile": ('<path class="bone" d="M-18 2C-20 -12 -10 -21 2 -21C12 -21 18 -15 19 -7L19 -3L23 3'
                'C23 4 22 5 20 5L20 7C21 8 20 9 19 9.5L19 11C19 14 16 16 12 16L8 17C2 19 -6 17 -11 13'
                'C-15 10 -17 7 -18 2Z"/>'
                '<path class="lead" style="stroke:#7d776b;fill:none" d="M-4 -2C-1 -2 0 2 -2 4C-3 5 -5 4 -5 2"/>'
                '<path class="lead" style="stroke:#7d776b;stroke-linecap:round" d="M10 -3Q12.5 -1.5 15 -3"/>'),
    # минимализм: шар и маленький «нос»-указатель, куда смотрит человек
    "ball": ('<circle class="bone" cx="0" cy="-1" r="19"/>'
             '<path class="bone" d="M17 -6L24 0L17 5Z"/>'),
    # «с мышцами»: череп в мышечном слое — височная и жевательная мышцы, как у тела
    "muscle": ('<path class="bone" d="M-18 4C-22 -9 -13 -21 1 -21C13 -21 20 -13 20 -3L22 3L19 5'
               'C19 10 16 15 9 16C3 18 -5 17 -10 13C-14 11 -17 8 -18 4Z"/>'
               '<path class="m" d="M-12 -6C-10 -15 2 -18 10 -13C13 -11 12 -7 8 -6C3 -5 -4 -4 -7 -1C-10 0 -13 -2 -12 -6Z"/>'
               '<path class="m" d="M-3 2C0 0 5 1 6 4L8 13C6 15 1 15 -1 13Z"/>'
               '<circle cx="10.5" cy="-2.5" r="3.6" fill="#7d776b"/>'),
})
HEADS_FRONT.update({
    "skull2": HEADS_FRONT["skull"],
    "profile": '<ellipse class="bone" cx="0" cy="-1" rx="16" ry="20"/>',
    "ball": '<circle class="bone" cx="0" cy="-1" r="19"/>',
    "muscle": ('<ellipse class="bone" cx="0" cy="-1" rx="17" ry="20"/>'
               '<path class="m" d="M-15 -4C-15 -12 -9 -17 -4 -17C-6 -12 -8 -8 -12 -2Z"/>'
               '<path class="m" d="M15 -4C15 -12 9 -17 4 -17C6 -12 8 -8 12 -2Z"/>'
               '<path class="m" d="M-13 4L-8 3L-7 13L-11 11Z"/><path class="m" d="M13 4L8 3L7 13L11 11Z"/>'
               '<ellipse cx="-6" cy="-1" rx="3.4" ry="3.8" fill="#7d776b"/><ellipse cx="6" cy="-1" rx="3.4" ry="3.8" fill="#7d776b"/>'),
})


def head_front(c, up, variant=None):
    fwd = (-up[1], up[0])
    a, b, cc, d = fwd[0], fwd[1], -up[0], -up[1]
    return (f'<g class="head front" transform="matrix({a:.3f} {b:.3f} {cc:.3f} {d:.3f} {c[0]:.1f} {c[1]:.1f})">'
            f'{HEADS_FRONT[variant or HEAD]}</g>')
