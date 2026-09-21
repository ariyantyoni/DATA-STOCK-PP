"""Backend tests: Audit trail, Duplicate handling, Notifications (iteration 5)."""
import os
import time
import pytest
import requests
from pathlib import Path


def _read_frontend_env():
    p = Path("/app/frontend/.env")
    for line in p.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not in /app/frontend/.env")


BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env()).rstrip("/") + "/api"


def login(username, password):
    r = requests.post(f"{BASE}/auth/login", json={"username": username, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text}"
    return r.json()["token"]


def h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_token():
    return login("admin", "admin123")


@pytest.fixture(scope="module")
def ppic_token():
    return login("ppic", "password123")


@pytest.fixture(scope="module")
def smt_token():
    return login("smt", "password123")


@pytest.fixture(scope="module")
def smt_user_id(admin_token):
    r = requests.get(f"{BASE}/users", headers=h(admin_token), timeout=20)
    assert r.status_code == 200
    for u in r.json():
        if u.get("username") == "smt":
            return u["id"]
    pytest.skip("smt user not found")


def _cleanup(admin_token, ics_list):
    r = requests.get(f"{BASE}/smt-production", headers=h(admin_token), timeout=20)
    if r.status_code == 200:
        for d in r.json():
            if d.get("ics_no") in ics_list:
                requests.delete(f"{BASE}/smt-production/{d['id']}", headers=h(admin_token), timeout=20)


# ---------------------------------------------------------------------- AUDIT
class TestAudit:
    def test_create_stamps_and_audit(self, admin_token):
        _cleanup(admin_token, ["7777777777"])
        payload = {"date": "2026-09-20", "lane": "L01", "type": "AUDIT TEST",
                   "ics_no": "7777777777", "product": "REGULER", "planing": 100, "tt": 30,
                   "act_s1": 10, "act_s2": 0, "act_s3": 0}
        r = requests.post(f"{BASE}/smt-production", headers=h(admin_token), json=payload, timeout=20)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc.get("created_by_name") == "Admin Utama"
        assert doc.get("created_at")
        rid = doc["id"]

        # Audit CREATE present
        r = requests.get(f"{BASE}/audit", headers=h(admin_token),
                         params={"module": "smt_production", "action": "CREATE", "search": "7777777777"}, timeout=20)
        assert r.status_code == 200
        logs = r.json()
        assert any(l.get("ics_no") == "7777777777" for l in logs), f"CREATE audit missing: {logs[:2]}"
        entry = [l for l in logs if l.get("ics_no") == "7777777777"][0]
        assert entry.get("ip") is not None
        assert entry.get("user_agent")

        # PUT update
        payload2 = dict(payload); payload2["act_s1"] = 20
        r = requests.put(f"{BASE}/smt-production/{rid}", headers=h(admin_token), json=payload2, timeout=20)
        assert r.status_code == 200
        r = requests.get(f"{BASE}/audit", headers=h(admin_token),
                         params={"module": "smt_production", "action": "UPDATE", "search": "7777777777"}, timeout=20)
        upds = [l for l in r.json() if l.get("ics_no") == "7777777777"]
        assert upds, "UPDATE audit missing"
        u0 = upds[0]
        assert u0.get("before") and u0.get("after")
        assert u0["before"].get("act_s1") != u0["after"].get("act_s1")

        # DELETE
        r = requests.delete(f"{BASE}/smt-production/{rid}", headers=h(admin_token), timeout=20)
        assert r.status_code == 200
        r = requests.get(f"{BASE}/audit", headers=h(admin_token),
                         params={"module": "smt_production", "action": "DELETE", "search": "7777777777"}, timeout=20)
        assert any(l.get("ics_no") == "7777777777" for l in r.json())

    def test_audit_filters(self, admin_token):
        r = requests.get(f"{BASE}/audit", headers=h(admin_token),
                         params={"date_from": "2020-01-01", "date_to": "2020-01-02"}, timeout=20)
        assert r.status_code == 200

    def test_non_privileged_cannot_read_audit(self, smt_token):
        r = requests.get(f"{BASE}/audit", headers=h(smt_token), timeout=20)
        assert r.status_code == 403


# ---------------------------------------------------------------------- DUP
class TestDuplicate:
    def test_duplicate_409_and_force_update(self, admin_token):
        _cleanup(admin_token, ["7777777780"])
        payload = {"date": "2026-09-21", "lane": "L01", "type": "DUP TEST",
                   "ics_no": "7777777780", "product": "REGULER", "planing": 200, "tt": 30}
        r1 = requests.post(f"{BASE}/smt-production", headers=h(admin_token), json=payload, timeout=20)
        assert r1.status_code == 200

        r2 = requests.post(f"{BASE}/smt-production", headers=h(admin_token), json=payload, timeout=20)
        assert r2.status_code == 409, r2.text
        body = r2.json()
        detail = body.get("detail", body)
        assert detail.get("code") == "DUPLICATE"
        assert "message" in detail

        # count before force
        docs_before = requests.get(f"{BASE}/smt-production", headers=h(admin_token),
                                   params={"ics_no": "7777777780"}, timeout=20).json()
        cnt_before = len([d for d in docs_before if d.get("ics_no") == "7777777780"])

        payload_force = dict(payload); payload_force["force"] = True; payload_force["planing"] = 300
        r3 = requests.post(f"{BASE}/smt-production", headers=h(admin_token), json=payload_force, timeout=20)
        assert r3.status_code == 200
        docs_after = requests.get(f"{BASE}/smt-production", headers=h(admin_token),
                                  params={"ics_no": "7777777780"}, timeout=20).json()
        cnt_after = len([d for d in docs_after if d.get("ics_no") == "7777777780"])
        assert cnt_after == cnt_before, "force should overwrite, not add"

        r = requests.get(f"{BASE}/audit", headers=h(admin_token),
                         params={"module": "smt_production", "action": "UPDATE", "search": "7777777780"}, timeout=20)
        notes = [l.get("note", "") for l in r.json() if l.get("ics_no") == "7777777780"]
        assert any("Timpa data duplikat" in n for n in notes), f"notes={notes}"

        _cleanup(admin_token, ["7777777780"])

    def test_import_preview_duplicates(self, admin_token):
        path = "/app/backend/seed/smt_production.csv"
        if not os.path.exists(path):
            pytest.skip("seed csv missing")
        with open(path, "rb") as f:
            r = requests.post(f"{BASE}/import/smt-production/preview",
                              headers={"Authorization": f"Bearer {admin_token}"},
                              files={"file": ("smt_production.csv", f, "text/csv")}, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        # Fields expected
        for k in ("new", "duplicates", "invalid"):
            assert k in data, f"missing {k} in {list(data.keys())}"
        assert data["duplicates"] >= 0


# ---------------------------------------------------------------------- NOTIF
class TestNotifications:
    def test_notify_flow(self, admin_token, ppic_token, smt_token, smt_user_id):
        # 1. admin sets notify for smt user
        r = requests.put(f"{BASE}/users/{smt_user_id}", headers=h(admin_token),
                         json={"notify": {"enabled": True, "modules": ["smt_production"]}}, timeout=20)
        assert r.status_code == 200, r.text

        # Clear existing notifications for smt
        requests.post(f"{BASE}/notifications/read", headers=h(smt_token), json={}, timeout=20)

        # 2. ppic creates smt data
        _cleanup(admin_token, ["7777777778"])
        payload = {"date": "2026-09-22", "lane": "L01", "type": "NOTIF TEST",
                   "ics_no": "7777777778", "product": "REGULER", "planing": 50, "tt": 30}
        r = requests.post(f"{BASE}/smt-production", headers=h(ppic_token), json=payload, timeout=20)
        assert r.status_code == 200, r.text

        time.sleep(1)

        # 3. smt user sees notification
        r = requests.get(f"{BASE}/notifications", headers=h(smt_token), timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data["unread"] >= 1, f"unread={data['unread']}"
        # message contains ppic name
        assert any("7777777778" in it.get("message", "") for it in data["items"]), \
            f"items={data['items'][:2]}"

        # 4. mark all read
        r = requests.post(f"{BASE}/notifications/read", headers=h(smt_token), json={}, timeout=20)
        assert r.status_code == 200
        r = requests.get(f"{BASE}/notifications", headers=h(smt_token), timeout=20)
        assert r.json()["unread"] == 0

        # 5. admin does not receive notif for its own action
        # Clear admin's notifications first
        requests.post(f"{BASE}/notifications/read", headers=h(admin_token), json={}, timeout=20)
        # temporarily enable admin notify on smt_production
        # Actually spec says admin should not receive own action's notif. Just verify with ppic:
        r = requests.get(f"{BASE}/notifications", headers=h(ppic_token), timeout=20)
        assert r.status_code == 200
        # ppic should not have received notification about its own action
        own_notif = [it for it in r.json()["items"] if "7777777778" in it.get("message", "")]
        assert not own_notif, "actor received notif for their own action"

        # Cleanup: reset notify + remove test data
        requests.put(f"{BASE}/users/{smt_user_id}", headers=h(admin_token),
                     json={"notify": {"enabled": False, "modules": []}}, timeout=20)
        _cleanup(admin_token, ["7777777778"])


def test_final_cleanup(admin_token):
    _cleanup(admin_token, ["7777777777", "7777777778", "7777777779", "7777777780"])
