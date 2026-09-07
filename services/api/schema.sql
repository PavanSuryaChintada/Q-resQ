-- Q-ResQ NER · Supabase / Postgres 15 + PostGIS
-- Run once:  psql $DATABASE_URL -f services/api/schema.sql
-- SRID 4326 throughout. This file is the source of truth — do not
-- retype DDL from docs/TRD.md or docs/MIGRATION.md.
--
-- NOT APPLIED YET as of the Foundation sub-project (2026-09-06) — Supabase
-- project setup is handled outside this build. Apply once a database exists.

create extension if not exists postgis;
create extension if not exists "uuid-ossp";
create extension if not exists pgcrypto;

-- ===============================================================
-- TERRAIN + RISK  ·  100 m grid (finer than the flood build's
-- 250 m: landslide failure surfaces are tens of metres across and
-- a coarse cell averages a failing slope into stable neighbours)
-- ===============================================================
create table if not exists risk_cells (
  id             bigserial primary key,
  geom           geometry(Polygon, 4326) not null,
  centroid       geometry(Point, 4326)   not null,

  -- static terrain (Stage: terrain)
  elevation_m    real,
  slope_deg      real,
  aspect_sin     real,          -- aspect is circular: never store raw degrees
  aspect_cos     real,
  curv_plan      real,
  curv_prof      real,
  ls_factor      real,
  hand_m         real,
  twi            real,
  dist_stream_m  real,
  dist_road_m    real,
  is_cut_slope   boolean default false,   -- dist_road<50m AND slope>25deg
  lithology      smallint,
  landcover      smallint,
  forest_frac    real,

  -- model outputs
  susceptibility real check (susceptibility between 0 and 1),
  trigger_score  real check (trigger_score between 0 and 1),
  risk_score     real check (risk_score between 0 and 1),
  risk_band      smallint check (risk_band between 0 and 4),
  -- 0 normal · 1 watch · 2 alert · 3 warning · 4 severe (IMD ladder)
  provenance     text default 'index'
                 check (provenance in ('model','index')),

  computed_at    timestamptz default now()
);
create index if not exists risk_cells_geom_idx     on risk_cells using gist (geom);
create index if not exists risk_cells_centroid_idx on risk_cells using gist (centroid);
create index if not exists risk_cells_band_idx     on risk_cells (risk_band);

-- ===============================================================
-- INSAR DEFORMATION  ·  pre-computed offline, never written at
-- request time. See docs/TRD.md §5.
-- ===============================================================
create table if not exists deformation_points (
  id             bigserial primary key,
  geom           geometry(Point, 4326) not null,
  corridor_id    text not null,
  velocity_mm_yr real,           -- line of sight; negative = moving away
  coherence      real check (coherence between 0 and 1),
  acceleration   real,           -- 2nd derivative; THIS is the warning signal
  alert_state    text default 'stable'
                 check (alert_state in ('stable','creeping','accelerating')),
  n_acquisitions smallint,
  first_date     date,
  last_date      date
);
create index if not exists deformation_geom_idx  on deformation_points using gist (geom);
create index if not exists deformation_state_idx on deformation_points (alert_state);
-- discard coherence < 0.3 at load time; vegetated hillslopes decorrelate
-- and low-coherence points produce confident-looking nonsense

create table if not exists deformation_series (
  point_id        bigint references deformation_points(id) on delete cascade,
  acq_date        date not null,
  displacement_mm real,
  primary key (point_id, acq_date)
);

create table if not exists insar_corridors (
  id           text primary key,
  geom         geometry(Polygon, 4326) not null,
  description  text,
  processed_at timestamptz,
  track        smallint,
  orbit_dir    text check (orbit_dir in ('ascending','descending')),
  n_scenes     smallint
);
create index if not exists corridors_geom_idx on insar_corridors using gist (geom);
-- the UI draws this boundary; outside it the deformation layer is empty
-- and says so. Never interpolate across unprocessed area.

-- ===============================================================
-- ROADS + SETTLEMENTS + ISOLATION
-- ===============================================================
create table if not exists road_segments (
  id             bigserial primary key,
  osm_id         bigint,
  geom           geometry(LineString, 4326) not null,
  road_class     text,
  length_m       real,
  base_speed_kmh real,
  min_elev_m     real,
  max_slope_adj  real,                    -- steepest adjacent cell
  blocked        boolean default false,
  block_reason   text check (block_reason in
                   ('predicted','reported','confirmed','cleared')),
  blocked_since  timestamptz,
  updated_at     timestamptz default now()
);
create index if not exists road_geom_idx    on road_segments using gist (geom);
create index if not exists road_blocked_idx on road_segments (blocked);

