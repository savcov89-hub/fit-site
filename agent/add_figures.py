"""Дорисовывает SVG-картинки к уже вышедшим статьям: под каждый подзаголовок без картинки.

python3 agent/add_figures.py                 # все статьи, где не хватает картинок
python3 agent/add_figures.py --slug <slug>   # одна статья
"""
import argparse
import json
import sys

import anthropic

import figures
import write_article as W


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", help="только эта статья")
    args = ap.parse_args()

    spent = W.month_spend()
    if spent >= W.MONTH_LIMIT_USD:
        sys.exit(f"Лимит месяца исчерпан: потрачено ${spent:.2f} из ${W.MONTH_LIMIT_USD:.2f}.")

    files = [W.ARTICLES / f"{args.slug}.md"] if args.slug else sorted(W.ARTICLES.glob("*.md"))
    client = anthropic.Anthropic()
    for path in files:
        raw = path.read_text(encoding="utf-8")
        head, body = raw.split("\n---\n", 1)
        meta = json.loads(head.removeprefix("---\n"))
        slug = meta.get("slug", path.stem)
        if not figures.missing(body):
            continue
        meter = W.Meter()
        body, n = figures.add(client, meter, W.create, W.MODEL, body, slug,
                              W.ROOT / "static" / "img" / slug, f"/img/{slug}")
        path.write_text(head + "\n---\n" + body.strip() + "\n", encoding="utf-8")
        usd = meter.usd()
        W.log_usage(f"картинки: {meta.get('keyword', slug)}", usd, meter.tin, meter.tout, 0, model=W.MODEL)
        print(f"{slug}: картинок +{n}, ${usd:.3f}")


if __name__ == "__main__":
    main()
