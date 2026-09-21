import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
from frontend import api_client

class State(dict):
    def __getattr__(self, key): return self[key]

class Frontend(unittest.TestCase):
    def test_logout_limpa_carrinho(self):
        state = State(usuario={},access_token="a",refresh_token="r",carrinho=[1])
        with patch.object(api_client.st,"session_state",state): api_client.logout()
        self.assertEqual(state,{})

    def test_paginacao_continua_apos_pagina_curta(self):
        responses = [SimpleNamespace(ok=True,json=lambda:[1,2]),SimpleNamespace(ok=True,json=lambda:[3]),SimpleNamespace(ok=True,json=lambda:[])]
        with patch.object(api_client,"request",side_effect=responses) as request:
            self.assertEqual(api_client.listar_todos("/produtos/"),[1,2,3])
            self.assertEqual(request.call_args_list[2].kwargs["params"]["offset"],3)

    def test_renovacao_reenvia_mesmo_payload(self):
        state = State(access_token="old",refresh_token="r")
        responses = [SimpleNamespace(status_code=401),SimpleNamespace(status_code=201)]
        refresh = SimpleNamespace(ok=True,json=lambda:dict(access_token="new",refresh_token="r2"))
        with patch.object(api_client.st,"session_state",state), patch.object(api_client.requests,"request",side_effect=responses) as request, patch.object(api_client.requests,"post",return_value=refresh):
            payload = {"operacao_id":"same"}
            self.assertEqual(api_client.request("POST","/vendas/",json=payload).status_code,201)
            self.assertEqual(request.call_args_list[1].kwargs["headers"]["Authorization"],"Bearer new")
            self.assertIs(request.call_args_list[1].kwargs["json"],payload)

    def test_erros_legiveis(self):
        response = SimpleNamespace(json=lambda:{"detail":[{"msg":"Total inválido"}]})
        self.assertEqual(api_client.api_error(response),"Total inválido")
