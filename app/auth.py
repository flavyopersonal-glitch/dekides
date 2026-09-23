import base64
import hashlib
import hmac
import os
import secrets

import requests
from fastapi import Header, HTTPException

from app.database import connection

COOKIE_NAME = "__Secure-neon-auth.session_token"


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ":" + digest.hex()


def check_password(password, stored):
    try:
        salt, expected = stored.split(":")
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def bearer(authorization):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Faça login para continuar.")
    token = authorization[7:].strip()
    if not token or len(token) > 8192:
        raise HTTPException(401, "Sessão inválida.")
    return token


def neon_request(method, path, payload=None, token=None):
    base = os.getenv("NEON_AUTH_BASE_URL", "").rstrip("/")
    if not base.startswith("https://"):
        raise HTTPException(503, "Autenticação Neon não configurada.")
    headers = {"Origin": os.getenv("NEON_AUTH_ORIGIN", "http://localhost:8501")}
    if token:
        try:
            value = base64.b64decode(token.encode(), altchars=b"-_", validate=True).decode("ascii")
            if not value or any(c in value for c in "\r\n; "):
                raise ValueError()
        except (ValueError, UnicodeError):
            raise HTTPException(401, "Sessão inválida.")
        headers["Cookie"] = COOKIE_NAME + "=" + value
    try:
        response = requests.request(method, base + path, headers=headers, json=payload,
                                    params={"disableCookieCache": "true"} if path == "/get-session" else None,
                                    timeout=(10, 20))
        data = response.json()
    except (requests.RequestException, ValueError):
        raise HTTPException(503, "Não foi possível consultar o login. Tente novamente.")
    if not response.ok:
        code = data.get("code", "") if isinstance(data, dict) else ""
        if response.status_code == 429:
            raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos.")
        if "ALREADY" in code and "EXIST" in code:
            raise HTTPException(409, "Esta conta já existe.")
        if response.status_code >= 500:
            raise HTTPException(503, "Serviço de login temporariamente indisponível.")
        if "PASSWORD" in code and ("SHORT" in code or "LONG" in code):
            raise HTTPException(422, "A senha definitiva deve ter entre 8 e 128 caracteres.")
        raise HTTPException(401, "Usuário, e-mail ou senha inválidos.")
    cookie = response.cookies.get(COOKIE_NAME)
    updated = base64.urlsafe_b64encode(cookie.encode()).decode() if cookie else token
    return data, updated


def sign_in(email, password):
    data, token = neon_request("POST", "/sign-in/email", {"email": email, "password": password})
    if not token or not data.get("user"):
        raise HTTPException(401, "Não foi possível iniciar a sessão.")
    return data["user"], token


def register_identity(email, password, name):
    try:
        data, token = neon_request("POST", "/sign-up/email", {"email": email, "password": password, "name": name})
        if not token:
            return sign_in(email, password)
        return data["user"], token
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        # Recupera cadastro interrompido apenas após provar a mesma credencial.
        return sign_in(email, password)


def remote_session(token):
    data, updated = neon_request("GET", "/get-session", token=token)
    if not data or not data.get("user"):
        raise HTTPException(401, "Sessão expirada. Entre novamente.")
    return data["user"], updated or token


def verificar_perfil(authorization: str | None = Header(default=None)) -> dict:
    identity, _ = remote_session(bearer(authorization))
    with connection() as conn:
        perfil = conn.execute("SELECT id,nome,email,username,role,ativo FROM usuarios WHERE id=%s", (identity["id"],)).fetchone()
    if not perfil or not perfil["ativo"]:
        raise HTTPException(403, "Usuário inativo ou sem acesso ao DeKids.")
    return perfil


def limit_login(identifier):
    # Limite compartilhado entre processos e instâncias da API.
    key = token_hash(identifier.strip().casefold())
    with connection() as conn:
        row = conn.execute("""INSERT INTO tentativas_login(identificador,quantidade) VALUES(%s,1)
            ON CONFLICT(identificador) DO UPDATE SET
            quantidade=CASE WHEN tentativas_login.inicio < now()-interval '15 minutes' THEN 1 ELSE tentativas_login.quantidade+1 END,
            inicio=CASE WHEN tentativas_login.inicio < now()-interval '15 minutes' THEN now() ELSE tentativas_login.inicio END
            RETURNING quantidade""", (key,)).fetchone()
    if row["quantidade"] > 10:
        raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos.")


def clear_login_limit(identifier):
    with connection() as conn:
        conn.execute("DELETE FROM tentativas_login WHERE identificador=%s", (token_hash(identifier.strip().casefold()),))
