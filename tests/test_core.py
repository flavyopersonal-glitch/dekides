import os
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

# Não usa credenciais reais nem faz chamadas externas.
os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_KEY"] = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiJ9.test"
os.environ["SUPABASE_SERVICE_KEY"] = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.test"
from app.schemas import VendaCriacao, CompraEntrada
from frontend.money import dinheiro, total_itens
from pydantic import ValidationError
from fastapi.testclient import TestClient
from app.main import app
from app.auth import verificar_perfil
import app.main as main


def venda():
    return dict(operacao_id=str(uuid4()), valor_total="0.30", forma_pagamento="pix",
                itens=[dict(variacao_id=str(uuid4()), quantidade=3, preco_unitario_pago="0.10")])


class Validacoes(unittest.TestCase):
    def test_centavos(self):
        dados = venda()
        dados["valor_total"] = str(total_itens(dados["itens"]))
        self.assertEqual(VendaCriacao(**dados).valor_total, Decimal("0.30"))
        self.assertEqual(dinheiro(3 * 0.1), Decimal("0.30"))

    def test_total_incorreto(self):
        dados = venda(); dados["valor_total"] = "1.00"
        with self.assertRaises(ValidationError): VendaCriacao(**dados)

    def test_duplicados(self):
        dados = venda(); dados["itens"] *= 2; dados["valor_total"] = "0.60"
        with self.assertRaises(ValidationError): VendaCriacao(**dados)

    def test_desconto(self):
        dados = venda(); dados["desconto"] = "0.31"
        with self.assertRaises(ValidationError): VendaCriacao(**dados)

    def test_compra_total(self):
        with self.assertRaises(ValidationError):
            CompraEntrada(operacao_id=uuid4(), valor_total="1", itens=[dict(variacao_id=uuid4(),quantidade=2,custo_unitario="10")])


class API(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.perfil = dict(id=str(uuid4()), nome="Teste", role="admin")
        app.dependency_overrides[verificar_perfil] = lambda: self.perfil
        self.patcher = patch.object(main, "supabase_admin")
        self.db = self.patcher.start()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.patcher.stop()
        self.client.close()

    def test_sem_token(self):
        app.dependency_overrides.clear()
        self.assertEqual(self.client.get("/produtos/").status_code, 401)

    def test_funcionario_sem_financeiro(self):
        self.perfil["role"] = "funcionario"
        self.assertEqual(self.client.get("/financeiro/resumo/").status_code, 403)
        self.db.rpc.assert_not_called()

    def test_admin_nao_cria_master(self):
        response = self.client.post("/usuarios/cadastro/", json=dict(nome="Teste",email="a@b.com",senha="12345678",role="master"))
        self.assertEqual(response.status_code, 403)
        self.db.auth.admin.create_user.assert_not_called()

    def test_venda_invalida_nao_grava(self):
        dados = venda(); dados["valor_total"] = "9"
        self.assertEqual(self.client.post("/vendas/",json=dados).status_code,422)
        self.db.rpc.assert_not_called()

    def test_identificador_preservado(self):
        dados = venda()
        self.db.rpc.return_value.execute.return_value.data = {"venda_id":"id"}
        for _ in range(2): self.assertEqual(self.client.post("/vendas/",json=dados).status_code,201)
        chamadas = self.db.rpc.call_args_list
        self.assertEqual(chamadas[0],chamadas[1])
        self.assertEqual(chamadas[0].args[1]["p_venda"]["operacao_id"],dados["operacao_id"])

    def test_produto_usa_transacao(self):
        self.db.rpc.return_value.execute.return_value.data = {"produto_id":"id"}
        response = self.client.post("/produtos/cadastro/",json=dict(nome="Blusa",preco_venda="10"))
        self.assertEqual(response.status_code,201)
        self.assertEqual(self.db.rpc.call_args.args[0],"cadastrar_produto")
        self.db.table.assert_not_called()

    def test_paginacao(self):
        query = self.db.table.return_value.select.return_value.order.return_value
        query.range.return_value.execute.return_value.data = []
        self.assertEqual(self.client.get("/produtos/?offset=100&limite=50").status_code,200)
        query.range.assert_called_once_with(100,149)
        self.assertEqual(self.client.get("/produtos/?limite=501").status_code,422)

    def test_logins_isolados(self):
        clientes = [MagicMock(),MagicMock()]
        for i,c in enumerate(clientes):
            c.auth.sign_in_with_password.return_value = SimpleNamespace(user=SimpleNamespace(id=str(i)),session=SimpleNamespace(access_token=str(i),refresh_token="r"))
        self.db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = dict(nome="Teste",role="admin",ativo=True)
        with patch.object(main,"cliente_auth",side_effect=clientes):
            tokens = [self.client.post("/auth/login/",json=dict(email="a@b.com",senha="12345678")).json()["access_token"] for _ in clientes]
        self.assertEqual(tokens,["0","1"])
        self.db.auth.sign_in_with_password.assert_not_called()

    def test_refresh_inativo(self):
        self.db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = dict(nome="Teste",role="admin",ativo=False)
        with patch.object(main,"cliente_auth") as factory:
            factory.return_value.auth.refresh_session.return_value = SimpleNamespace(user=SimpleNamespace(id="u"),session=SimpleNamespace(access_token="a",refresh_token="r"))
            self.assertEqual(self.client.post("/auth/refresh/",json={"refresh_token":"r"}).status_code,403)

if __name__ == "__main__": unittest.main()
