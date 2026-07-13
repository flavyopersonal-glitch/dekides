import os

import requests
import streamlit as st

API_URL = os.getenv("DEKIDS_API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 15


def headers() -> dict:
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def request(method: str, path: str, **kwargs) -> requests.Response:
    return requests.request(method, f"{API_URL}{path}", headers=headers(), timeout=TIMEOUT, **kwargs)


def api_error(response: requests.Response) -> str:
    try:
        return response.json().get("detail", "Erro inesperado na API.")
    except ValueError:
        return "A API retornou uma resposta inválida."


def logout() -> None:
    for chave in ("usuario", "access_token", "refresh_token"):
        st.session_state.pop(chave, None)
