"""SVG-картинки к статье: по одной под каждым подзаголовком.

Модель только описывает картинку (вид, подписи, цифры из текста), а рисует код из svgkit,
поэтому стиль у всех картинок один, а описание стоит центы.
"""
import json
import re

import moves as M
import svgkit as K

KINDS = ["pose", "bars", "range", "compare", "checklist", "steps"]
MUSCLES = ["quads", "glutes", "hams", "calves", "back", "abs", "traps"]
TARGETS = ["bar", "head", "shoulder", "chest", "back", "belly", "hip", "knee", "foot", "heel", "toe"]
PRESETS = {
    # голень вперёд, бедро от вертикали, наклон корпуса (None — подобрать по балансу), штанга, руки
    "stand": (3, 2, 3, False, "down"),
    "stand_bar": (4, 3, None, True, "down"),
    "squat_mid": (24, 52, None, True, "down"),
    "squat_bottom": (33, 96, None, True, "down"),
    "bodyweight_squat": (30, 90, 40, False, "forward"),
    "hinge": (6, 12, 72, False, "down"),
}

FIGURE_SCHEMA = {
    "type": "object",
    "properties": {
        "figures": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "heading": {"type": "string", "description": "текст подзаголовка из статьи, точно как в ней, без ##"},
                "kind": {"type": "string", "enum": KINDS},
                "title": {"type": "string", "description": "заголовок картинки, до 40 символов; для pose пусто"},
                "caption": {"type": "string", "description": "подпись под картинкой, одно предложение"},
                "unit": {"type": "string", "description": "единица для bars и range, например «подходов в неделю»"},
                "source": {"type": "string", "description": "откуда цифры (автор и год), для bars и range"},
                "items": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "value": {"type": "number"},
                        "value2": {"type": "number"},
                        "note": {"type": "string"},
                    },
                    "required": ["label", "value", "value2", "note"], "additionalProperties": False}},
                "pose": {
                    "type": "object",
                    "properties": {
                        "preset": {"type": "string", "enum": list(PRESETS)},
                        "ghost": {"type": "string", "enum": ["none"] + list(PRESETS)},
                        "highlight": {"type": "array", "items": {"type": "string", "enum": MUSCLES}},
                        "guide": {"type": "string", "enum": ["none", "bar_over_midfoot", "toe_line"]},
                        "labels": {"type": "array", "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "sub": {"type": "string"},
                                "target": {"type": "string", "enum": TARGETS},
                            },
                            "required": ["title", "sub", "target"], "additionalProperties": False}},
                    },
                    "required": ["preset", "ghost", "highlight", "guide", "labels"], "additionalProperties": False},
            },
            "required": ["heading", "kind", "title", "caption", "unit", "source", "items", "pose"],
            "additionalProperties": False}},
    },
    "required": ["figures"],
    "additionalProperties": False,
}

PROMPT = """Ниже статья для сайта тренера. Подбери SVG-картинку к КАЖДОМУ подзаголовку (## и ###) из списка.

Виды картинок:
- pose — скелет с мышцами сбоку в позе (preset): stand, stand_bar (со штангой на спине), squat_mid, squat_bottom,
  bodyweight_squat (присед без веса), hinge (наклон с прямой спиной). highlight — какие мышцы работают
  (quads — квадрицепс, glutes — ягодичные, hams — задняя поверхность бедра, calves — икры, back — разгибатели спины,
  abs — пресс, traps — трапеции и верх спины). labels — 1–3 выноски: title до 22 символов, sub до 26 символов,
  target — к какой точке тела. ghost — полупрозрачная вторая поза, чтобы показать движение. guide — линия-ориентир.
  Бери pose, только если раздел про технику, положение тела или работу мышц и одна из поз подходит.
- bars — сравнение чисел из текста: items[].label (до 30 символов), value — число, note — как подписать число
  («65 мм рт. ст.»). 2–6 строк. Заполни unit и source.
- range — диапазоны: items[].label, value — от, value2 — до, note — подпись («10–20»). Заполни unit и source.
- compare — 2–3 варианта рядом: items[].label — название варианта, note — 2–4 коротких пункта через «|».
- checklist — что делать и чего не делать: items[].label до 45 символов, value 1 — правильно, 0 — ошибка. 3–6 строк.
- steps — последовательность: items[].label до 30 символов, note — пояснение до 50 символов. 3–6 шагов.

Правила:
- Цифры только из текста статьи, ничего не придумывать. Нет цифр в разделе — не bars и не range.
- Подписи по-русски, коротко, на «ты», без призывов и обещаний вылечить.
- Чередуй виды, не делай подряд три одинаковых.
- Неиспользуемые поля: пустые строки, value и value2 = 0, items = [], для pose вне pose:
  preset stand, ghost none, highlight [], guide none, labels [].
- heading пиши точно как в статье.

Подзаголовки:
{headings}

Статья:
{body}"""


