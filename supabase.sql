-- Run once in Supabase -> SQL Editor.
-- One table holds the page's shared data: Fit/Unfit marks (collection "verdicts")
-- and sync status (collection "runs").
create table if not exists public.docs (
  collection text        not null,
  id         text        not null,
  data       jsonb       not null,
  updated_at timestamptz not null default now(),
  primary key (collection, id)
);

-- No login: anyone with the page link can read and write (security not required).
alter table public.docs disable row level security;
grant select, insert, update, delete on public.docs to anon, authenticated;

-- Live updates: a mark saved by one person shows on everyone's screen.
alter publication supabase_realtime add table public.docs;
