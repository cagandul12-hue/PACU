-- Jalankan sekali di Supabase: SQL Editor -> New query -> paste -> Run
create table if not exists public.pacu_state (
  id         text primary key,
  data       jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- Kunci tabel dari akses publik. Aplikasi memakai Secret key (server), jadi tetap bisa baca/tulis.
alter table public.pacu_state enable row level security;
