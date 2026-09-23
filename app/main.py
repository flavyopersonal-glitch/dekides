import logging
import os
import secrets
from contextlib import asynccontextmanager

import psycopg
from psycopg.types.json import Jsonb
from fastapi import Depends, FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import auth
from app.database import connection, close_pool
from app.schemas import Login, PrimeiroAcesso, UsuarioCadastro, ProdutoCadastro, CompraEntrada, VendaCriacao, Renovacao

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    yield
    close_pool()


app = FastAPI(title="DeKids", version="2.0.0", lifespan=lifespan)
origens = [s.strip() for s in os.getenv("CORS_ORIGINS", "").split(",") if s.strip()]
if origens:
    app.add_middleware(CORSMiddleware, allow_origins=origens, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])


@app.exception_handler(psycopg.Error)
async def database_error(request, exc):
    # Não exponha SQL, URLs de conexão ou dados pessoais em mensagens.
    logger.error("Falha no banco (%s)", exc.sqlstate)
    if exc.sqlstate == "P0001":
        return JSONResponse(status_code=409, content={"detail": exc.diag.message_primary})
    if exc.sqlstate in {"23502", "23503", "23505", "23514", "22003", "22P02"}:
        return JSONResponse(status_code=409, content={"detail": "Dados em conflito. Revise o cadastro ou a operação."})
    return JSONResponse(status_code=503, content={"detail": "Sem confirmação do banco. Tente novamente com a mesma operação."})


def exigir_gestao(usuario):
    if usuario["role"] not in {"master", "admin"}:
        raise HTTPException(403, "Acesso permitido apenas para Admin ou Master.")


def sessao(token, perfil):
    if not perfil or not perfil["ativo"]:
        raise HTTPException(403, "Usuário inativo ou sem perfil de acesso.")
    return {"access_token": token, "refresh_token": token,
            "usuario": {k: perfil[k] for k in ("id", "nome", "role")}}


@app.get("/")
def raiz():
    return {"status": "online", "sistema": "DeKids", "banco": "Neon PostgreSQL"}


@app.get("/health/ready/")
def ready():
    with connection() as conn:
        conn.execute("SELECT 1 FROM usuarios LIMIT 1")
    return {"status": "ready"}


@app.post("/auth/login/")
def login(dados: Login):
    identifier = dados.email.strip().lower()
    auth.limit_login(identifier)
    with connection() as conn:
        bootstrap = conn.execute("SELECT * FROM primeiro_acesso WHERE singleton=true FOR UPDATE").fetchone()
        if bootstrap and not bootstrap["concluido"] and identifier == bootstrap["username"].lower():
            if not auth.check_password(dados.senha, bootstrap["senha_hash"]):
                raise HTTPException(401, "Usuário, e-mail ou senha inválidos.")
            token = secrets.token_urlsafe(32)
            conn.execute("UPDATE primeiro_acesso SET token_hash=%s,expira_em=now()+interval '15 minutes' WHERE singleton=true", (auth.token_hash(token),))
            return {"primeiro_acesso": True, "setup_token": token, "nome": bootstrap["username"]}
        perfil = conn.execute("SELECT * FROM usuarios WHERE lower(email)=%s OR lower(username)=%s", (identifier, identifier)).fetchone()
    if not perfil or not perfil["ativo"]:
        raise HTTPException(401, "Usuário, e-mail ou senha inválidos.")
    identity, token = auth.sign_in(perfil["email"], dados.senha)
    if identity["id"] != perfil["id"]:
        raise HTTPException(401, "Conta inválida.")
    auth.clear_login_limit(identifier)
    return sessao(token, perfil)


@app.post("/auth/primeiro-acesso/")
def primeiro_acesso(dados: PrimeiroAcesso):
    with connection() as conn:
        bootstrap = conn.execute("SELECT * FROM primeiro_acesso WHERE singleton=true AND NOT concluido AND token_hash=%s AND expira_em>now() FOR UPDATE", (auth.token_hash(dados.setup_token),)).fetchone()
        if not bootstrap:
            raise HTTPException(401, "Acesso provisório expirado. Entre novamente.")
        if bootstrap["email_pendente"] and bootstrap["email_pendente"] != dados.email:
            raise HTTPException(409, "Repita a configuração usando o mesmo e-mail da primeira tentativa.")
        conn.execute("UPDATE primeiro_acesso SET email_pendente=%s WHERE singleton=true", (dados.email,))
    identity, token = auth.register_identity(dados.email, dados.senha, dados.nome)
    with connection() as conn:
        bootstrap = conn.execute("SELECT * FROM primeiro_acesso WHERE singleton=true AND NOT concluido AND token_hash=%s AND expira_em>now() FOR UPDATE", (auth.token_hash(dados.setup_token),)).fetchone()
        if not bootstrap:
            raise HTTPException(409, "A configuração já foi concluída ou expirou. Entre usando o e-mail e a nova senha.")
        perfil = conn.execute("INSERT INTO usuarios(id,nome,email,username,role) VALUES(%s,%s,%s,%s,'master') RETURNING *", (identity["id"],dados.nome,dados.email,bootstrap["username"])).fetchone()
        conn.execute("UPDATE primeiro_acesso SET concluido=true,senha_hash='',token_hash=NULL,expira_em=NULL WHERE singleton=true")
    return sessao(token, perfil)


@app.post("/auth/refresh/")
def renovar(dados: Renovacao):
    identity, token = auth.remote_session(dados.refresh_token)
    with connection() as conn:
        perfil = conn.execute("SELECT * FROM usuarios WHERE id=%s", (identity["id"],)).fetchone()
    return sessao(token, perfil)


