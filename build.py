"""Собирает статичный сайт из content/ в public/.

Запуск: python3 build.py
Cloudflare Pages: Build command `pip install -r requirements.txt && python3 build.py`,
Build output directory `public`.
"""
import datetime as dt
import html
import json
import re
import shutil
from pathlib import Path

import markdown

ROOT = Path(__file__).parent
CONTENT = ROOT / "content"
OUT = ROOT / "public"
SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
BASE = SITE["base_url"].rstrip("/")

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
          "августа", "сентября", "октября", "ноября", "декабря"]


def parse_front_matter(text):
    """Front matter — JSON между строками '---' в начале файла."""
    if not text.startswith("---\n"):
        return {}, text
    head, body = text[4:].split("\n---\n", 1)
    return json.loads(head), body


def ru_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def esc(s):
    return html.escape(str(s), quote=True)


def placeholder(value):
    return not value or value.startswith("[")


def head(title, description, path, extra="", image=None):
    verif = ""
    if SITE.get("yandex_verification"):
        verif += f'<meta name="yandex-verification" content="{esc(SITE["yandex_verification"])}">'
    if SITE.get("google_verification"):
        verif += f'<meta name="google-site-verification" content="{esc(SITE["google_verification"])}">'
    metrika = ""
    if SITE.get("yandex_metrika_id"):
        mid = esc(SITE["yandex_metrika_id"])
        metrika = (
            '<script>(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};'
            'm[i].l=1*new Date();k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,'
            'a.parentNode.insertBefore(k,a)})(window,document,"script","https://mc.yandex.ru/metrika/tag.js","ym");'
            f'ym({mid},"init",{{clickmap:true,trackLinks:true,accurateTrackBounce:true}});</script>'
        )
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{BASE}{path}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{BASE}{path}">
<meta property="og:locale" content="ru_RU">
{f'<meta property="og:image" content="{BASE}{esc(image)}">' if image else ""}
<link rel="stylesheet" href="/style.css">
{verif}{extra}{metrika}
</head>
<body>
<header class="top"><div class="wrap">
<a class="logo" href="/">{esc(SITE["author"])}</a>
<nav><a href="/stati/">Статьи</a><a href="/#uslugi">Тренировки</a><a href="/#kontakty">Контакты</a></nav>
</div></header>
<main class="wrap">
"""


def foot():
    year = dt.date.today().year
    return f"""</main>
<footer class="bottom"><div class="wrap">
<p>© {year} {esc(SITE["author"])}, {esc(SITE["author_role"])}, {esc(SITE["city"])}.</p>
<p class="muted">Статьи на сайте не заменяют консультацию врача. Если что-то болит вне зала, сначала к врачу.</p>
</div></footer>
</body>
</html>
"""


def contacts_html():
    rows = []
    if not placeholder(SITE.get("telegram")):
        rows.append(f'<li>Telegram: <a href="{esc(SITE["telegram"])}">{esc(SITE["telegram"])}</a></li>')
    if not placeholder(SITE.get("phone")):
        rows.append(f'<li>Телефон: <a href="tel:{esc(re.sub(r"[^+0-9]", "", SITE["phone"]))}">{esc(SITE["phone"])}</a></li>')
    if not placeholder(SITE.get("instagram")):
        rows.append(f'<li>Instagram: <a href="{esc(SITE["instagram"])}">@fitness_savtsov</a></li>')
    place = SITE["club"]
    if not placeholder(SITE.get("address")):
        place += f", {SITE['address']}"
    rows.append(f"<li>Где тренирую: {esc(place)}, {esc(SITE['city'])}</li>")
    if SITE.get("club_hours"):
        rows.append(f"<li>Клуб работает: {esc(SITE['club_hours'])}</li>")
    if SITE.get("club_phone"):
        rows.append(f'<li>Ресепшн клуба: <a href="tel:{esc(re.sub(r"[^+0-9]", "", SITE["club_phone"]))}">{esc(SITE["club_phone"])}</a></li>')
    if SITE.get("club_url"):
        rows.append(f'<li>Страница клуба: <a href="{esc(SITE["club_url"])}" rel="noopener">{esc(SITE["club_url"])}</a></li>')
    return "<ul class=\"contacts\">" + "".join(rows) + "</ul>"


def load_articles():
    items = []
    for f in sorted((CONTENT / "articles").glob("*.md")):
        meta, body = parse_front_matter(f.read_text(encoding="utf-8"))
        if meta.get("draft"):
            continue
        meta.setdefault("slug", f.stem)
        meta["body"] = body
        items.append(meta)
    items.sort(key=lambda a: a["date"], reverse=True)
    return items


def article_jsonld(a, url):
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": a["title"],
        "description": a["description"],
        "datePublished": a["date"],
        "dateModified": a.get("updated", a["date"]),
        "inLanguage": "ru",
        "mainEntityOfPage": url,
        **({"image": BASE + a["image"]} if a.get("image") else {}),
        "author": {"@type": "Person", "name": SITE["author"], "jobTitle": SITE["author_role"],
                   "url": BASE + "/"},
    }
    blocks = [f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>']
    if a.get("faq"):
        faq = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q["q"],
                            "acceptedAnswer": {"@type": "Answer", "text": q["a"]}} for q in a["faq"]],
        }
        blocks.append(f'<script type="application/ld+json">{json.dumps(faq, ensure_ascii=False)}</script>')
    return "".join(blocks)


def render_article(a, all_articles):
    path = f"/stati/{a['slug']}/"
    md = markdown.Markdown(extensions=["extra", "sane_lists", "toc"])
    body = md.convert(a["body"])
    faq = ""
    if a.get("faq"):
        faq = "<section class=\"faq\"><h2>Частые вопросы</h2>" + "".join(
            f"<details><summary>{esc(q['q'])}</summary><p>{esc(q['a'])}</p></details>" for q in a["faq"]
        ) + "</section>"
    sources = ""
    if a.get("sources"):
        sources = "<section class=\"sources\"><h2>Источники</h2><ol>" + "".join(
            f'<li><a href="{esc(s["url"])}" rel="nofollow noopener" target="_blank">{esc(s["title"])}</a></li>'
            for s in a["sources"]
        ) + "</ol></section>"
    related = [x for x in all_articles if x["slug"] != a["slug"]]
    tags = set(a.get("tags", []))
    related.sort(key=lambda x: -len(tags & set(x.get("tags", []))))
    rel_html = ""
    if related:
        rel_html = "<section class=\"related\"><h2>Ещё по теме</h2><ul>" + "".join(
            f'<li><a href="/stati/{esc(x["slug"])}/">{esc(x["title"])}</a></li>' for x in related[:4]
        ) + "</ul></section>"
    cover = ""
    if a.get("image"):
        credit = ""
        if a.get("image_credit"):
            credit = f'<figcaption><a href="{esc(a.get("image_credit_url", "#"))}" rel="nofollow noopener" target="_blank">{esc(a["image_credit"])}</a></figcaption>'
        cover = f'<figure class="cover"><img src="{esc(a["image"])}" alt="{esc(a.get("image_alt", a["title"]))}" width="1200" height="800">{credit}</figure>'
    page = head(a.get("seo_title", a["title"]), a["description"], path, article_jsonld(a, BASE + path),
                a.get("image"))
    page += f"""<article class="post">
