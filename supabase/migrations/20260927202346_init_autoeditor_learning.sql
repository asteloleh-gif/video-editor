create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid null references auth.users(id) on delete set null,
  name text not null,
  status text not null default 'draft',
  target_duration_ms integer null check (target_duration_ms is null or target_duration_ms > 0),
  source_provider text null,
  source_root text null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.source_files (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  provider text not null default 'google_drive',
  external_id text null,
  file_name text not null,
  mime_type text null,
  size_bytes bigint null check (size_bytes is null or size_bytes >= 0),
  duration_ms integer null check (duration_ms is null or duration_ms >= 0),
  width integer null,
  height integer null,
  fps numeric(8,3) null,
  source_url text null,
  checksum text null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(provider, external_id)
);

create table if not exists public.events (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  source_file_id uuid not null references public.source_files(id) on delete cascade,
  event_type text not null,
  start_ms integer not null check (start_ms >= 0),
  end_ms integer not null check (end_ms >= start_ms),
  confidence numeric(5,4) null check (confidence is null or (confidence >= 0 and confidence <= 1)),
  subject text null,
  subject_color text null,
  ai_model text null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.presets (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid null references auth.users(id) on delete cascade,
  name text not null,
  version integer not null default 1 check (version > 0),
  description text null,
  config jsonb not null default '{}'::jsonb,
  is_default boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_id, name, version)
);

create table if not exists public.renders (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  preset_id uuid null references public.presets(id) on delete set null,
  status text not null default 'queued',
  output_provider text null,
  output_external_id text null,
  output_file_name text null,
  output_url text null,
  duration_ms integer null check (duration_ms is null or duration_ms >= 0),
  width integer null,
  height integer null,
  codec text null,
  render_meta jsonb not null default '{}'::jsonb,
  error_text text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.edits (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  render_id uuid null references public.renders(id) on delete cascade,
  source_file_id uuid null references public.source_files(id) on delete cascade,
  event_id uuid null references public.events(id) on delete set null,
  action text not null,
  sequence_position integer null,
  source_start_ms integer null,
  source_end_ms integer null,
  output_start_ms integer null,
  output_end_ms integer null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.feedback (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  render_id uuid null references public.renders(id) on delete cascade,
  event_id uuid null references public.events(id) on delete set null,
  feedback_type text not null,
  ai_decision jsonb not null default '{}'::jsonb,
  user_decision jsonb not null default '{}'::jsonb,
  note text null,
  created_at timestamptz not null default now()
);

create index if not exists idx_source_files_project on public.source_files(project_id);
create index if not exists idx_events_project on public.events(project_id);
create index if not exists idx_events_source_time on public.events(source_file_id, start_ms);
create index if not exists idx_events_type on public.events(event_type);
create index if not exists idx_renders_project_created on public.renders(project_id, created_at desc);
create index if not exists idx_edits_project on public.edits(project_id);
create index if not exists idx_feedback_project on public.feedback(project_id);
create index if not exists idx_feedback_event on public.feedback(event_id);

drop trigger if exists trg_projects_updated_at on public.projects;
create trigger trg_projects_updated_at before update on public.projects
for each row execute function public.set_updated_at();

drop trigger if exists trg_source_files_updated_at on public.source_files;
create trigger trg_source_files_updated_at before update on public.source_files
for each row execute function public.set_updated_at();

drop trigger if exists trg_presets_updated_at on public.presets;
create trigger trg_presets_updated_at before update on public.presets
for each row execute function public.set_updated_at();

drop trigger if exists trg_renders_updated_at on public.renders;
create trigger trg_renders_updated_at before update on public.renders
for each row execute function public.set_updated_at();

alter table public.projects enable row level security;
alter table public.source_files enable row level security;
alter table public.events enable row level security;
alter table public.presets enable row level security;
alter table public.renders enable row level security;
alter table public.edits enable row level security;
alter table public.feedback enable row level security;

insert into public.presets (name, version, description, is_default, config)
select
  'OLEH_STYLE',
  1,
  'Battle Box fast-cut preset learned from the first reference edit.',
  true,
  jsonb_build_object(
    'target_duration_ms', 30000,
    'speech_policy', 'remove',
    'orange_priority', 1.4,
    'goal_weight', 2.0,
    'attempt_weight', 1.0,
    'collision_weight', 1.2,
    'reaction_weight', 0.9,
    'dead_time_weight', 0.0,
    'reaction_max_ms', 900,
    'clip_target_ms', 1300,
    'preserve_ball_travel', true,
    'impact_transition', true,
    'goal_sfx', true,
    'goal_text', 'GOAL!',
    'orange_goal_text', false,
    'natural_audio', false
  )
where not exists (
  select 1 from public.presets
  where owner_id is null and name = 'OLEH_STYLE' and version = 1
);
