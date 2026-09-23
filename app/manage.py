"""Migrações e primeiro acesso: python -m app.manage migrate|bootstrap."""
import argparse
import getpass
import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg


def migrate():
    load_dotenv(os.getenv("DEKIDS_ENV_FILE", ".env"))
    url = os.getenv("DATABASE_URL_UNPOOLED")
    if not url:
        raise RuntimeError("Configure DATABASE_URL_UNPOOLED para aplicar migrações.")
    with psycopg.connect(url, connect_timeout=15) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(61283051)")
        conn.execute("CREATE SCHEMA IF NOT EXISTS dekids")
        conn.execute("CREATE TABLE IF NOT EXISTS dekids.schema_migrations (nome text primary key, checksum text not null, aplicado_em timestamptz not null default now())")
        for path in sorted((Path(__file__).resolve().parents[1] / "migrations").glob("*.sql")):
            text = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(text.encode()).hexdigest()
            previous = conn.execute("SELECT checksum FROM dekids.schema_migrations WHERE nome=%s", (path.name,)).fetchone()
            if previous:
                if previous[0] != checksum:
                    raise RuntimeError(f"Migração já aplicada foi modificada: {path.name}")
                continue
            conn.execute(text)
            conn.execute("INSERT INTO dekids.schema_migrations(nome,checksum) VALUES(%s,%s)", (path.name, checksum))
            print(f"Aplicada: {path.name}")
    print("Banco atualizado.")


def bootstrap(username, password):
    from app.database import connection
    from app.auth import hash_password
    with connection() as conn:
        if conn.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
            raise RuntimeError("Já existem usuários. O primeiro acesso não pode ser recriado.")
        conn.execute("INSERT INTO primeiro_acesso(singleton,username,senha_hash) VALUES(true,%s,%s) ON CONFLICT DO NOTHING", (username, hash_password(password)))
    print("Primeiro acesso preparado; senha não exibida.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["migrate", "bootstrap"])
    parser.add_argument("--username", default="Monica")
    args = parser.parse_args()
    if args.action == "migrate":
        migrate()
    else:
        bootstrap(args.username, getpass.getpass("Senha provisória: "))
