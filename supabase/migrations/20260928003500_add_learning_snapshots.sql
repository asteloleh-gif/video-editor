create table if not exists public.learning_snapshots (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  preset_id uuid null references public.presets(id) on delete set null,
  feedback_count integer not null default 0 check (feedback_count >= 0),
  confidence text not null default 'cold_start',
  summary jsonb not null default '{}'::jsonb,
  candidate_config jsonb not null default '{}'::jsonb,
  status text not null default 'candidate'
    check (status in ('candidate', 'approved', 'rejected', 'promoted')),
  promoted_preset_id uuid null references public.presets(id) on delete set null,
  created_at timestamptz not null default now()
);

create index if not exists idx_learning_snapshots_project_created
  on public.learning_snapshots(project_id, created_at desc);

alter table public.learning_snapshots enable row level security;
