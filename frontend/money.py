from decimal import Decimal, ROUND_HALF_UP


def dinheiro(valor):
    return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def total_itens(itens):
    return sum((item["quantidade"] * dinheiro(item["preco_unitario_pago"]) for item in itens), Decimal("0.00"))
