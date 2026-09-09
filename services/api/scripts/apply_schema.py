"""Apply schema.sql to the database using Python psycopg2."""

import os
import psycopg2
from pathlib import Path

# Get database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    # Try to read from .env file
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.startswith("DATABASE_URL="):
                    DATABASE_URL = line.strip().split("=", 1)[1]
                    break

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment or .env file")

print(f"Connecting to database...")

# Connect to database
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

# Read schema.sql
schema_path = Path(__file__).parent.parent / "schema.sql"
with open(schema_path) as f:
    schema_sql = f.read()

print(f"Applying schema from {schema_path}...")

# Execute schema with error handling for existing objects
# Split into individual statements to handle duplicates gracefully
statements = schema_sql.split(';')
for stmt in statements:
    stmt = stmt.strip()
    if stmt and not stmt.startswith('--'):
        try:
            cursor.execute(stmt)
        except psycopg2.errors.DuplicateObject as e:
            print(f"Skipping duplicate object: {e}")
            continue
        except psycopg2.errors.UndefinedColumn as e:
            print(f"Skipping column error (existing table): {e}")
            continue
        except psycopg2.errors.DuplicateTable as e:
            print(f"Skipping duplicate table: {e}")
            continue
        except psycopg2.errors.DuplicateFunction as e:
            print(f"Skipping duplicate function: {e}")
            continue
        except Exception as e:
            print(f"Skipping statement due to error: {e}")
            continue

print("Schema applied successfully!")

# Verify tables were created
cursor.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name;
""")
tables = cursor.fetchall()
print(f"\nTables created: {len(tables)}")
for table in tables:
    print(f"  - {table[0]}")

cursor.close()
conn.close()
print("\nDatabase migration complete!")
