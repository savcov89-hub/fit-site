"""Пишет одну SEO-статью по следующей теме из agent/topics.csv.

Шаг 1: Claude ищет источники в интернете (web search) и собирает выжимку фактов.
Шаг 2: Claude пишет статью по выжимке и правилам из agent/style.md, ответ — строгий JSON.
Статья сохраняется в content/articles/<slug>.md, тема помечается done,
расход пишется в agent/usage.csv.

Запуск: ANTHROPIC_API_KEY=... python3 agent/write_article.py [--topic "запрос"]
Переменные: MODEL (по умолчанию claude-opus-5-5), MONTH_LIMIT_USD (по умолчанию 25).
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import urllib.parse
import urllib.request

import anthropic

ROOT = Path(__file__).resolve().parent.parent
AGENT = ROOT / "agent"
ARTICLES = ROOT / "content" / "articles"
TOPICS = AGENT / "topics.csv"
USAGE = AGENT / "usage.csv"
PHOTOS = ROOT / "content" / "photos"
STOCK_DIR = ROOT / "static" / "img"

MODEL = os.environ.get("MODEL", "claude-opus-5-5")
MONTH_LIMIT_USD = float(os.environ.get("MONTH_LIMIT_USD", "25"))
BETAS = ["server-side-fallback-2026-07-01"]

# $ за 1 млн токенов (вход, выход) и за 1000 поисков
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}
SEARCH_PER_1000 = 10.0

TRANSLIT = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p",
                     "r", "s", "t", "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))

ARTICLE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "H1 статьи, содержит главный запрос"},
        "seo_title": {"type": "string", "description": "title страницы, до 65 символов"},
        "description": {"type": "string", "description": "meta description, 120–160 символов"},
        "slug": {"type": "string", "description": "адрес латиницей через дефис, 3–6 слов"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "body_markdown": {"type": "string",
                          "description": "текст статьи в Markdown без H1, разделы с ## и ###"},
        "faq": {"type": "array", "items": {
            "type": "object",
            "properties": {"q": {"type": "string"}, "a": {"type": "string"}},
            "required": ["q", "a"], "additionalProperties": False}},
        "sources": {"type": "array", "items": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "url": {"type": "string"}},
            "required": ["title", "url"], "additionalProperties": False}},
        "cover": {
            "type": "object",
            "description": "обложка статьи",
            "properties": {
                "own_photo": {"type": "string",
                              "description": "имя файла из списка фото Михаила или пустая строка, если ни одно не подходит"},
                "stock_query": {"type": "string",
                                "description": "запрос на английском для фотостока, 2–4 слова, если своё фото не подошло"},
                "alt": {"type": "string", "description": "описание картинки на русском для alt"},
            },
            "required": ["own_photo", "stock_query", "alt"], "additionalProperties": False},
    },
    "required": ["title", "seo_title", "description", "slug", "tags", "body_markdown", "faq", "sources",
                 "cover"],
    "additionalProperties": False,
}


def slugify(text):
    s = "".join(TRANSLIT.get(c, c) for c in text.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:70].rstrip("-") or "statya"


def read_topics():
    with TOPICS.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_topics(rows):
    with TOPICS.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["keyword", "status", "slug"])
        w.writeheader()
        w.writerows(rows)


def month_spend():
    if not USAGE.exists():
        return 0.0
    month = dt.date.today().strftime("%Y-%m")
    with USAGE.open(encoding="utf-8") as f:
        return sum(float(r["usd"]) for r in csv.DictReader(f) if r["date"].startswith(month))


def log_usage(keyword, usd, tokens_in, tokens_out, searches):
    new = not USAGE.exists()
    with USAGE.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "keyword", "model", "tokens_in", "tokens_out", "searches", "usd"])
        w.writerow([dt.date.today().isoformat(), keyword, MODEL, tokens_in, tokens_out, searches,
                    f"{usd:.4f}"])


class Meter:
    def __init__(self):
        self.tin = self.tout = self.searches = 0

    def add(self, usage):
        self.tin += (usage.input_tokens or 0) + (usage.cache_read_input_tokens or 0) \
            + (usage.cache_creation_input_tokens or 0)
        self.tout += usage.output_tokens or 0
        stu = getattr(usage, "server_tool_use", None)
        if stu is not None:
            self.searches += getattr(stu, "web_search_requests", 0) or 0

    def usd(self):
        pin, pout = PRICES.get(MODEL, PRICES["claude-opus-5-5"])
        return self.tin / 1e6 * pin + self.tout / 1e6 * pout + self.searches / 1000 * SEARCH_PER_1000


def check_stop(msg, step):
    if msg.stop_reason == "refusal":
        sys.exit(f"{step}: модель отказалась отвечать ({getattr(msg, "stop_details", None)}). Тему стоит заменить.")
    if msg.stop_reason == "max_tokens":
        sys.exit(f"{step}: ответ обрезан по max_tokens.")


def research(client, meter, keyword):
    prompt = (
        f"Поисковый запрос читателя: «{keyword}».\n\n"
        "Найди в интернете надёжные источники по этому вопросу: систематические обзоры, мета-анализы, "
        "исследования (PubMed, journals), позиции профессиональных организаций (ACSM, ISSN, NSCA, ВОЗ), "
        "материалы признанных специалистов (Stronger By Science, Jeff Nippard, Mike Israetel / RP). "
        "Посмотри и выдачу на русском: какие подвопросы люди задают по этой теме.\n\n"
        "Верни выжимку на русском:\n"
        "1. Короткий ответ на запрос.\n"
        "2. Ключевые факты и цифры, у каждого — ссылка на источник (URL) и сила доказательств.\n"
        "3. Где данные спорные или их мало.\n"
        "4. Подвопросы читателей, которые стоит раскрыть, и 3–5 вопросов для блока FAQ.\n"
        "5. Список источников: название и URL.\n"
        "Ничего не выдумывай: если факт не нашёлся в источнике, не включай его."
    )
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 8}]
    for _ in range(5):
        with client.beta.messages.stream(
            model=MODEL, max_tokens=32000, betas=BETAS, fallbacks="default",
            output_config={"effort": "medium"}, tools=tools, messages=messages,
        ) as stream:
            msg = stream.get_final_message()
        meter.add(msg.usage)
        check_stop(msg, "Поиск")
        if msg.stop_reason != "pause_turn":
            return "\n".join(b.text for b in msg.content if b.type == "text")
        messages = [messages[0], {"role": "assistant", "content": msg.content}]
    sys.exit("Поиск: слишком много пауз, попробуйте позже.")


def write(client, meter, keyword, notes, existing, photos):
    style = (AGENT / "style.md").read_text(encoding="utf-8")
    links = "\n".join(f"- {a['title']}: /stati/{a['slug']}/" for a in existing) or "(пока статей нет)"
    photo_list = "\n".join(f"- {p['file']}: {p['description']}" for p in photos) or "(пока фото нет)"
    system = (
        "Ты пишешь статьи для личного сайта персонального тренера Михаила Савцова. "
        "Статья выходит от его имени. Следуй правилам ниже строго.\n\n" + style
    )
    user = (
        f"Главный поисковый запрос: «{keyword}».\n\n"
        f"Выжимка исследования (используй только эти факты и источники):\n{notes}\n\n"
        f"Статьи сайта, на которые можно поставить внутренние ссылки (2–3, только по теме):\n{links}\n\n"
        "Фото Михаила (его тренировки и клиенты в зале), можно взять на обложку и вставить в текст "
        "через ![описание](/photos/<файл>), только если фото действительно по теме:\n"
        f"{photo_list}\n\n"
        "Напиши статью. В body_markdown не ставь H1 и не дублируй FAQ и список источников: "
        "они выводятся отдельно. В sources — только реально использованные источники из выжимки."
    )
    with client.beta.messages.stream(
        model=MODEL, max_tokens=64000, betas=BETAS, fallbacks="default",
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": ARTICLE_SCHEMA}},
        system=system, messages=[{"role": "user", "content": user}],
    ) as stream:
        msg = stream.get_final_message()
    meter.add(msg.usage)
    check_stop(msg, "Статья")
    text = next(b.text for b in msg.content if b.type == "text")
    return json.loads(text)


def own_photos():
    """Фото Михаила: content/photos/photos.csv (file,description)."""
    index = PHOTOS / "photos.csv"
    if not index.exists():
        return []
    with index.open(encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if (PHOTOS / r["file"]).exists()]


def stock_photo(query, slug):
    """Ищет фото на Pexels (нужен PEXELS_API_KEY), сохраняет в static/img/<slug>.jpg."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key or not query:
        return None
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": query, "per_page": 5, "orientation": "landscape"})
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "fit-site-agent"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            photos = json.load(r).get("photos", [])
        if not photos:
            return None
        p = photos[0]
        STOCK_DIR.mkdir(parents=True, exist_ok=True)
        out = STOCK_DIR / f"{slug}.jpg"
        img = urllib.request.Request(p["src"]["large"], headers={"User-Agent": "fit-site-agent"})
        with urllib.request.urlopen(img, timeout=60) as r:
            out.write_bytes(r.read())
    except Exception as e:  # без обложки статья всё равно выйдет
        print(f"Фотосток: не получилось ({e})")
        return None
    return {"image": f"/img/{slug}.jpg",
            "image_credit": f"Фото: {p['photographer']}, Pexels",
            "image_credit_url": p["url"]}


