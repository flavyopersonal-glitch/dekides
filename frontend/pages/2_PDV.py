import sys
from uuid import uuid4
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from money import dinheiro, total_itens
from api_client import api_error, request, listar_todos  # noqa: E402

st.set_page_config(page_title="PDV", page_icon="🛒", layout="wide")

if not st.session_state.get("usuario"):
    st.warning("Faça login na página Home para acessar o PDV.")
    st.stop()

st.title("🛒 Frente de Caixa")
if "carrinho" not in st.session_state:
    st.session_state.carrinho = []

try:
    produtos = listar_todos("/produtos/")
except Exception:
    produtos = []
    st.error("Não foi possível buscar os produtos.")

# Uma tentativa com resposta incerta deve reutilizar exatamente a mesma operação.
if st.session_state.get("venda_pendente"):
    st.warning("Há uma venda aguardando confirmação. Confirme antes de iniciar outra.")
    if st.button("Confirmar ou tentar novamente", type="primary"):
        try:
            resposta = request("POST", "/vendas/", json=st.session_state.venda_pendente)
            if resposta.ok:
                st.session_state.carrinho = []
                del st.session_state["venda_pendente"]
                st.session_state["venda_sucesso"] = True
                st.rerun()
            else:
                st.error(api_error(resposta))
                if resposta.status_code in (409, 422):
                    del st.session_state["venda_pendente"]
                    st.session_state["erro_venda"] = api_error(resposta)
                    st.rerun()
        except Exception:
            st.error("Sem confirmação da API. Tente novamente; a mesma venda não será duplicada.")
    st.stop()
if st.session_state.pop("venda_sucesso", False):
    st.success("Venda concluída. Estoque e fluxo de caixa atualizados.")

if st.session_state.get("erro_venda"):
    st.error(st.session_state.pop("erro_venda"))

opcoes = []
for produto in produtos:
    for variacao in produto.get("variacoes_produto", []):
        if variacao.get("estoque_atual", 0) > 0:
            opcoes.append({"produto": produto, "variacao": variacao})

with st.expander("Adicionar item", expanded=True):
    if not opcoes:
        st.info("Não há itens disponíveis em estoque.")
    else:
        labels = [
            f"{x['produto']['nome']} | {x['variacao']['tamanho']} / {x['variacao']['cor']} "
            f"(disponível: {x['variacao']['estoque_atual']})"
            for x in opcoes
        ]
        indice = st.selectbox("Produto e variação", range(len(opcoes)), format_func=lambda i: labels[i])
        selecionado = opcoes[indice]
        estoque = selecionado["variacao"]["estoque_atual"]
        quantidade = st.number_input("Quantidade", min_value=1, max_value=estoque, value=1, step=1)
        preco = st.number_input(
            "Preço unitário (R$)", min_value=0.01,
            value=float(selecionado["produto"]["preco_venda"]), step=0.01,
        )
        if st.button("Adicionar ao carrinho"):
            existente = next(
                (item for item in st.session_state.carrinho if item["variacao_id"] == selecionado["variacao"]["id"]), None
            )
            if existente:
                if existente["quantidade"] + quantidade > estoque:
                    st.error("A quantidade total no carrinho supera o estoque disponível.")
                else:
                    existente["quantidade"] += quantidade
                    existente["preco_unitario_pago"] = str(dinheiro(preco))
                    st.rerun()
            else:
                st.session_state.carrinho.append({
                    "variacao_id": selecionado["variacao"]["id"], "quantidade": quantidade,
                    "preco_unitario_pago": str(dinheiro(preco)), "descricao": labels[indice],
                })
                st.rerun()

st.subheader("Carrinho")
if not st.session_state.carrinho:
    st.caption("Adicione itens para iniciar uma venda.")
else:
    for posicao, item in enumerate(st.session_state.carrinho):
        subtotal = item["quantidade"] * dinheiro(item["preco_unitario_pago"])
        coluna_item, coluna_valor, coluna_remover = st.columns([6, 2, 1])
        coluna_item.write(f"{item['quantidade']}x {item['descricao']}")
        coluna_valor.write(f"R$ {subtotal:.2f}")
        if coluna_remover.button("Remover", key=f"remover-{posicao}"):
            st.session_state.carrinho.pop(posicao)
            st.rerun()

    bruto = total_itens(st.session_state.carrinho)
    forma = st.selectbox("Forma de pagamento", ["pix", "credito", "debito", "dinheiro"])
    desconto = st.number_input("Desconto (R$)", min_value=0.0, max_value=float(bruto), value=0.0, step=0.01)
    total = bruto - dinheiro(desconto)
    st.markdown(f"### Total: R$ {total:.2f}")
    if st.button("Concluir venda", type="primary"):
        payload = {
            "operacao_id": str(uuid4()), "valor_total": str(bruto), "desconto": str(dinheiro(desconto)), "forma_pagamento": forma,
            "itens": [{k: v for k, v in item.items() if k != "descricao"} for item in st.session_state.carrinho],
        }
        st.session_state.venda_pendente = payload
        st.rerun()
