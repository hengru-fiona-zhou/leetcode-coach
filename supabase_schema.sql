-- Run in Supabase > SQL Editor, once.
-- User-specific practice history with Row-Level Security (RLS).
create extension if not exists pgcrypto;

create table if not exists public.practice_attempts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    source_uid text,
    problem_title text not null,
    topic text not null,
    difficulty text not null,
    practice_date date not null,
    outcome text not null check (outcome in (
        'solved_independently', 'solved_with_hints', 'viewed_solution',
        'gave_up', 'reviewed_easily', 'struggled'
    )),
    minutes integer check (minutes is null or (minutes >= 0 and minutes <= 1440)),
    notes text not null default '',
    review_on date,
    created_at timestamptz not null default now(),
    constraint unique_import_per_user unique (user_id, source_uid)
);

create index if not exists practice_attempts_user_date_idx
    on public.practice_attempts (user_id, practice_date desc);

alter table public.practice_attempts enable row level security;

-- Idempotent policy setup if you rerun this schema during development.
drop policy if exists "attempts_select_own" on public.practice_attempts;
drop policy if exists "attempts_insert_own" on public.practice_attempts;
drop policy if exists "attempts_update_own" on public.practice_attempts;
drop policy if exists "attempts_delete_own" on public.practice_attempts;

create policy "attempts_select_own" on public.practice_attempts
    for select to authenticated using ((select auth.uid()) = user_id);
create policy "attempts_insert_own" on public.practice_attempts
    for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "attempts_update_own" on public.practice_attempts
    for update to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);
create policy "attempts_delete_own" on public.practice_attempts
    for delete to authenticated using ((select auth.uid()) = user_id);

grant select, insert, update, delete on public.practice_attempts to authenticated;
revoke all on public.practice_attempts from anon;
