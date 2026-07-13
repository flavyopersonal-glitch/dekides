import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_client import api_error, request  # noqa: E402

st.set_page_config(page_title="Finanças", page_icon="💰", layout="wide")

if not st.session_state.get("usuario"):
    st.warning("Faça login na página Home para acessar o financeiro.")
    st.stop()
if st.session_state["usuario"]["role"] not in {"master", "admin"}:
    st.error("Seu perfil não pode visualizar o financeiro.")
    st.stop()

st.title("💰 Fluxo de Caixa")
try:
    resposta = request("GET", "/financeiro/fluxo-caixa/")
    if not resposta.ok:
        st.error(api_error(resposta))
        st.stop()
    lancamentos = resposta.json()
except Exception:
    st.error("Não foi possível carregar o fluxo de caixa.")
    st.stop()

if not lancamentos:
    st.info("Nenhum lançamento financeiro encontrado.")
    st.stop()

entradas = sum(float(item["valor"]) for item in lancamentos if item.get("tipo") == "entrada")
saidas = sum(float(item["valor"]) for item in lancamentos if item.get("tipo") == "saida")
col1, col2, col3 = st.columns(3)
col1.metric("Entradas", f"R$ {entradas:.2f}")
col2.metric("Saídas", f"R$ {saidas:.2f}")
col3.metric("Saldo", f"R$ {entradas - saidas:.2f}")
st.dataframe(lancamentos, use_container_width=True, hide_index=True)
