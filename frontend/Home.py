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
                dono = st.session_state.get("operacao_dono")
                if dono and dados["usuario"]["id"] != dono:
                    st.error("Entre com o usuário anterior para confirmar a operação pendente.")
                    st.stop()
                st.session_state.pop("operacao_dono", None)
                st.session_state.update(dados)
                st.rerun()
            else:
                st.error(api_error(resposta))
        except requests.RequestException:
            st.error("Não foi possível conectar à API. Verifique a configuração DEKIDS_API_URL.")
else:
    usuario = st.session_state["usuario"]
    st.success(f"Bem-vindo(a), {usuario['nome']} | Acesso: {usuario['role'].upper()}")
    st.info("Use o menu lateral para acessar Estoque, PDV, Finanças, Compras e Usuários.")
    pendente = bool(st.session_state.get("venda_pendente") or st.session_state.get("compra_pendente"))
    if pendente:
        st.warning("Confirme a operação pendente antes de sair.")
    if st.button("Sair", disabled=pendente):
        logout()
        st.rerun()
