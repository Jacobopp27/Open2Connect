-- Apply only to the Supabase project explicitly chosen for Open2Connect.
-- No automatic import from SQLite. App auth remains in the Python backend.
-- Owner IDs are issued by that auth service, NOT by a request body or auth.uid().
begin;
create table public.o2c_general_profiles (
  owner_id text primary key check (length(owner_id) between 1 and 100),
  data jsonb not null check (jsonb_typeof(data) = 'object' and octet_length(data::text) <= 16000),
  updated_at timestamptz not null default now()
);
create table public.o2c_event_profiles (
  owner_id text not null references public.o2c_general_profiles(owner_id) on delete cascade,
  event_id text not null check (length(event_id) between 1 and 100),
  data jsonb not null check (jsonb_typeof(data) = 'object' and octet_length(data::text) <= 32000),
  visible boolean not null default false,
  updated_at timestamptz not null default now(),
  primary key (owner_id,event_id)
);
alter table public.o2c_general_profiles enable row level security;
alter table public.o2c_event_profiles enable row level security;
-- Deny direct browser/anon/Supabase-Auth access. Explicit restrictive policy also
-- prevents a later permissive policy from accidentally opening these tables.
create policy backend_only_general on public.o2c_general_profiles as restrictive
  for all to anon, authenticated using (false) with check (false);
create policy backend_only_event on public.o2c_event_profiles as restrictive
  for all to anon, authenticated using (false) with check (false);
revoke all on public.o2c_general_profiles, public.o2c_event_profiles from public, anon, authenticated;
grant select,insert,update,delete on public.o2c_general_profiles, public.o2c_event_profiles to service_role;

create function public.o2c_save_profile(p_owner text, p_event text, p_general jsonb, p_data jsonb, p_visible boolean)
returns void language plpgsql security invoker set search_path = '' as $$
begin
  insert into public.o2c_general_profiles(owner_id,data) values(p_owner,p_general)
  on conflict(owner_id) do update set data=excluded.data, updated_at=now();
  insert into public.o2c_event_profiles(owner_id,event_id,data,visible) values(p_owner,p_event,p_data,p_visible)
  on conflict(owner_id,event_id) do update set data=excluded.data,visible=excluded.visible,updated_at=now();
end;
$$;
revoke all on function public.o2c_save_profile(text,text,jsonb,jsonb,boolean) from public, anon, authenticated;
grant execute on function public.o2c_save_profile(text,text,jsonb,jsonb,boolean) to service_role;
commit;
