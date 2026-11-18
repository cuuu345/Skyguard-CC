import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def database_url() -> URL:
    return URL.create(
        drivername="mysql+pymysql",
        username=os.getenv("DB_USER", "skyguard"),
        password=os.getenv("DB_PASSWORD", "skyguard_dev"),
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "skyguard"),
        query={"charset": "utf8mb4"},
    )
