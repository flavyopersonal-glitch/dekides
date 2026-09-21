# DeKids

Estoque, PDV, compras, usuários e fluxo de caixa para moda infantil.

## Preparação e atualização

1. Use Python 3.11, crie um ambiente virtual e execute `pip install -r requirements.txt`.
2. Copie `.env.example` para `.env` e preencha as três variáveis do Supabase. A chave de serviço é obrigatória, fica somente no backend e nunca deve ser enviada ao navegador.
3. Faça backup do banco existente. No SQL Editor do Supabase, aplique as migrations em ordem:
   - `202607130000_estrutura.sql`: cria as tabelas ausentes, sem apagar dados.
   - `202607130001_operacoes_atomicas.sql`: funções originais.
   - `202609200001_integridade.sql`: funções corrigidas, permissões, cadastro atômico e proteção contra duplicação.
4. Em bancos que já receberam a migration original, aplique a estrutura e a migration de integridade. Não reaplique a original depois da nova.
5. A migration de integridade interrompe a instalação se encontrar triggers ativos nas tabelas de compras/vendas. Revise esses triggers e desative somente os que duplicam estoque/financeiro. Ela também rejeita estoque negativo existente; reconcilie os registros antes de repetir. Revise triggers existentes em `auth.users` que criem perfis para evitar conflito com `dekids_criar_perfil`.
6. As tabelas ficam acessíveis exclusivamente pelo backend com `service_role`; clientes públicos não possuem acesso direto. Políticas RLS antigas não substituem a autorização da API.
7. Para criar o primeiro administrador, crie uma conta no painel Authentication do Supabase e insira em `public.usuarios` seu UUID, nome, `role = master` e `ativo = true`. Se o perfil já existir, atualize-o. Depois use a tela Usuários.
8. Inicie a API com `uvicorn app.main:app --reload`.
9. Em outro terminal PowerShell, configure `$env:DEKIDS_API_URL = "http://localhost:8000"` e execute `streamlit run frontend/Home.py`.

## Comportamento

- Login e renovação usam clientes de autenticação separados. A API valida token e perfil ativo em cada requisição protegida.
- Produtos e variações são criados em uma transação. Contas criadas pela API recebem perfil por trigger na mesma transação de `auth.users`; a role vem de metadados administrativos, nunca de metadados editáveis pelo usuário.
- Compras e vendas exigem `operacao_id` UUID. Reenvie o mesmo identificador **e os mesmos dados** após falhas de conexão. Alterar o conteúdo com o mesmo identificador é rejeitado.
- Totais devem corresponder à soma dos itens, com valores monetários decimais enviados como strings. Variações duplicadas são rejeitadas.
- A tela mantém operações pendentes durante novas tentativas e exige o mesmo usuário após expiração da sessão. Não feche a aba durante uma confirmação incerta: o estado da interface não é persistido após reinício do Streamlit.
- Listagens aceitam `offset` e `limite` (1 a 500). O saldo financeiro é agregado no banco, independentemente da página exibida.
- A tela de compras registra uma variação por operação; a API aceita até 500 itens.

## Verificação

Execute `python -B -m unittest discover -s tests -v`. Os testes usam credenciais fictícias e mocks; não acessam o Supabase.

O teste SQL `supabase/tests/integridade.sql` deve ser executado em um projeto de homologação após as migrations. Ele usa transação com rollback e verifica idempotência, estoque, valores e atomicidade. A execução das migrations e os testes de concorrência precisam ser validados no PostgreSQL real antes de produção.

## Deploy

Existem Dockerfiles separados para API e Streamlit. Configure segredos no provedor; não copie `.env` para imagens. Aplique as migrations antes de publicar a nova API. A nova versão exige `operacao_id` nas compras/vendas e a chave de serviço; atualize clientes externos junto com o backend.
