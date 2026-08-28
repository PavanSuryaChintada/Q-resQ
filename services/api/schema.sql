-- Q-ResQ · Supabase / Postgres 15 + PostGIS
-- Run once:  psql $DATABASE_URL -f services/api/schema.sql
-- SRID 4326 throughout. This file is the source of truth — do not
-- retype it from docs/TRD.md.

create extension if not exists postgis;
create extension if not exists "uuid-ossp";

-- ---------------------------------------------------------------
-- STAGE 01/02 · terrain features and computed flood risk
-- One row per 250 m grid cell.
-- ---------------------------------------------------------------
create table if not exists risk_cells (
  id             bigserial primary key,
  geom           geometry(Polygon, 4326) not null,
  centroid       geometry(Point, 4326)   not null,

  -- terrain, computed once at seed time (Stage 01)
  elevation_m    real,
  hand_m         real,          -- height above nearest drainage
  slope_deg      real,
  twi            real,          -- ln(upslope_area / tan slope)
  dist_stream_m  real,
  soil_drainage  smallint,      -- ordinal class
  landcover      smallint,      -- categorical, one-hot at inference

  -- model output (Stage 02)
  risk_score     real check (risk_score between 0 and 1),
  risk_band      smallint check (risk_band between 0 and 4),
  -- 0 normal · 1 watch · 2 alert · 3 warning · 4 severe (IMD ladder)

  computed_at    timestamptz default now()
);
create index if not exists risk_cells_geom_idx     on risk_cells using gist (geom);
create index if not exists risk_cells_centroid_idx on risk_cells using gist (centroid);
create index if not exists risk_cells_band_idx     on risk_cells (risk_band);

-- ---------------------------------------------------------------
-- STAGE 03 · road network with dynamic passability
-- ---------------------------------------------------------------
create table if not exists road_segments (
  id             bigserial primary key,
  osm_id         bigint,
  geom           geometry(LineString, 4326) not null,
  road_class     text,
  length_m       real,
  base_speed_kmh real,
  min_elev_m     real,                  -- lowest point sampled along segment

  water_depth_m  real    default 0,
  passable_car   boolean default true,  -- water_depth_m < 0.30
  passable_boat  boolean default true,
  updated_at     timestamptz default now()
);
create index if not exists road_segments_geom_idx on road_segments using gist (geom);
create index if not exists road_segments_pass_idx on road_segments (passable_car, passable_boat);

-- ---------------------------------------------------------------
-- Rescue requests
-- id is CLIENT-GENERATED so offline replay is idempotent.
-- ---------------------------------------------------------------
create table if not exists requests (
  id            uuid primary key,
  location      geometry(Point, 4326) not null,
  people_count  smallint not null check (people_count > 0),
  category      text     not null check (category in ('medical','stranded','evacuation')),
  note          text,
  status        text     not null default 'open'
                check (status in ('open','assigned','in_progress','resolved','cancelled')),

  -- Stage 04 triage output
  severity      real check (severity between 0 and 1),
  sev_people    real,   -- components stored so the officer can see WHY
  sev_category  real,
  sev_area_risk real,
  sev_wait      real,

  created_at    timestamptz not null,   -- client clock; may precede synced_at
  synced_at     timestamptz default now(),
  resolved_at   timestamptz
);
create index if not exists requests_location_idx on requests using gist (location);
create index if not exists requests_queue_idx    on requests (status, severity desc);

-- ---------------------------------------------------------------
-- Rescue units
-- ---------------------------------------------------------------
create table if not exists units (
  id         uuid primary key default uuid_generate_v4(),
  label      text not null,                       -- 'Boat 03', 'Ambulance 07'
  kind       text not null check (kind in ('boat','ambulance','truck','team')),
  capacity   smallint not null check (capacity > 0),
  position   geometry(Point, 4326) not null,
  home_base  geometry(Point, 4326),
  status     text not null default 'available'
             check (status in ('available','assigned','en_route','returning','offline')),
  updated_at timestamptz default now()
);
create index if not exists units_position_idx on units using gist (position);
create index if not exists units_status_idx   on units (status);

-- ---------------------------------------------------------------
-- STAGE 05 · dispatch rounds and assignments
-- ---------------------------------------------------------------
create table if not exists dispatch_rounds (
  id            uuid primary key default uuid_generate_v4(),
  started_at    timestamptz default now(),
  zone_count    smallint,
  request_count smallint,
  unit_count    smallint,
  backend       text check (backend in ('qaoa','annealing','ortools','greedy')),
  fell_back     boolean default false,
  objective     real,
  solve_ms      integer
);

create table if not exists assignments (
  id         uuid primary key default uuid_generate_v4(),
  round_id   uuid references dispatch_rounds(id) on delete cascade,
  unit_id    uuid references units(id),
  request_id uuid references requests(id),
  zone_id    smallint,
  travel_s   integer,
  route      geometry(LineString, 4326),
  created_at timestamptz default now()
);
create index if not exists assignments_round_idx on assignments (round_id);
-- a unit or a request may appear at most once per round; the solver
-- guarantees this, and these constraints make a bug impossible to persist
create unique index if not exists assignments_unit_per_round    on assignments (round_id, unit_id);
create unique index if not exists assignments_request_per_round on assignments (round_id, request_id);

-- ---------------------------------------------------------------
-- Solver benchmark · one row per backend per instance
-- Honest results, including losses. Do not filter this table.
-- ---------------------------------------------------------------
create table if not exists benchmarks (
  id                bigserial primary key,
  round_id          uuid references dispatch_rounds(id) on delete cascade,
  backend           text not null,
  objective         real,
  solve_ms          integer,
  constraints_valid boolean,
  qubit_count       smallint,
  notes             text
);
create index if not exists benchmarks_round_idx on benchmarks (round_id);

-- ---------------------------------------------------------------
-- Append-only operations ledger (the UI signature element)
-- Never UPDATE or DELETE from this table.
-- ---------------------------------------------------------------
create table if not exists dispatch_log (
  id       bigserial primary key,
  at       timestamptz default now(),
  channel  text not null check (channel in ('risk','intake','dispatch','road','system')),
  severity smallint default 0 check (severity between 0 and 4),
  message  text not null
);
create index if not exists dispatch_log_at_idx on dispatch_log (at desc);

-- ---------------------------------------------------------------
-- Realtime · the web client subscribes to these
-- ---------------------------------------------------------------
alter publication supabase_realtime add table requests;
alter publication supabase_realtime add table assignments;
alter publication supabase_realtime add table dispatch_log;
alter publication supabase_realtime add table units;

-- ---------------------------------------------------------------
-- Demo-scope RLS: single operator, permissive.
-- Tighten before any real deployment.
-- ---------------------------------------------------------------
alter table requests      enable row level security;
alter table units         enable row level security;
alter table assignments   enable row level security;
alter table dispatch_log  enable row level security;

create policy demo_all_requests     on requests     for all using (true) with check (true);
create policy demo_all_units        on units        for all using (true) with check (true);
create policy demo_all_assignments  on assignments  for all using (true) with check (true);
create policy demo_all_log          on dispatch_log for all using (true) with check (true);
