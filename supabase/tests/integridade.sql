-- Execute somente em homologação, depois das migrations. Nenhum dado é mantido.
begin;
do $$
declare
 u uuid := gen_random_uuid(); p uuid; v uuid; operacao uuid := gen_random_uuid();
 dados jsonb; r1 jsonb; r2 jsonb; n integer; antes integer; falhou boolean;
begin
 insert into auth.users(id,raw_app_meta_data) values(u,jsonb_build_object('dekids_nome','Teste SQL','dekids_role','master'));
 if not exists(select 1 from public.usuarios where id=u and role='master') then raise exception 'Perfil não foi criado'; end if;
 r1 := public.cadastrar_produto('{"nome":"Teste SQL","preco_venda":"10.00","variacoes":[{"tamanho":"P","cor":"Azul","estoque_atual":5,"estoque_minimo":0}]}'::jsonb);
 p := (r1->>'produto_id')::uuid;
 select id into strict v from public.variacoes_produto where produto_id=p;
 dados := jsonb_build_object('operacao_id',operacao,'valor_total','20.00','desconto','0.00','forma_pagamento','pix',
 'itens',jsonb_build_array(jsonb_build_object('variacao_id',v,'quantidade',2,'preco_unitario_pago','10.00')));
 r1 := public.registrar_venda(u,dados);
 r2 := public.registrar_venda(u,dados);
 if r1<>r2 then raise exception 'Repetição mudou o resultado'; end if;
 select estoque_atual into n from public.variacoes_produto where id=v;
 if n<>3 then raise exception 'Baixa duplicada'; end if;
 select count(*) into n from public.fluxo_caixa where venda_id=(r1->>'venda_id')::uuid;
 if n<>1 then raise exception 'Lançamento duplicado'; end if;
 falhou := false;
 begin
 perform public.registrar_venda(u,jsonb_set(dados,'{valor_total}','"1.00"'));
 exception when others then falhou := true; end;
 if not falhou then raise exception 'Reutilização com dados diferentes aceita'; end if;
 dados := jsonb_set(dados,'{operacao_id}',to_jsonb(gen_random_uuid()));
 dados := jsonb_set(dados,'{itens}',(dados->'itens')||(dados->'itens'));
 dados := jsonb_set(dados,'{valor_total}','"40.00"');
 falhou := false;
 begin perform public.registrar_venda(u,dados); exception when others then falhou := true; end;
 if not falhou then raise exception 'Duplicação aceita'; end if;
 dados := jsonb_set(dados,'{itens}',jsonb_build_array(jsonb_build_object('variacao_id',v,'quantidade',4,'preco_unitario_pago','10.00')));
 falhou := false;
 begin perform public.registrar_venda(u,dados); exception when others then falhou := true; end;
 if not falhou then raise exception 'Estoque insuficiente aceito'; end if;
 select estoque_atual into n from public.variacoes_produto where id=v;
 if n<>3 then raise exception 'Falha alterou estoque'; end if;
 select count(*) into antes from public.produtos;
 falhou := false;
 begin perform public.cadastrar_produto('{"nome":"Falha","preco_venda":"10","variacoes":[{"tamanho":"P","cor":"Azul","estoque_atual":-1,"estoque_minimo":0}]}');
 exception when others then falhou := true; end;
 select count(*) into n from public.produtos;
 if not falhou or n<>antes then raise exception 'Cadastro parcial'; end if;
 dados := jsonb_build_object('operacao_id',gen_random_uuid(),'valor_total','4.00','itens',jsonb_build_array(jsonb_build_object('variacao_id',v,'quantidade',2,'custo_unitario','2.00')));
 r1 := public.registrar_compra(u,dados);
 r2 := public.registrar_compra(u,dados);
 select estoque_atual into n from public.variacoes_produto where id=v;
 if n<>5 or r1<>r2 then raise exception 'Compra duplicada'; end if;
 if has_table_privilege('anon','public.produtos','SELECT') or has_function_privilege('authenticated','public.registrar_venda(uuid,jsonb)','EXECUTE') then raise exception 'Permissões públicas indevidas'; end if;
 raise notice 'Testes de integridade aprovados';
end $$;
rollback;
