"""Focused tests for the User Management bug fix:
- POST /api/users without email (twice) should both succeed (no unique-null collision).
- Duplicate username -> 400 not 500.
- GET /api/users returns email as "" not null.
- Login uses username field; email fallback works.
"""
import os
import time
import uuid
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"


def _login(username, password):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=20)
    return r


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _admin_token():
    r = _login("admin", "admin123")
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


# ------------ Login ------------
class TestLogin:
    def test_login_admin_username(self):
        r = _login("admin", "admin123")
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["role"] == "admin"
        assert d["user"].get("username") == "admin"

    def test_login_smt_username(self):
        r = _login("smt", "password123")
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "smt"

    def test_login_email_fallback(self):
        r = _login("smt@cds.co.id", "password123")
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "smt"

    def test_login_invalid(self):
        r = _login("noone", "wrongpass")
        assert r.status_code == 401


# ------------ User creation bug fix ------------
class TestUserNoEmailBug:
    _created = []

    @classmethod
    def teardown_class(cls):
        tok = _admin_token()
        for uid in cls._created:
            try:
                requests.delete(f"{API}/users/{uid}", headers=auth(tok), timeout=10)
            except Exception:
                pass

    def _create(self, tok, body):
        return requests.post(f"{API}/users", json=body, headers=auth(tok), timeout=15)

    def test_create_two_users_without_email(self):
        tok = _admin_token()
        suffix = uuid.uuid4().hex[:6]
        b1 = {"username": f"test_noemail_a_{suffix}", "password": "pass1234",
              "name": "Test NoEmail A", "role": "assembly"}
        b2 = {"username": f"test_noemail_b_{suffix}", "password": "pass1234",
              "name": "Test NoEmail B", "role": "assembly"}
        r1 = self._create(tok, b1)
        assert r1.status_code == 200, f"first no-email create failed: {r1.status_code} {r1.text}"
        u1 = r1.json()
        assert u1["email"] == ""  # returned as empty string
        self._created.append(u1["id"])

        r2 = self._create(tok, b2)
        assert r2.status_code == 200, f"second no-email create failed (regression): {r2.status_code} {r2.text}"
        u2 = r2.json()
        assert u2["email"] == ""
        self._created.append(u2["id"])

        # ensure GET /users returns them with email == ""
        listing = requests.get(f"{API}/users", headers=auth(tok), timeout=15).json()
        for u in listing:
            assert u.get("email") is not None, "email should never be null"
            assert isinstance(u.get("email"), str)

    def test_duplicate_username_returns_400(self):
        tok = _admin_token()
        suffix = uuid.uuid4().hex[:6]
        username = f"test_dup_{suffix}"
        r = self._create(tok, {"username": username, "password": "pass1234",
                               "name": "Dup 1", "role": "assembly"})
        assert r.status_code == 200
        self._created.append(r.json()["id"])
        r2 = self._create(tok, {"username": username, "password": "pass1234",
                                "name": "Dup 2", "role": "assembly"})
        assert r2.status_code == 400, f"expected 400 on duplicate, got {r2.status_code} {r2.text}"
        assert "sudah dipakai" in r2.text.lower() or "sudah" in r2.text.lower()

    def test_create_with_email_ok(self):
        tok = _admin_token()
        suffix = uuid.uuid4().hex[:6]
        body = {"username": f"test_wmail_{suffix}", "email": f"test_wmail_{suffix}@cds.co.id",
                "password": "pass1234", "name": "With Email", "role": "assembly"}
        r = self._create(tok, body)
        assert r.status_code == 200, r.text
        u = r.json()
        assert u["email"] == body["email"]
        self._created.append(u["id"])

    def test_edit_and_login_with_new_credentials(self):
        tok = _admin_token()
        suffix = uuid.uuid4().hex[:6]
        r = self._create(tok, {"username": f"test_edit_{suffix}", "password": "pass1234",
                               "name": "Edit Me", "role": "assembly"})
        assert r.status_code == 200
        uid = r.json()["id"]
        self._created.append(uid)

        new_username = f"test_edited_{suffix}"
        r2 = requests.put(f"{API}/users/{uid}", json={
            "username": new_username, "password": "newpass1", "role": "smt",
            "name": "Edited", "permissions": {"variance": "read"}
        }, headers=auth(tok), timeout=15)
        assert r2.status_code == 200, r2.text
        u2 = r2.json()
        assert u2["username"] == new_username
        assert u2["role"] == "smt"

        # login with new username+password
        login_r = _login(new_username, "newpass1")
        assert login_r.status_code == 200, login_r.text

    def test_delete_user(self):
        tok = _admin_token()
        suffix = uuid.uuid4().hex[:6]
        r = self._create(tok, {"username": f"test_del_{suffix}", "password": "pass1234",
                               "name": "Del Me", "role": "assembly"})
        assert r.status_code == 200
        uid = r.json()["id"]
        dr = requests.delete(f"{API}/users/{uid}", headers=auth(tok), timeout=15)
        assert dr.status_code == 200

    def test_main_admin_not_deletable(self):
        tok = _admin_token()
        listing = requests.get(f"{API}/users", headers=auth(tok), timeout=15).json()
        admin_row = next(u for u in listing if u.get("is_main_admin"))
        r = requests.delete(f"{API}/users/{admin_row['id']}", headers=auth(tok), timeout=15)
        assert r.status_code == 400
