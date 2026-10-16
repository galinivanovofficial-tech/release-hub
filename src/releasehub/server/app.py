"""REST API.

Admin (ADMIN_TOKEN):    create customers, upload releases, see download stats
Customer (own token):   list / download releases of the products they are entitled to

401 Unauthorized = we don't know who you are (missing or wrong token)
403 Forbidden    = we know who you are, but you may not access this product
"""
import hashlib
import secrets

from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from releasehub.server.config import Settings
from releasehub.server.db import AlreadyExists, Repo
from releasehub.server.storage import ArtifactStore, safe_filename, valid_product
from releasehub.version import InvalidVersionError, Version


class NewCustomer(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    products: list[str] = Field(min_length=1)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    repo = Repo(settings.database_url)
    repo.init()
    store = ArtifactStore(settings.storage_dir)
    bearer = HTTPBearer(auto_error=False)
    app = FastAPI(title="Release Hub", version="0.2.0")

    # ---- authentication / authorization (FastAPI "dependencies") ----------------
    def require_admin(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
        # compare_digest takes the same time for any input: no timing attacks
        if creds is None or not secrets.compare_digest(creds.credentials, settings.admin_token):
            raise HTTPException(401, "admin token required")

    def require_customer(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
        customer = creds and repo.customer_by_token_hash(hash_token(creds.credentials))
        if not customer:
            raise HTTPException(401, "valid customer token required")
        return customer

    def check_product(product: str) -> None:
        if not valid_product(product):
            raise HTTPException(422, "product name: lowercase letters, digits and '-'")

    def require_entitled(product: str, customer: dict = Depends(require_customer)) -> dict:
        check_product(product)
        if product not in customer["products"]:
            raise HTTPException(403, f"not entitled to {product}")
        return customer

    def sorted_releases(product: str) -> list[dict]:
        rows = repo.list_releases(product)
        # sort by SEMANTIC version (1.10.0 > 1.9.3), not as text
        return sorted(rows, key=lambda r: Version.parse(r["version"]), reverse=True)

    def public(row: dict) -> dict:
        return {k: row[k] for k in ("product", "version", "filename", "sha256", "size_bytes")}

    # ---- health ---------------------------------------------------------------
    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready(response: Response):
        if repo.ping():
            return {"status": "ready"}
        response.status_code = 503
        return {"status": "database unavailable"}

    # ---- admin ------------------------------------------------------------------
    @app.post("/admin/customers", status_code=201, dependencies=[Depends(require_admin)])
    def create_customer(body: NewCustomer):
        for product in body.products:
            check_product(product)
        token = secrets.token_urlsafe(32)        # shown ONCE, only its hash is stored
        try:
            repo.create_customer(body.name, hash_token(token), body.products)
        except AlreadyExists as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"name": body.name, "products": sorted(set(body.products)), "token": token}

    @app.post("/admin/products/{product}/releases", status_code=201,
              dependencies=[Depends(require_admin)])
    def upload_release(product: str, version: str = Form(...), file: UploadFile = File(...)):
        check_product(product)
        try:
            version = str(Version.parse(version))
            filename = safe_filename(file.filename)
        except (InvalidVersionError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        if repo.get_release(product, version):
            raise HTTPException(409, f"{product} {version} already exists; releases are immutable")
        sha256, size = store.save(product, version, filename, file.file)
        try:
            repo.add_release(product, version, filename, sha256, size)
        except AlreadyExists as exc:              # two uploads raced each other
            raise HTTPException(409, str(exc)) from exc
        return {"product": product, "version": version, "filename": filename,
                "sha256": sha256, "size_bytes": size}

    @app.get("/admin/products/{product}/downloads", dependencies=[Depends(require_admin)])
    def download_stats(product: str):
        check_product(product)
        return repo.download_stats(product)

    # ---- customers ----------------------------------------------------------------
    @app.get("/products/{product}/releases")
    def list_releases(product: str, customer: dict = Depends(require_entitled)):
        return [public(r) for r in sorted_releases(product)]

    @app.get("/products/{product}/releases/latest")
    def latest_release(product: str, customer: dict = Depends(require_entitled)):
        rows = sorted_releases(product)
        if not rows:
            raise HTTPException(404, f"no releases for {product}")
        return public(rows[0])

    @app.get("/products/{product}/releases/{version}/download")
    def download(product: str, version: str, customer: dict = Depends(require_entitled)):
        row = repo.get_release(product, version)
        if not row:
            raise HTTPException(404, f"{product} {version} not found")
        repo.log_download(customer["id"], row["id"])
        return FileResponse(
            store.path(product, version, row["filename"]),
            filename=row["filename"],
            headers={"X-Checksum-SHA256": row["sha256"]},   # client verifies integrity
        )

    return app
