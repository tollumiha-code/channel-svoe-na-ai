#!/usr/bin/env python3
"""
Автопубликация постов канала "Своё на AI" в Telegram.

Запуск:
    export TELEGRAM_TOKEN=123456789:AAH...      # токен от @BotFather
    export TELEGRAM_CHANNEL=@svoe_na_ai        # юзернейм канала
    python3 bot/post_bot.py                   # публикует следующий пост
    python3 bot/post_bot.py --all              # публикует все неопубликованные
    python3 bot/post_bot.py --dry              # только показать, что будет
    python3 bot/post_bot.py --status           # что уже опубликовано

Требования: pip install requests
"""

import os
import re
import json
import sys
import time
import pathlib
import urllib.request

BASE = pathlib.Path(__file__).resolve().parent.parent
POSTS_DIR = BASE / "posts"
STATE_FILE = BASE / "bot" / "state.json"


def api(method, payload=None):
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    if not token:
        sys.exit("Нет TELEGRAM_TOKEN. Получи токен у @BotFather и задай переменную.")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        sys.exit(f"Telegram ответил ошибкой {e.code}: {body}")


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"published": []}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def all_posts():
    """Возвращает список (номер, путь, текст), отсортированный по номеру."""
    items = []
    for f in POSTS_DIR.glob("post*.md"):
        m = re.match(r"post(\d+)", f.name)
        if not m:
            continue
        raw = f.read_text(encoding="utf-8")
        # убираем markdown-заголовок "# Пост N. ..." — в Telegram он лишний
        lines = raw.splitlines()
        while lines and (not lines[0].strip() or lines[0].startswith("#")):
            lines.pop(0)
        items.append((int(m.group(1)), f, "\n".join(lines).strip()))
    return sorted(items, key=lambda x: x[0])


def publish(text, channel, pin=False):
    res = api("sendMessage", {
        "chat_id": channel,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })
    if not res.get("ok"):
        sys.exit("Telegram не принял пост: " + json.dumps(res, ensure_ascii=False))
    msg = res["result"]
    print(f"Опубликовано: message_id={msg['message_id']}")
    if pin:
        time.sleep(1)
        api("pinChatMessage", {"chat_id": channel, "message_id": msg["message_id"]})
        print("Закреплено.")
    return msg["message_id"]


def main():
    channel = os.environ.get("TELEGRAM_CHANNEL", "").strip()
    if not channel:
        sys.exit("Нет TELEGRAM_CHANNEL. Укажи юзернейм канала, например @svoe_na_ai")

    state = load_state()
    posts = all_posts()

    if "--status" in sys.argv:
        print("Опубликовано:", state["published"] or "пока ничего")
        print("Всего постов в папке:", len(posts))
        return

    pending = [(n, p, t) for n, p, t in posts if n not in state["published"]]
    if not pending:
        print("Все посты опубликованы. Добавляй новые файлы post16-*.md в папку posts/")
        return

    if "--dry" in sys.argv:
        for n, p, t in pending:
            print(f"--- Пост {n} ({p.name}) ---")
            print(t[:120].replace("\n", " "), "...")
        return

    limit = len(pending) if "--all" in sys.argv else 1
    for n, p, t in pending[:limit]:
        print(f"\n=== Пост {n}: {p.name} ===")
        publish(t, channel, pin=(n == 1))
        state["published"].append(n)
        save_state(state)
        if n != pending[0][0]:
            time.sleep(60)  # не спамить подряд, чтобы не словить флуд-лимит


if __name__ == "__main__":
    main()