def headings(body):
    return [m.group(2).strip() for m in re.finditer(r"^(#{2,3})\s+(.+?)\s*$", body, flags=re.M)]


def plan(client, meter, create, model, body, todo):
    msg = create(client, model, max_tokens=16000,
                 output_config={"effort": "medium", "format": {"type": "json_schema", "schema": FIGURE_SCHEMA}},
                 messages=[{"role": "user", "content": PROMPT.format(
                     headings="\n".join(f"- {h}" for h in todo), body=body)}])
    meter.add(msg.usage, model)
    text = next(b.text for b in msg.content if b.type == "text")
    return json.loads(text)["figures"]


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
    return lines or [""]


def text(x, y, s, cls="s", anchor="start"):
    return f'<text class="{cls}" x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}">{K.esc(s)}</text>'


def header(f):
    out, y = [], 44
    for line in wrap(f["title"], 44)[:2]:
        out.append(text(32, y, line, "t"))
        y += 28
    return "".join(out), y + 6


def footer(f, y):
    src = f.get("source", "").strip()
    return (text(32, y + 8, f"Источник: {src}", "s small") if src else ""), y + (34 if src else 10)


def fmt(v):
    return f"{v:g}".replace(".", ",")


def draw_bars(f):
    items = [i for i in f["items"] if i["label"]][:6]
    head, y = header(f)
    top = max(i["value"] for i in items) or 1
    out = [head]
    x0, x1 = 32, 520
    for i in items:
        out.append(text(x0, y + 4, wrap(i["label"], 48)[0]))
        w = max(4, (x1 - x0) * i["value"] / top)
        out.append(f'<rect class="barfill" x="{x0}" y="{y + 14}" width="{w:.0f}" height="22" rx="4"/>')
        out.append(text(x0 + w + 10, y + 32, i["note"] or fmt(i["value"]), "t"))
        y += 66
    if f.get("unit"):
        out.append(text(x0, y + 2, f["unit"], "s small"))
        y += 26
    foot, y = footer(f, y)
    return "".join(out) + foot, y + 10


def draw_range(f):
    items = [i for i in f["items"] if i["label"]][:6]
    head, y = header(f)
    lo = min(min(i["value"], i["value2"]) for i in items)
    hi = max(max(i["value"], i["value2"]) for i in items)
    lo = 0 if lo >= 0 and lo < hi * 0.5 else lo
    span = (hi - lo) or 1
    x0, x1 = 32, 600
    X = lambda v: x0 + (x1 - x0) * (v - lo) / span  # noqa: E731
    out = [head]
    for i in items:
        a, b = sorted((i["value"], i["value2"]))
        out.append(text(x0, y + 4, wrap(i["label"], 52)[0]))
        out.append(f'<line class="track" x1="{x0}" y1="{y + 26}" x2="{x1}" y2="{y + 26}"/>')
        out.append(f'<rect class="barfill" x="{X(a):.0f}" y="{y + 16}" width="{max(8, X(b) - X(a)):.0f}" height="20" rx="10"/>')
        note = i["note"] or (f"{fmt(a)}–{fmt(b)}" if a != b else fmt(a))
        anchor = "end" if X(b) > x1 - 90 else "start"
        tx = X(a) - 10 if anchor == "end" else X(b) + 10
        out.append(text(tx, y + 32, note, "t", anchor))
        y += 66
    out.append(text(x0, y + 4, fmt(lo), "s small"))
    out.append(text(x1, y + 4, fmt(hi), "s small", "end"))
    if f.get("unit"):
        out.append(text((x0 + x1) / 2, y + 4, f["unit"], "s small", "middle"))
    foot, y = footer(f, y + 24)
    return "".join(out) + foot, y + 10