def existing_articles():
    items = []
    for f in sorted(ARTICLES.glob("*.md")):
        head = f.read_text(encoding="utf-8").split("\n---\n", 1)[0].removeprefix("---\n")
        try:
            meta = json.loads(head)
        except json.JSONDecodeError:
            continue
        items.append({"title": meta.get("title", f.stem), "slug": meta.get("slug", f.stem)})
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", help="написать по этому запросу вместо следующего из topics.csv")
    args = ap.parse_args()

    spent = month_spend()
    if spent >= MONTH_LIMIT_USD:
        sys.exit(f"Лимит месяца исчерпан: потрачено ${spent:.2f} из ${MONTH_LIMIT_USD:.2f}.")

    rows = read_topics()
    if args.topic:
        keyword = args.topic.strip()
        row = next((r for r in rows if r["keyword"] == keyword), None)
        if row is None:
            row = {"keyword": keyword, "status": "todo", "slug": ""}
            rows.append(row)
    else:
        row = next((r for r in rows if r["status"] == "todo"), None)
        if row is None:
            sys.exit("В agent/topics.csv не осталось тем со статусом todo.")
        keyword = row["keyword"]

    client = anthropic.Anthropic()
    meter = Meter()
    existing = existing_articles()
    print(f"Тема: {keyword}")
    notes = research(client, meter, keyword)
    photos = own_photos()
    art = write(client, meter, keyword, notes, existing, photos)

    slug = slugify(art["slug"]) if re.fullmatch(r"[a-z0-9-]+", art["slug"] or "") is None else art["slug"]
    taken = {a["slug"] for a in existing}
    base, n = slug, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1

    meta = {
        "title": art["title"],
        "seo_title": art["seo_title"],
        "description": art["description"],
        "slug": slug,
        "date": dt.date.today().isoformat(),
        "keyword": keyword,
        "tags": art["tags"],
        "faq": art["faq"],
        "sources": art["sources"],
    }
    cover = art["cover"]
    own = {p["file"] for p in photos}
    if cover["own_photo"] in own:
        meta["image"] = f"/photos/{cover['own_photo']}"
    else:
        meta.update(stock_photo(cover["stock_query"], slug) or {})
    if "image" in meta:
        meta["image_alt"] = cover["alt"]

    ARTICLES.mkdir(parents=True, exist_ok=True)
    out = ARTICLES / f"{slug}.md"
    out.write_text("---\n" + json.dumps(meta, ensure_ascii=False, indent=2) + "\n---\n"
                   + art["body_markdown"].strip() + "\n", encoding="utf-8")

    row["status"], row["slug"] = "done", slug
    write_topics(rows)
    usd = meter.usd()
    log_usage(keyword, usd, meter.tin, meter.tout, meter.searches)

    words = len(art["body_markdown"].split())
    print(f"Статья: {out.relative_to(ROOT)} ({words} слов), стоимость ${usd:.3f}, "
          f"за месяц ${spent + usd:.2f} из ${MONTH_LIMIT_USD:.2f}")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"slug={slug}\ntitle={art['title']}\nusd={usd:.3f}\nwords={words}\n")


if __name__ == "__main__":
    main()
