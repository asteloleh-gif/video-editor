create table if not exists public.jobs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  source_file_id uuid null references public.source_files(id) on delete cascade,
  render_id uuid null references public.renders(id) on delete cascade,
  job_type text not null check (job_type in ('analyze', 'create_short')),
  status text not null default 'queued'
    check (status in ('queued', 'running', 'completed', 'failed', 'cancelled')),
  priority integer not null default 100,
  worker_id text null,
  attempts integer not null default 0 check (attempts >= 0),
  payload jsonb not null default '{}'::jsonb,
  result jsonb not null default '{}'::jsonb,
  error_text text null,
  available_at timestamptz not null default now(),
  started_at timestamptz null,
  finished_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_jobs_queue
  on public.jobs(status, priority desc, available_at, created_at);

create index if not exists idx_jobs_project_created
  on public.jobs(project_id, created_at desc);

drop trigger if exists trg_jobs_updated_at on public.jobs;
create trigger trg_jobs_updated_at before update on public.jobs
for each row execute function public.set_updated_at();

alter table public.jobs enable row level security;

create or replace function public.claim_autoeditor_job(p_worker_id text)
returns public.jobs
language plpgsql
security definer
set search_path = public
as $$
declare
  claimed public.jobs;
begin
  update public.jobs
  set
    status = 'running',
    worker_id = p_worker_id,
    attempts = attempts + 1,
    started_at = coalesce(started_at, now()),
    updated_at = now()
  where id = (
    select id
    from public.jobs
    where status = 'queued'
      and available_at <= now()
    order by priority desc, created_at asc
    for update skip locked
    limit 1
  )
  returning * into claimed;

  return claimed;
end;
$$;

revoke all on function public.claim_autoeditor_job(text) from public;
grant execute on function public.claim_autoeditor_job(text) to service_role;