<p class="crumbs"><a href="/">Главная</a> / <a href="/stati/">Статьи</a></p>
<h1>{esc(a["title"])}</h1>
<p class="meta">{esc(SITE["author"])}, {esc(SITE["author_role"])} · {ru_date(a["date"])}</p>
{cover}
{body}
{faq}
{sources}
<aside class="author-box"><p><b>{esc(SITE["author"])}</b> — {esc(SITE["author_role"])} в {esc(SITE["club"])}, {esc(SITE["city"])}. {esc(". ".join(SITE.get("credentials", [])))}. <a href="/#obo-mne">Подробнее об авторе</a></p></aside>
{rel_html}
</article>
"""
    page += foot()
    out = OUT / "stati" / a["slug"] / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return path


def article_list(items):
    return "<ul class=\"list\">" + "".join(
        f'<li><a href="/stati/{esc(a["slug"])}/">{esc(a["title"])}</a>'
        f'<p>{esc(a["description"])}</p><span class="muted">{ru_date(a["date"])}</span></li>'
        for a in items
    ) + "</ul>"


def render_index(items):
    about = ""
    about_file = CONTENT / "pages" / "home.md"
    if about_file.exists():
        about = markdown.markdown(about_file.read_text(encoding="utf-8"), extensions=["extra"])
    person = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": SITE["author"],
        "jobTitle": SITE["author_role"],
        "url": BASE + "/",
        "address": {"@type": "PostalAddress", "addressLocality": SITE["city"], "addressCountry": "RU"},
        "sameAs": [u for u in (SITE.get("instagram"), SITE.get("club_trainer_url")) if not placeholder(u)],
        "hasCredential": SITE.get("credentials", []),
        "alumniOf": "Новосибирский государственный педагогический университет",
    }
    extra = f'<script type="application/ld+json">{json.dumps(person, ensure_ascii=False)}</script>'
    title = f"{SITE['author']} — {SITE['author_role']} в {SITE['city']}е"
    page = head(title, SITE["tagline"], "/", extra)
    page += f"""<section class="hero">
<h1>{esc(SITE["author"])}</h1>
<p class="lead">{esc(SITE["author_role"].capitalize())}, {esc(SITE["club"])}, {esc(SITE["city"])}.</p>
<p>{esc(SITE["tagline"])}</p>
</section>
{about}
<section id="kontakty"><h2>Контакты</h2>{contacts_html()}</section>
<section><h2>Новые статьи</h2>{article_list(items[:6])}<p><a href="/stati/">Все статьи</a></p></section>
"""
    page += foot()
    (OUT / "index.html").write_text(page, encoding="utf-8")


def render_list(items):
    page = head(f"Статьи о тренировках и питании — {SITE['author']}",
                "Статьи о силовых тренировках, технике упражнений и питании на основе исследований.",
                "/stati/")
    page += f"<h1>Статьи</h1>{article_list(items)}"
    page += foot()
    (OUT / "stati").mkdir(parents=True, exist_ok=True)
    (OUT / "stati" / "index.html").write_text(page, encoding="utf-8")


def render_sitemap(paths):
    today = dt.date.today().isoformat()
    urls = "".join(f"<url><loc>{BASE}{p}</loc><lastmod>{d or today}</lastmod></url>" for p, d in paths)
    (OUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n',
        encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n",
                                    encoding="utf-8")


def render_404():
    page = head("Страница не найдена", "Такой страницы нет.", "/404.html")
    page += '<h1>Такой страницы нет</h1><p><a href="/stati/">Все статьи</a></p>'
    page += foot()
    (OUT / "404.html").write_text(page, encoding="utf-8")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "static", OUT)
    photos = CONTENT / "photos"
    if photos.exists():
        shutil.copytree(photos, OUT / "photos", ignore=shutil.ignore_patterns("*.csv", "*.md"))
    items = load_articles()
    paths = [("/", None), ("/stati/", None)]
    for a in items:
        paths.append((render_article(a, items), a.get("updated", a["date"])))
    render_index(items)
    render_list(items)
    render_404()
    render_sitemap(paths)
    print(f"Готово: {len(items)} статей в {OUT}")


if __name__ == "__main__":
    main()
