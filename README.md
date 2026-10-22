# Сайт Михаила Савцова и SEO-агент статей

Статичный сайт (главная, статьи, карта сайта, разметка для поисковиков) и агент, который раз в день пишет статью через Claude API и отдаёт её на проверку.

## Как это работает

1. Каждый день в 10:00 по Новосибирску GitHub Actions (`.github/workflows/article.yml`) берёт следующую тему со статусом `todo` из `agent/topics.csv`.
2. Дешёвая модель (`RESEARCH_MODEL`, Haiku) ищет источники в интернете (обзоры, мета-анализы, исследования, ACSM, ISSN и т.п.) и собирает выжимку фактов со ссылками. Связанные запросы из колонки `related` в `topics.csv` подсказывают, какие подвопросы раскрыть.
3. Основная модель (`MODEL`, Opus) пишет статью по выжимке и правилам `agent/style.md` (инфостиль, словарь Михаила, без призывов и медицинских обещаний) и `agent/seo.md`.
4. `agent/seo.py` проверяет длину title и description, запретные фразы, главный запрос в H1 и первом абзаце, разделы, объём, ссылки и качество источников. Ошибки правит один короткий вызов модели, замечания попадают в описание PR.
5. Статья приходит запросом на слияние (Pull Request) `Статья: …`. Cloudflare Pages сам добавляет ссылку на превью.
6. Нажали **Merge** — статья на сайте через минуту. **Close** — статья не выходит.

Расход пишется в `agent/usage.csv`. Агент останавливается, если за месяц потрачено больше `MONTH_LIMIT_USD` (по умолчанию $25).

## Что нужно один раз

1. **Cloudflare.** dash.cloudflare.com → Workers & Pages → Create → Import a repository → `fit-site`.
   Имя проекта: `fit-site` (должно совпадать с `name` в `wrangler.jsonc`). Build command: `pip install -r requirements.txt && python3 build.py`. Deploy command: `npx wrangler deploy` (по умолчанию). Сайт раздаётся из `public/` по настройкам `wrangler.jsonc`.
   Адрес вида `fit-site.<аккаунт>.workers.dev` записать в `site.json` → `base_url`. Свой домен: проект → Settings → Domains & Routes.
1а. **Yandex Object Storage (основной хостинг для России).** Cloudflare часть российских провайдеров режет, поэтому сайт выкладывается в бакет Яндекса workflow `deploy` (после каждого пуша в main и после автопубликации статьи).
   - console.yandex.cloud → Object Storage → Создать бакет. Имя бакета = домен (`example.ru`), доступ на чтение объектов — публичный. В бакете: Веб-сайт → Хостинг, главная страница `index.html`, страница ошибки `404.html`.
   - Сервисный аккаунт с ролью `storage.editor` → Создать статический ключ доступа. ID ключа → секрет `YC_ACCESS_KEY_ID`, секретный ключ → секрет `YC_SECRET_ACCESS_KEY`, имя бакета → переменная `YC_BUCKET`.
   - Домен: у регистратора DNS-серверы `ns1.yandexcloud.net` и `ns2.yandexcloud.net`; в Cloud DNS зона домена и запись ANAME на `<бакет>.website.yandexcloud.net`. HTTPS: Certificate Manager → сертификат Let's Encrypt → привязать к бакету (Безопасность → HTTPS).
   - В `site.json` → `base_url` поставить `https://<домен>`.
2. **Ключ Claude API.** platform.claude.com → API Keys → Create key. Положить в GitHub: Settings → Secrets and variables → Actions → New repository secret, имя `ANTHROPIC_API_KEY`. В консоли Anthropic стоит поставить лимит расходов: Settings → Limits.
3. **Разрешить агенту создавать запросы на проверку.** Settings → Actions → General → Workflow permissions → Read and write permissions и галочка «Allow GitHub Actions to create and approve pull requests».
4. **Поисковики.** Яндекс Вебмастер и Google Search Console: добавить сайт, код подтверждения вписать в `site.json` (`yandex_verification`, `google_verification`), затем отправить `https://<адрес>/sitemap.xml`. Яндекс Метрика — номер счётчика в `yandex_metrika_id`.

## Фото в статьях

1. **Свои фото — лучший вариант**: и для доверия, и для поиска по картинкам. Кладите их в `content/photos/` и описывайте одной строкой в `content/photos/photos.csv` (подробно в `content/photos/README.md`). Подойдут стоп-кадры из Reels. Агент сам выбирает фото по теме для обложки и для текста.
2. **Бесплатный фотосток Pexels**: включается, если своего фото по теме нет. Ключ бесплатный: pexels.com/api → Get Started. Положите его в секрет `PEXELS_API_KEY`. Под фото агент указывает автора.

## Настройки (Settings → Secrets and variables → Actions → Variables)

| Переменная | Что делает | По умолчанию |
|---|---|---|
| `MODEL` | модель, которая пишет текст: `claude-opus-5-5` (лучше текст) или `claude-sonnet-5-5` (дешевле примерно вдвое) | `claude-opus-5-5` |
| `RESEARCH_MODEL` | модель для поиска источников | `claude-haiku-5-5` |
| `MONTH_LIMIT_USD` | потолок расходов в месяц | `25` |
| `AUTO_PUBLISH` | `true` — публиковать без проверки | проверка включена |
| `YC_BUCKET` | имя бакета Yandex Object Storage; пусто — выкладка в Яндекс выключена | пусто |

## Темы

`agent/topics.csv`: одна строка — один поисковый запрос. Колонки: `keyword`, `status` (todo/done), `slug`, `cluster`, `related` (связанные подсказки через `|`). Порядок строк — очередь. Лучше брать запросы из Яндекс Wordstat (wordstat.yandex.ru): реальные формулировки людей, с частотой от 50–100 показов в месяц.
Написать статью прямо сейчас или по своей теме: Actions → write-article → Run workflow → поле «Запрос».

## Править руками

- Главная: `content/pages/home.md` и `site.json`.
- Статья: `content/articles/<slug>.md`. Сверху JSON с заголовком, описанием, FAQ и источниками, ниже текст в Markdown. Скрыть статью: `"draft": true`.
- Проверить сборку локально: `pip install -r requirements.txt && python3 build.py`, сайт появится в `public/`.

## Сколько стоит

Первая статья, где и поиск, и текст делал Opus, стоила $2,52: при поиске модель прочитала почти 500 тысяч токенов страниц. Теперь поиск делает Haiku, и ожидаемая цена статьи около $0,5–0,8. Точные цифры — в `agent/usage.csv`.
При одной статье в день $100 хватает примерно на 5–8 месяцев на Opus и на год на Sonnet. Хостинг Cloudflare Pages и GitHub Actions бесплатные.
