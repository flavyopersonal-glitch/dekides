from fastapi import FastAPI, Depends, HTTPException, Header
from app.database import supabase
from app.auth import verificar_perfil

app = FastAPI(title="DeKids - Sistema de Estoque e Finanças")

@app.get("/")
def raiz():
    return {"status": "Online", "sistema": "DeKids Moda Infantil"}


# =========================================================================
# 👤 1. GESTÃO DE LOGINS / USUÁRIOS (Restrito: Apenas Master e Admin)
# =========================================================================

@app.post("/usuarios/cadastro/")
async def cadastrar_usuario(dados_usuario: dict, usuario_logado: dict = Depends(verificar_perfil)):
    # Garante que funcionários comuns não criem novos logins
    if usuario_logado["role"] not in ["master", "admin"]:
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas Admin ou Master podem criar logins.")
    
    try:
        # 1. Cria o usuário no Auth do Supabase (Email e Senha)
        auth_response = supabase.auth.admin.create_user({
            "email": dados_usuario["email"],
            "password": dados_usuario["senha"],
            "email_confirm": True
        })
        
        user_id = auth_response.user.id
        
        # 2. Vincula o ID criado ao perfil na nossa tabela 'usuarios' com a role definida
        perfil_response = supabase.table("usuarios").insert({
            "id": user_id,
            "nome": dados_usuario["nome"],
            "role": dados_usuario["role"], # 'master', 'admin' ou 'funcionario'
            "ativo": True
        }).execute()
        
        return {"status": "Sucesso", "usuario": perfil_response.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao criar usuário: {str(e)}")


# =========================================================================
# 📦 2. CADASTRO DE PRODUTOS E GRADE (Restrito: Apenas Master e Admin)
# =========================================================================

@app.post("/produtos/cadastro/")
async def cadastrar_produto_completo(dados_produto: dict, usuario_logado: dict = Depends(verificar_perfil)):
    if usuario_logado["role"] not in ["master", "admin"]:
        raise HTTPException(status_code=403, detail="Acesso negado para cadastro de produtos.")
        
    try:
        # 1. Cadastra o Produto Pai
        produto_pai = supabase.table("produtos").insert({
            "nome": dados_produto["nome"],
            "descricao": dados_produto.get("descricao"),
            "categoria": dados_produto.get("categoria"),
            "marca": dados_produto.get("marca"),
            "preco_venda": dados_produto["preco_venda"]
        }).execute()
        
        produto_id = produto_pai.data[0]["id"]
        
        # 2. Se houver uma grade inicial de variações (Tamanho/Cor), cadastra elas
        if "variacoes" in dados_produto and dados_produto["variacoes"]:
            variacoes = []
            for var in dados_produto["variacoes"]:
                variacoes.append({
                    "produto_id": produto_id,
                    "tamanho": var["tamanho"], # Ex: RN, P, 2A
                    "cor": var["cor"],
                    "codigo_barras": var.get("codigo_barras"),
                    "estoque_atual": var.get("estoque_atual", 0),
                    "estoque_minimo": var.get("estoque_minimo", 2)
                })
            supabase.table("variacoes_produto").insert(variacoes).execute()
            
        return {"status": "Sucesso", "produto_id": produto_id, "mensagem": "Produto e grade salvos."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================================
# 🛒 3. ENTRADA DE ESTOQUE / COMPRAS (Restrito: Apenas Master e Admin)
# =========================================================================

@app.post("/compras/entrada/")
async def registrar_compra_estoque(dados_compra: dict, usuario_logado: dict = Depends(verificar_perfil)):
    if usuario_logado["role"] not in ["master", "admin"]:
        raise HTTPException(status_code=403, detail="Acesso negado para registro de compras.")
        
    try:
        # 1. Registra o cabeçalho da compra de fornecedor
        compra = supabase.table("compras").insert({
            "fornecedor": dados_compra.get("fornecedor"),
            "valor_total": dados_compra["valor_total"],
            "status": "recebido"
        }).execute()
        
        compra_id = compra.data[0]["id"]
        
        # 2. Registra os itens comprados (Custo Unitário e Quantidade)
        itens_compra = []
        for item in dados_compra["itens"]:
            itens_compra.append({
                "compra_id": compra_id,
                "variacao_id": item["variacao_id"],
                "quantidade": item["quantidade"],
                "custo_unitario": item["custo_unitario"]
            })
            
            # 3. Atualiza o estoque atual somando o que foi comprado
            # Nota: Podemos automatizar isso com trigger futuramente, mas no código fica assim:
            supabase.rpc("incrementar_estoque", {
                "var_id": item["variacao_id"], 
                "qtd": item["quantidade"]
            }).execute()
            
        supabase.table("itens_compra").insert(itens_compra).execute()
        
        # 4. Lança a saída automática no Fluxo de Caixa Empresarial
        supabase.table("fluxo_caixa").insert({
            "tipo": "saida",
            "categoria": "compra_estoque",
            "valor": dados_compra["valor_total"],
            "descricao": f"Compra de estoque do fornecedor: {dados_compra.get('fornecedor', 'Não informado')}",
            "compra_id": compra_id
        }).execute()
        
        return {"status": "Sucesso", "compra_id": compra_id, "mensagem": "Estoque atualizado e financeiro lançado."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================================
# 💰 4. CONTROLE DE ESTOQUE & VENDAS (Disponível para Todos os Logins)
# =========================================================================

@app.get("/produtos/")
async def listar_produtos_e_estoque(usuario_logado: dict = Depends(verificar_perfil)):
    # Traz a lista de roupas com seus respectivos tamanhos, cores e quantidades em estoque
    response = supabase.table("produtos").select("*, variacoes_produto(*)").execute()
    return response.data


@app.post("/vendas/")
async def criar_venda(dados_venda: dict, usuario_logado: dict = Depends(verificar_perfil)):
    try:
        # Cadastra a venda usando o ID do funcionário/admin que está operando o sistema
        venda = supabase.table("vendas").insert({
            "usuario_id": usuario_logado["id"],
            "valor_total": dados_venda["valor_total"],
            "desconto": dados_venda.get("desconto", 0),
            "forma_pagamento": dados_venda["forma_pagamento"]
        }).execute()
        
        venda_id = venda.data[0]["id"]
        
        # Cadastra os itens vendidos (O trigger do banco vai reduzir o estoque e lançar no caixa)
        itens = []
        for item in dados_venda["itens"]:
            itens.append({
                "venda_id": venda_id,
                "variacao_id": item["variacao_id"],
                "quantidade": item["quantidade"],
                "preco_unitario_pago": item["preco_unitario_pago"]
            })
        supabase.table("itens_venda").insert(itens).execute()
        
        return {"status": "Sucesso", "venda_id": venda_id, "mensagem": "Venda concluída com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================================
# 📈 5. RELATÓRIO FINANCEIRO (Restrito: Apenas Master e Admin)
# =========================================================================

@app.get("/financeiro/fluxo-caixa/")
async def ver_financeiro(usuario_logado: dict = Depends(verificar_perfil)):
    if usuario_logado["role"] not in ["master", "admin"]:
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas Admin ou Master visualizam o financeiro.")
        
    response = supabase.table("fluxo_caixa").select("*").order("data_competencia", desc=True).execute()
    return response.data