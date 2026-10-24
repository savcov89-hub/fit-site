"""Меняет голову скелета во всех уже нарисованных SVG на текущую svgkit.HEAD (можно запускать повторно).

Старые картинки рисовались с головой-кругом и треугольной челюстью; по челюсти и глазу
восстанавливаем, куда смотрит голова, и ставим новую. Новые картинки рисуются сразу с новой головой.

python3 agent/redraw_heads.py
"""
import re

import svgkit as K

OLD = re.compile(r'<circle class="bone" cx="([\d.]+)" cy="([\d.]+)" r="20"/><path class="bone" d="M([^"]+)Z"/>'
                 r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4.5" fill="#7d776b"/>')


def replace(m):
    hx, hy = float(m.group(1)), float(m.group(2))
    jaw = [tuple(map(float, p.split())) for p in m.group(3).split("L")]
    ex, ey = float(m.group(4)), float(m.group(5))
    # в системе корпуса: глаз = H + 0.03·U + 6·A, первая точка челюсти = H − 0.08·U + 4.5·A
    e = (ex - hx, ey - hy)
    j = (jaw[0][0] - hx, jaw[0][1] - hy)
    det = 0.03 * 4.5 - 6 * (-0.08)
    U = ((e[0] * 4.5 - 6 * j[0]) / det, (e[1] * 4.5 - 6 * j[1]) / det)
    A = ((0.03 * j[0] + 0.08 * e[0]) / det, (0.03 * j[1] + 0.08 * e[1]) / det)
    return K.head((hx, hy), K.norm(A), K.norm(U))


NEW = re.compile(r'<g class="head( front)?" transform="matrix\(([^)]+)\)">.*?</g>')


def again(m):
    """Голова уже новая — меняем только рисунок на текущий вариант."""
    front = bool(m.group(1))
    body = (K.HEADS_FRONT if front else K.HEADS)[K.HEAD]
    return f'<g class="head{m.group(1) or ""}" transform="matrix({m.group(2)})">{body}</g>'


def main():
    n = 0
    for path in sorted((K.ROOT / "static" / "img").rglob("*.svg")):
        s = path.read_text(encoding="utf-8")
        new = OLD.sub(replace, s)
        new, k = NEW.subn(again, new)  # после первой замены все головы уже в новом виде
        if k:
            path.write_text(new, encoding="utf-8")
            n += k
            print(f"{path.relative_to(K.ROOT)}: {k}")
    print(f"голов заменено: {n}")


if __name__ == "__main__":
    main()
