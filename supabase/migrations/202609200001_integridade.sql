begin;
-- Interrompe a instalação em vez de alterar silenciosamente triggers existentes.
do $$ begin
 if exists(select 1 from pg_trigger where not tgisinternal and tgenabled <> 'D' and tgrelid in
 ('public.itens_venda'::regclass,'public.itens_compra'::regclass,'public.vendas'::regclass,'public.compras'::regclass)) then
 raise exception 'Revise os triggers legados de compras/vendas antes de aplicar esta migration.'; end if;
end $$;
-- Também protege instalações antigas sem a restrição de estoque.
alter table public.variacoes_produto drop constraint if exists dekids_estoque_nao_negativo;
alter table public.variacoes_produto add constraint dekids_estoque_nao_negativo check(estoque_atual >= 0);
create table if not exists public.operacoes(id uuid primary key,usuario_id uuid not null references public.usuarios(id),tipo text not null,payload jsonb not null,resultado jsonb);
do $$ declare t text; begin
 foreach t in array array['usuarios','produtos','variacoes_produto','compras','vendas','itens_compra','itens_venda','fluxo_caixa','operacoes'] loop
 execute format('alter table public.%I enable row level security',t);
 execute format('revoke all on table public.%I from public,anon,authenticated',t);
 execute format('grant all on table public.%I to service_role',t);
 end loop;
end $$;
create or replace function public.dekids_criar_perfil() returns trigger language plpgsql security definer set search_path=public as $$
begin
 if new.raw_app_meta_data ? 'dekids_role' then
 insert into public.usuarios(id,nome,role,ativo) values(new.id,new.raw_app_meta_data->>'dekids_nome',new.raw_app_meta_data->>'dekids_role',true);
 end if;
 return new;
end $$;
drop trigger if exists dekids_criar_perfil on auth.users;
create trigger dekids_criar_perfil after insert on auth.users for each row execute function public.dekids_criar_perfil();
revoke all on function public.dekids_criar_perfil() from public,anon,authenticated;
create or replace function public.cadastrar_produto(p_produto jsonb) returns jsonb language plpgsql security definer set search_path=public as $$
declare pid uuid; item jsonb;
begin
 insert into produtos(nome,descricao,categoria,marca,preco_venda) values(p_produto->>'nome',p_produto->>'descricao',p_produto->>'categoria',p_produto->>'marca',(p_produto->>'preco_venda')::numeric) returning id into pid;
 for item in select value from jsonb_array_elements(p_produto->'variacoes') loop
 insert into variacoes_produto(produto_id,tamanho,cor,codigo_barras,estoque_atual,estoque_minimo) values(pid,item->>'tamanho',item->>'cor',nullif(item->>'codigo_barras',''),(item->>'estoque_atual')::integer,(item->>'estoque_minimo')::integer);
 end loop;
 return jsonb_build_object('produto_id',pid);
end $$;
revoke all on function public.cadastrar_produto(jsonb) from public,anon,authenticated;
grant execute on function public.cadastrar_produto(jsonb) to service_role;
drop function if exists public.registrar_compra(jsonb);

create or replace function public.registrar_venda(p_usuario_id uuid,p_venda jsonb) returns jsonb language plpgsql security definer set search_path=public as $$
declare payload jsonb := p_venda; op uuid := (p_venda->>'operacao_id')::uuid;
 anterior operacoes%rowtype; item jsonb; total numeric := 0; estoque integer; registro uuid; resposta jsonb;
begin
 if not exists(select 1 from usuarios where id=p_usuario_id and ativo ) then raise exception 'Perfil sem acesso'; end if;
 if op is null then raise exception 'Identificador obrigatório'; end if;
 insert into operacoes(id,usuario_id,tipo,payload) values(op,p_usuario_id,'venda',payload) on conflict(id) do nothing;
 select * into anterior from operacoes where id=op for update;
 if anterior.usuario_id <> p_usuario_id or anterior.tipo <> 'venda' or anterior.payload <> payload then raise exception 'Identificador utilizado com outros dados'; end if;
 if anterior.resultado is not null then return anterior.resultado; end if;
 if jsonb_typeof(payload->'itens') is distinct from 'array' then raise exception 'Itens obrigatórios'; end if;
 if jsonb_array_length(payload->'itens') not between 1 and 500 then raise exception 'Quantidade de itens inválida'; end if;
 if exists(select 1 from jsonb_array_elements(payload->'itens') x group by (x->>'variacao_id')::uuid having count(*)>1) then raise exception 'Variações duplicadas'; end if;
 -- Bloqueio em ordem fixa para evitar deadlocks.
 for item in select value from jsonb_array_elements(payload->'itens') order by (value->>'variacao_id')::uuid loop
 if item->>'quantidade' is null or (item->>'quantidade')::numeric <> trunc((item->>'quantidade')::numeric) or (item->>'quantidade')::integer not between 1 and 10000
 or item->>'preco_unitario_pago' is null or (item->>'preco_unitario_pago')::numeric<=0 or (item->>'preco_unitario_pago')::numeric<>round((item->>'preco_unitario_pago')::numeric,2) then raise exception 'Item inválido'; end if;
 select estoque_atual into estoque from variacoes_produto where id=(item->>'variacao_id')::uuid for update;
 if not found then raise exception 'Variação não encontrada'; end if;
 if estoque < (item->>'quantidade')::integer then raise exception 'Estoque insuficiente'; end if;
 total := total + (item->>'quantidade')::integer * (item->>'preco_unitario_pago')::numeric;
 end loop;
 if payload->>'valor_total' is null or total<>(payload->>'valor_total')::numeric then raise exception 'Total divergente dos itens'; end if;
 if coalesce((payload->>'desconto')::numeric,0)<0 or coalesce((payload->>'desconto')::numeric,0)>total or coalesce((payload->>'desconto')::numeric,0)<>round(coalesce((payload->>'desconto')::numeric,0),2) then raise exception 'Desconto inválido'; end if;
 if payload->>'forma_pagamento' is null or payload->>'forma_pagamento' not in ('pix','credito','debito','dinheiro') then raise exception 'Pagamento inválido'; end if;
 insert into vendas(usuario_id,valor_total,desconto,forma_pagamento) values(p_usuario_id,total,coalesce((payload->>'desconto')::numeric,0),payload->>'forma_pagamento') returning id into registro;
 for item in select value from jsonb_array_elements(payload->'itens') loop
 insert into itens_venda(venda_id,variacao_id,quantidade,preco_unitario_pago) values(registro,(item->>'variacao_id')::uuid,(item->>'quantidade')::integer,(item->>'preco_unitario_pago')::numeric);
 update variacoes_produto set estoque_atual=estoque_atual - (item->>'quantidade')::integer where id=(item->>'variacao_id')::uuid;
 end loop;
 insert into fluxo_caixa(tipo,categoria,valor,descricao,venda_id) values('entrada','venda',total - coalesce((payload->>'desconto')::numeric,0),'venda ' || registro::text,registro);
 resposta := jsonb_build_object('venda_id',registro,'mensagem','Operação concluída.');
 update operacoes set resultado=resposta where id=op;
 return resposta;
