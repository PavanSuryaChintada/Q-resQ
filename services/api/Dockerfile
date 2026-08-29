# Build context is the repo root (Railway: leave Root Directory blank,
# set Dockerfile Path to services/api/Dockerfile) - needed because
# requirements.txt has an editable install of the sibling
# packages/qubo-dispatch package, one level up from services/api.
FROM python:3.11-slim

# System libs for rasterio/geopandas/pysheds (GDAL/GEOS/PROJ) and
# netCDF4 (libnetcdf) - these packages need them even though the pip
# wheels handle most of the Python-side compilation themselves.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin libgdal-dev libgeos-dev libproj-dev libnetcdf-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY packages/qubo-dispatch /app/packages/qubo-dispatch
COPY services/api /app/services/api

WORKDIR /app/services/api
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Railway injects PORT at runtime - must bind to it, not a fixed 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
