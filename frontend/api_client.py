import os

import requests
import streamlit as st

API_URL = os.getenv("DEKIDS_API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 15


def headers() -> dict:
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def request(method: str, path: str, **kwargs) -> requests.Response:
    resposta = requests.request(method, f"{API_URL}{path}", headers=headers(), timeout=TIMEOUT, **kwargs)
    if resposta.status_code == 401 and st.session_state.get("refresh_token"):
        renovacao = requests.post(f"{API_URL}/auth/refresh/", json={"refresh_token": st.session_state.refresh_token}, timeout=TIMEOUT)
        if renovacao.ok:
            st.session_state.update(renovacao.json())
            resposta = requests.request(method, f"{API_URL}{path}", headers=headers(), timeout=TIMEOUT, **kwargs)
        elif renovacao.status_code in (401, 403):
            pendentes = {k: st.session_state[k] for k in ("venda_pendente", "compra_pendente") if k in st.session_state}
            dono = st.session_state.get("usuario", {}).get("id")
            logout()
            if pendentes:
                st.session_state.update(pendentes)
                st.session_state["operacao_dono"] = dono
            st.warning("Sessão expirada. Entre novamente na Home.")
            st.stop()
    return resposta


def api_error(response: requests.Response) -> str:
    try:
        detail = response.json().get("detail", "Erro inesperado na API.")
        if isinstance(detail, list):
            return "; ".join(str(item.get("msg", "Dados inválidos")) for item in detail)
        return str(detail)
    except ValueError:
        return "A API retornou uma resposta inválida."


def logout() -> None:
    for chave in list(st.session_state):
        st.session_state.pop(chave, None)


def listar_todos(path):
    itens = []
    while True:
        resposta = request("GET", path, params={"offset": len(itens), "limite": 100})
        if not resposta.ok:
            raise ValueError(api_error(resposta))
        pagina = resposta.json()
        if not pagina:
            return itens
        itens.extend(pagina)