def draw_compare(f):
    items = [i for i in f["items"] if i["label"]][:3]
    head, y = header(f)
    n = len(items)
    gap = 16
    cw = (640 - 64 - gap * (n - 1)) / n
    # ширина символа: заголовок ~13 px, подпись ~10.5 px
    head_chars = int((cw - 32) / 13)
    note_chars = int((cw - 48) / 10.5)
    cols, hmax = [], 0
    for k, i in enumerate(items):
        x = 32 + k * (cw + gap)
        body, yy = [], y + 34
        # длинное слово не влезает в колонку — уменьшаем шрифт заголовка
        longest = max(len(w) for w in str(i["label"]).split() or [""])
        size = max(15, min(21, int((cw - 32) / max(longest, 1) / 0.58)))
        for line in wrap(i["label"], max(head_chars, longest)):
            body.append(text(x + 16, yy, line, "t").replace("<text ", f'<text style="font-size:{size}px" ', 1))
            yy += 26
        yy += 6
        for point in [p.strip() for p in i["note"].split("|") if p.strip()][:4]:
            lines = wrap(point, note_chars)
            body.append(f'<circle class="dot" cx="{x + 20:.0f}" cy="{yy - 6:.0f}" r="4"/>')
            for line in lines:
                body.append(text(x + 32, yy, line))
                yy += 22
            yy += 8
        cols.append((x, body))
        hmax = max(hmax, yy - y)
    out = [head]
    for x, body in cols:
        out.append(f'<rect class="card" x="{x:.0f}" y="{y}" width="{cw:.0f}" height="{hmax:.0f}" rx="12"/>')
        out += body
    return "".join(out), y + hmax + 24


def draw_checklist(f):
    items = [i for i in f["items"] if i["label"]][:6]
    head, y = header(f)
    out = [head]
    for i in items:
        ok = i["value"] >= 0.5
        out.append(f'<circle class="{"okc" if ok else "badc"}" cx="48" cy="{y + 10}" r="15"/>')
        mark = (f'<path class="mark" d="M41 {y + 10}l5 5 9 -10"/>' if ok else
                f'<path class="mark" d="M42 {y + 4}l12 12M54 {y + 4}l-12 12"/>')
        out.append(mark)
        lines = wrap(i["label"], 46)
        for k, line in enumerate(lines[:2]):
            out.append(text(76, y + 17 + k * 24, line, "t" if k == 0 else "s"))
        y += 30 + 24 * min(len(lines), 2)
    return "".join(out), y + 14


def draw_steps(f):
    items = [i for i in f["items"] if i["label"]][:6]
    head, y = header(f)
    out = [head]
    for k, i in enumerate(items, 1):
        out.append(f'<circle class="num" cx="50" cy="{y + 12}" r="18"/>')
        out.append(text(50, y + 19, str(k), "numt", "middle"))
        out.append(text(84, y + 12, wrap(i["label"], 44)[0], "t"))
        lines = wrap(i["note"], 52)[:2] if i["note"] else []
        for j, line in enumerate(lines):
            out.append(text(84, y + 38 + j * 22, line))
        if k < len(items):
            out.append(f'<line class="track" x1="50" y1="{y + 34}" x2="50" y2="{y + 52 + 22 * len(lines)}"/>')
        y += 56 + 22 * len(lines)
    return "".join(out), y + 6


def target_point(P, name):
    T = K.frame(P["hip"], P["top"])
    pts = {
        "bar": P["bar"] or T(1.03, -10.5), "head": T(1.3, -3.5), "shoulder": P["joint"], "chest": T(0.7, 5),
        "back": T(0.6, -10), "belly": T(0.3, 6), "hip": P["hip"], "knee": P["knee"],
        "foot": ((P["heel"][0] + P["toe"][0]) / 2, 2), "heel": P["heel"], "toe": P["toe"],
    }
    return K.scr(pts[name])


