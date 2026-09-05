# Deploying Q-resQ

**Backend → Railway. Frontend → Vercel.** This is the pinned split per `CLAUDE.md` §2.3 — Vercel auto-detects Vite with zero config, so this is the simple path, not a fallback.

Two independent deploys. Order matters: backend first, because the frontend's build needs the backend's URL baked in.

---

## 0. Commit what deploy needs

Run from the repo root. Three things must be committed and pushed before either deploy will actually work.

```bash
# The 5 precomputed risk cache files - the backend reads these directly
# and never needs the ~130MB of raw DEM/rainfall source files at
# runtime. Without these committed, a fresh deploy has no risk data
# and no way to compute it (no DEM, no OpenTopography key set).
git add services/api/data/raw/risk_cells_cache.npy \
        services/api/data/raw/risk_cells_cache_flood.npy \
        services/api/data/raw/risk_cells_cache_urban_flooding.npy \
        services/api/data/raw/risk_cells_cache_landslide.npy \
        services/api/data/raw/risk_terrain_cache.npy

# The deploy-readiness fixes: CORS, the frontend's API base URL, and
# the backend's Dockerfile (Railway's zero-config build is a real risk
# given rasterio/pysheds/geopandas/qiskit-aer in requirements.txt).
git add services/api/Dockerfile services/api/main.py \
        services/api/risk/features.py apps/web/src/lib/api.ts .gitignore

git commit -m "Deployment: Dockerfile, CORS, precomputed risk caches"
git push
```

`apps/web/Dockerfile` and the root `.dockerignore` from an earlier Railway-only draft aren't needed for this path — Vercel doesn't look at them. Harmless to leave in the repo, just ignore them.

---

## 1. Backend on Railway

1. **New Project → Deploy from GitHub repo** → pick this repo. Rename the service `q-resq-api`.
2. **Settings → Build.** Leave **Root Directory** blank (the build context must stay the repo root — `requirements.txt` installs a sibling package one level up via `-e ../../packages/qubo-dispatch`). Set **Dockerfile Path** to:
   ```
   services/api/Dockerfile
   ```
3. **Variables.** Nothing is strictly required to boot — the app runs on in-memory stores and the committed risk caches. Add `ALLOWED_ORIGINS` once you have the Vercel URL (step 3 below); leave it empty for now.
4. **Settings → Networking → Generate Domain.** Copy it — e.g. `https://q-resq-api-production.up.railway.app`. You need this exact URL next.
5. Push triggers the build automatically. Expect several minutes — `qiskit-aer` and the GDAL-linked packages are slow to install. Watch **Deployments** for the active build's logs.

**Verify before moving on:**
```bash
curl https://<your-api-domain>/health          # {"status":"ok"}
curl https://<your-api-domain>/risk/cells       # real GeoJSON, not an error
```
The second call is the one that actually proves the committed caches made it into the image.

---

## 2. Frontend on Vercel

1. **Add New Project → Import Git Repository** → same repo.
2. **Root Directory: `apps/web`.** This is the one setting that matters — Vercel then treats `apps/web` as the project root and auto-detects Vite (build command `vite build` / `tsc -b && vite build` from `package.json`, output `dist`, both already correct with no changes needed).
3. **Environment Variables** → add:
   ```
   VITE_API_URL = https://q-resq-api-production.up.railway.app
   ```
   Use the exact Railway domain from step 1.4, **no trailing slash**. Vite bakes this into the JS bundle at build time — it is not read at runtime. If you change it later, redeploy (not just restart).
4. **Deploy.** Copy the resulting URL (e.g. `https://q-resq-web.vercel.app`) — needed for step 3.

---

## 3. Connect them

Back on Railway, `q-resq-api` → **Variables**:
```
ALLOWED_ORIGINS = https://q-resq-web.vercel.app
```
Setting a variable triggers a redeploy automatically.

---

## Verify, in order

- [ ] `curl https://<api-domain>/health` → `{"status":"ok"}`
- [ ] `curl https://<api-domain>/risk/cells` → real risk-cell GeoJSON
- [ ] Open the Vercel URL — the map loads, no blank page
- [ ] DevTools → Network tab — requests go to the Railway domain, not `/api/...` on Vercel's own origin (confirms `VITE_API_URL` actually baked into the build)
- [ ] No CORS errors in the console (confirms `ALLOWED_ORIGINS` matches exactly)
- [ ] Click **Seed scenario**, then **Dispatch** — a real round comes back, routes draw on the map

---

## If something breaks

| Symptom | Fix |
|---|---|
| Map/panels never populate; Network tab shows requests to the *Vercel* domain | `VITE_API_URL` wasn't set before the build ran. Set it in Vercel's env vars, then trigger a fresh deploy — a cached build won't pick it up. |
| Browser console: CORS error, no `Access-Control-Allow-Origin` header | `ALLOWED_ORIGINS` on Railway doesn't exactly match the Vercel domain — check for a trailing slash or `http` vs `https` mismatch. |
| Railway build fails installing rasterio/geopandas/pysheds | Confirm the service is building from the Dockerfile (Settings → Build shows "Dockerfile", not "Nixpacks") and that **Root Directory is blank**, not `services/api` — a non-blank Root Directory breaks the build context the Dockerfile's `COPY packages/qubo-dispatch ...` line depends on. |
| `/risk/cells` times out or 500s on first request | The precomputed `.npy` caches weren't committed. Run `git ls-files \| grep npy` — all 5 files from step 0 should be listed. If not, go back to step 0. |
| Vercel build fails on `tsc -b` | Almost always a real type error, not a config problem — run `npx tsc --noEmit` locally in `apps/web` first and fix what it reports before redeploying. |

---

**Commit the caches first. Backend before frontend. Watch the first Railway build patiently — it's the slow one.**
