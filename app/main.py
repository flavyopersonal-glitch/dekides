import logging
import os

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.auth import verificar_perfil
from app.database import supabase, supabase_admin
from app.schemas import CompraEntrada, Login, ProdutoCadastro, UsuarioCadastro, VendaCriacao

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
async def login(dados: Login):
    try:
        sessao = supabase.auth.sign_in_with_password({"email": dados.email, "password": dados.senha})
        if not sessao.user or not sessao.session:
            raise ValueError("Sessão não criada")
        perfil = supabase.table("usuarios").select("nome, role, ativo").eq("id", sessao.user.id).single().execute().data
    except Exception as exc:
        logger.info("Tentativa de login sem sucesso para %s", dados.email)
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.") from exc

    if not perfil or not perfil.get("ativo"):
        raise HTTPException(status_code=403, detail="Usuário inativo ou sem perfil de acesso.")
    return {
        "access_token": sessao.session.access_token,
        "refresh_token": sessao.session.refresh_token,
        "usuario": {"nome": perfil["nome"], "role": perfil["role"]},
    }


@app.get("/auth/me/")
async def meu_perfil(usuario: dict = Depends(verificar_perfil)):
    return usuario


@app.post("/usuarios/cadastro/", status_code=status.HTTP_201_CREATED)
async def cadastrar_usuario(dados: UsuarioCadastro, usuario: dict = Depends(verificar_perfil)):
    exigir_gestao(usuario)
    if dados.role == "master" and usuario["role"] != "master":
        raise HTTPException(status_code=403, detail="Apenas Master pode criar outro Master.")
    try:
        auth_response = supabase_admin.auth.admin.create_user(
            {"email": dados.email, "password": dados.senha, "email_confirm": True}
        )
        perfil = supabase.table("usuarios").insert(
            {"id": auth_response.user.id, "nome": dados.nome, "role": dados.role, "ativo": True}
        ).execute()
        return {"status": "sucesso", "usuario": perfil.data[0]}
    except Exception as exc:
        logger.exception("Erro ao cadastrar usuário")
        raise HTTPException(status_code=400, detail="Não foi possível cadastrar o usuário.") from exc


@app.post("/produtos/cadastro/", status_code=status.HTTP_201_CREATED)
async def cadastrar_produto_completo(dados: ProdutoCadastro, usuario: dict = Depends(verificar_perfil)):
    exigir_gestao(usuario)
    try:
        produto = supabase.table("produtos").insert(
            {
                "nome": dados.nome,
                "descricao": dados.descricao,
                "categoria": dados.categoria,
                "marca": dados.marca,
                "preco_venda": str(dados.preco_venda),
            }
        ).execute()
        produto_id = produto.data[0]["id"]
        if dados.variacoes:
            variacoes = [{"produto_id": produto_id, **serializar(item)} for item in dados.variacoes]
            supabase.table("variacoes_produto").insert(variacoes).execute()
        return {"status": "sucesso", "produto_id": produto_id, "mensagem": "Produto e grade salvos."}
    except Exception as exc:
        logger.exception("Erro ao cadastrar produto")
        raise HTTPException(status_code=400, detail="Não foi possível cadastrar o produto.") from exc


@app.post("/compras/entrada/", status_code=status.HTTP_201_CREATED)
async def registrar_compra_estoque(dados: CompraEntrada, usuario: dict = Depends(verificar_perfil)):
    exigir_gestao(usuario)
    try:
        resultado = supabase_admin.rpc("registrar_compra", {"p_compra": serializar(dados)}).execute()
        return {"status": "sucesso", **resultado.data}
    except Exception as exc:
        logger.exception("Erro ao registrar compra")
        raise HTTPException(status_code=400, detail="Não foi possível registrar a compra.") from exc


@app.get("/produtos/")
async def listar_produtos_e_estoque(_: dict = Depends(verificar_perfil)):
    try:
        return supabase.table("produtos").select("*, variacoes_produto(*)").execute().data
    except Exception as exc:
        logger.exception("Erro ao consultar produtos")
        raise HTTPException(status_code=503, detail="Não foi possível consultar o estoque.") from exc


@app.post("/vendas/", status_code=status.HTTP_201_CREATED)
async def criar_venda(dados: VendaCriacao, usuario: dict = Depends(verificar_perfil)):
    if dados.desconto > dados.valor_total:
        raise HTTPException(status_code=422, detail="O desconto não pode ser maior que o total da venda.")
    try:
        resultado = supabase_admin.rpc(
            "registrar_venda", {"p_usuario_id": usuario["id"], "p_venda": serializar(dados)}
        ).execute()
        return {"status": "sucesso", **resultado.data}
    except Exception as exc:
        logger.exception("Erro ao registrar venda")
        raise HTTPException(status_code=400, detail="Não foi possível concluir a venda.") from exc


@app.get("/financeiro/fluxo-caixa/")
async def ver_financeiro(usuario: dict = Depends(verificar_perfil)):
    exigir_gestao(usuario)
    try:
        return supabase.table("fluxo_caixa").select("*").order("data_competencia", desc=True).execute().data
    except Exception as exc:
        logger.exception("Erro ao consultar fluxo de caixa")
        raise HTTPException(status_code=503, detail="Não foi possível consultar o financeiro.") from exc