create table if not exists settlements (
  id              bigserial primary key,
  name            text,
  geom            geometry(Point, 4326) not null,
  population      integer,
  isolated        boolean default false,
  isolation_score real check (isolation_score between 0 and 1),
  component_size  integer,                -- settlements in same road component
  path_to_hq      boolean default true,
  updated_at      timestamptz default now()
);
create index if not exists settlements_geom_idx on settlements using gist (geom);
create index if not exists settlements_iso_idx  on settlements (isolated, isolation_score desc);

create table if not exists facilities (
  id       bigserial primary key,
  osm_id   bigint,
  name     text,
  kind     text,          -- hospital | clinic | school | fire_station | police | shelter
  geom     geometry(Point, 4326) not null,
  capacity integer
);
create index if not exists facilities_geom_idx on facilities using gist (geom);

-- ===============================================================
-- CITIZEN REPORTS  ·  id is CLIENT-generated so offline replay is
-- idempotent by construction
-- ===============================================================
create table if not exists citizen_reports (
  id            uuid primary key,
  location      geometry(Point, 4326) not null,
  accuracy_m    real,
  kind          text check (kind in
                  ('crack','slope_movement','road_blocked','water_seepage','other')),
  auto_class    text,                     -- on-device ONNX output
  auto_conf     real check (auto_conf between 0 and 1),
  note          text,
  media_url     text,
  media_type    text check (media_type in ('image','video')),
  status        text default 'pending'
                check (status in ('pending','verified','dismissed','duplicate')),
  cluster_id    bigint,                   -- 100 m / 60 min dedup group
  reporter_hash text,                     -- hashed device id, NEVER identity
  lang          text,
  created_at    timestamptz not null,     -- client clock
  synced_at     timestamptz default now(),
  reviewed_at   timestamptz
);
create index if not exists reports_geom_idx    on citizen_reports using gist (location);
create index if not exists reports_queue_idx   on citizen_reports (status, created_at desc);
create index if not exists reports_cluster_idx on citizen_reports (cluster_id);

create table if not exists report_clusters (
  id           bigserial primary key,
  centroid     geometry(Point, 4326) not null,
  report_count integer default 1,
  first_seen   timestamptz,
  last_seen    timestamptz,
  dominant_kind text
);
create index if not exists clusters_geom_idx on report_clusters using gist (centroid);

-- ===============================================================
-- ALERTS  ·  CAP payloads generated and displayed; gateway
-- delivery is out of scope (procurement, not engineering).
-- languages stored as ISO codes from {'en','hi','as'} only — see
-- services/api/config.py:LANGUAGES.
-- ===============================================================
create table if not exists alerts (
  id          uuid primary key default gen_random_uuid(),
  cap_xml     text not null,
  severity    smallint check (severity between 0 and 4),
  headline    text,
  geofence    geometry(Polygon, 4326),
  languages   text[],
  trigger_src text check (trigger_src in
                ('risk_band','deformation','report','manual')),
  issued_at   timestamptz default now(),
  expires_at  timestamptz
);
create index if not exists alerts_geofence_idx on alerts using gist (geofence);
create index if not exists alerts_issued_idx   on alerts (issued_at desc);

-- ===============================================================
-- HELP REQUESTS + DISPATCH  ·  carried from the flood build
-- ===============================================================
create table if not exists requests (
  id             uuid primary key,        -- client-generated
  location       geometry(Point, 4326) not null,
  people_count   smallint not null check (people_count > 0),
  category       text not null check (category in ('medical','stranded','evacuation')),
  note           text,
  status         text not null default 'open'
                 check (status in ('open','assigned','in_progress','resolved','cancelled')),
  settlement_id  bigint references settlements(id),

  severity       real check (severity between 0 and 1),
  sev_persons    real,   -- components stored individually so the officer
  sev_category   real,   -- can see WHY one request outranks another
  sev_area_risk  real,
  sev_wait       real,
  sev_isolation  real,   -- NEW for NER: cut-off settlements have no self-rescue route

  created_at     timestamptz not null,
  synced_at      timestamptz default now(),
  resolved_at    timestamptz
);
create index if not exists requests_geom_idx  on requests using gist (location);
create index if not exists requests_queue_idx on requests (status, severity desc);

