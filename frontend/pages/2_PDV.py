import streamlit as st
import requests

st.set_page_config(page_title="PDV - Caixa", page_icon="🛒", layout="wide")

API_URL = "https://dekides.onrender.com"

# Proteção de Tela
if "usuario" not in st.session_state or st.session_state["usuario"] is None:
    st.warning("Por favor, faça login na página Home primeiro.")
else:
    st.title("🛒 Frente de Caixa - Lançar Venda")
    
    # 1. Seleção do Produto (Simulado - na prática busca do GET /produtos/)
    st.subheader("1. Adicionar Itens")
    produto_sel = st.selectbox("Selecione o Produto", ["Body Manga Curta Dino", "Conjunto Moletom Brandili", "Vestido Floral Gatinha"])
    tamanho_sel = st.radio("Tamanho", ["RN", "P", "M", "G", "2A", "4A"], horizontal=True)
    cor_sel = st.selectbox("Cor", ["Azul", "Rosa", "Verde", "Cinza"])
    quantidade = st.number_input("Quantidade", min_value=1, value=1)
    preco_un = st.number_input("Preço Unitário (R$)", min_value=0.0, value=49.90)
    
    if st.button("Adicionar ao Carrinho"):
        st.toast(f"{quantidade}x {produto_sel} ({tamanho_sel}/{cor_sel}) adicionado!")

    st.write("---")
    
    # 2. Fechamento da Venda
    st.subheader("2. Pagamento")
    forma_pagto = st.selectbox("Forma de Pagamento", ["pix", "credito", "debito", "dinheiro"])
    desconto = st.number_input("Desconto (R$)", min_value=0.0, value=0.0)
    
    total = (quantidade * preco_un) - desconto
    st.markdown(f"### 💰 Total a Pagar: **R$ {total:.2f}**")
    
    if st.button("🟢 Concluir e Emitir Venda"):
        # Aqui o frontend faz o POST para a rota /vendas/ do seu Render
        st.success("Venda enviada com sucesso! Estoque baixado e financeiro atualizado.")