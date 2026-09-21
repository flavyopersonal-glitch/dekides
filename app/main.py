import logging
import os

from fastapi import Depends, FastAPI, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from postgrest.exceptions import APIError

from app.auth import verificar_perfil
from app.database import cliente_auth, supabase_admin
from app.schemas import CompraEntrada, Login, ProdutoCadastro, UsuarioCadastro, VendaCriacao, Renovacao

logger = logging.getLogger(__name__)
app = FastAPI(title="DeKids - Sistema de Estoque e Finanças", version="1.0.0")

origens = [origem.strip() for origem in os.getenv("CORS_ORIGINS", "").split(",") if origem.strip()]
if origens:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origens,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def exigir_gestao(usuario: dict) -> None:
    if usuario["role"] not in {"master", "admin"}:
        raise HTTPException(status_code=403, detail="Acesso permitido apenas para Admin ou Master.")


def serializar(modelo) -> dict:
    """Converte Decimals de modelos Pydantic para valores aceitos pelo PostgREST."""
    return modelo.model_dump(mode="json")


@app.get("/")
def raiz():
    return {"status": "online", "sistema": "DeKids Moda Infantil"}


@app.post("/auth/login/")
def login(dados: Login):
    try:
        sessao = cliente_auth().auth.sign_in_with_password({"email": dados.email, "password": dados.senha})
        if not sessao.user or not sessao.session:
            raise ValueError("Sessão não criada")
        perfil = supabase_admin.table("usuarios").select("nome, role, ativo").eq("id", sessao.user.id).single().execute().data
    except Exception as exc:
        logger.info("Tentativa de login sem sucesso para %s", dados.email)
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.") from exc

    return resposta_sessao(sessao, perfil)


def resposta_sessao(sessao, perfil):
    if not perfil or not perfil.get("ativo"):
        raise HTTPException(status_code=403, detail="Usuário inativo ou sem perfil de acesso.")
    return {
        "access_token": sessao.session.access_token,
        "refresh_token": sessao.session.refresh_token,
        "usuario": {"id": sessao.user.id, "nome": perfil["nome"], "role": perfil["role"]},
    }


@app.post("/auth/refresh/")
def renovar(dados: Renovacao):
    try:
        sessao = cliente_auth().auth.refresh_session(dados.refresh_token)
        perfil = supabase_admin.table("usuarios").select("nome, role, ativo").eq("id", sessao.user.id).single().execute().data
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Sessão expirada. Entre novamente.") from exc
    return resposta_sessao(sessao, perfil)


@app.get("/auth/me/")
def meu_perfil(usuario: dict = Depends(verificar_perfil)):
    return usuario


@app.post("/usuarios/cadastro/", status_code=status.HTTP_201_CREATED)
def cadastrar_usuario(dados: UsuarioCadastro, usuario: dict = Depends(verificar_perfil)):
    exigir_gestao(usuario)
    if dados.role == "master" and usuario["role"] != "master":
        raise HTTPException(status_code=403, detail="Apenas Master pode criar outro Master.")
    try:
        auth_response = supabase_admin.auth.admin.create_user(
            {"email": dados.email, "password": dados.senha, "email_confirm": True,
             "app_metadata": {"dekids_nome": dados.nome, "dekids_role": dados.role}}
        )
        # O trigger do banco cria o perfil na mesma transação da conta.
        return {"status": "sucesso", "usuario": {"id": auth_response.user.id, "nome": dados.nome, "role": dados.role}}

    except Exception as exc:
        logger.exception("Erro ao cadastrar usuário")
        raise HTTPException(status_code=400, detail="Não foi possível cadastrar o usuário.") from exc


@app.post("/produtos/cadastro/", status_code=status.HTTP_201_CREATED)
def cadastrar_produto_completo(dados: ProdutoCadastro, usuario: dict = Depends(verificar_perfil)):
    exigir_gestao(usuario)
    try:
        resultado = supabase_admin.rpc("cadastrar_produto", {"p_produto": serializar(dados)}).execute()
        return {"status": "sucesso", **resultado.data}

    except Exception as exc:
        logger.exception("Erro ao cadastrar produto")
        raise HTTPException(status_code=400, detail="Não foi possível cadastrar o produto.") from exc


@app.post("/compras/entrada/", status_code=status.HTTP_201_CREATED)
def registrar_compra_estoque(dados: CompraEntrada, usuario: dict = Depends(verificar_perfil)):
    exigir_gestao(usuario)
    try:
        resultado = supabase_admin.rpc("registrar_compra", {"p_compra": serializar(dados), "p_usuario_id": usuario["id"]}).execute()
        return {"status": "sucesso", **resultado.data}
    except APIError as exc:
        raise erro_operacao(exc) from exc
    except Exception as exc:
        logger.exception("Erro ao registrar compra")
        raise HTTPException(status_code=503, detail="Sem confirmação da compra. Reutilize o identificador da operação.") from exc


@app.get("/produtos/")
def listar_produtos_e_estoque(_: dict = Depends(verificar_perfil), offset: int = Query(0, ge=0), limite: int = Query(100, ge=1, le=500)):
    try:
        return supabase_admin.table("produtos").select("*, variacoes_produto(*)").order("id").range(offset, offset + limite - 1).execute().data
    except Exception as exc:
        logger.exception("Erro ao consultar produtos")
        raise HTTPException(status_code=503, detail="Não foi possível consultar o estoque.") from exc


@app.post("/vendas/", status_code=status.HTTP_201_CREATED)
def criar_venda(dados: VendaCriacao, usuario: dict = Depends(verificar_perfil)):
    if dados.desconto > dados.valor_total:
        raise HTTPException(status_code=422, detail="O desconto não pode ser maior que o total da venda.")
    try:
        resultado = supabase_admin.rpc(
            "registrar_venda", {"p_usuario_id": usuario["id"], "p_venda": serializar(dados)}
        ).execute()
        return {"status": "sucesso", **resultado.data}
    except APIError as exc:
        raise erro_operacao(exc) from exc
    except Exception as exc:
        logger.exception("Erro ao registrar venda")
        raise HTTPException(status_code=503, detail="Sem confirmação da venda. Reutilize o identificador da operação.") from exc


@app.get("/financeiro/fluxo-caixa/")
def ver_financeiro(usuario: dict = Depends(verificar_perfil), offset: int = Query(0, ge=0), limite: int = Query(100, ge=1, le=500)):
    exigir_gestao(usuario)
    try:
        return supabase_admin.table("fluxo_caixa").select("*").order("data_competencia", desc=True).order("id").range(offset, offset + limite - 1).execute().data
    except Exception as exc:
        logger.exception("Erro ao consultar fluxo de caixa")
        raise HTTPException(status_code=503, detail="Não foi possível consultar o financeiro.") from exc


@app.get("/financeiro/resumo/")
def resumo_financeiro(usuario: dict = Depends(verificar_perfil)):
    exigir_gestao(usuario)
    try:
        return supabase_admin.rpc("resumo_financeiro", {}).execute().data
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Não foi possível calcular o saldo.") from exc


def erro_operacao(exc):
    # Apenas erros confirmados pelo PostgreSQL permitem descartar a tentativa.
    if exc.code == "P0001":
        return HTTPException(status_code=409, detail=exc.message)
    if exc.code in {"23502", "23503", "23505", "23514", "22003", "22P02"}:
        return HTTPException(status_code=409, detail="Operação rejeitada pelo banco. Revise os dados.")
    return HTTPException(status_code=503, detail="Sem confirmação. Tente novamente com a mesma operação.")
