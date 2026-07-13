import requests
import streamlit as st

from api_client import API_URL, TIMEOUT, api_error, logout

st.set_page_config(page_title="DeKids Sistema", page_icon="🛍️", layout="wide")
st.title("🛍️ DeKids Moda Infantil")

if "usuario" not in st.session_state:
    st.session_state["usuario"] = None

if st.session_state["usuario"] is None:
    st.subheader("Acesse o sistema")
    with st.form("login"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")
    if entrar:
        try:
            resposta = requests.post(
                f"{API_URL}/auth/login/", json={"email": email, "senha": senha}, timeout=TIMEOUT
            )
            if resposta.ok:
                dados = resposta.json()
                st.session_state.update(dados)
                st.rerun()
            else:
                st.error(api_error(resposta))
        except requests.RequestException:
            st.error("Não foi possível conectar à API. Verifique a configuração DEKIDS_API_URL.")
else:
    usuario = st.session_state["usuario"]
    st.success(f"Bem-vindo(a), {usuario['nome']} | Acesso: {usuario['role'].upper()}")
    st.info("Use o menu lateral para acessar Estoque, PDV e Finanças.")
    if st.button("Sair"):
        logout()
        st.rerun()
