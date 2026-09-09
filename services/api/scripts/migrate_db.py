"""Clean database migration script that handles existing tables."""

import os
import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]  # see services/api/.env - gitignored, never hardcode this

print(f"Connecting to database...")

# Connect to database
conn = psycopg2.connect(DATABASE_URL)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cursor = conn.cursor()

print("Connected successfully!")

# First, check what tables already exist
cursor.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name;
""")
existing_tables = [row[0] for row in cursor.fetchall()]
print(f"Existing tables: {existing_tables}")

# Enable extensions
print("Enabling extensions...")
try:
    cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    print("Extensions enabled!")
except Exception as e:
    print(f"Extension error (may already exist): {e}")

# Create tables one by one with error handling
tables_to_create = [
    # Risk cells
    """CREATE TABLE IF NOT EXISTS risk_cells (
      id             bigserial primary key,
      geom           geometry(Polygon, 4326) not null,
      centroid       geometry(Point, 4326)   not null,
      elevation_m    real,
      slope_deg      real,
      aspect_sin     real,
      aspect_cos     real,
      curv_plan      real,
      curv_prof      real,
      ls_factor      real,
      hand_m         real,
      twi            real,
      dist_stream_m  real,
      dist_road_m    real,
      is_cut_slope   boolean default false,
      lithology      smallint,
      landcover      smallint,
      forest_frac    real,
      susceptibility real check (susceptibility between 0 and 1),
      trigger_score  real check (trigger_score between 0 and 1),
      risk_score     real check (risk_score between 0 and 1),
      risk_band      smallint check (risk_band between 0 and 4),
      provenance     text default 'index' check (provenance in ('model','index')),
      computed_at    timestamptz default now()
    )""",

    # Deformation points
    """CREATE TABLE IF NOT EXISTS deformation_points (
      id             bigserial primary key,
      geom           geometry(Point, 4326) not null,
      corridor_id    text not null,
      velocity_mm_yr real,
      coherence      real check (coherence between 0 and 1),
      acceleration   real,
      alert_state    text default 'stable' check (alert_state in ('stable','creeping','accelerating')),
      n_acquisitions smallint,
      first_date     date,
      last_date      date
    )""",

    # Deformation series
    """CREATE TABLE IF NOT EXISTS deformation_series (
      point_id        bigint references deformation_points(id) on delete cascade,
      acq_date        date not null,
      displacement_mm real,
      primary key (point_id, acq_date)
    )""",

    # InSAR corridors
    """CREATE TABLE IF NOT EXISTS insar_corridors (
      id           text primary key,
      geom         geometry(Polygon, 4326) not null,
      description  text,
      processed_at timestamptz,
      track        smallint,
      orbit_dir    text check (orbit_dir in ('ascending','descending')),
      n_scenes     smallint
    )""",

    # Road segments
    """CREATE TABLE IF NOT EXISTS road_segments (
      id             bigserial primary key,
      osm_id         bigint,
      geom           geometry(LineString, 4326) not null,
      road_class     text,
      length_m       real,
      base_speed_kmh real,
      min_elev_m     real,
      max_slope_adj  real,
      blocked        boolean default false,
      block_reason   text check (block_reason in ('predicted','reported','confirmed','cleared')),
      blocked_since  timestamptz,
      updated_at     timestamptz default now()
    )""",

    # Settlements
    """CREATE TABLE IF NOT EXISTS settlements (
      id              bigserial primary key,
      name            text,
      geom            geometry(Point, 4326) not null,
      population      integer,
      isolated        boolean default false,
      isolation_score real check (isolation_score between 0 and 1),
      component_size  integer,
      path_to_hq      boolean default true,
      updated_at      timestamptz default now()
    )""",

    # Facilities
    """CREATE TABLE IF NOT EXISTS facilities (
      id       bigserial primary key,
      osm_id   bigint,
      name     text,
      kind     text,
      geom     geometry(Point, 4326) not null,
      capacity integer
    )""",

    # Citizen reports
    """CREATE TABLE IF NOT EXISTS citizen_reports (
      id            uuid primary key,
      location      geometry(Point, 4326) not null,
      accuracy_m    real,
      kind          text check (kind in ('crack','slope_movement','road_blocked','water_seepage','other')),
      auto_class    text,
      auto_conf     real check (auto_conf between 0 and 1),
      note          text,
      media_url     text,
      media_type    text check (media_type in ('image','video')),
      status        text default 'pending' check (status in ('pending','verified','dismissed','duplicate')),
      cluster_id    bigint,
      reporter_hash text,
      lang          text,
      created_at    timestamptz not null,
      synced_at     timestamptz default now(),
      reviewed_at   timestamptz
    )""",

    # Report clusters
    """CREATE TABLE IF NOT EXISTS report_clusters (
      id           bigserial primary key,
      centroid     geometry(Point, 4326) not null,
      report_count integer default 1,
      first_seen   timestamptz,
      last_seen    timestamptz,
      dominant_kind text
    )""",

    # Alerts
    """CREATE TABLE IF NOT EXISTS alerts (
      id          uuid primary key default gen_random_uuid(),
      cap_xml     text not null,
      severity    smallint check (severity between 0 and 4),
      headline    text,
      geofence    geometry(Polygon, 4326),
      languages   text[],
      trigger_src text check (trigger_src in ('risk_band','deformation','report','manual')),
      issued_at   timestamptz default now(),
      expires_at  timestamptz
    )""",

    # Requests
    """CREATE TABLE IF NOT EXISTS requests (
      id             uuid primary key,
      location       geometry(Point, 4326) not null,
      people_count   smallint not null check (people_count > 0),
      category       text not null check (category in ('medical','stranded','evacuation')),
      note           text,
      status         text not null default 'open' check (status in ('open','assigned','in_progress','resolved','cancelled')),
      settlement_id  bigint references settlements(id),
      severity       real check (severity between 0 and 1),
      sev_persons    real,
      sev_category   real,
      sev_area_risk  real,
      sev_wait       real,
      sev_isolation  real,
      created_at     timestamptz not null,
      synced_at      timestamptz default now(),
      resolved_at    timestamptz
    )""",

    # Units
    """CREATE TABLE IF NOT EXISTS units (
      id         uuid primary key default uuid_generate_v4(),
      label      text not null,
      kind       text not null check (kind in ('team','ambulance','truck','excavator','helicopter')),
      capacity   smallint not null check (capacity > 0),
      position   geometry(Point, 4326) not null,
      home_base  geometry(Point, 4326),
      status     text not null default 'available' check (status in ('available','assigned','en_route','returning','offline')),
      updated_at timestamptz default now()
    )""",

    # Dispatch rounds
    """CREATE TABLE IF NOT EXISTS dispatch_rounds (
      id            uuid primary key default gen_random_uuid(),
      started_at    timestamptz default now(),
      zone_count    smallint,
      request_count smallint,
      unit_count    smallint,
      backend       text check (backend in ('qaoa','annealing','ortools','greedy','manual')),
      fell_back     boolean default false,
      objective     real,
      solve_ms      integer
    )""",

    # Assignments
    """CREATE TABLE IF NOT EXISTS assignments (
      id         uuid primary key default gen_random_uuid(),
      round_id   uuid references dispatch_rounds(id) on delete cascade,
      unit_id    uuid references units(id),
      request_id uuid references requests(id),
      zone_id    smallint,
      travel_s   integer,
      route      geometry(LineString, 4326),
      route_source text check (route_source in ('road','direct')),
      created_at timestamptz default now()
    )""",

    # Benchmarks
    """CREATE TABLE IF NOT EXISTS benchmarks (
      id                bigserial primary key,
      round_id          uuid references dispatch_rounds(id) on delete cascade,
      backend           text not null,
      objective         real,
      solve_ms          integer,
      constraints_valid boolean,
      qubit_count       smallint
    )""",

    # Operations log
    """CREATE TABLE IF NOT EXISTS ops_log (
      id       bigserial primary key,
      at       timestamptz default now(),
      channel  text not null check (channel in ('risk','deformation','intake','dispatch','road','alert','system')),
      severity smallint default 0 check (severity between 0 and 4),
      message  text not null
    )""",

    # Sensor readings
    """CREATE TABLE IF NOT EXISTS sensor_readings (
      id          bigserial primary key,
      sensor_id   text not null,
      geom        geometry(Point, 4326) not null,
      kind        text check (kind in ('soil_moisture','tilt','piezometer','rain_gauge','extensometer')),
      value       real,
      unit        text,
      quality     smallint,
      recorded_at timestamptz not null,
      source      text default 'satellite' check (source in ('satellite','in_situ','modelled'))
    )""",
]

# Create tables
for i, table_sql in enumerate(tables_to_create):
    try:
        cursor.execute(table_sql)
        print(f"[OK] Table {i+1}/{len(tables_to_create)} created")
    except Exception as e:
        print(f"[ERROR] Table {i+1}/{len(tables_to_create)} error: {e}")

# Create indexes
print("\nCreating indexes...")
indexes = [
    "CREATE INDEX IF NOT EXISTS risk_cells_geom_idx ON risk_cells USING gist (geom)",
    "CREATE INDEX IF NOT EXISTS risk_cells_centroid_idx ON risk_cells USING gist (centroid)",
    "CREATE INDEX IF NOT EXISTS risk_cells_band_idx ON risk_cells (risk_band)",
    "CREATE INDEX IF NOT EXISTS deformation_geom_idx ON deformation_points USING gist (geom)",
    "CREATE INDEX IF NOT EXISTS deformation_state_idx ON deformation_points (alert_state)",
    "CREATE INDEX IF NOT EXISTS corridors_geom_idx ON insar_corridors USING gist (geom)",
    "CREATE INDEX IF NOT EXISTS road_geom_idx ON road_segments USING gist (geom)",
    "CREATE INDEX IF NOT EXISTS road_blocked_idx ON road_segments (blocked)",
    "CREATE INDEX IF NOT EXISTS settlements_geom_idx ON settlements USING gist (geom)",
    "CREATE INDEX IF NOT EXISTS settlements_iso_idx ON settlements (isolated, isolation_score desc)",
    "CREATE INDEX IF NOT EXISTS facilities_geom_idx ON facilities USING gist (geom)",
    "CREATE INDEX IF NOT EXISTS reports_geom_idx ON citizen_reports USING gist (location)",
    "CREATE INDEX IF NOT EXISTS reports_queue_idx ON citizen_reports (status, created_at desc)",
    "CREATE INDEX IF NOT EXISTS reports_cluster_idx ON citizen_reports (cluster_id)",
    "CREATE INDEX IF NOT EXISTS clusters_geom_idx ON report_clusters USING gist (centroid)",
    "CREATE INDEX IF NOT EXISTS alerts_geofence_idx ON alerts USING gist (geofence)",
    "CREATE INDEX IF NOT EXISTS alerts_issued_idx ON alerts (issued_at desc)",
    "CREATE INDEX IF NOT EXISTS requests_geom_idx ON requests USING gist (location)",
    "CREATE INDEX IF NOT EXISTS requests_queue_idx ON requests (status, severity desc)",
    "CREATE INDEX IF NOT EXISTS units_geom_idx ON units USING gist (position)",
    "CREATE INDEX IF NOT EXISTS units_status_idx ON units (status)",
    "CREATE INDEX IF NOT EXISTS assignments_round_idx ON assignments (round_id)",
    "CREATE INDEX IF NOT EXISTS ops_log_at_idx ON ops_log (at desc)",
    "CREATE INDEX IF NOT EXISTS sensor_geom_idx ON sensor_readings USING gist (geom)",
    "CREATE INDEX IF NOT EXISTS sensor_time_idx ON sensor_readings (recorded_at desc)",
]

for i, index_sql in enumerate(indexes):
    try:
        cursor.execute(index_sql)
        print(f"[OK] Index {i+1}/{len(indexes)} created")
    except Exception as e:
        print(f"[ERROR] Index {i+1}/{len(indexes)} error: {e}")

# Setup Realtime
print("\nSetting up Realtime...")
realtime_tables = ['citizen_reports', 'requests', 'assignments', 'ops_log', 'road_segments', 'alerts']
for table in realtime_tables:
    try:
        cursor.execute(f"ALTER PUBLICATION supabase_realtime ADD TABLE {table}")
        print(f"[OK] {table} added to Realtime")
    except Exception as e:
        print(f"[ERROR] {table} Realtime error: {e}")

# Setup RLS
print("\nSetting up RLS...")
rls_tables = ['citizen_reports', 'requests', 'alerts', 'ops_log']
for table in rls_tables:
    try:
        cursor.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        cursor.execute(f"CREATE POLICY demo_{table} ON {table} FOR ALL USING (true) WITH CHECK (true)")
        print(f"[OK] {table} RLS enabled")
    except Exception as e:
        print(f"[ERROR] {table} RLS error: {e}")

# Verify final state
cursor.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name;
""")
final_tables = [row[0] for row in cursor.fetchall()]
print(f"\nFinal table count: {len(final_tables)}")
print("Tables:", final_tables)

cursor.close()
conn.close()
print("\n[SUCCESS] Database migration complete!")
