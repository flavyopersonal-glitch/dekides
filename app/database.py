import os
from dotenv import load_dotenv
from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
if not all((SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY)):
    raise RuntimeError("Configure SUPABASE_URL, SUPABASE_KEY e SUPABASE_SERVICE_KEY.")


def cliente_auth() -> Client:
    # Cada operação recebe sua própria sessão, sem renovação em segundo plano.
    return create_client(SUPABASE_URL, SUPABASE_KEY,
                         options=ClientOptions(auto_refresh_token=False, persist_session=False))


# Nunca faça login neste cliente. As permissões são verificadas pela API.
supabase_admin: Client = create_client(
    SUPABASE_URL, SUPABASE_SERVICE_KEY,
    options=ClientOptions(auto_refresh_token=False, persist_session=False),
)
