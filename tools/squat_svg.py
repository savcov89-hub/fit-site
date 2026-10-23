"""Рисует SVG-иллюстрации к статье про присед: скелет с мышцами, вид сбоку.

python3 tools/squat_svg.py  ->  static/img/squat/*.svg
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))
from svgkit import OY, S, arrow, figure, ground, label, lerp, pose, scr  # noqa: E402
from svgkit import svg as _svg  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "static" / "img" / "squat"


def svg(name, title, body):
    _svg(OUT / f"{name}.svg", title, body)


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
