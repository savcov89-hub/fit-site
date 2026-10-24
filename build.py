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
PORTRAIT = SITE.get("portrait", "")

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


def portrait(cls, width, height, eager=False, small=False):
    """Портрет Михаила: webp с запасным jpg; small — квадрат с лицом (файл <имя>-face)."""
    if not PORTRAIT:
        return ""
    stem = PORTRAIT.rsplit(".", 1)[0] + ("-face" if small else "")
    loading = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (f'<picture class="{cls}"><source srcset="{esc(stem)}.webp" type="image/webp">'
            f'<img src="{esc(stem)}.jpg" alt="{esc(SITE["author"])}, {esc(SITE["author_role"])}" '
            f'width="{width}" height="{height}" {loading} decoding="async"></picture>')


def logo_mark():
    """Значок у имени в шапке и подвале: фото лица, без портрета — буквы МС."""
    if not PORTRAIT:
        return '<span class="mark">МС</span>'
    stem = PORTRAIT.rsplit(".", 1)[0] + "-face"
    return (f'<picture class="mark mark-photo"><source srcset="{esc(stem)}.webp" type="image/webp">'
            f'<img src="{esc(stem)}.jpg" alt="" width="80" height="80" decoding="async"></picture>')


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
            f'ym({mid},"init",{{clickmap:true,trackLinks:true,accurateTrackBounce:true,webvisor:true}});</script>'
        )
    if SITE.get("google_analytics_id"):
        gid = esc(SITE["google_analytics_id"])
        metrika += (f'<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>'
                    '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}'
                    f'gtag("js",new Date());gtag("config","{gid}");</script>')
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
<meta name="theme-color" content="#121214" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#f6f5f1" media="(prefers-color-scheme: light)">
<link rel="preload" href="/fonts/montserrat-cyrillic.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/style.css">
<script>document.documentElement.classList.add("js")</script>
{verif}{extra}{metrika}
</head>
<body>
<header class="top"><div class="wrap">
<a class="logo" href="/" aria-label="{esc(SITE["author"])}, на главную">{logo_mark()}<span class="logo-name">{esc(SITE["author"])}</span></a>
<nav><a href="/#obo-mne">Обо мне</a><a href="/#uslugi">Тренировки</a><a href="/stati/">Статьи</a><a class="nav-cta" href="/#kontakty">Контакты</a></nav>
</div></header>
<main>
"""


def foot():
    year = dt.date.today().year
    insta = ""
    if not placeholder(SITE.get("instagram")):
        insta = f'<a href="{esc(SITE["instagram"])}" rel="noopener">Instagram* @fitness_savtsov</a>'
    return f"""</main>
