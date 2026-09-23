import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "frontend"))
import api_client

class Pages(unittest.TestCase):
    def test_paginas_sem_login(self):
        for page in Path("frontend/pages").glob("*.py"):
            with self.subTest(page=page.name):
                at = AppTest.from_file(str(page), default_timeout=20).run()
                self.assertEqual(len(at.exception),0)
                self.assertTrue(len(at.warning))

    def test_paginas_gestor(self):
        def response(method,path,**kwargs):
            data = {"entradas":"10.00","saidas":"2.00"} if path.endswith("resumo/") else []
            return SimpleNamespace(ok=True,status_code=200,json=lambda:data)
        for page in Path("frontend/pages").glob("*.py"):
            with self.subTest(page=page.name), patch.object(api_client,"request",side_effect=response), patch.object(api_client,"listar_todos",return_value=[]):
                at = AppTest.from_file(str(page), default_timeout=20)
                at.session_state["usuario"] = {"id":"u","nome":"Teste","role":"master"}
                at.run()
                self.assertEqual(len(at.exception),0)

    def test_pdv_centavos(self):
        produto = {"id":"p","nome":"Blusa","preco_venda":"0.10","variacoes_produto":[{"id":"v","tamanho":"P","cor":"Azul","estoque_atual":5}]}
        with patch.object(api_client,"listar_todos",return_value=[produto]):
            at = AppTest.from_file("frontend/pages/2_PDV.py", default_timeout=20)
            at.session_state["usuario"] = {"id":"u","nome":"Teste","role":"admin"}
            at.run()
            at.number_input[0].set_value(3).run()
            at.button[0].click().run()
            self.assertEqual(at.session_state["carrinho"][0]["preco_unitario_pago"],"0.10")
            concluir = next(b for b in at.button if b.label=="Concluir venda")
            with patch.object(api_client,"request",return_value=SimpleNamespace(ok=False,status_code=503,json=lambda:{"detail":"Sem confirmação"})):
                concluir.click().run()
            self.assertEqual(at.session_state["venda_pendente"]["valor_total"],"0.30")
            self.assertEqual(len(at.exception),0)


    def test_login_provisorio_abre_cadastro(self):
        resposta = SimpleNamespace(ok=True, json=lambda: {
            "primeiro_acesso": True, "setup_token": "teste-token", "nome": "Monica"})
        at = AppTest.from_file("frontend/Home.py", default_timeout=20).run()
        at.text_input[0].set_value("Monica")
        at.text_input[1].set_value("senha-de-teste")
        with patch("requests.post", return_value=resposta):
            at.button[0].click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual([field.label for field in at.text_input],
                         ["Nome", "E-mail", "Nova senha (mínimo de 8 caracteres)", "Confirme a nova senha"])
        self.assertEqual(at.session_state["setup_token"], "teste-token")

    def test_cadastro_com_estado_da_versao_anterior(self):
        at = AppTest.from_file("frontend/Home.py", default_timeout=20)
        at.session_state["primeiro_acesso"] = True
        at.session_state["setup_token"] = "teste-token"
        at.session_state["nome"] = "Monica"
        at.run()
        self.assertEqual(len(at.exception), 0)
        at.text_input[1].set_value("teste@example.com")
        at.text_input[2].set_value("senha-de-teste")
        at.text_input[3].set_value("senha-de-teste")
        resposta = SimpleNamespace(ok=True, json=lambda: {
            "access_token": "teste", "refresh_token": "teste",
            "usuario": {"id": "teste", "nome": "Monica", "role": "master"}})
        with patch("requests.post", return_value=resposta) as post:
            at.button[0].click().run()
            self.assertEqual(post.call_args.kwargs["json"]["setup_token"], "teste-token")
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(at.session_state["usuario"]["nome"], "Monica")
        self.assertTrue(any("Bem-vindo" in message.value for message in at.success))
