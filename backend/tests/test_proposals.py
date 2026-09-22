"""Reorder proposals with Yes buttons, answered from the web or from Telegram."""

from app.services.notify.telegram import TelegramBot, parse_update


def _auth(client, login, email):
    return {"Authorization": f"Bearer {login(client, email)}"}


def _seeded(client, login, email="prop@x.y"):
    h = _auth(client, login, email)
    client.post("/seed/dev", headers=h)
    return h


def test_propose_once_per_product_and_answer_yes(app_client, login):
    client, _ = app_client
    h = _seeded(client, login)

    created = client.post("/notifications/propose", headers=h).json()["created"]
    names = sorted(n["title"].split(" ")[0] for n in created)
    assert names == ["Milk", "Rice"]  # seeded at 50 % and 25 %: both inside the reorder window; water is not
    milk = next(n for n in created if n["title"].startswith("Milk"))
    assert len(milk["payload"]["offers"]) == 3
    assert "runs out" in milk["title"]

    # Asking again does not nag.
    assert client.post("/notifications/propose", headers=h).json()["created"] == []
    unanswered = client.get("/notifications", params={"unanswered": True}, headers=h).json()["notifications"]
    assert len(unanswered) == 2

    answer = client.post(f"/notifications/{milk['id']}/respond", json={"choice": "1"}, headers=h).json()
    assert answer["notification"]["response"] == "1"
    order = answer["order"]
    assert order["vendor_name"] == milk["payload"]["offers"][0]["vendor_name"]
    assert order["status"] in {"confirmed", "handoff"}
    assert client.post(f"/notifications/{milk['id']}/respond", json={"choice": "2"}, headers=h).status_code == 409

    # With an open order for milk, no new milk proposal is created even after the 24 h window logic.
    assert client.post("/notifications/propose", headers=h).json()["created"] == []


def test_skip(app_client, login):
    client, _ = app_client
    h = _seeded(client, login, "skip@x.y")
    note = client.post("/notifications/propose", headers=h).json()["created"][0]
    body = client.post(f"/notifications/{note['id']}/respond", json={"choice": "skip"}, headers=h).json()
    assert body["order"] is None and body["notification"]["response"] == "skip"


def test_parse_update():
    assert parse_update({"message": {"chat": {"id": 42}, "text": "/start abcd1234"}}) == ("start", "42", "abcd1234", None)
    assert parse_update({"message": {"chat": {"id": 42}, "text": "hello"}}) == ("other", "42", "hello", None)
    cb = {"callback_query": {"id": "cb1", "data": "n:7:2", "message": {"chat": {"id": 42}}}}
    assert parse_update(cb) == ("callback", "42", "n:7:2", "cb1")


def test_telegram_link_and_button_tap(app_client, login, monkeypatch):
    client, _ = app_client
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "AutoBasketBot")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "hook")
    from app.core.config import get_settings

    get_settings.cache_clear()
    sent: list[tuple[str, str, list | None]] = []
    monkeypatch.setattr(TelegramBot, "send_message", lambda self, chat, text, buttons=None: sent.append((chat, text, buttons)) or True)
    monkeypatch.setattr(TelegramBot, "answer_callback", lambda self, cid, text: True)

    h = _seeded(client, login, "tg@x.y")
    link = client.post("/telegram/link", headers=h).json()
    assert link["url"] == f"https://t.me/AutoBasketBot?start={link['code']}"
    assert client.get("/telegram/link", headers=h).json() == {"enabled": True, "connected": False, "bot_username": "AutoBasketBot"}

    hook = {"X-Telegram-Bot-Api-Secret-Token": "hook"}
    assert client.post("/telegram/webhook", json={"message": {"chat": {"id": 42}, "text": "/start nope"}}, headers=hook).json()["linked"] is False
    assert client.post("/telegram/webhook", json={"message": {"chat": {"id": 42}, "text": "/start wrong"}}, headers={"X-Telegram-Bot-Api-Secret-Token": "bad"}).status_code == 403
    assert client.post("/telegram/webhook", json={"message": {"chat": {"id": 42}, "text": f"/start {link['code']}"}}, headers=hook).json()["linked"] is True
    assert client.get("/telegram/link", headers=h).json()["connected"] is True

    # A proposal now goes to Telegram too, with Yes buttons carrying the notification id.
    created = client.post("/notifications/propose", headers=h).json()["created"]
    note = created[0]
    assert note["channel"] == "inapp+telegram"
    chat, text, buttons = next(m for m in sent if note["title"] in m[1])
    assert chat == "42"
    assert buttons[0] == ("Yes #1", f"n:{note['id']}:1") and buttons[-1] == ("Skip", f"n:{note['id']}:skip")

    tap = {"callback_query": {"id": "cb1", "data": f"n:{note['id']}:1", "message": {"chat": {"id": 42}}}}
    body = client.post("/telegram/webhook", json=tap, headers=hook).json()
    assert body["order_id"]
    orders = client.get("/orders", headers=h).json()["orders"]
    assert orders[0]["order_id"] == body["order_id"]

    # Another chat cannot answer this household's proposals.
    other = {"callback_query": {"id": "cb2", "data": f"n:{created[1]['id']}:1", "message": {"chat": {"id": 99}}}}
    client.post("/telegram/webhook", json=other, headers=hook)
    assert len(client.get("/orders", headers=h).json()["orders"]) == 1

    client.delete("/telegram/link", headers=h)
    assert client.get("/telegram/link", headers=h).json()["connected"] is False
