-- v1.3 Activity log. Run once in Supabase -> SQL Editor -> New query -> Run.
-- Safe to run again: it creates nothing twice and imports old marks only once.

-- 1. The log table: one row per action (mark, mark change, Sync button, sync result).
create table if not exists public.activity_log (
  id        uuid        primary key default gen_random_uuid(),
  at        timestamptz not null default now(),
  who       text        not null default '',
  action    text        not null,
  cand      text        not null default '',
  phone     text        not null default '',
  pos       text        not null default '',
  old_value text        not null default '',
  new_value text        not null default '',
  reason    text        not null default '',
  detail    jsonb
);
create index if not exists activity_log_at_idx on public.activity_log (at desc);

-- 2. Insert-only: the page can add and read log rows, but cannot edit or delete them.
alter table public.activity_log disable row level security;
revoke all on public.activity_log from anon, authenticated;
grant select, insert on public.activity_log to anon, authenticated;

-- 3. Live updates: a new log row shows on everyone's open Activity log.
do $$
begin
  if not exists (select 1 from pg_publication_tables
                 where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'activity_log') then
    alter publication supabase_realtime add table public.activity_log;
  end if;
end $$;

-- 4. Import the marks made before v1.3 (their latest state only; earlier changes were not kept).
insert into public.activity_log (at, who, action, cand, phone, pos, new_value, reason, detail)
select coalesce(nullif(d.data->>'at', '')::timestamptz, d.updated_at),
       coalesce(d.data->>'hr', ''),
       'mark_imported',
       coalesce(d.data->>'cand', ''),
       coalesce(d.data->>'phone', ''),
       coalesce(d.data->>'pos', ''),
       coalesce(d.data->>'verdict', ''),
       coalesce(d.data->>'reason', ''),
       jsonb_build_object('doc_id', d.id)
from public.docs d
where d.collection = 'verdicts'
  and not exists (select 1 from public.activity_log l
                  where l.action = 'mark_imported' and l.detail->>'doc_id' = d.id);
