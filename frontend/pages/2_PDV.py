import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_client import api_error, request  # noqa: E402

st.set_page_config(page_title="PDV", page_icon="🛒", layout="wide")

if not st.session_state.get("usuario"):
    st.warning("Faça login na página Home para acessar o PDV.")
    st.stop()

st.title("🛒 Frente de Caixa")
if "carrinho" not in st.session_state:
    st.session_state.carrinho = []

try:
    resposta = request("GET", "/produtos/")
    produtos = resposta.json() if resposta.ok else []
    if not resposta.ok:
        st.error(api_error(resposta))
except Exception:
    produtos = []
    st.error("Não foi possível buscar os produtos.")

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
                    existente["preco_unitario_pago"] = preco
                    st.rerun()
            else:
                st.session_state.carrinho.append({
                    "variacao_id": selecionado["variacao"]["id"], "quantidade": quantidade,
                    "preco_unitario_pago": preco, "descricao": labels[indice],
                })
                st.rerun()

st.subheader("Carrinho")
if not st.session_state.carrinho:
    st.caption("Adicione itens para iniciar uma venda.")
else:
    for posicao, item in enumerate(st.session_state.carrinho):
        subtotal = item["quantidade"] * item["preco_unitario_pago"]
        coluna_item, coluna_valor, coluna_remover = st.columns([6, 2, 1])
        coluna_item.write(f"{item['quantidade']}x {item['descricao']}")
        coluna_valor.write(f"R$ {subtotal:.2f}")
        if coluna_remover.button("Remover", key=f"remover-{posicao}"):
            st.session_state.carrinho.pop(posicao)
            st.rerun()

    bruto = sum(item["quantidade"] * item["preco_unitario_pago"] for item in st.session_state.carrinho)
    forma = st.selectbox("Forma de pagamento", ["pix", "credito", "debito", "dinheiro"])
    desconto = st.number_input("Desconto (R$)", min_value=0.0, max_value=float(bruto), value=0.0, step=0.01)
    total = bruto - desconto
    st.markdown(f"### Total: R$ {total:.2f}")
    if st.button("Concluir venda", type="primary"):
        payload = {
            "valor_total": bruto, "desconto": desconto, "forma_pagamento": forma,
            "itens": [{k: v for k, v in item.items() if k != "descricao"} for item in st.session_state.carrinho],
        }
        try:
            resposta = request("POST", "/vendas/", json=payload)
            if resposta.ok:
                st.session_state.carrinho = []
                st.success("Venda concluída. Estoque e fluxo de caixa atualizados.")
                st.rerun()
            else:
                st.error(api_error(resposta))
        except Exception:
            st.error("Não foi possível concluir a venda.")
