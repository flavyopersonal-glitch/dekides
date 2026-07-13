# DeKids

Sistema de estoque, PDV e fluxo de caixa para moda infantil.

## Execução local

1. Crie um ambiente virtual e instale `pip install -r requirements.txt`.
2. Configure `.env` com `SUPABASE_URL`, `SUPABASE_KEY` e `SUPABASE_SERVICE_KEY`. A chave de serviço fica somente no backend.
3. Aplique `supabase/migrations/202607130001_operacoes_atomicas.sql` no SQL Editor do Supabase. Desative triggers antigos que também baixem estoque ou criem lançamentos de venda.
4. Inicie a API: `uvicorn app.main:app --reload`.
5. Em outro terminal, defina `DEKIDS_API_URL=http://localhost:8000` e inicie `streamlit run frontend/Home.py`.

Para deploy, defina as variáveis no provedor; não copie o `.env` para imagens Docker.
