import streamlit as st
import requests

st.set_page_config(page_title="Gerenciamento de Estoque", page_icon="📦", layout="wide")

API_URL = "https://dekides.onrender.com"

# --- VERIFICAÇÃO DE LOGIN ---
if "usuario" not in st.session_state or st.session_state["usuario"] is None:
    st.warning("🔒 Por favor, faça login na página Home para acessar o estoque.")
else:
    u = st.session_state["usuario"]
    
    st.title("📦 Controle de Estoque e Grade de Produtos")
    
    # Criamos duas abas na tela: uma para ver o estoque e outra para cadastrar
    aba_consulta, aba_cadastro = st.tabs(["🔎 Consultar Estoque", "➕ Cadastrar Novo Produto"])
    
    # =========================================================================
    # ABA 1: CONSULTA DE ESTOQUE (Todos os níveis têm acesso)
    # =========================================================================
    with aba_consulta:
        st.subheader("👕 Peças e Variações em Loja")
        
        if st.button("🔄 Atualizar Lista"):
            st.rerun()
            
        try:
            # Busca a lista de produtos atualizada direto do Render
            # Nota: Em produção, passaríamos o Token de autenticação no header
            response = requests.get(f"{API_URL}/produtos/")
            
            if response.status_code == 200:
                produtos = response.json()
                
                if not produtos:
                    st.info("Nenhum produto cadastrado no momento.")
                
                for prod in produtos:
                    # Cria um painel expansível para cada produto "Pai"
                    with st.expander(f"🔹 {prod['nome']} - R$ {prod['preco_venda']:.2f} ({prod['marca']})"):
                        st.write(f"**Descrição:** {prod['descricao']} | **Categoria:** {prod['categoria']}")
                        
                        # Se o produto tiver variações de tamanho/cor, mostra em uma tabela
                        if prod.get("variacoes_produto"):
                            st.write("**Grade de Tamanhos e Cores:**")
                            
                            # Formatando a tabela de variações para exibição limpa
                            grade_dados = []
                            for var in prod["variacoes_produto"]:
                                grade_dados.append({
                                    "Código de Barras": var.get("codigo_barras", "N/A"),
                                    "Tamanho": var["tamanho"],
                                    "Cor": var["cor"],
                                    "Estoque Atual": var["estoque_atual"],
                                    "Estoque Mínimo": var["estoque_minimo"]
                                })
                            st.table(grade_dados)
                        else:
                            st.warning("Este produto não possui grade ou variações cadastradas.")
            else:
                st.error(f"Erro ao buscar produtos do backend: {response.status_code}")
        except Exception as e:
            st.error(f"Não foi possível conectar à API: {str(e)}")

    # =========================================================================
    # ABA 2: CADASTRO DE PRODUTOS (Bloqueado para Funcionários comuns)
    # =========================================================================
    with aba_cadastro:
        st.subheader("📝 Formulinho de Entrada de Peças")
        
        if u["role"] not in ["master", "admin"]:
            st.error("🚫 Desculpe, seu nível de acesso não permite cadastrar novos produtos.")
        else:
            with st.form("form_cadastro_produto"):
                col1, col2 = st.columns(2)
                with col1:
                    nome_prod = st.text_input("Nome do Produto (Ex: Vestido Festa Tulipa)", placeholder="Obrigatório")
                    marca_prod = st.text_input("Marca (Ex: Kyly, Brandili)", value="DeKids")
                    categoria_prod = st.selectbox("Categoria", ["Conjuntos", "Bodys", "Vestidos", "Calças/Bermudas", "Acessórios"])
                
                with col2:
                    preco_venda = st.number_input("Preço de Venda ao Consumidor (R$)", min_value=0.0, step=1.0, value=59.90)
                    descricao_prod = st.text_area("Descrição da Peça", placeholder="Detalhes como tecido, estampas...")
                
                st.write("---")
                st.markdown("### 📏 Configurar Grade Inicial (Tamanhos e Cores)")
                st.caption("Adicione pelo menos 1 variação para inicializar o produto com estoque.")
                
                # Criamos campos dinâmicos simplificados para adicionar até 3 variações de uma vez no form
                variacoes_lista = []
                col_t, col_c, col_e, col_b = st.columns([1, 1, 1, 2])
                
                with col_t:
                    t1 = st.text_input("Tamanho 1", value="P")
                    t2 = st.text_input("Tamanho 2", value="M")
                with col_c:
                    c1 = st.text_input("Cor 1", value="Única")
                    c2 = st.text_input("Cor 2", value="Única")
                with col_e:
                    e1 = st.number_input("Qtd Inicial 1", min_value=0, value=5)
                    e2 = st.number_input("Qtd Inicial 2", min_value=0, value=5)
                with col_b:
                    b1 = st.text_input("Cód. Barras 1", placeholder="Opcional")
                    b2 = st.text_input("Cód. Barras 2", placeholder="Opcional")
                
                # Monta a estrutura JSON se os campos forem preenchidos
                if t1:
                    variacoes_lista.append({"tamanho": t1, "cor": c1, "estoque_atual": e1, "estoque_minimo": 2, "codigo_barras": b1 if b1 else None})
                if t2:
                    variacoes_lista.append({"tamanho": t2, "cor": c2, "estoque_atual": e2, "estoque_minimo": 2, "codigo_barras": b2 if b2 else None})
                
                botao_enviar = st.form_submit_button("💾 Salvar Produto e Grade")
                
                if botao_enviar:
                    if not nome_prod:
                        st.error("O campo 'Nome do Produto' é obrigatório.")
                    else:
                        # Monta o JSON exato esperado pela sua API FastAPI
                        payload = {
                            "nome": nome_prod,
                            "descricao": descricao_prod,
                            "categoria": categoria_prod,
                            "marca": marca_prod,
                            "preco_venda": preco_venda,
                            "variacoes": variacoes_lista
                        }
                        
                        try:
                            # Faz o envio para o servidor online no Render
                            headers = {"Authorization": "Bearer TOKEN_MOCKADO_PARA_TESTES"}
                            response = requests.post(f"{API_URL}/produtos/cadastro/", json=payload)
                            
                            if response.status_code == 200:
                                st.success(f"🎉 Sucesso! Produto '{nome_prod}' e suas variações foram registrados.")
                                st.balloons()
                            else:
                                st.error(f"Erro no servidor ({response.status_code}): {response.text}")
                        except Exception as e:
                            st.error(f"Falha de comunicação com o servidor: {str(e)}")