def make_pose(name):
    sh, th, torso, bar, arms = PRESETS[name]
    return K.pose(sh, th, torso=torso, bar=bar, arms=arms)


def draw_pose(f):
    p = f["pose"]
    P = make_pose(p["preset"])
    out = [K.ground()]
    if p["ghost"] != "none" and p["ghost"] != p["preset"]:
        out.append(K.figure(make_pose(p["ghost"]), ghost=True))
    out.append(K.figure(P, on=set(p["highlight"])))
    if p["guide"] == "bar_over_midfoot" and P["bar"]:
        x = K.scr(P["bar"])[0]
        out.append(f'<line class="guide" x1="{x:.0f}" y1="40" x2="{x:.0f}" y2="{K.OY:.0f}"/>')
    elif p["guide"] == "toe_line":
        x = K.scr(P["toe"])[0]
        out.append(f'<line class="guide" x1="{x:.0f}" y1="{K.OY - 160:.0f}" x2="{x:.0f}" y2="{K.OY:.0f}"/>')
    labels = p["labels"][:3]
    for k, lb in enumerate(labels):
        y = 70 + k * (300 / max(len(labels), 1))
        out.append(K.label(380, y, lb["title"][:26], wrap(lb["sub"], 26)[:2] if lb["sub"] else None,
                           to=target_point(P, lb["target"])))
    return "".join(out), K.H


DRAW = {"pose": draw_pose, "bars": draw_bars, "range": draw_range, "compare": draw_compare,
        "checklist": draw_checklist, "steps": draw_steps}

EXTRA_STYLE = """<style>
.small{font-size:15px}
.barfill{fill:#d2491d}.track{stroke:#d9d5ca;stroke-width:3}
.card{fill:#f3f1ea;stroke:#e2ded2}.dot{fill:#d2491d}
.okc{fill:#2e8b57}.badc{fill:#c0392b}.mark{stroke:#fff;stroke-width:3.5;fill:none;stroke-linecap:round}
.num{fill:#d2491d}.numt{font:700 18px system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;fill:#fff}
@media (prefers-color-scheme:dark){.barfill,.dot,.num{fill:#f0703f}.track{stroke:#3a3934}.card{fill:#26262a;stroke:#34343a}}
</style>"""


def render(f, path):
    body, h = DRAW[f["kind"]](f)
    alt = f["caption"] or f["title"] or f["heading"]
    K.svg(path, alt, EXTRA_STYLE + body, h=int(h))
    return alt


def usable(f):
    if f["kind"] == "pose":
        return f["pose"]["preset"] in PRESETS
    items = [i for i in f["items"] if i["label"]]
    if f["kind"] in ("bars", "range"):
        return len(items) >= 2 and any(i["value"] or i["value2"] for i in items)
    return len(items) >= 2


def insert(body, heading, html):
    """Ставит картинку сразу под подзаголовком; если там уже есть картинка — не трогает."""
    pat = re.compile(r"^(#{2,3})\s+" + re.escape(heading) + r"\s*$", re.M)
    m = pat.search(body)
    if not m:
        return body, False
    rest = body[m.end():].lstrip("\n")
    if rest.startswith("<figure"):
        return body, False
    return body[:m.end()] + "\n\n" + html + "\n\n" + rest, True


def missing(body):
    """Подзаголовки, под которыми ещё нет картинки."""
    out = []
    for m in re.finditer(r"^(#{2,3})\s+(.+?)\s*$", body, flags=re.M):
        if not body[m.end():].lstrip("\n").startswith("<figure"):
            out.append(m.group(2).strip())
    return out


ANGLE_KEYS = ["torso", "thigh", "shank", "foot", "upper", "fore", "thigh2", "shank2", "foot2", "upper2", "fore2"]
POSE_ANGLES = {"type": "object", "properties": {k: {"type": "number"} for k in ANGLE_KEYS},
               "required": ANGLE_KEYS, "additionalProperties": False}
POINTS = ["none", "head", "hip", "knee", "heel", "toe", "hand", "hand2", "heel2"]

