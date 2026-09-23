create schema if not exists dekids;
set local search_path = dekids, public;
create table if not exists dekids.usuarios (
 id text primary key, nome text not null, email text not null unique,
 username text unique, role text not null check(role in ('master','admin','funcionario')),
 ativo boolean not null default true, criado_em timestamptz not null default now()
);
create table if not exists dekids.produtos(id uuid primary key default gen_random_uuid(),nome text not null,descricao text,categoria text,marca text,preco_venda numeric(12,2) not null check(preco_venda>0));
create table if not exists dekids.variacoes_produto(id uuid primary key default gen_random_uuid(),produto_id uuid not null references dekids.produtos(id),tamanho text not null,cor text not null,codigo_barras text unique,estoque_atual integer not null default 0 check(estoque_atual>=0),estoque_minimo integer not null default 2 check(estoque_minimo>=0));
create table if not exists dekids.compras(id uuid primary key default gen_random_uuid(),fornecedor text,valor_total numeric(12,2) not null check(valor_total>0),status text not null);
create table if not exists dekids.vendas(id uuid primary key default gen_random_uuid(),usuario_id text not null references dekids.usuarios(id),valor_total numeric(12,2) not null check(valor_total>0),desconto numeric(12,2) not null default 0 check(desconto>=0 and desconto<=valor_total),forma_pagamento text not null check(forma_pagamento in ('pix','credito','debito','dinheiro')));
create table if not exists dekids.itens_compra(id uuid primary key default gen_random_uuid(),compra_id uuid not null references dekids.compras(id),variacao_id uuid not null references dekids.variacoes_produto(id),quantidade integer not null check(quantidade>0),custo_unitario numeric(12,2) not null check(custo_unitario>0));
create table if not exists dekids.itens_venda(id uuid primary key default gen_random_uuid(),venda_id uuid not null references dekids.vendas(id),variacao_id uuid not null references dekids.variacoes_produto(id),quantidade integer not null check(quantidade>0),preco_unitario_pago numeric(12,2) not null check(preco_unitario_pago>0));
create table if not exists dekids.fluxo_caixa(id uuid primary key default gen_random_uuid(),tipo text not null check(tipo in ('entrada','saida')),categoria text not null,valor numeric(12,2) not null check(valor>=0),descricao text,compra_id uuid references dekids.compras(id),venda_id uuid references dekids.vendas(id),data_competencia timestamptz not null default now());


create table if not exists dekids.operacoes(id uuid primary key,usuario_id text not null references dekids.usuarios(id),tipo text not null,payload jsonb not null,resultado jsonb);
create table if not exists dekids.primeiro_acesso (
 singleton boolean primary key default true check(singleton), username text not null,
 senha_hash text not null, concluido boolean not null default false,
 token_hash text, expira_em timestamptz, email_pendente text
);
create table if not exists dekids.tentativas_login (
 identificador text primary key, quantidade integer not null default 0,
 inicio timestamptz not null default now()
);
create table if not exists dekids.cadastros_pendentes (
 email text primary key, nome text not null, role text not null check(role in ('master','admin','funcionario')),
 criado_por text not null references dekids.usuarios(id), criado_em timestamptz not null default now()
);
create or replace function dekids.cadastrar_produto(p_produto jsonb) returns jsonb language plpgsql security invoker set search_path=dekids,public as $$
declare pid uuid; item jsonb;
begin
 insert into produtos(nome,descricao,categoria,marca,preco_venda) values(p_produto->>'nome',p_produto->>'descricao',p_produto->>'categoria',p_produto->>'marca',(p_produto->>'preco_venda')::numeric) returning id into pid;
 for item in select value from jsonb_array_elements(p_produto->'variacoes') loop
 insert into variacoes_produto(produto_id,tamanho,cor,codigo_barras,estoque_atual,estoque_minimo) values(pid,item->>'tamanho',item->>'cor',nullif(item->>'codigo_barras',''),(item->>'estoque_atual')::integer,(item->>'estoque_minimo')::integer);
 end loop;
 return jsonb_build_object('produto_id',pid);
end $$;

create or replace function dekids.registrar_venda(p_usuario_id text,p_venda jsonb) returns jsonb language plpgsql security invoker set search_path=dekids,public as $$
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

create or replace function dekids.registrar_compra(p_usuario_id text,p_compra jsonb) returns jsonb language plpgsql security invoker set search_path=dekids,public as $$
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

create or replace function dekids.resumo_financeiro() returns jsonb language sql security invoker set search_path=dekids,public as $$
 select jsonb_build_object('entradas',coalesce(sum(valor) filter(where tipo='entrada'),0)::text,'saidas',coalesce(sum(valor) filter(where tipo='saida'),0)::text) from fluxo_caixa;
$$;
create index if not exists fluxo_caixa_ordenacao on dekids.fluxo_caixa(data_competencia desc,id);
create index if not exists variacoes_produto_produto on dekids.variacoes_produto(produto_id);
revoke all on schema dekids from public;
revoke all on all tables in schema dekids from public;
revoke execute on all functions in schema dekids from public;
