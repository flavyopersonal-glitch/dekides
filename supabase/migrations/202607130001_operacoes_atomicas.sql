-- Execute esta migration no projeto Supabase antes de publicar a nova API.
-- As funções agrupam cada operação em uma única transação PostgreSQL.

create or replace function public.registrar_compra(p_compra jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_compra_id uuid;
  v_item jsonb;
begin
  insert into compras (fornecedor, valor_total, status)
  values (nullif(p_compra->>'fornecedor', ''), (p_compra->>'valor_total')::numeric, 'recebido')
  returning id into v_compra_id;

  for v_item in select value from jsonb_array_elements(p_compra->'itens') loop
    -- O lock impede que duas entradas concorrentes percam atualizações de estoque.
    perform 1 from variacoes_produto
      where id = (v_item->>'variacao_id')::uuid for update;
    if not found then
      raise exception 'Variação de produto não encontrada';
    end if;

    insert into itens_compra (compra_id, variacao_id, quantidade, custo_unitario)
    values (
      v_compra_id,
      (v_item->>'variacao_id')::uuid,
      (v_item->>'quantidade')::integer,
      (v_item->>'custo_unitario')::numeric
    );
    update variacoes_produto
      set estoque_atual = estoque_atual + (v_item->>'quantidade')::integer
      where id = (v_item->>'variacao_id')::uuid;
  end loop;

  insert into fluxo_caixa (tipo, categoria, valor, descricao, compra_id)
  values (
    'saida', 'compra_estoque', (p_compra->>'valor_total')::numeric,
    'Compra de estoque do fornecedor: ' || coalesce(nullif(p_compra->>'fornecedor', ''), 'Não informado'),
    v_compra_id
  );
  return jsonb_build_object('compra_id', v_compra_id, 'mensagem', 'Estoque e financeiro atualizados.');
end;
$$;

revoke all on function public.registrar_compra(jsonb) from public;
grant execute on function public.registrar_compra(jsonb) to service_role;

create or replace function public.registrar_venda(p_usuario_id uuid, p_venda jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_venda_id uuid;
  v_item jsonb;
  v_estoque integer;
begin
  for v_item in select value from jsonb_array_elements(p_venda->'itens') loop
    select estoque_atual into v_estoque from variacoes_produto
      where id = (v_item->>'variacao_id')::uuid for update;
    if not found then
      raise exception 'Variação de produto não encontrada';
    end if;
    if v_estoque < (v_item->>'quantidade')::integer then
      raise exception 'Estoque insuficiente para a venda';
    end if;
  end loop;

  insert into vendas (usuario_id, valor_total, desconto, forma_pagamento)
  values (
    p_usuario_id, (p_venda->>'valor_total')::numeric,
    coalesce((p_venda->>'desconto')::numeric, 0), p_venda->>'forma_pagamento'
  ) returning id into v_venda_id;

  for v_item in select value from jsonb_array_elements(p_venda->'itens') loop
    insert into itens_venda (venda_id, variacao_id, quantidade, preco_unitario_pago)
    values (
      v_venda_id, (v_item->>'variacao_id')::uuid,
      (v_item->>'quantidade')::integer, (v_item->>'preco_unitario_pago')::numeric
    );
    -- A baixa é feita aqui; remova/desative qualquer trigger antigo em itens_venda
    -- que também faça a mesma baixa ou lançamento financeiro.
    update variacoes_produto
      set estoque_atual = estoque_atual - (v_item->>'quantidade')::integer
      where id = (v_item->>'variacao_id')::uuid;
  end loop;

  insert into fluxo_caixa (tipo, categoria, valor, descricao, venda_id)
  values (
    'entrada', 'venda', (p_venda->>'valor_total')::numeric - coalesce((p_venda->>'desconto')::numeric, 0),
    'Venda ' || v_venda_id::text, v_venda_id
  );
  return jsonb_build_object('venda_id', v_venda_id, 'mensagem', 'Venda concluída com sucesso.');
end;
$$;

revoke all on function public.registrar_venda(uuid, jsonb) from public;
grant execute on function public.registrar_venda(uuid, jsonb) to service_role;