@app.get("/auth/me/")
def me(usuario=Depends(auth.verificar_perfil)):
    return {k: usuario[k] for k in ("id", "nome", "role")}


@app.post("/auth/logout/")
def sair(authorization: str | None = Header(default=None)):
    auth.neon_request("POST", "/sign-out", {}, auth.bearer(authorization))
    return {"status": "sucesso"}


@app.post("/usuarios/cadastro/", status_code=201)
def cadastrar_usuario(dados: UsuarioCadastro, usuario=Depends(auth.verificar_perfil)):
    exigir_gestao(usuario)
    if dados.role == "master" and usuario["role"] != "master":
        raise HTTPException(403, "Apenas Master pode criar outro Master.")
    with connection() as conn:
        if conn.execute("SELECT 1 FROM usuarios WHERE email=%s", (dados.email,)).fetchone():
            raise HTTPException(409, "Este e-mail já está cadastrado no sistema.")
        conn.execute("INSERT INTO cadastros_pendentes(email,nome,role,criado_por) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING", (dados.email,dados.nome,dados.role,usuario["id"]))
        pending = conn.execute("SELECT * FROM cadastros_pendentes WHERE email=%s", (dados.email,)).fetchone()
        if pending["criado_por"] != usuario["id"] or pending["role"] != dados.role:
            raise HTTPException(409, "Há um cadastro pendente para este e-mail com outros dados.")
    identity, token = auth.register_identity(dados.email, dados.senha, dados.nome)
    with connection() as conn:
        conn.execute("SELECT 1 FROM cadastros_pendentes WHERE email=%s FOR UPDATE", (dados.email,))
        perfil = conn.execute("INSERT INTO usuarios(id,nome,email,role) VALUES(%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING RETURNING id,nome,role", (identity["id"],dados.nome,dados.email,dados.role)).fetchone()
        if not perfil:
            raise HTTPException(409, "Usuário já cadastrado.")
        conn.execute("DELETE FROM cadastros_pendentes WHERE email=%s", (dados.email,))
    # A sessão gerada durante a criação nunca é entregue ao administrador.
    try:
        auth.neon_request("POST", "/sign-out", {}, token)
    except HTTPException:
        logger.warning("Não foi possível encerrar a sessão temporária do cadastro.")
    return {"status": "sucesso", "usuario": perfil}


def rpc(name, dados, usuario_id=None):
    allowed = {"cadastrar_produto", "registrar_compra", "registrar_venda"}
    if name not in allowed:
        raise ValueError("Função inválida")
    from psycopg import sql
    args = [Jsonb(dados.model_dump(mode="json"))]
    if usuario_id is not None:
        args.insert(0, usuario_id)
    query = sql.SQL("SELECT {}({}) AS resultado").format(sql.Identifier(name), sql.SQL(",").join(sql.Placeholder() for _ in args))
    with connection() as conn:
        result = conn.execute(query, args).fetchone()["resultado"]
    return {"status": "sucesso", **result}


@app.post("/produtos/cadastro/", status_code=201)
def cadastrar_produto(dados: ProdutoCadastro, usuario=Depends(auth.verificar_perfil)):
    exigir_gestao(usuario)
    return rpc("cadastrar_produto", dados)


@app.post("/compras/entrada/", status_code=201)
def comprar(dados: CompraEntrada, usuario=Depends(auth.verificar_perfil)):
    exigir_gestao(usuario)
    return rpc("registrar_compra", dados, usuario["id"])


@app.post("/vendas/", status_code=201)
def vender(dados: VendaCriacao, usuario=Depends(auth.verificar_perfil)):
    return rpc("registrar_venda", dados, usuario["id"])


@app.get("/produtos/")
def produtos(usuario=Depends(auth.verificar_perfil), offset: int = Query(0, ge=0), limite: int = Query(100, ge=1, le=500), busca: str = Query("", max_length=150)):
    with connection() as conn:
        rows = conn.execute("SELECT id,nome,descricao,categoria,marca,preco_venda FROM produtos WHERE nome ILIKE %s ORDER BY id LIMIT %s OFFSET %s", ("%"+busca+"%",limite,offset)).fetchall()
        if rows:
            variacoes = conn.execute("SELECT id,produto_id,tamanho,cor,codigo_barras,estoque_atual,estoque_minimo FROM variacoes_produto WHERE produto_id=ANY(%s) ORDER BY id", ([r["id"] for r in rows],)).fetchall()
            by_product = {}
            for v in variacoes:
                by_product.setdefault(v["produto_id"], []).append(v)
            for row in rows:
                row["preco_venda"] = str(row["preco_venda"])
                row["variacoes_produto"] = by_product.get(row["id"], [])
    return rows


@app.get("/financeiro/fluxo-caixa/")
def fluxo(usuario=Depends(auth.verificar_perfil), offset: int = Query(0, ge=0), limite: int = Query(100, ge=1, le=500)):
    exigir_gestao(usuario)
    with connection() as conn:
        rows = conn.execute("SELECT id,tipo,categoria,valor,descricao,compra_id,venda_id,data_competencia FROM fluxo_caixa ORDER BY data_competencia DESC,id LIMIT %s OFFSET %s", (limite,offset)).fetchall()
    for row in rows:
        row["valor"] = str(row["valor"])
    return rows


@app.get("/financeiro/resumo/")
def resumo(usuario=Depends(auth.verificar_perfil)):
    exigir_gestao(usuario)
    with connection() as conn:
        return conn.execute("SELECT resumo_financeiro() AS resumo").fetchone()["resumo"]
