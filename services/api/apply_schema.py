"""Apply schema.sql to Supabase database using Supabase client."""
import os
from dotenv import load_dotenv
from supabase import Client, create_client
import psycopg2
from urllib.parse import urlparse, unquote

load_dotenv()

# Use Supabase client for safer operations
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
DATABASE_URL = os.environ["DATABASE_URL"]

print(f"Connecting to Supabase at {SUPABASE_URL}...")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# For DDL operations, we need direct Postgres connection
parsed = urlparse(DATABASE_URL)
user = parsed.username
password = unquote(parsed.password)
host = parsed.hostname
port = parsed.port
database = parsed.path.lstrip("/")

print(f"Connecting to Postgres at {host}...")

conn = psycopg2.connect(
    host=host,
    port=port,
    database=database,
    user=user,
    password=password
)

conn.autocommit = True
cursor = conn.cursor()

# Read and execute schema.sql
with open("schema.sql", "r") as f:
    schema_sql = f.read()

print("Applying schema...")

# Split by semicolon to handle errors gracefully
statements = [s.strip() for s in schema_sql.split(';') if s.strip()]

for i, stmt in enumerate(statements):
    if not stmt or stmt.startswith('--'):
        continue
    try:
        cursor.execute(stmt)
        print(f"Statement {i+1}/{len(statements)}: OK")
    except psycopg2.errors.DuplicateObject as e:
        print(f"Statement {i+1}/{len(statements)}: SKIPPED (already exists)")
    except psycopg2.errors.DuplicateTable as e:
        print(f"Statement {i+1}/{len(statements)}: SKIPPED (table exists)")
    except psycopg2.errors.DuplicateColumn as e:
        print(f"Statement {i+1}/{len(statements)}: SKIPPED (column exists)")
    except Exception as e:
        print(f"Statement {i+1}/{len(statements)}: ERROR - {e}")
        # Continue with other statements

print("Schema applied (with possible skips for existing objects)!")

cursor.close()
conn.close()

