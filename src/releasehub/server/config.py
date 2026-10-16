"""Settings from environment variables. Secrets never live in the code."""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    admin_token: str
    database_url: str = "sqlite:///data/releasehub.db"
    storage_dir: Path = Path("data/artifacts")

    @classmethod
    def from_env(cls) -> "Settings":
        admin = os.environ.get("ADMIN_TOKEN", "").strip()
        if len(admin) < 16:
            raise ValueError("ADMIN_TOKEN must be set (at least 16 characters)")
        return cls(
            admin_token=admin,
            database_url=os.environ.get("DATABASE_URL", cls.database_url),
            storage_dir=Path(os.environ.get("STORAGE_DIR", str(cls.storage_dir))),
        )