create table if not exists units (
  id         uuid primary key default uuid_generate_v4(),
  label      text not null,
  kind       text not null check (kind in ('team','ambulance','truck','excavator','helicopter')),
  capacity   smallint not null check (capacity > 0),
  position   geometry(Point, 4326) not null,
  home_base  geometry(Point, 4326),
  status     text not null default 'available'
             check (status in ('available','assigned','en_route','returning','offline')),
  updated_at timestamptz default now()
);
create index if not exists units_geom_idx   on units using gist (position);
create index if not exists units_status_idx on units (status);

create table if not exists dispatch_rounds (
  id            uuid primary key default gen_random_uuid(),
  started_at    timestamptz default now(),
  zone_count    smallint,
  request_count smallint,
  unit_count    smallint,
  backend       text check (backend in ('qaoa','annealing','ortools','greedy','manual')),
  fell_back     boolean default false,
  objective     real,
  solve_ms      integer
);

create table if not exists assignments (
  id         uuid primary key default gen_random_uuid(),
  round_id   uuid references dispatch_rounds(id) on delete cascade,
  unit_id    uuid references units(id),
  request_id uuid references requests(id),
  zone_id    smallint,
  travel_s   integer,
  route      geometry(LineString, 4326),
  route_source text check (route_source in ('road','direct')),
  created_at timestamptz default now()
);
create index if not exists assignments_round_idx on assignments (round_id);
-- last line of defence: a double-booking cannot be persisted even if
-- the solver validator is somehow bypassed
create unique index if not exists assignments_unit_per_round    on assignments (round_id, unit_id);
create unique index if not exists assignments_request_per_round on assignments (round_id, request_id);

create table if not exists benchmarks (
  id                bigserial primary key,
  round_id          uuid references dispatch_rounds(id) on delete cascade,
  backend           text not null,
  objective         real,
  solve_ms          integer,
  constraints_valid boolean,
  qubit_count       smallint
);

-- ===============================================================
-- APPEND-ONLY OPERATIONS LEDGER
-- Never UPDATE. Never DELETE. This is the post-event audit trail.
-- ===============================================================
create table if not exists ops_log (
  id       bigserial primary key,
  at       timestamptz default now(),
  channel  text not null check (channel in
             ('risk','deformation','intake','dispatch','road','alert','system')),
  severity smallint default 0 check (severity between 0 and 4),
  message  text not null
);
create index if not exists ops_log_at_idx on ops_log (at desc);

-- ===============================================================
-- SENSOR INGEST CONTRACT
-- No in-situ hardware exists. This table documents the interface so
-- physical sensors drop in without a rewrite. Do NOT populate it
-- with simulated readings.
-- ===============================================================
create table if not exists sensor_readings (
  id          bigserial primary key,
  sensor_id   text not null,
  geom        geometry(Point, 4326) not null,
  kind        text check (kind in
                ('soil_moisture','tilt','piezometer','rain_gauge','extensometer')),
  value       real,
  unit        text,
  quality     smallint,
  recorded_at timestamptz not null,
  source      text default 'satellite'
              check (source in ('satellite','in_situ','modelled'))
);
create index if not exists sensor_geom_idx on sensor_readings using gist (geom);
create index if not exists sensor_time_idx on sensor_readings (recorded_at desc);

-- ===============================================================
-- REALTIME
-- ===============================================================
alter publication supabase_realtime add table citizen_reports;
alter publication supabase_realtime add table requests;
alter publication supabase_realtime add table assignments;
alter publication supabase_realtime add table ops_log;
alter publication supabase_realtime add table road_segments;
alter publication supabase_realtime add table alerts;

-- ===============================================================
-- RLS  ·  demo scope. Tighten before any real deployment.
-- ===============================================================
alter table citizen_reports enable row level security;
alter table requests        enable row level security;
alter table alerts          enable row level security;
alter table ops_log         enable row level security;

create policy demo_reports on citizen_reports for all using (true) with check (true);
create policy demo_requests on requests       for all using (true) with check (true);
create policy demo_alerts   on alerts         for all using (true) with check (true);
create policy demo_log      on ops_log        for all using (true) with check (true);