<footer class="bottom"><div class="wrap">
<div class="foot-brand">{logo_mark()}<div><b>{esc(SITE["author"])}</b><br>{esc(SITE["author_role"].capitalize())}, {esc(SITE["club"])}, {esc(SITE["city"])}</div></div>
<nav class="foot-nav"><a href="/#obo-mne">Обо мне</a><a href="/#uslugi">Тренировки</a><a href="/stati/">Статьи</a><a href="/#kontakty">Контакты</a>{insta}</nav>
<p class="muted">© {year} {esc(SITE["author"])}. Статьи на сайте не заменяют консультацию врача. Если что-то болит вне зала, сначала к врачу.{META_NOTE if insta else ""}</p>
</div></footer>
<script>
document.addEventListener("click",function(e){{var a=e.target.closest&&e.target.closest("[data-goal]");if(!a)return;var g=a.getAttribute("data-goal");
if(window.ym){{ym({esc(SITE.get("yandex_metrika_id") or 0)},"reachGoal",g)}}if(window.gtag){{gtag("event",g,{{link_url:a.href}})}}}});
(function(){{var els=document.querySelectorAll(".reveal");if(!("IntersectionObserver" in window)){{els.forEach(function(e){{e.classList.add("in")}});return}}
var io=new IntersectionObserver(function(es){{es.forEach(function(e){{if(e.isIntersecting){{e.target.classList.add("in");io.unobserve(e.target)}}}})}},{{rootMargin:"0px 0px -8% 0px"}});
els.forEach(function(e){{io.observe(e)}})}})();
</script>
</body>
</html>
"""


META_NOTE = " *Instagram принадлежит компании Meta, признанной в России экстремистской и запрещённой."


def contacts_html():
    rows = []
    if not placeholder(SITE.get("phone")):
        rows.append(("Телефон", f'<a data-goal="click_phone" href="tel:{esc(re.sub(r"[^+0-9]", "", SITE["phone"]))}">{esc(SITE["phone"])}</a>'))
    if not placeholder(SITE.get("instagram")):
        rows.append(("Instagram*", f'<a href="{esc(SITE["instagram"])}" rel="noopener">@fitness_savtsov</a>'))
    place = SITE["club"]
    if not placeholder(SITE.get("address")):
        place += f", {SITE['address']}"
    rows.append(("Где тренирую", f"{esc(place)}, {esc(SITE['city'])}"))
    if SITE.get("club_hours"):
        rows.append(("Клуб работает", esc(SITE["club_hours"])))
    if SITE.get("club_phone"):
        rows.append(("Ресепшн клуба", f'<a href="tel:{esc(re.sub(r"[^+0-9]", "", SITE["club_phone"]))}">{esc(SITE["club_phone"])}</a>'))
    if SITE.get("club_url"):
        rows.append(("Страница клуба", f'<a href="{esc(SITE["club_url"])}" rel="noopener">hammer-fit.ru/kontinent</a>'))
    return "<ul class=\"contacts\">" + "".join(
        f"<li><span class=\"label\">{label}</span><span>{value}</span></li>" for label, value in rows
    ) + "</ul>"


def messengers_html():
    """Кнопки связи: звонок и мессенджеры. Пустые и [заглушки] пропускаются."""
    links = []
    if not placeholder(SITE.get("phone")):
        links.append(("btn-primary", f'tel:{re.sub(r"[^+0-9]", "", SITE["phone"])}', "Позвонить", "click_phone"))
    # WhatsApp последним: с февраля 2026 в России открывается в основном через VPN
    for key, name in (("telegram", "Telegram"), ("max", "Max"), ("whatsapp", "WhatsApp")):
        if not placeholder(SITE.get(key)):
            links.append(("btn-ghost", SITE[key], name, f"click_{key}"))
    if not links:
        return ""
    return '<div class="actions messengers">' + "".join(
        f'<a class="btn {cls}" href="{esc(url)}" data-goal="{goal}"{"" if url.startswith("tel:") else " rel=\"noopener\""}>{label}</a>'
        for cls, url, label, goal in links
    ) + "</div>"


def reviews_html():
    """Отзывы клиентов из site.json (reviews: name, text, необязательно goal). Пусто — блока нет."""
    items = [r for r in SITE.get("reviews", []) if r.get("text") and not placeholder(r["text"])]
    if not items:
        return ""
    cards = "".join(
        f'<li class="review reveal"><p>{esc(r["text"])}</p>'
        f'<span class="review-who"><b>{esc(r.get("name", ""))}</b>'
        f'{" · " + esc(r["goal"]) if r.get("goal") else ""}</span></li>'
        for r in items
    )
    return (f'<section class="block reviews" id="otzyvy"><div class="wrap"><h2>Отзывы</h2>'
            f'<ul class="review-list">{cards}</ul></div></section>')


def cta_html():
    """Блок связи в конце статьи: где тренирую и кнопки мессенджеров."""
    buttons = messengers_html()
    if not buttons:
        return ""
    return (f'<aside class="cta-box"><p class="cta-title">Разберём на тренировке</p>'
            f'<p>Тренирую в {esc(SITE["club"])}, {esc(SITE["city"])}. Если хотите поставить технику '
            f'или собрать программу под свою цель, напишите или позвоните.</p>{buttons}</aside>')


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
    body = re.sub(r"<table>", '<div class="table"><table>', body).replace("</table>", "</table></div>")
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
        rel_html = "<section class=\"related\"><h2>Ещё по теме</h2>" + article_list(related[:4]) + "</section>"
    cover = ""
    if a.get("image"):
        credit = ""
        if a.get("image_credit"):
            credit = f'<figcaption><a href="{esc(a.get("image_credit_url", "#"))}" rel="nofollow noopener" target="_blank">{esc(a["image_credit"])}</a></figcaption>'
        cover = f'<figure class="cover"><img src="{esc(a["image"])}" alt="{esc(a.get("image_alt", a["title"]))}" width="1200" height="800">{credit}</figure>'
    words = len(a["body"].split())
    minutes = max(1, round(words / 180))
    page = head(a.get("seo_title", a["title"]), a["description"], path, article_jsonld(a, BASE + path),
                a.get("image"))
    page += f"""<article class="post wrap narrow">
