"""Database layer (SQLAlchemy Core). Works with PostgreSQL in production and SQLite in tests.

Tables:
  customers     who can download (we store only a HASH of their token)
  entitlements  which products each customer may download
  releases      every uploaded version: product + version is UNIQUE (releases are immutable)
  downloads     audit log: who downloaded what, and when
"""
from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Integer, MetaData, String, Table,
    UniqueConstraint, create_engine, func, insert, select, text,
)
from sqlalchemy.exc import IntegrityError

metadata = MetaData()

customers = Table(
    "customers", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(100), unique=True, nullable=False),
    Column("token_hash", String(64), unique=True, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)
entitlements = Table(
    "entitlements", metadata,
    Column("customer_id", ForeignKey("customers.id"), primary_key=True),
    Column("product", String(100), primary_key=True),
)
releases = Table(
    "releases", metadata,
    Column("id", Integer, primary_key=True),
    Column("product", String(100), nullable=False, index=True),
    Column("version", String(50), nullable=False),
    Column("filename", String(255), nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("size_bytes", BigInteger, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("product", "version", name="uq_release_product_version"),
)
downloads = Table(
    "downloads", metadata,
    Column("id", Integer, primary_key=True),
    Column("customer_id", ForeignKey("customers.id"), nullable=False),
    Column("release_id", ForeignKey("releases.id"), nullable=False),
    Column("downloaded_at", DateTime(timezone=True), server_default=func.now()),
)


class AlreadyExists(Exception):
    """The database refused a duplicate (unique constraint)."""


class Repo:
    def __init__(self, url: str):
        # pool_pre_ping: test a pooled connection before using it (survives DB restarts)
        self.engine = create_engine(url, pool_pre_ping=True)

    def init(self) -> None:
        metadata.create_all(self.engine)            # CREATE TABLE IF NOT EXISTS (idempotent)

    def ping(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    # ---- customers -------------------------------------------------------
    def create_customer(self, name: str, token_hash: str, products: list[str]) -> int:
        try:
            with self.engine.begin() as conn:       # begin() = one TRANSACTION: all or nothing
                cid = conn.execute(
                    insert(customers).values(name=name, token_hash=token_hash)
                ).inserted_primary_key[0]
                for product in set(products):
                    conn.execute(insert(entitlements).values(customer_id=cid, product=product))
            return cid
        except IntegrityError as exc:
            raise AlreadyExists(f"customer {name!r} already exists") from exc

    def customer_by_token_hash(self, token_hash: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(customers.c.id, customers.c.name).where(customers.c.token_hash == token_hash)
            ).mappings().first()
            if row is None:
                return None
            products = conn.execute(
                select(entitlements.c.product).where(entitlements.c.customer_id == row["id"])
            ).scalars().all()
        return {"id": row["id"], "name": row["name"], "products": set(products)}

    # ---- releases ----------------------------------------------------------
    def add_release(self, product: str, version: str, filename: str, sha256: str, size: int) -> int:
        try:
            with self.engine.begin() as conn:
                return conn.execute(insert(releases).values(
                    product=product, version=version, filename=filename,
                    sha256=sha256, size_bytes=size,
                )).inserted_primary_key[0]
        except IntegrityError as exc:
            raise AlreadyExists(f"{product} {version} already exists") from exc

    def list_releases(self, product: str) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(releases).where(releases.c.product == product)
            ).mappings().all()
        return [dict(r) for r in rows]

    def get_release(self, product: str, version: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(releases).where(
                releases.c.product == product, releases.c.version == version
            )).mappings().first()
        return dict(row) if row else None

    # ---- downloads (audit log) -------------------------------------------------
    def log_download(self, customer_id: int, release_id: int) -> None:
        with self.engine.begin() as conn:
            conn.execute(insert(downloads).values(customer_id=customer_id, release_id=release_id))

    def download_stats(self, product: str) -> list[dict]:
        """How many times each version was downloaded: a JOIN + GROUP BY."""
        query = (
            select(releases.c.version, func.count(downloads.c.id).label("downloads"))
            .select_from(releases.outerjoin(downloads, downloads.c.release_id == releases.c.id))
            .where(releases.c.product == product)
            .group_by(releases.c.version)
        )
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(query).mappings().all()]
