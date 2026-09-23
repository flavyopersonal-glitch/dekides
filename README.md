# DeKids — Neon

Sistema de estoque, PDV, compras, usuários e fluxo de caixa. Backend FastAPI, telas Streamlit, PostgreSQL e autenticação gerenciada no Neon. O aplicativo não depende mais do Supabase.

## Primeiro acesso

O ambiente configurado já tem o acesso provisório **Monica**. Use a senha provisória combinada e complete o cadastro com nome, e-mail e uma senha definitiva de pelo menos 8 caracteres. Depois disso, entre com **Monica** ou com o e-mail cadastrado, usando a nova senha.

A senha provisória é armazenada apenas como hash com salt no banco e deixa de funcionar quando o cadastro é concluído. Esse acesso permite somente configurar a conta; ele não dá acesso às operações da loja. As demais contas são criadas por um administrador na tela Usuários.

## Iniciar no Windows

Na pasta do projeto, execute `powershell -ExecutionPolicy Bypass -File iniciar.ps1`.

Abra **http://localhost:8501**. O script inicia API e telas em segundo plano, acessíveis somente neste computador, com registros em `.logs/`. Execute `parar.ps1` para encerrar os processos que ele iniciou.

## Instalação em outro ambiente

1. Use Python 3.11 e um ambiente virtual.
2. Instale `pip install -r requirements.txt`.
3. Configure o `.env` com base em `.env.example`. A API precisa de `DATABASE_URL` (pooled), `DATABASE_URL_UNPOOLED` (migrações) e `NEON_AUTH_BASE_URL`. Nunca envie essas credenciais ao navegador ou ao GitHub.
4. O `neon.ts` declara `auth: true`. Se estiver provisionando outro ambiente, vincule a branch correta e execute `neon deploy`.
5. Aplique `python -m app.manage migrate`. Migrações versionadas ficam em `migrations/`; o comando usa a conexão direta, transação e verifica checksums. Não execute os SQL da pasta `supabase/`: são arquivos históricos da versão anterior.
6. Apenas em um banco novo: `python -m app.manage bootstrap --username Monica`. A senha provisória é solicitada sem aparecer no terminal; não há senha padrão no código.
7. API: `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
8. Telas: `streamlit run frontend/Home.py --server.address=127.0.0.1 --server.port=8501`.

## Autenticação e permissões

O login definitivo usa a API HTTP do Neon Auth. A API do DeKids transporta a sessão assinada como um token opaco e consulta `/get-session` com o cache de cookies desativado, além de conferir o perfil ativo no banco. Logout revoga a sessão no provedor. Não há sessão global compartilhada nem senha definitiva armazenada pelo DeKids.

Contas no Neon Auth sem perfil em `dekids.usuarios` não têm acesso ao sistema. Um cadastro interrompido pode ser retomado com o mesmo e-mail e senha; o perfil é concedido somente depois da confirmação da identidade. Somente Master pode criar outro Master. Funcionários podem consultar estoque e vender, mas não acessar finanças, compras ou cadastro de produtos/usuários.

O primeiro acesso exige um token temporário de 15 minutos. Após começar o cadastro, uma repetição deve usar o mesmo e-mail. Limites de tentativas são persistidos no banco. As contas definitivas usam senhas de no mínimo 8 caracteres.

A origem usada pelo backend no Neon Auth é `NEON_AUTH_ORIGIN`, por padrão `http://localhost:8501`. Ao publicar em outro domínio, configure essa origem e autorize-a com `neon neon-auth domain add https://seu-dominio` na branch correta. O fluxo atual não exige envio de e-mail ou verificação por e-mail; recuperação e verificação por e-mail não fazem parte desta versão.

## Consistência das operações

- Compras e vendas exigem UUID `operacao_id`. Repetir o mesmo identificador com os mesmos dados devolve o resultado anterior sem duplicar estoque ou caixa.
- Se houver falha de conexão, a tela mantém a tentativa pendente. Não feche a aba antes da confirmação; o estado da tela não sobrevive à reinicialização do Streamlit.
- Valores são calculados com Decimal e enviados como strings. API e banco conferem totais, quantidades, descontos e variações repetidas.
- Estoque é bloqueado em ordem fixa durante a transação, impedindo venda acima do disponível mesmo com dois caixas simultâneos.
- Produto e variações são cadastrados em uma transação. O financeiro é agregado no banco, sem depender da página de lançamentos.
- O pool reutiliza até cinco conexões e libera conexões ociosas. As consultas de produtos paginam e selecionam somente as colunas necessárias.

## Testes

`python -B -m unittest discover -s tests -v` executa os testes locais, sem chamadas externas.

`tests/integration_neon.py` verifica os fluxos reais na branch temporária: primeiro acesso, login, sessão, produtos, compras, vendas, repetição, concorrência, permissões e logout. Ele exige `DEKIDS_ENV_FILE=.env.neon-test`, compara as credenciais com produção e recusa bancos com usuários existentes. Use uma branch descartável nova para repetir o teste completo; não execute em produção.

A branch `dekids-validacao` foi criada com expiração automática em 23/09/2026. As configurações locais principais continuam apontando para `production`.

## Hospedagem

Neon hospeda banco e autenticação. A API Python e o Streamlit ainda precisam executar no computador da loja ou em um provedor de hospedagem. Existem Dockerfiles separados. Configure os segredos no provedor, aplique as migrações antes de iniciar a nova versão e defina `DEKIDS_API_URL` para a URL da API no serviço Streamlit.

A disponibilidade da API pode ser verificada em `/health/ready/`. Nenhum dado do Supabase foi importado.


## Render — serviço único gratuito

Use o serviço Docker existente `dekides`, branch `main`, Dockerfile `./Dockerfile`, sem substituir o Docker Command. O Dockerfile principal inicia a API internamente e as telas na porta PORT fornecida pelo Render. Não é necessário criar outro serviço ou banco no Render.

Variáveis obrigatórias: `DATABASE_URL` (conexão pooled da branch production do Neon) e `NEON_AUTH_BASE_URL` (URL pública do Neon Auth). Configure também `NEON_AUTH_ORIGIN=https://dekides.onrender.com` e autorize esse domínio no Neon Auth. As credenciais nunca devem ser colocadas no repositório.

Health check: `/_stcore/health`. Não defina `DEKIDS_API_URL` externo: o iniciador configura a comunicação interna. `DATABASE_URL_UNPOOLED` só é necessário para executar migrações; o banco atual já foi preparado. Migrações futuras são executadas pelo administrador antes de publicar a nova versão.

A instância gratuita pode suspender por inatividade e demora a acordar. Carrinhos e sessões da tela não persistem em reinícios, mas produtos, vendas e usuários ficam no Neon. O `render.yaml` documenta a configuração para novos ambientes; não crie um Blueprint duplicado para o serviço existente.
