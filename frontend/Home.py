import streamlit as st
import requests

st.set_page_config(page_title="DeKids Sistema", page_icon="🛍️", layout="wide")

API_URL = "https://dekides.onrender.com" # Seu link do Render

st.title("🛍️ DeKids Moda Infantil - Sistema de Gestão")

# --- SISTEMA SIMPLES DE LOGIN (ESTADO DA SESSÃO) ---
if "usuario" not in st.session_state:
    st.session_state["usuario"] = None

if st.session_state["usuario"] is None:
    st.subheader("🔑 Faça Login para Acessar o Sistema")
    
    email = st.text_input("E-mail")
    senha = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        # Aqui simulamos a validação de perfil (integração com seu backend)
        # Em produção, seu backend retorna o Token JWT e a Role do usuário
        if email == "master@dekids.com":
            st.session_state["usuario"] = {"nome": "Flavyo (Master)", "role": "master"}
            st.rerun()
        elif email == "dona@dekids.com":
            st.session_state["usuario"] = {"nome": "Dona da Loja", "role": "admin"}
            st.rerun()
        elif email == "vendedor@dekids.com":
            st.session_state["usuario"] = {"nome": "Funcionário Caixa", "role": "funcionario"}
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")
else:
    u = st.session_state["usuario"]
    st.success(f"Bem-vindo(a), {u['nome']} | Nível de Acesso: **{u['role'].upper()}**")
    
    # Painel de resumo rápido (Dashboard)
    st.write("---")
    st.subheader("📊 Resumo do Dia")
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Vendas Hoje", value="R$ 1.250,00", delta="+12%")
    col2.metric(label="Peças Vendidas", value="18 peças")
    col3.metric(label="Alertas de Estoque Baixo", value="3 itens", delta="-1", delta_color="inverse")

    if st.button("Sair / Logoff"):
        st.session_state["usuario"] = None
        st.rerun()