end $$;
revoke all on function public.registrar_venda(uuid,jsonb) from public,anon,authenticated;
grant execute on function public.registrar_venda(uuid,jsonb) to service_role;

create or replace function public.registrar_compra(p_usuario_id uuid,p_compra jsonb) returns jsonb language plpgsql security definer set search_path=public as $$
declare payload jsonb := p_compra; op uuid := (p_compra->>'operacao_id')::uuid;
 anterior operacoes%rowtype; item jsonb; total numeric := 0; estoque integer; registro uuid; resposta jsonb;
begin
 if not exists(select 1 from usuarios where id=p_usuario_id and ativo and role in ('master','admin')) then raise exception 'Perfil sem acesso'; end if;
 if op is null then raise exception 'Identificador obrigatório'; end if;
 insert into operacoes(id,usuario_id,tipo,payload) values(op,p_usuario_id,'compra',payload) on conflict(id) do nothing;
 select * into anterior from operacoes where id=op for update;
 if anterior.usuario_id <> p_usuario_id or anterior.tipo <> 'compra' or anterior.payload <> payload then raise exception 'Identificador utilizado com outros dados'; end if;
 if anterior.resultado is not null then return anterior.resultado; end if;
 if jsonb_typeof(payload->'itens') is distinct from 'array' then raise exception 'Itens obrigatórios'; end if;
 if jsonb_array_length(payload->'itens') not between 1 and 500 then raise exception 'Quantidade de itens inválida'; end if;
 if exists(select 1 from jsonb_array_elements(payload->'itens') x group by (x->>'variacao_id')::uuid having count(*)>1) then raise exception 'Variações duplicadas'; end if;
 -- Bloqueio em ordem fixa para evitar deadlocks.
 for item in select value from jsonb_array_elements(payload->'itens') order by (value->>'variacao_id')::uuid loop
 if item->>'quantidade' is null or (item->>'quantidade')::numeric <> trunc((item->>'quantidade')::numeric) or (item->>'quantidade')::integer not between 1 and 10000
 or item->>'custo_unitario' is null or (item->>'custo_unitario')::numeric<=0 or (item->>'custo_unitario')::numeric<>round((item->>'custo_unitario')::numeric,2) then raise exception 'Item inválido'; end if;
 select estoque_atual into estoque from variacoes_produto where id=(item->>'variacao_id')::uuid for update;
 if not found then raise exception 'Variação não encontrada'; end if;

 total := total + (item->>'quantidade')::integer * (item->>'custo_unitario')::numeric;
 end loop;
 if payload->>'valor_total' is null or total<>(payload->>'valor_total')::numeric then raise exception 'Total divergente dos itens'; end if;
insert into compras(fornecedor,valor_total,status) values(payload->>'fornecedor',total,'recebido') returning id into registro;
 for item in select value from jsonb_array_elements(payload->'itens') loop
 insert into itens_compra(compra_id,variacao_id,quantidade,custo_unitario) values(registro,(item->>'variacao_id')::uuid,(item->>'quantidade')::integer,(item->>'custo_unitario')::numeric);
 update variacoes_produto set estoque_atual=estoque_atual + (item->>'quantidade')::integer where id=(item->>'variacao_id')::uuid;
 end loop;
 insert into fluxo_caixa(tipo,categoria,valor,descricao,compra_id) values('saida','compra_estoque',total ,'compra ' || registro::text,registro);
 resposta := jsonb_build_object('compra_id',registro,'mensagem','Operação concluída.');
 update operacoes set resultado=resposta where id=op;
 return resposta;
end $$;
revoke all on function public.registrar_compra(uuid,jsonb) from public,anon,authenticated;
grant execute on function public.registrar_compra(uuid,jsonb) to service_role;

create or replace function public.resumo_financeiro() returns jsonb language sql security definer set search_path=public as $$
 select jsonb_build_object('entradas',coalesce(sum(valor) filter(where tipo='entrada'),0)::text,'saidas',coalesce(sum(valor) filter(where tipo='saida'),0)::text) from fluxo_caixa;
$$;
revoke all on function public.resumo_financeiro() from public,anon,authenticated;
grant execute on function public.resumo_financeiro() to service_role;
create index if not exists fluxo_caixa_ordenacao on public.fluxo_caixa(data_competencia desc,id);
create index if not exists variacoes_produto_produto on public.variacoes_produto(produto_id);
commit;
