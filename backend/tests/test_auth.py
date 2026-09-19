def test_request_otp_returns_dev_code(app_client):
    client, _ = app_client
    r = client.post("/auth/request-otp", json={"email": "a@b.c"})
    assert r.status_code == 200
    assert len(r.json()["dev_code"]) == 6


def test_verify_creates_user_and_household(app_client, login):
    client, _ = app_client
    token = login(client, "new@user.io")
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["user"]["email"] == "new@user.io"
    assert me["household"]["name"].startswith("new@user.io")
    assert me["memberships"][0]["role"] == "owner"


def test_second_login_reuses_household(app_client, login):
    client, _ = app_client
    h1 = {"Authorization": f"Bearer {login(client, 'again@x.y')}"}
    h2 = {"Authorization": f"Bearer {login(client, 'again@x.y')}"}
    assert client.get("/auth/me", headers=h1).json()["household"]["id"] == client.get("/auth/me", headers=h2).json()["household"]["id"]


def test_wrong_code_rejected(app_client):
    client, _ = app_client
    client.post("/auth/request-otp", json={"email": "x@y.z"})
    r = client.post("/auth/verify-otp", json={"email": "x@y.z", "code": "000000"})
    assert r.status_code == 401


def test_protected_route_requires_token(app_client):
    client, _ = app_client
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_sixth_otp_request_in_window_is_throttled(app_client):
    client, _ = app_client
    for _ in range(5):
        assert client.post("/auth/request-otp", json={"email": "t@t.t"}).status_code == 200
    assert client.post("/auth/request-otp", json={"email": "t@t.t"}).status_code == 429
