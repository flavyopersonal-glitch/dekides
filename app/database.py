import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# A chave de serviço é necessária somente para criar contas. Em produção, use
# uma chave distinta da chave pública usada pelas chamadas normais.
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or SUPABASE_KEY

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL e SUPABASE_KEY devem estar configuradas.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
