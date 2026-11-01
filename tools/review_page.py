"""Страница проверки схем для Михаила (Artifact): галерея, фильтр по статусу, «Верно» / «Нужна правка» и замечание.

python3 tools/review_page.py OUT.html  — собирает страницу из exercises/exercises.csv.
Отметки хранятся в базе страницы (коллекция reviews), Claude переносит их в exercises.csv.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))
import exlib  # noqa: E402
import moves as M  # noqa: E402

rows = [dict(id=r["id"], name=r["name"], section=r["section"], status=r["status"], comment=r["comment"],
             muscles=", ".join(M.RU.get(m, m) for m in r["muscles"].split())) for r in exlib.manifest()]
html = (Path(__file__).with_name("review_template.html").read_text(encoding="utf-8")
        .replace("/*DATA*/[]", json.dumps(rows, ensure_ascii=False)))
Path(sys.argv[1]).write_text(html, encoding="utf-8")
print(f"Упражнений на странице: {len(rows)}")
