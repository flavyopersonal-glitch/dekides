"""Teste real e descartável. Executar apenas com DEKIDS_ENV_FILE=.env.neon-test."""
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from dotenv import dotenv_values

if os.getenv("DEKIDS_ENV_FILE") != ".env.neon-test":
    raise SystemExit("Este teste exige a branch temporária .env.neon-test.")
test_env = dotenv_values(".env.neon-test")
production = dotenv_values(".env")
if test_env.get("DATABASE_URL") == production.get("DATABASE_URL"):
    raise SystemExit("Não execute contra produção.")

from fastapi.testclient import TestClient
from app.main import app
from app.manage import bootstrap
from app.database import connection


def expect(response, status):
    if response.status_code != status:
        # Nunca imprimir tokens, senhas ou respostas de login.
        raise AssertionError(f"Esperado {status}; recebido {response.status_code}: {response.json().get('detail', 'resposta inesperada')}")
    return response.json()


with connection() as conn:
    exists = conn.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone()
if exists:
    raise SystemExit("Branch de teste já utilizada. Use uma branch nova para repetir este teste.")
password = secrets.token_urlsafe(24)
bootstrap("Monica", password)
with TestClient(app) as client:
    expect(client.get("/health/ready/"), 200)
    expect(client.get("/produtos/"), 401)
    expect(client.post("/auth/login/",json={"email":"Monica","senha":"incorreta"}),401)
    setup = expect(client.post("/auth/login/",json={"email":"Monica","senha":password}),200)
    assert setup["primeiro_acesso"] and "access_token" not in setup
    expect(client.get("/produtos/",headers={"Authorization":"Bearer "+setup["setup_token"]}),401)
    email = "dekids-"+secrets.token_hex(6)+"@example.com"
    new_password=secrets.token_urlsafe(24)
    session=expect(client.post("/auth/primeiro-acesso/",json={"setup_token":setup["setup_token"],"nome":"Monica","email":email,"senha":new_password}),200)
    headers={"Authorization":"Bearer "+session["access_token"]}
    expect(client.post("/auth/login/",json={"email":"Monica","senha":password}),401)
    expect(client.post("/auth/login/",json={"email":"Monica","senha":new_password}),200)
    expect(client.post("/auth/refresh/",json={"refresh_token":session["refresh_token"]}),200)
    print("OK: primeiro acesso, troca da senha, sessão e renovação",flush=True)
    created=expect(client.post("/produtos/cadastro/",headers=headers,json={"nome":"Blusa teste","preco_venda":"10.00","variacoes":[{"tamanho":"P","cor":"Azul","estoque_atual":5}]}),201)
    products=expect(client.get("/produtos/",headers=headers),200)
    variant=next(p for p in products if p["id"]==created["produto_id"])["variacoes_produto"][0]["id"]
    sale={"operacao_id":str(uuid4()),"valor_total":"20.00","desconto":"1.00","forma_pagamento":"pix","itens":[{"variacao_id":variant,"quantidade":2,"preco_unitario_pago":"10.00"}]}
    one=expect(client.post("/vendas/",headers=headers,json=sale),201)
    two=expect(client.post("/vendas/",headers=headers,json=sale),201)
    assert one["venda_id"]==two["venda_id"]
    expect(client.post("/vendas/",headers=headers,json={**sale,"valor_total":"1.00"}),422)
    expect(client.post("/vendas/",headers=headers,json={**sale,"valor_total":"40.00","itens":sale["itens"]*2}),422)
    buy={"operacao_id":str(uuid4()),"valor_total":"4.00","itens":[{"variacao_id":variant,"quantidade":2,"custo_unitario":"2.00"}]}
    c1=expect(client.post("/compras/entrada/",headers=headers,json=buy),201)
    c2=expect(client.post("/compras/entrada/",headers=headers,json=buy),201)
    assert c1["compra_id"]==c2["compra_id"]
    totals=expect(client.get("/financeiro/resumo/",headers=headers),200)
    assert totals=={"entradas":"19.00","saidas":"4.00"},totals
    def concurrent_sale(_):
        data={**sale,"operacao_id":str(uuid4()),"valor_total":"40.00","desconto":"0","itens":[{"variacao_id":variant,"quantidade":4,"preco_unitario_pago":"10.00"}]}
        return client.post("/vendas/",headers=headers,json=data).status_code
    with ThreadPoolExecutor(max_workers=2) as workers:
        statuses=list(workers.map(concurrent_sale,range(2)))
    assert sorted(statuses)==[201,409],statuses
    print("OK: produtos, compras, vendas, financeiro, idempotência e concorrência",flush=True)
    staff_email="func-"+secrets.token_hex(6)+"@example.com"
    staff_password=secrets.token_urlsafe(24)
    expect(client.post("/usuarios/cadastro/",headers=headers,json={"nome":"Funcionário","email":staff_email,"senha":staff_password,"role":"funcionario"}),201)
    staff=expect(client.post("/auth/login/",json={"email":staff_email,"senha":staff_password}),200)
    sh={"Authorization":"Bearer "+staff["access_token"]}
    expect(client.get("/financeiro/resumo/",headers=sh),403)
    expect(client.post("/compras/entrada/",headers=sh,json=buy),403)
    expect(client.get("/produtos/",headers=sh),200)
    expect(client.post("/auth/logout/",headers=headers),200)
    expect(client.get("/auth/me/",headers=headers),401)
    print("OK: criação de usuário, permissões e revogação de sessão",flush=True)
print("Integração Neon aprovada.")
