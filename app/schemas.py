from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Role = Literal["master", "admin", "funcionario"]


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    senha: str = Field(min_length=6, max_length=128)

    @field_validator("email")
    @classmethod
    def validar_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("Informe um e-mail válido.")
        return value


class UsuarioCadastro(Login):
    nome: str = Field(min_length=2, max_length=120)
    role: Role


class VariacaoProduto(BaseModel):
    tamanho: str = Field(min_length=1, max_length=30)
    cor: str = Field(min_length=1, max_length=50)
    codigo_barras: str | None = Field(default=None, max_length=100)
    estoque_atual: int = Field(default=0, ge=0)
    estoque_minimo: int = Field(default=2, ge=0)


class ProdutoCadastro(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    descricao: str | None = Field(default=None, max_length=2000)
    categoria: str | None = Field(default=None, max_length=80)
    marca: str | None = Field(default=None, max_length=80)
    preco_venda: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    variacoes: list[VariacaoProduto] = Field(default_factory=list, max_length=100)


class ItemCompra(BaseModel):
    variacao_id: str = Field(min_length=1)
    quantidade: int = Field(gt=0, le=10000)
    custo_unitario: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class CompraEntrada(BaseModel):
    fornecedor: str | None = Field(default=None, max_length=150)
    valor_total: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    itens: list[ItemCompra] = Field(min_length=1, max_length=500)


class ItemVenda(BaseModel):
    variacao_id: str = Field(min_length=1)
    quantidade: int = Field(gt=0, le=10000)
    preco_unitario_pago: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class VendaCriacao(BaseModel):
    valor_total: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    desconto: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    forma_pagamento: Literal["pix", "credito", "debito", "dinheiro"]
    itens: list[ItemVenda] = Field(min_length=1, max_length=500)
