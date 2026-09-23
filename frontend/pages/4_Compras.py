import sys
from pathlib import Path
from uuid import uuid4
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_client import request, api_error, listar_todos
from money import dinheiro

st.set_page_config(page_title="Compras", page_icon="📥", layout="wide")
st.title("Entrada de compras")
if not st.session_state.get("usuario"):
    st.warning("Faça login na Home.")
    st.stop()
if st.session_state.usuario["role"] not in {"master", "admin"}:
    st.error("Seu perfil não pode registrar compras.")
    st.stop()
if st.session_state.pop("compra_sucesso", False):
    st.success("Compra registrada. Estoque e caixa atualizados.")
if st.session_state.get("erro_compra"):
    st.error(st.session_state.pop("erro_compra"))
if st.session_state.get("compra_pendente"):
    st.warning("Confirme a compra pendente antes de iniciar outra.")
    st.write(f"Fornecedor: {st.session_state.compra_pendente.get('fornecedor') or 'Não informado'}")
    st.write(f"Total: R$ {st.session_state.compra_pendente['valor_total']}")
    if st.button("Confirmar ou tentar novamente", type="primary"):
        try:
            resposta = request("POST", "/compras/entrada/", json=st.session_state.compra_pendente)
            if resposta.ok:
                del st.session_state["compra_pendente"]
                st.session_state["compra_sucesso"] = True
                st.rerun()
            st.error(api_error(resposta))
            if resposta.status_code in (409, 422):
                del st.session_state["compra_pendente"]
                st.session_state["erro_compra"] = api_error(resposta)
                st.rerun()
        except Exception:
            st.error("Sem confirmação. Tente novamente para consultar ou concluir a mesma compra.")
    st.stop()
try:
    produtos = listar_todos("/produtos/")
except Exception:
    st.error("Não foi possível consultar os produtos.")
    st.stop()
opcoes = [(p, v) for p in produtos for v in p.get("variacoes_produto", [])]
if not opcoes:
    st.info("Cadastre um produto com variação antes de registrar uma compra.")
    st.stop()
with st.form("entrada_compra"):
    fornecedor = st.text_input("Fornecedor")
    indice = st.selectbox("Produto", range(len(opcoes)), format_func=lambda i: f"{opcoes[i][0]['nome']} | {opcoes[i][1]['tamanho']} / {opcoes[i][1]['cor']}")
    quantidade = st.number_input("Quantidade recebida", min_value=1, max_value=10000, value=1, step=1)
    custo = st.number_input("Custo unitário (R$)", min_value=0.01, value=1.0, step=0.01)
    salvar = st.form_submit_button("Revisar compra")
if salvar:
    st.session_state.compra_pendente = {
        "operacao_id": str(uuid4()), "fornecedor": fornecedor or None,
        "valor_total": str(quantidade * dinheiro(custo)),
        "itens": [{"variacao_id": opcoes[indice][1]["id"], "quantidade": quantidade, "custo_unitario": str(dinheiro(custo))}],
    }
    st.rerun()
