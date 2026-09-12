-- Run with psql against an explicitly authorized TEST Supabase DB; rolls back.
begin;
do $$
declare tab text; role_name text; action text;
begin
  foreach tab in array array['o2c_general_profiles','o2c_event_profiles'] loop
    if not (select relrowsecurity from pg_class where oid=('public.'||tab)::regclass) then
      raise exception 'RLS missing on %',tab;
    end if;
    foreach role_name in array array['anon','authenticated'] loop
      foreach action in array array['SELECT','INSERT','UPDATE','DELETE'] loop
        if has_table_privilege(role_name,'public.'||tab,action) then
          raise exception 'Unexpected % grant to % on %',action,role_name,tab;
        end if;
      end loop;
    end loop;
  end loop;
  if has_function_privilege('anon','public.o2c_save_profile(text,text,jsonb,jsonb,boolean)','EXECUTE')
     or has_function_privilege('authenticated','public.o2c_save_profile(text,text,jsonb,jsonb,boolean)','EXECUTE') then
    raise exception 'RPC unexpectedly accessible to client roles';
  end if;
end $$;
set local role service_role;
select public.o2c_save_profile('test-rollback-only','test-event','{"name":"Synthetic"}','{"contact":"private@example.invalid"}',false);
do $$ begin
  if (select count(*) from public.o2c_event_profiles where owner_id='test-rollback-only') != 1 then
    raise exception 'Service role profile transaction failed';
  end if;
end $$;
rollback;
