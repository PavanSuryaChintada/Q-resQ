# PRD — PRAHARI

**Problem statement:** #1, Disaster Prediction and Community Response System
**Event:** HackSprint 2.0, AITAM Tekkali
**Build window:** 24 hours
**Version:** 1.0

---

## 1. The insight

Every disaster-management project stops at prediction. Rainfall goes in, a risk map comes out, the demo ends.

But a risk map does not rescue anyone. The moment a flood starts, a district emergency officer faces a different question entirely: *I have 15 boats and 200 families calling. Who do I send where, and in what order, while roads are going underwater as we speak?*

That is not a prediction problem. It is a decision problem, and it is NP-hard.

PRAHARI solves both, and treats them as the separate problems they are.

| | Question | Discipline |
|---|---|---|
| **Prediction** | Which areas will flood, and how badly? | Supervised ML |
| **Decision** | Given what is flooding, who gets rescued first? | Combinatorial optimization |

---

## 2. Why ML cannot solve the decision problem

This section exists because it is the question judges will ask.

**No training data.** A supervised model learns from labelled examples. There is no dataset of optimal rescue dispatch decisions — nobody recorded the right answer, only what overwhelmed officials actually did under pressure.

**No hard constraints.** A neural network outputs probabilities. It can assign one boat to two locations simultaneously, because nothing in its architecture forbids it. An optimizer treats "one unit, one destination" as a constraint that cannot be violated. In a rescue, an invalid plan is worse than no plan.

**No pattern to match.** Every disaster presents a novel configuration — different units, different requests, different impassable roads. This is search through a solution space, not recognition of a learned pattern.

The dispatch problem is combinatorial optimization. That is precisely the problem class quantum optimization targets — not image recognition, not language.

---

## 3. Users

**Primary — District Emergency Operations officer.** Sits at a desk in the district collectorate during an event. Needs to see risk, see incoming requests, and get a dispatch plan they can act on and override. Not technical. Judges every second of latency.

**Secondary — Field responder.** On a boat or in a vehicle. Phone only. Intermittent or absent connectivity. Needs their assignment and the route, and needs to log completion.

**Tertiary — Affected citizen.** Submitting a rescue request from a flooded area on a degraded network. Must be able to submit offline and trust it will send.

---

## 4. Scope

### In scope — must ship

**F1 · Risk map**
Choropleth of flood risk across the district at ward/grid resolution, driven by terrain and rainfall. Toggleable layers: risk, elevation, road status, facilities. Click any cell for its risk score and the top three contributing features.

**F2 · Rescue request intake**
Citizen-facing form: location (auto-detected or map-pinned), people count, category (medical / stranded / evacuation), free-text note. Works fully offline; queues locally and syncs on reconnect.

**F3 · Severity triage**
Every request gets a computed severity score from people count, category, area risk, and time waiting. Requests are ranked, and the ranking is explainable — the officer can see why one outranks another.

**F4 · Dispatch engine**
Partitions open requests into geographic zones, formulates each zone as a QUBO, solves in parallel across the solver chain, and returns an assignment of units to requests with routes over the flood-aware road graph.

**F5 · Solver benchmark**
A visible comparison of QAOA, simulated annealing, greedy, and OR-Tools on the same problem instances: objective value, wall-clock time, constraint validity. Honest results, including cases where quantum loses.

**F6 · Operations dashboard**
Live view: open requests, unit status, current assignments, and an append-only dispatch log.

**F7 · Offline capability**
Cached map tiles for the district, queued request submission, background sync, idempotent replay.

### Out of scope — explicitly cut

- User accounts beyond a single demo operator login
- SMS or push delivery (the alert payload is generated and displayed, not sent)
- Multi-district support
- Multi-stop vehicle routing (each unit takes one request per dispatch round)
- Real quantum hardware execution
- Mobile native apps
- Historical analytics beyond the seeded scenario

Cutting these is a decision, not an oversight. Say so if asked.

---

## 5. The demo scenario

Cyclone Titli made landfall near Palasa, Srikakulam district, on 11 October 2018. It is within living memory for everyone in the room at AITAM.

Seeded from real data:
- IMD cyclone track coordinates and landfall timing
- NASA POWER rainfall for the actual dates
- Copernicus DEM elevation for the district
- OSM facility locations — district hospital, fire stations, schools used as shelters
- ~200 synthetic rescue requests placed at real village coordinates, weighted toward genuinely low-lying areas per the computed HAND raster
- 15 rescue units at real facility positions

**The demo arc, in order:**
1. Rainfall accumulates, the risk map lights up
2. Requests begin arriving
3. Zones partition, the dispatch engine solves, units are assigned
4. A road segment floods
5. The engine re-solves and assignments visibly change

Step 5 is the peak. Rehearse it until it is muscle memory.

---

## 6. Success criteria

**Must be true at demo time**
- Dispatch returns a valid assignment for 200 requests across 40 zones in under 5 seconds
- No returned assignment ever double-books a unit or a request, across any solver
- The system produces a plan with Qiskit uninstalled
- A request submitted offline appears on the dashboard within 3 seconds of reconnecting
- The benchmark table displays real measured numbers, not placeholders

**Judged on**
- Recognising that prediction and decision are different problems — this is the whole pitch
- Honest quantum positioning, benchmarked rather than claimed
- Offline capability actually demonstrated, not described
- A demo where nothing breaks

---

## 7. Positioning

> "Everyone predicts the flood. We also decide who gets rescued first."

**Full answer, for the quantum question:**
> AI predicts what will happen. Optimization decides what to do about it. Those are different problems, and a neural network cannot do the second — there is no training data for optimal rescue decisions, and it cannot enforce that one boat goes to one place. So we formulated dispatch as a QUBO. It runs on OR-Tools today and QAOA on the same formulation, benchmarked side by side. Quantum is not in the critical path. If the hardware never improves, this still ships.

**Real-world deployment path.** Quantum execution is not viable inside a real-time rescue loop — QPU access is queued and pay-per-shot. But cyclones are forecast 48 hours ahead. Pre-positioning rescue assets during the warning window is an optimization that can afford to run slowly. That is a genuine near-term use case, and it did not require overstating anything.

---

## 8. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Qiskit dependency conflicts eat hours | High | Pin exact versions hour 1, isolated venv, commit lockfile |
| GDAL / rasterio install fails | High | Docker or conda env, set up by hour 2 |
| Sentinel-1 flood labels take too long | Medium | Hard 90-minute cap, then fall back to a stated physical index |
| Only one person understands the QUBO | Medium | Two people must know: penalty weights, ansatz depth, qubit count, and why each |
| Demo dies on venue wifi | Medium | Pre-recorded backup video, local-only demo mode |