<p class="crumbs"><a href="/">Главная</a><span>/</span><a href="/stati/">Статьи</a></p>
<h1>{esc(a["title"])}</h1>
<div class="byline">{portrait("avatar", 240, 240, small=True)}<div><b>{esc(SITE["author"])}</b><br><span class="muted">{esc(SITE["author_role"].capitalize())} · {ru_date(a["date"])} · {minutes} мин чтения</span></div></div>
{cover}
<div class="prose">
{body}
</div>
{faq}
{sources}
{cta_html()}
<aside class="author-box">{portrait("avatar", 240, 240, small=True)}<p><b>{esc(SITE["author"])}</b> — {esc(SITE["author_role"])} в {esc(SITE["club"])}, {esc(SITE["city"])}. {esc(". ".join(SITE.get("credentials", [])))}. <a href="/#obo-mne">Подробнее об авторе</a></p></aside>
{rel_html}
</article>
"""
    page += foot()
    out = OUT / "stati" / a["slug"] / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return path


def article_list(items):
    return "<ul class=\"cards\">" + "".join(
        f'<li class="card reveal"><a href="/stati/{esc(a["slug"])}/">'
        f'<span class="card-date">{ru_date(a["date"])}</span>'
        f'<span class="card-title">{esc(a["title"])}</span>'
        f'<span class="card-text">{esc(a["description"])}</span>'
        f'<span class="card-more">Читать →</span></a></li>'
        for a in items
    ) + "</ul>"


def home_sections(html_text):
    """Делит home.md по заголовкам H2 на отдельные секции главной."""
    parts = re.split(r"(?=<h2)", html_text)
    out = []
    for part in parts:
        if not part.strip():
            continue
        m = re.match(r'<h2(?: id="([^"]+)")?>', part)
        sid = m.group(1) if m else ""
        cls = {"uslugi": "services", "obo-mne": "about"}.get(sid, "plain")
        if sid:
            part = part.replace(f' id="{sid}"', "", 1)
        id_attr = f' id="{sid}"' if sid else ""
        out.append(f'<section class="block {cls}"{id_attr}><div class="wrap">{part}</div></section>')
    return "\n".join(out)


def render_index(items):
    about = ""
    about_file = CONTENT / "pages" / "home.md"
    if about_file.exists():
        about = home_sections(markdown.markdown(about_file.read_text(encoding="utf-8"), extensions=["extra"]))
    person = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": SITE["author"],
        "jobTitle": SITE["author_role"],
        "url": BASE + "/",
        **({"image": BASE + PORTRAIT} if PORTRAIT else {}),
        **({"telephone": SITE["phone"]} if not placeholder(SITE.get("phone")) else {}),
        "address": {"@type": "PostalAddress", "addressLocality": SITE["city"], "addressCountry": "RU"},
        "sameAs": [u for u in (SITE.get("instagram"), SITE.get("club_trainer_url")) if not placeholder(u)],
        "hasCredential": SITE.get("credentials", []),
        "alumniOf": "Новосибирский государственный педагогический университет",
    }
    extra = f'<script type="application/ld+json">{json.dumps(person, ensure_ascii=False)}</script>'
    title = f"{SITE['author']} — {SITE['author_role']} в {SITE['city']}е"
    first, last = SITE["author"].split(" ", 1)
    stats = "".join(
        f'<li class="stat reveal"><b>{esc(s["value"])}</b><span>{esc(s["label"])}</span></li>'
        for s in SITE.get("stats", [])
    )
    articles = ""
    if items:
        articles = (f'<section class="block" id="stati"><div class="wrap"><div class="block-head">'
                    f'<h2>Новые статьи</h2><a class="link-more" href="/stati/">Все статьи →</a></div>'
                    f'{article_list(items[:6])}</div></section>')
    page = head(title, SITE["tagline"], "/", extra, PORTRAIT or None)
    page += f"""<section class="hero"><div class="wrap hero-grid">
<div class="hero-text">
<p class="kicker">{esc(SITE["author_role"].capitalize())} · {esc(SITE["city"])}</p>
<h1><span>{esc(first)}</span> <span class="accent">{esc(last)}</span></h1>
<p class="lead">{esc(SITE["tagline"])}</p>
<p class="club">{esc(SITE["club"])}</p>
<div class="actions"><a class="btn btn-primary" href="/#kontakty">Записаться на тренировку</a><a class="btn btn-ghost" href="/stati/">Читать статьи</a></div>
</div>
<div class="hero-photo">
{portrait("photo", 960, 1280, eager=True)}
<span class="sticker">Мастер спорта России</span>
</div>
</div>
{f'<div class="wrap"><ul class="stats">{stats}</ul></div>' if stats else ""}
</section>
{about}
{reviews_html()}
<section class="block contacts-block" id="kontakty"><div class="wrap">
<h2>Контакты</h2>
{messengers_html()}
{contacts_html()}
</div></section>
{articles}
"""
    page += foot()
    (OUT / "index.html").write_text(page, encoding="utf-8")


def render_list(items):
    page = head(f"Статьи о тренировках и питании — {SITE['author']}",
                "Статьи о силовых тренировках, технике упражнений и питании на основе исследований.",
                "/stati/")
    empty = '<p class="muted">Статьи скоро появятся.</p>' if not items else ""
    page += (f'<section class="block page-head"><div class="wrap"><p class="kicker">Блог тренера</p>'
             f'<h1>Статьи</h1><p class="lead">Силовые тренировки, техника упражнений и питание. '
             f'Каждая статья опирается на исследования, ссылки в конце.</p>'
             f'{article_list(items)}{empty}</div></section>')
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
    page += ('<section class="block page-head"><div class="wrap"><p class="kicker">Ошибка 404</p>'
             '<h1>Такой страницы нет</h1><p><a class="btn btn-primary" href="/stati/">Все статьи</a></p>'
             '</div></section>')
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
