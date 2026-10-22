"""SEO-проверка статьи: правила agent/seo.md, которые можно проверить кодом.

check(art, keyword, existing) возвращает список проблем.
check_and_fix(...) один раз просит модель поправить метаданные и запретные фразы,
затем проверяет заново и возвращает статью и отчёт в Markdown для PR.
"""
import json
import re

FORBIDDEN = [
    # закон о рекламе и медицина
    "запишись", "записывайся", "приходи", "купи", "закажи", "пиши в директ", "подпишись",
    "вылечит", "вылечить", "избавит от боли", "гарантир", "старший тренер",
    # штампы нейросети и фитнеса
    "важно понимать", "стоит отметить", "ключевой момент", "давайте разберёмся", "давайте разберемся",
    "в современном мире", "тело мечты", "лучшая версия себя", "зона комфорта", "жиросжигающ",
    "проработать мышцы", "индивидуальный подход",
]
WEAK_SOURCE = re.compile(r"shop|store|market|ozon|wildberries|aliexpress|apteka|lookgreatnaked", re.I)
SCIENCE = re.compile(r"pubmed|ncbi|doi\.org|springer|wiley|frontiersin|bmj|jamanetwork|sciencedirect|"
                     r"journals\.|mdpi|lww|tandfonline|nature\.com|thelancet|who\.int|acsm|nsca|jissn|"
                     r"cochrane", re.I)

FIX_SCHEMA = {
    "type": "object",
    "properties": {
        "seo_title": {"type": "string"},
        "description": {"type": "string"},
        "replacements": {"type": "array", "items": {
            "type": "object",
            "properties": {"old": {"type": "string"}, "new": {"type": "string"}},
            "required": ["old", "new"], "additionalProperties": False}},
    },
    "required": ["seo_title", "description", "replacements"],
    "additionalProperties": False,
}


def stems(keyword):
    """Основы значимых слов запроса: первые 5 букв слов длиннее 3 символов."""
    return [w[:5] for w in re.findall(r"[а-яёa-z]+", keyword.lower()) if len(w) > 3]


def covers(text, keyword):
    words = stems(keyword)
    low = text.lower()
    hit = sum(1 for s in words if s in low)
    return not words or hit >= max(1, round(len(words) * 0.6))


def check(art, keyword, existing):
    """Возвращает (ошибки, замечания). Ошибки правим, замечания показываем человеку."""
    errors, notes = [], []
    body = art["body_markdown"]
    text_all = " ".join([art["title"], art["description"], body] + [q["q"] + " " + q["a"] for q in art["faq"]])

    n = len(art["seo_title"])
    if not 30 <= n <= 65:
        errors.append(f"seo_title {n} символов, нужно 40–65")
    n = len(art["description"])
    if not 110 <= n <= 165:
        errors.append(f"description {n} символов, нужно 120–160")
    for phrase in FORBIDDEN:
        if phrase in text_all.lower():
            errors.append(f"запретная фраза «{phrase}»")

    if not covers(art["title"], keyword):
        notes.append("главного запроса нет в H1")
    if not covers(art["seo_title"], keyword):
        notes.append("главного запроса нет в title")
    first = body.strip().split("\n\n", 1)[0]
    if not covers(first, keyword):
        notes.append("главного запроса нет в первом абзаце")
    h2 = len(re.findall(r"^## ", body, re.M))
    if not 4 <= h2 <= 10:
        notes.append(f"разделов H2: {h2}, лучше 4–8")
    words = len(body.split())
    if not 1000 <= words <= 3000:
        notes.append(f"объём {words} слов, ориентир 1200–2500")
    if len(art["faq"]) < 3:
        notes.append("в FAQ меньше 3 вопросов")
    links = len(re.findall(r"\]\(/stati/", body))
    if existing and links == 0:
        notes.append("нет внутренних ссылок на другие статьи")
    sources = art["sources"]
    sci = sum(1 for s in sources if SCIENCE.search(s["url"]))
    if len(sources) < 3:
        notes.append(f"источников {len(sources)}, нужно от 3")
    if sources and sci == 0:
        notes.append("нет ни одного научного источника")
    weak = [s["url"] for s in sources if WEAK_SOURCE.search(s["url"])]
    if weak:
        notes.append("слабые источники: " + ", ".join(weak))
    return errors, notes, {"h2": h2, "words": words, "internal_links": links,
                           "sources": len(sources), "science_sources": sci}


def check_and_fix(client, meter, create, model, art, keyword, existing):
    errors, notes, stats = check(art, keyword, existing)
    fixed = []
    if errors:
        prompt = (
            f"Главный запрос статьи: «{keyword}».\n"
            f"Текущий seo_title: {art['seo_title']}\n"
            f"Текущий description: {art['description']}\n"
            f"Проблемы: {'; '.join(errors)}.\n\n"
            "Исправь: seo_title 40–65 символов с главным запросом в начале; description 120–160 "
            "символов, суть и польза без призывов. Для каждой запретной фразы дай замену: old — "
            "точный фрагмент из текста ниже (с окружающими словами, чтобы он был уникален), new — "
            "та же мысль без запретной фразы. Если seo_title или description в порядке, верни их "
            "без изменений.\n\nТекст статьи:\n" + art["body_markdown"]
            + "\n\nFAQ:\n" + json.dumps(art["faq"], ensure_ascii=False)
        )
        msg = create(client, model, max_tokens=8000,
                     output_config={"effort": "low", "format": {"type": "json_schema", "schema": FIX_SCHEMA}},
                     messages=[{"role": "user", "content": prompt}])
        meter.add(msg.usage, model)
        if msg.stop_reason not in ("refusal", "max_tokens"):
            fix = json.loads(next(b.text for b in msg.content if b.type == "text"))
            art["seo_title"], art["description"] = fix["seo_title"], fix["description"]
            for r in fix["replacements"]:
                if r["old"] and r["old"] in art["body_markdown"]:
                    art["body_markdown"] = art["body_markdown"].replace(r["old"], r["new"], 1)
                    fixed.append(f"«{r['old'][:60]}» → «{r['new'][:60]}»")
                else:
                    for q in art["faq"]:
                        if r["old"] and r["old"] in q["a"]:
                            q["a"] = q["a"].replace(r["old"], r["new"], 1)
                            fixed.append(f"FAQ: «{r['old'][:60]}» → «{r['new'][:60]}»")
            errors, notes, stats = check(art, keyword, existing)

    lines = ["**SEO-проверка**",
             f"- title: {len(art['seo_title'])} симв., description: {len(art['description'])} симв.",
             f"- разделов H2: {stats['h2']}, слов: {stats['words']}, внутренних ссылок: "
             f"{stats['internal_links']}, источников: {stats['sources']} (научных {stats['science_sources']})"]
    if fixed:
        lines.append("- исправлено автоматически: " + "; ".join(fixed))
    problems = errors + notes
    lines.append("- замечания: " + ("; ".join(problems) if problems else "нет"))
    return art, "\n".join(lines)
