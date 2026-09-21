import sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_client import request, api_error

st.set_page_config(page_title="Usuários", page_icon="👥", layout="wide")
st.title("Cadastrar usuário")
usuario = st.session_state.get("usuario")
if not usuario:
    st.warning("Faça login na Home.")
    st.stop()
if usuario["role"] not in {"master", "admin"}:
    st.error("Seu perfil não pode cadastrar usuários.")
    st.stop()
with st.form("novo_usuario", clear_on_submit=True):
    nome = st.text_input("Nome")
    email = st.text_input("E-mail")
    senha = st.text_input("Senha inicial", type="password")
    roles = ["funcionario", "admin"] + (["master"] if usuario["role"] == "master" else [])
    role = st.selectbox("Perfil", roles)
    salvar = st.form_submit_button("Cadastrar")
if salvar:
    try:
        resposta = request("POST", "/usuarios/cadastro/", json={"nome": nome, "email": email, "senha": senha, "role": role})
        if resposta.ok:
            st.success("Conta e perfil cadastrados.")
        else:
            st.error(api_error(resposta))
    except Exception:
        st.error("Não foi possível confirmar o cadastro. Verifique a conta antes de tentar novamente.")
