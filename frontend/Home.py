import requests
import streamlit as st

from api_client import API_URL, TIMEOUT, api_error, logout, request

st.set_page_config(page_title="DeKids Sistema", page_icon="🛍️", layout="wide")
st.title("🛍️ DeKids Moda Infantil")

if st.session_state.get("setup_token"):
    st.subheader("Conclua seu primeiro acesso")
    st.info("Cadastre seu e-mail e escolha a senha definitiva para liberar o sistema.")
    with st.form("formulario_primeiro_acesso"):
        nome = st.text_input("Nome", value=st.session_state.get("nome", "Monica"))
        email = st.text_input("E-mail")
        senha = st.text_input("Nova senha (mínimo de 8 caracteres)", type="password")
        confirmar = st.text_input("Confirme a nova senha", type="password")
        salvar = st.form_submit_button("Concluir cadastro", type="primary")
    if salvar:
        if senha != confirmar:
            st.error("As senhas não coincidem.")
        elif len(senha) < 8:
            st.error("Use uma senha com pelo menos 8 caracteres.")
        else:
            try:
                resposta = requests.post(f"{API_URL}/auth/primeiro-acesso/", json={"nome": nome, "email": email,
                    "senha": senha, "setup_token": st.session_state.setup_token}, timeout=TIMEOUT)
                if resposta.ok:
                    st.session_state.pop("setup_token", None)
                    st.session_state.pop("primeiro_acesso", None)
                    st.session_state.update(resposta.json())
                    st.rerun()
                else:
                    st.error(api_error(resposta))
            except requests.RequestException:
                st.error("Não foi possível confirmar o cadastro. Repita com o mesmo e-mail e senha; se já concluiu, volte ao login.")
    if st.button("Voltar ao login"):
        logout()
        st.rerun()
    st.stop()

if not st.session_state.get("usuario"):
    st.subheader("Acesse o sistema")
    with st.form("login"):
        email = st.text_input("Usuário ou e-mail")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar", type="primary")
    if entrar:
        try:
            resposta = requests.post(f"{API_URL}/auth/login/", json={"email": email, "senha": senha}, timeout=TIMEOUT)
            if resposta.ok:
                dados = resposta.json()
                if dados.get("primeiro_acesso"):
                    st.session_state["setup_token"] = dados["setup_token"]
                    st.session_state["nome"] = dados["nome"]
                    st.rerun()
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
            st.error("Não foi possível conectar à API. Verifique se o sistema está iniciado.")
else:
    usuario = st.session_state["usuario"]
    st.success(f"Bem-vindo(a), {usuario['nome']} | Acesso: {usuario['role'].upper()}")
    st.info("Use o menu lateral para acessar Estoque, PDV, Finanças, Compras e Usuários.")
    pendente = bool(st.session_state.get("venda_pendente") or st.session_state.get("compra_pendente"))
    if pendente:
        st.warning("Confirme a operação pendente antes de sair.")
    if st.button("Sair", disabled=pendente):
        try:
            resposta = request("POST", "/auth/logout/")
            if not resposta.ok and resposta.status_code != 401:
                st.error(api_error(resposta))
                st.stop()
        except requests.RequestException:
            st.error("Não foi possível encerrar a sessão. Tente novamente.")
            st.stop()
        logout()
        st.rerun()
