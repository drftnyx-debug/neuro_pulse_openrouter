import os
import json
import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

RSS_FEEDS = [
    "https://blog.google/technology/ai/rss/",
    "https://openai.com/news/rss.xml",
]
STATE_FILE = Path("state.json")
MAX_ITEMS_PER_FEED = 8


def get(url, headers=None, timeout=25):
    req = Request(url, headers=headers or {"User-Agent": "NeuroPulseBot/1.0"})
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logging.warning("State file unreadable; starting with empty state.")
    return {"published": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_feed(url):
    try:
        root = ET.fromstring(get(url, timeout=20))
    except Exception as exc:
        logging.warning("RSS feed failed (%s): %s", url, exc)
        return []
    items = []
    for node in root.findall(".//item")[:MAX_ITEMS_PER_FEED]:
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        description = (node.findtext("description") or "").strip()
        if title and link:
            items.append({"title": title, "link": link,
                          "description": re.sub(r"<[^>]+>", " ", description)[:1200]})
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    if not items:
        for node in root.findall(".//atom:entry", ns)[:MAX_ITEMS_PER_FEED]:
            title = (node.findtext("atom:title", default="", namespaces=ns) or "").strip()
            summary = (node.findtext("atom:summary", default="", namespaces=ns) or "").strip()
            link_node = node.find("atom:link", ns)
            link = link_node.attrib.get("href", "") if link_node is not None else ""
            if title and link:
                items.append({"title": title, "link": link,
                              "description": re.sub(r"<[^>]+>", " ", summary)[:1200]})
    return items


def generate_post(item):
    prompt = f"""Ты редактор русскоязычного Telegram-канала NEURO PULSE об ИИ и технологиях.
Напиши один полезный пост на русском языке на основе материала ниже.
Правила:
- Не добавляй факты, которых нет в исходных данных.
- Не выдавай предположения за подтверждённые факты.
- Перескажи своими словами, не копируй исходный текст дословно.
- Короткий заголовок, 2-4 коротких абзаца и практический вывод.
- Без кликбейта, выдуманных цитат и обещаний заработка.
- В конце добавь строку «Источник: {item['link']}».
- Максимум 1200 знаков. Верни только готовый пост.

Заголовок: {item['title']}
Описание: {item['description']}
Ссылка: {item['link']}"""

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "Ты точный редактор. Не выдумывай факты."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.6,
        "max_tokens": 700
    }
    req = Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/",
            "X-Title": "NEURO PULSE"
        },
        method="POST"
    )
    try:
        with urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        if isinstance(text, list):
            text = " ".join(part.get("text", "") for part in text if isinstance(part, dict))
        return str(text).strip()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:700]
        raise RuntimeError(f"OpenRouter API HTTP {exc.code}: {detail}") from exc


def telegram_send(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text[:3900], "disable_web_page_preview": False}
    req = Request(url, data=json.dumps(payload).encode("utf-8"),
                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok"):
            raise RuntimeError(f"Telegram API error: {result}")
        return result["result"]["message_id"]
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Telegram API HTTP {exc.code}: {detail}") from exc


def main():
    state = load_state()
    published = set(state.get("published", []))
    candidates = []
    for feed in RSS_FEEDS:
        candidates.extend(parse_feed(feed))

    seen_this_run = set()
    for item in candidates:
        digest = hashlib.sha256(item["link"].encode("utf-8")).hexdigest()
        if digest in published or digest in seen_this_run:
            continue
        seen_this_run.add(digest)
        try:
            post = generate_post(item)
            if not post or len(post) < 80:
                logging.warning("Generated post too short; skipping %s", item["link"])
                continue
            message_id = telegram_send(post)
            published.add(digest)
            state["published"] = list(published)[-500:]
            state["last_success_utc"] = datetime.now(timezone.utc).isoformat()
            save_state(state)
            logging.info("Published message_id=%s source=%s", message_id, item["link"])
            return
        except Exception:
            logging.exception("Failed item %s", item["link"])

    logging.info("No new item published. Check feeds or wait for new material.")
    save_state(state)


if __name__ == "__main__":
    main()
