"""API tests: a real app with a temporary SQLite database and temp storage."""
import hashlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from releasehub.server.app import create_app
from releasehub.server.config import Settings

ADMIN = "admin-token-for-tests-123"
ADMIN_H = {"Authorization": f"Bearer {ADMIN}"}


@pytest.fixture
def env(tmp_path):
    db = tmp_path / "test.db"
    app = create_app(Settings(admin_token=ADMIN, database_url=f"sqlite:///{db}",
                              storage_dir=tmp_path / "artifacts"))
    return TestClient(app), db


def customer(client, name="acme", products=("hana-tools",)):
    r = client.post("/admin/customers", json={"name": name, "products": list(products)},
                    headers=ADMIN_H)
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['token']}"}


def upload(client, version, content=b"binary-data", product="hana-tools", filename="tool.tar.gz"):
    return client.post(f"/admin/products/{product}/releases", headers=ADMIN_H,
                       data={"version": version}, files={"file": (filename, content)})


def test_health_and_ready(env):
    client, _ = env
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").status_code == 200


def test_admin_endpoints_need_admin_token(env):
    client, _ = env
    assert client.post("/admin/customers", json={"name": "x", "products": ["p"]}).status_code == 401
    bad = {"Authorization": "Bearer wrong-token"}
    assert client.post("/admin/customers", json={"name": "x", "products": ["p"]},
                       headers=bad).status_code == 401


def test_token_is_stored_only_as_hash(env):
    client, db = env
    r = client.post("/admin/customers", json={"name": "acme", "products": ["p"]}, headers=ADMIN_H)
    token = r.json()["token"]
    stored = sqlite3.connect(db).execute("SELECT token_hash FROM customers").fetchone()[0]
    assert stored != token
    assert stored == hashlib.sha256(token.encode()).hexdigest()


def test_duplicate_customer_is_409(env):
    client, _ = env
    customer(client, "acme")
    r = client.post("/admin/customers", json={"name": "acme", "products": ["p"]}, headers=ADMIN_H)
    assert r.status_code == 409


def test_upload_returns_checksum(env):
    client, _ = env
    r = upload(client, "1.0.0", b"hello")
    assert r.status_code == 201
    assert r.json()["sha256"] == hashlib.sha256(b"hello").hexdigest()
    assert r.json()["size_bytes"] == 5


def test_releases_are_immutable(env):
    client, _ = env
    assert upload(client, "1.0.0").status_code == 201
    assert upload(client, "1.0.0", b"other").status_code == 409


def test_invalid_version_is_422(env):
    client, _ = env
    assert upload(client, "latest").status_code == 422


def test_versions_sorted_semantically(env):
    client, _ = env
    for v in ("1.9.3", "1.10.0", "1.2.0"):
        upload(client, v)
    h = customer(client)
    versions = [r["version"] for r in client.get("/products/hana-tools/releases", headers=h).json()]
    assert versions == ["1.10.0", "1.9.3", "1.2.0"]
    assert client.get("/products/hana-tools/releases/latest", headers=h).json()["version"] == "1.10.0"


def test_401_without_token_403_without_entitlement(env):
    client, _ = env
    upload(client, "1.0.0")
    assert client.get("/products/hana-tools/releases").status_code == 401
    other = customer(client, "globex", products=["other-product"])
    assert client.get("/products/hana-tools/releases", headers=other).status_code == 403


def test_download_with_checksum_and_audit_log(env):
    client, _ = env
    upload(client, "2.0.0", b"payload-bytes")
    h = customer(client)
    r = client.get("/products/hana-tools/releases/2.0.0/download", headers=h)
    assert r.status_code == 200
    assert r.content == b"payload-bytes"
    assert r.headers["X-Checksum-SHA256"] == hashlib.sha256(b"payload-bytes").hexdigest()
    stats = client.get("/admin/products/hana-tools/downloads", headers=ADMIN_H).json()
    assert stats == [{"version": "2.0.0", "downloads": 1}]


def test_download_missing_version_is_404(env):
    client, _ = env
    h = customer(client)
    assert client.get("/products/hana-tools/releases/9.9.9/download", headers=h).status_code == 404


def test_path_traversal_filename_is_neutralised(env):
    client, _ = env
    r = upload(client, "1.0.0", filename="../../etc/passwd")
    assert r.status_code == 201 and r.json()["filename"] == "passwd"


def test_bad_product_name_is_422(env):
    client, _ = env
    assert upload(client, "1.0.0", product="Bad_Name!").status_code == 422