MOVES_SCHEMA = {
    "type": "object",
    "properties": {
        "moves": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "after": {"type": "string", "description": "точный кусок текста статьи (20–60 символов) из абзаца или пункта, где описано упражнение"},
                "exercise": {"type": "string", "enum": list(M.EXERCISES) + ["custom"]},
                "title": {"type": "string", "description": "название упражнения, до 34 символов"},
                "cues": {"type": "array", "items": {"type": "string"}, "description": "1–2 подсказки по технике, каждая до 60 символов"},
                "highlight": {"type": "array", "items": {"type": "string", "enum": M.MUSCLES}},
                "verdict": {"type": "string", "enum": ["none", "ok", "bad"]},
                "custom": {"type": "object", "properties": {
                    "has_start": {"type": "boolean"}, "start": POSE_ANGLES, "end": POSE_ANGLES,
                    "arrow": {"type": "string", "enum": POINTS}},
                    "required": ["has_start", "start", "end", "arrow"], "additionalProperties": False},
            },
            "required": ["after", "exercise", "title", "cues", "highlight", "verdict", "custom"],
            "additionalProperties": False}},
    },
    "required": ["moves"],
    "additionalProperties": False,
}

MOVES_PROMPT = """Ниже статья для сайта тренера. Найди в ней КАЖДОЕ упражнение или движение, техника которого
описана (поза, как двигаться, на что смотреть), и подбери к нему схему: скелет с мышцами, вид сбоку,
начальная поза бледно, конечная ярко, рабочие мышцы подсвечены. Одно упражнение — одна схема.
Не нужно: голые названия упражнений в списке программы без описания техники, упражнения в тренажёре или
со скамьёй (снаряды не рисуются), просто упоминания вида спорта («кардио», «ходьба»), бытовые советы.
Упражнение из списка «пока не делай» можно дать с verdict bad, одно на статью.
Если упражнений с описанием техники нет — верни пустой список.

Готовые упражнения (exercise):
- breathing — лёжа на спине, ноги согнуты, выдох и подтягивание живота (поперечная мышца)
- heel_slide — скольжение пятки: из положения лёжа с согнутыми ногами выпрямляешь ногу по полу
- leg_lower — лёжа, ноги согнуты «столиком», поочерёдно опускаешь стопу к полу
- head_lift — короткий подъём головы и плеч лёжа (малая амплитуда)
- self_test — лёжа, голова и плечи приподняты, пальцы на животе (самопроверка диастаза)
- full_crunch — полное скручивание до сидя
- glute_bridge — ягодичный мостик
- dead_bug_legs — «мёртвый жук»: лёжа, одна нога из «столика» выпрямляется вперёд
- bird_dog — «птица-собака»: на четвереньках вытягиваешь противоположные руку и ногу
- plank — планка на предплечьях
- side_plank_knees — боковая планка с колен (рисуется видом спереди)
- custom — любое другое упражнение без снаряда: задай углы сегментов сам.

Углы для custom: градусы от вертикали «вверх», положительные — по часовой, человек смотрит вправо.
0 — вверх, 90 — вправо (вперёд), 180 — вниз, -90 — влево (назад). torso — от таза к плечам, thigh — от таза
к колену, shank — от колена к стопе, foot — поворот стопы (0 стоит на полу, -90 носок вверх, 90 носок вниз),
upper — от плеча к локтю, fore — от локтя к кисти. С цифрой 2 — дальняя нога и рука (если двигаются так же,
повтори те же числа). Поза сама встаёт на пол.
Примеры: стойка torso 0, thigh 180, shank 180, foot 0, upper 180, fore 180; присед без веса torso 40, thigh 92,
shank 150, foot 0, upper 90, fore 90; наклон с прямой спиной torso 75, thigh 172, shank 176, foot 0, upper 180,
fore 180; выпад вперёд torso 0, thigh 100, shank 165, thigh2 200, shank2 260, foot2 60; лёжа на спине —
torso -90, на животе и на четвереньках — torso 90.
has_start false — только одна поза. arrow — какая точка движется сильнее всего.
Для готовых упражнений custom заполни нулями, has_start false, arrow none.

Правила:
- after — точная цитата из статьи, из того абзаца или пункта списка, где упражнение описано. Не из подзаголовка.
- title — название упражнения по-русски; cues — 1–2 подсказки из текста статьи, коротко, на «ты».
- highlight — какие мышцы работают в упражнении (если пусто, возьмутся мышцы по умолчанию).
- verdict: bad — упражнение из списка «пока не делай», ok — правильный вариант рядом с ошибкой, иначе none.
- Без призывов и медицинских обещаний.

Статья:
{body}"""


