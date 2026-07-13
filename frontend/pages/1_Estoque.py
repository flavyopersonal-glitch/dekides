import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_client import api_error, request  # noqa: E402

st.set_page_config(page_title="Estoque", page_icon="📦", layout="wide")

if not st.session_state.get("usuario"):
    st.warning("Faça login na página Home para acessar o estoque.")
    st.stop()

usuario = st.session_state["usuario"]
st.title("📦 Controle de Estoque")
aba_consulta, aba_cadastro = st.tabs(["Consultar estoque", "Cadastrar produto"])

with aba_consulta:
    if st.button("Atualizar lista"):
        st.rerun()
    try:
        resposta = request("GET", "/produtos/")
        if resposta.ok:
            produtos = resposta.json()
            if not produtos:
                st.info("Nenhum produto cadastrado.")
            for produto in produtos:
                preco = float(produto["preco_venda"])
                with st.expander(f"{produto['nome']} — R$ {preco:.2f}"):
                    st.write(f"Marca: {produto.get('marca') or '-'} | Categoria: {produto.get('categoria') or '-'}")
                    if produto.get("descricao"):
                        st.caption(produto["descricao"])
                    variacoes = produto.get("variacoes_produto", [])
                    if variacoes:
                        st.dataframe(variacoes, use_container_width=True, hide_index=True)
                    else:
                        st.info("Produto sem variações cadastradas.")
        else:
            st.error(api_error(resposta))
    except Exception:
        st.error("Não foi possível carregar o estoque. Tente novamente.")

with aba_cadastro:
    if usuario["role"] not in {"master", "admin"}:
        st.error("Seu perfil não pode cadastrar produtos.")
    else:
        with st.form("produto"):
            nome = st.text_input("Nome do produto")
            marca = st.text_input("Marca", value="DeKids")
            categoria = st.text_input("Categoria")
            descricao = st.text_area("Descrição")
            preco = st.number_input("Preço de venda (R$)", min_value=0.01, value=59.90, step=1.0)
            st.caption("Cadastre uma variação inicial. Outras variações podem ser incluídas no banco posteriormente.")
            tamanho = st.text_input("Tamanho", value="P")
            cor = st.text_input("Cor", value="Única")
            quantidade = st.number_input("Quantidade inicial", min_value=0, value=0)
            codigo_barras = st.text_input("Código de barras (opcional)")
            salvar = st.form_submit_button("Salvar produto")
        if salvar:
            payload = {
                "nome": nome, "marca": marca or None, "categoria": categoria or None,
                "descricao": descricao or None, "preco_venda": preco,
                "variacoes": [{"tamanho": tamanho, "cor": cor, "estoque_atual": quantidade,
                                "codigo_barras": codigo_barras or None}],
            }
            try:
                resposta = request("POST", "/produtos/cadastro/", json=payload)
                if resposta.ok:
                    st.success("Produto e variação cadastrados.")
                else:
                    st.error(api_error(resposta))
            except Exception:
                st.error("Não foi possível salvar o produto.")
