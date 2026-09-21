import sys
from decimal import Decimal
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
    pagina = st.number_input("Página de lançamentos", min_value=1, value=1, step=1)
    resposta = request("GET", "/financeiro/fluxo-caixa/", params={"offset": (pagina - 1) * 100, "limite": 100})
    if not resposta.ok:
        st.error(api_error(resposta))
        st.stop()
    lancamentos = resposta.json()
except Exception:
    st.error("Não foi possível carregar o fluxo de caixa.")
    st.stop()

try:
    resposta = request("GET", "/financeiro/resumo/")
    if not resposta.ok:
        st.error(api_error(resposta))
        st.stop()
    resumo = resposta.json()
    entradas, saidas = Decimal(resumo["entradas"]), Decimal(resumo["saidas"])
except Exception:
    st.error("Não foi possível calcular o saldo completo.")
    st.stop()
if not lancamentos:
    st.info("Nenhum lançamento nesta página.")
col1, col2, col3 = st.columns(3)
col1.metric("Entradas", f"R$ {entradas:.2f}")
col2.metric("Saídas", f"R$ {saidas:.2f}")
col3.metric("Saldo", f"R$ {entradas - saidas:.2f}")
st.dataframe(lancamentos, use_container_width=True, hide_index=True)
