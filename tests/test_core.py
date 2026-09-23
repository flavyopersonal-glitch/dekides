import os
import unittest
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError
from app import auth
from app.main import app
import app.main as main
from app.schemas import VendaCriacao, CompraEntrada, PrimeiroAcesso
from frontend.money import dinheiro, total_itens


def venda():
    return {"operacao_id":str(uuid4()),"valor_total":"0.30","forma_pagamento":"pix", "itens":[{"variacao_id":str(uuid4()),"quantidade":3,"preco_unitario_pago":"0.10"}]}


class Validacoes(unittest.TestCase):
    def test_centavos(self):
        dados=venda(); dados["valor_total"]=str(total_itens(dados["itens"]))
        self.assertEqual(VendaCriacao(**dados).valor_total,Decimal("0.30"))
        self.assertEqual(dinheiro(3*0.1),Decimal("0.30"))

    def test_total_incorreto(self):
        with self.assertRaises(ValidationError): VendaCriacao(**{**venda(),"valor_total":"1"})

    def test_duplicados(self):
        dados=venda(); dados["itens"]*=2; dados["valor_total"]="0.60"
        with self.assertRaises(ValidationError): VendaCriacao(**dados)

    def test_desconto(self):
        with self.assertRaises(ValidationError): VendaCriacao(**{**venda(),"desconto":"1"})

    def test_compra_total(self):
        with self.assertRaises(ValidationError): CompraEntrada(operacao_id=uuid4(),valor_total="1",itens=[dict(variacao_id=uuid4(),quantidade=2,custo_unitario="10")])

    def test_senha_definitiva(self):
        with self.assertRaises(ValidationError): PrimeiroAcesso(email="a@example.com",nome="Teste",senha="1234",setup_token="x"*32)

    def test_email_invalido(self):
        with self.assertRaises(ValidationError): PrimeiroAcesso(email="invalido",nome="Teste",senha="12345678",setup_token="x"*32)

    def test_hash_salgado(self):
        hashed=auth.hash_password("senha-teste")
        self.assertNotEqual(hashed,auth.hash_password("senha-teste"))
        self.assertTrue(auth.check_password("senha-teste",hashed))
        self.assertFalse(auth.check_password("errada",hashed))


class API(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(app)
        self.perfil=dict(id="u",nome="Teste",role="admin",ativo=True,email="a@example.com")
        app.dependency_overrides[auth.verificar_perfil]=lambda:self.perfil
        self.patch=patch.object(main,"connection")
        self.connection=self.patch.start()
        self.db=self.connection.return_value.__enter__.return_value

    def tearDown(self):
        app.dependency_overrides.clear(); self.patch.stop(); self.client.close()

    def test_sem_token(self):
        app.dependency_overrides.clear()
        self.assertEqual(self.client.get("/produtos/").status_code,401)

    def test_funcionario_sem_financeiro(self):
        self.perfil["role"]="funcionario"
        self.assertEqual(self.client.get("/financeiro/resumo/").status_code,403)
        self.db.execute.assert_not_called()

    def test_admin_nao_cria_master(self):
        response=self.client.post("/usuarios/cadastro/",json=dict(nome="Teste",email="a@example.com",senha="12345678",role="master"))
        self.assertEqual(response.status_code,403)

    def test_venda_invalida_nao_grava(self):
        response=self.client.post("/vendas/",json={**venda(),"valor_total":"99"})
        self.assertEqual(response.status_code,422)
        self.db.execute.assert_not_called()

    def test_identificador_preservado(self):
        dados=venda()
        self.db.execute.return_value.fetchone.return_value={"resultado":{"venda_id":"id"}}
        for _ in range(2): self.assertEqual(self.client.post("/vendas/",json=dados).status_code,201)
        calls=self.db.execute.call_args_list
        self.assertEqual(calls[0].args[1][1].obj,calls[1].args[1][1].obj)

    def test_produto_usa_transacao(self):
        self.db.execute.return_value.fetchone.return_value={"resultado":{"produto_id":"id"}}
        response=self.client.post("/produtos/cadastro/",json=dict(nome="Blusa",preco_venda="10"))
        self.assertEqual(response.status_code,201)
        self.connection.assert_called_once()

    def test_paginacao(self):
        self.db.execute.return_value.fetchall.return_value=[]
        self.assertEqual(self.client.get("/produtos/?offset=100&limite=50").status_code,200)
        self.assertEqual(self.db.execute.call_args.args[1],("%%",50,100))
        self.assertEqual(self.client.get("/produtos/?limite=501").status_code,422)

    def test_primeiro_acesso_sem_token_valido(self):
        self.db.execute.return_value.fetchone.return_value=None
        with patch.object(auth,"register_identity") as register:
            response=self.client.post("/auth/primeiro-acesso/",json=dict(nome="Teste",email="a@example.com",senha="12345678",setup_token="x"*32))
            self.assertEqual(response.status_code,401)
            register.assert_not_called()

    def test_refresh_perfil_inativo(self):
        self.db.execute.return_value.fetchone.return_value={**self.perfil,"ativo":False}
        with patch.object(auth,"remote_session",return_value=({"id":"u"},"token")):
            self.assertEqual(self.client.post("/auth/refresh/",json={"refresh_token":"token"}).status_code,403)

    def test_logout_revoga_no_provedor(self):
        with patch.object(auth,"neon_request",return_value=({},None)) as remote:
            self.assertEqual(self.client.post("/auth/logout/",headers={"Authorization":"Bearer token"}).status_code,200)
            remote.assert_called_once_with("POST","/sign-out",{},"token")


class NeonAuth(unittest.TestCase):
    def test_token_invalido_nao_faz_chamada(self):
        with patch.dict(os.environ,{"NEON_AUTH_BASE_URL":"https://auth.example.com"}), patch.object(auth.requests,"request") as request:
            with self.assertRaises(Exception) as error:
                auth.neon_request("GET","/get-session",token="not base64")
            self.assertEqual(error.exception.status_code,401)
            request.assert_not_called()

    def test_timeout_nao_invalida_sessao(self):
        with patch.dict(os.environ,{"NEON_AUTH_BASE_URL":"https://auth.example.com"}),patch.object(auth.requests,"request",side_effect=auth.requests.Timeout):
            with self.assertRaises(Exception) as error: auth.neon_request("GET","/get-session")
            self.assertEqual(error.exception.status_code,503)

    def test_recupera_cadastro_interrompido(self):
        from fastapi import HTTPException
        with patch.object(auth,"neon_request",side_effect=HTTPException(409,"existe")),patch.object(auth,"sign_in",return_value=({"id":"u"},"t")) as sign_in:
            self.assertEqual(auth.register_identity("a@example.com","senha","Teste"),({"id":"u"},"t"))
            sign_in.assert_called_once_with("a@example.com","senha")