def plan_moves(client, meter, create, model, body):
    msg = create(client, model, max_tokens=12000,
                 output_config={"effort": "medium", "format": {"type": "json_schema", "schema": MOVES_SCHEMA}},
                 messages=[{"role": "user", "content": MOVES_PROMPT.format(body=body)}])
    meter.add(msg.usage, model)
    text = next(b.text for b in msg.content if b.type == "text")
    return json.loads(text)["moves"]


def has_moves(body):
    return 'class="step move"' in body


def render_move(m, path):
    body, h = M.draw_exercise(m)
    alt = m["title"] + (": " + m["cues"][0] if m.get("cues") else "")
    K.svg(path, alt, body, h=int(h))
    return alt


def insert_after(body, quote, html):
    """Ставит схему после абзаца или всего списка, где встретилась цитата."""
    i = body.find(quote.strip())
    if i < 0 or not quote.strip():
        return body, False
    end = body.find("\n\n", i)
    end = len(body) if end < 0 else end
    # уже вставленные схемы этого блока идут подряд — новую ставим после них
    while body.startswith("\n\n<figure", end):
        nxt = body.find("\n\n", end + 2)
        end = len(body) if nxt < 0 else nxt
    return body[:end] + "\n\n" + html + body[end:], True


def add_moves(client, meter, create, model, body, img_dir, url_prefix):
    """Схемы ко всем описанным упражнениям. Возвращает (новый текст, сколько добавлено)."""
    if has_moves(body):
        return body, 0
    return place_moves(plan_moves(client, meter, create, model, body), body, img_dir, url_prefix)


def place_moves(items, body, img_dir, url_prefix):
    n = 0
    for k, m in enumerate(items, 1):
        if m["exercise"] == "custom":
            c = m["custom"]
            m = dict(m, exercise="custom", start=c["start"] if c["has_start"] else None, end=c["end"],
                     arrow=c["arrow"])
        name = f"move-{k:02d}.svg"
        try:
            alt = render_move(m, img_dir / name)
        except Exception as e:  # одна кривая схема не должна ронять статью
            print(f"Схема «{m['title']}» не получилась: {e}")
            continue
        # подписи нет: название и подсказки уже на самой схеме
        html = (f'<figure class="step move"><img src="{url_prefix}/{name}" alt="{K.esc(alt)}" width="640" '
                f'loading="lazy"></figure>')
        body, ok = insert_after(body, m["after"], html)
        n += ok
    return body, n


def add(client, meter, create, model, body, slug, img_dir, url_prefix):
    """Схемы к упражнениям и картинки ко всем подзаголовкам без картинки. Возвращает (новый текст, сколько добавлено)."""
    body, n_moves = add_moves(client, meter, create, model, body, img_dir, url_prefix)
    todo = missing(body)
    if not todo:
        return body, n_moves
    figs = plan(client, meter, create, model, body, todo)
    n = 0
    # при повторном запуске номера продолжаются, чтобы не затереть старые картинки
    used = [int(p.name[:2]) for p in img_dir.glob("[0-9][0-9]-*.svg")] if img_dir.exists() else []
    start = max(used, default=0)
    for k, f in enumerate(figs, start + 1):
        if f["heading"] not in todo or not usable(f):
            continue
        name = f"{k:02d}-{f['kind']}.svg"
        try:
            alt = render(f, img_dir / name)
        except Exception as e:  # одна кривая картинка не должна ронять статью
            print(f"Картинка к «{f['heading']}» не получилась: {e}")
            continue
        cap = K.esc(f["caption"] or alt)
        html = (f'<figure class="step"><img src="{url_prefix}/{name}" alt="{K.esc(alt)}" width="640" '
                f'loading="lazy"><figcaption>{cap}</figcaption></figure>')
        body, ok = insert(body, f["heading"], html)
        if ok:
            todo.remove(f["heading"])
            n += 1
    return body, n + n_moves
