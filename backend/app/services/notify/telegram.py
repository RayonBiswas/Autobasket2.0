"""Thin Telegram Bot API client. Sends messages with inline buttons; parses the two update shapes we care about."""

import logging

import httpx

log = logging.getLogger("autobasket.telegram")
API = "https://api.telegram.org/bot{token}/{method}"


class TelegramBot:
    def __init__(self, token: str, http: httpx.Client | None = None):
        self.token = token
        self.http = http or httpx.Client(timeout=10)

    def _call(self, method: str, payload: dict) -> bool:
        try:
            r = self.http.post(API.format(token=self.token, method=method), json=payload)
            r.raise_for_status()
            return bool(r.json().get("ok"))
        except Exception as exc:  # fail soft: a Telegram outage must not block the in-app alert
            log.warning("telegram %s failed: %s", method, exc)
            return False

    def send_message(self, chat_id: str, text: str, buttons: list[tuple[str, str]] | None = None) -> bool:
        """buttons = [(label, callback_data)], shown as one row of inline buttons."""
        payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in buttons]]}
        return self._call("sendMessage", payload)

    def answer_callback(self, callback_id: str, text: str) -> bool:
        return self._call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})

    def set_webhook(self, url: str, secret: str | None) -> bool:
        payload: dict = {"url": url, "allowed_updates": ["message", "callback_query"]}
        if secret:
            payload["secret_token"] = secret
        return self._call("setWebhook", payload)


def parse_update(update: dict) -> tuple[str, str, str, str | None]:
    """Returns (kind, chat_id, data, callback_id): ("start", chat, code, None) | ("callback", chat, data, id) | ("other", chat, text, None)."""
    if "callback_query" in update:
        cq = update["callback_query"]
        chat = str(cq.get("message", {}).get("chat", {}).get("id") or cq.get("from", {}).get("id", ""))
        return "callback", chat, str(cq.get("data", "")), str(cq.get("id", ""))
    msg = update.get("message") or {}
    chat = str(msg.get("chat", {}).get("id", ""))
    text = (msg.get("text") or "").strip()
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        return "start", chat, parts[1].strip() if len(parts) > 1 else "", None
    return "other", chat, text, None
