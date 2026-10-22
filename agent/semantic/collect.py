"""Собирает поисковые подсказки Яндекса (регион Новосибирск) и Google по затравкам из seeds.txt.

Строки seeds.txt: «*» в начале — затравку ещё расширяем буквами алфавита («запрос а», «запрос б»...).
Результат: agent/semantic/suggest_raw.csv (seed, source, suggestion).
Запуск: python3 agent/semantic/collect.py (нужен интернет без ограничений, например в GitHub Actions)
"""
import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEEDS = HERE / "seeds.txt"
OUT = HERE / "suggest_raw.csv"
NSK = 65  # регион Новосибирск в Яндексе
ALPHABET = "абвгдежзиклмнопрстуфхцчшэя"
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        raw = r.read()
    for enc in ("utf-8", "cp1251"):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    return None


def yandex(q):
    url = "https://suggest.yandex.ru/suggest-ff.cgi?" + urllib.parse.urlencode(
        {"part": q, "lr": NSK, "uil": "ru"})
    data = get_json(url)
    return [s for s in (data[1] if data and len(data) > 1 else []) if isinstance(s, str)]


def google(q):
    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(
        {"client": "firefox", "hl": "ru", "gl": "ru", "q": q})
    data = get_json(url)
    return [s for s in (data[1] if data and len(data) > 1 else []) if isinstance(s, str)]


def main():
    rows, seen = [], set()
    queries = []
    for line in SEEDS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        expand = line.startswith("*")
        seed = line.lstrip("* ").strip()
        queries.append((seed, seed))
        if expand:
            queries += [(seed, f"{seed} {ch}") for ch in ALPHABET]
    for seed, q in queries:
        for name, fn in (("yandex", yandex), ("google", google)):
            try:
                found = fn(q)
            except Exception as e:  # сеть, лимит, формат
                print(f"! {name} {q}: {e}")
                found = []
            for s in found:
                key = (name, s.lower())
                if key not in seen:
                    seen.add(key)
                    rows.append({"seed": seed, "source": name, "suggestion": s.lower()})
            time.sleep(0.25)
        print(f"{q}: всего {len(rows)}")
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["seed", "source", "suggestion"])
        w.writeheader()
        w.writerows(rows)
    print(f"Готово: {len(rows)} подсказок → {OUT}")


if __name__ == "__main__":
    main()
