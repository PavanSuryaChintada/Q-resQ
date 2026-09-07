# TRAINING — Q-ResQ NER

Everything needed to assemble features, train the models, and export them. Read `docs/DATA.md` first — ingest must complete before any of this runs.

Three models:

| | Model | Output | Risk |
|---|---|---|---|
| **M1** | Landslide susceptibility | 0-1 per 100 m cell | Label sparsity |
| **M2** | Rainfall trigger | 0-1 per cell per timestep | Low — physical index |
| **M3** | Photo classifier | 4 classes, on-device | No dataset exists |

---

## 0. The three traps

Read these before writing any training code. Each one produces a model that looks excellent and is worthless.

### Trap 1 — Random cross-validation

**This is the one that will get you.** Geospatial grid cells are spatially autocorrelated: a cell and its neighbour share almost identical terrain. Random k-fold puts neighbours in both train and test, the model effectively memorises locations, and you get AUC 0.97 that means nothing.

**Use spatial block cross-validation.** Partition the district into blocks of roughly 5 km, assign whole blocks to folds, never split a block. Expect AUC to drop to perhaps 0.75-0.85. **That lower number is the real one.** Report it.

If a judge or reviewer asks how you validated, "spatial block cross-validation, because random folds leak through spatial autocorrelation" is a sentence that establishes competence immediately.

### Trap 2 — Naive negative sampling

Landslide inventories are presence-only. There is no record of where landslides did not happen.

Sample negatives uniformly across the district and the model learns "steep terrain = landslide," because every negative you handed it was flat. Feature importance will be ~70% slope and the model will flag every hillside in Mizoram.

**Sample negatives from terrain that is plausibly susceptible but has no recorded event.** Details in §3.

### Trap 3 — Circular aspect

Aspect is degrees on a circle. 359° and 1° are one degree apart; a model fed raw degrees treats them as maximally distant.

**Always `sin(aspect)` and `cos(aspect)` as two features.** Never the raw value.

---

## 1. Directory layout

```
services/api/ml/
├── features.py        # assemble the training matrix
├── sampling.py        # negative sampling + spatial blocks
├── train_susceptibility.py
├── trigger.py         # M2, physical index — no training
├── evaluate.py        # spatial CV, metrics, importances
├── photo/
│   ├── dataset.py
│   ├── train_photo.py
│   └── export_onnx.py
└── artifacts/
    ├── susceptibility_lgbm.txt
    ├── feature_importance.json
    ├── metrics.json
    ├── spatial_cv_report.json
    └── photo_classifier.onnx
```

---

## 2. M1 — Feature assembly (`features.py`)

Builds one row per 100 m grid cell from the rasters produced by ingest.

| Feature | Type | Source |
|---|---|---|
| `elevation_m` | float | dem.tif |
| `slope_deg` | float | terrain/ |
| `aspect_sin`, `aspect_cos` | float | terrain/ — **two columns** |
| `curv_plan`, `curv_prof` | float | terrain/ |
| `ls_factor` | float | terrain/ |
| `hand_m` | float | terrain/ |
| `twi` | float | terrain/ |
| `dist_stream_m` | float | terrain/ |
| `dist_road_m` | float | road_cut.tif |
| `is_cut_slope` | bool | road_cut.tif |
| `lithology` | categorical | GSI, one-hot |
| `landcover` | categorical | WorldCover, one-hot |
| `forest_frac` | float | WorldCover |

**Static only.** Rainfall does not enter M1 — it belongs to M2. Susceptibility answers "is this slope capable of failing"; triggering answers "are conditions right today." Mixing them produces a model that cannot be evaluated against a presence-only inventory, because the inventory records events, not conditions.

Write `data/processed/features.parquet`. Print row count, null counts per column, and the fraction flagged `is_cut_slope`.

---

## 3. M1 — Sampling (`sampling.py`)

### Positives

Landslide points from the NASA catalogue and, if available, the GSI inventory. Buffer each to 100 m and mark intersecting cells positive.

**Print the count immediately and honestly.** Inside Aizawl district you may find only single-digit or low-double-digit events. If so:

1. Expand to all of Mizoram, then to neighbouring districts of Manipur and Assam. Terrain and lithology are comparable, so this is defensible transfer rather than cheating — but **say that you did it** and report both counts.
2. If total positives fall below ~150, do not ship a learned model. Ship the physical index in §6 and label it as such. A model trained on 40 points is noise with a confidence interval.

### Negatives

```python
candidate_negatives = cells where:
    slope_deg > 15                        # plausibly susceptible
    AND no positive within 500 m          # buffer to avoid mislabelled near-misses
    AND lithology in classes present in positives
sample_ratio = 3 negatives per positive
```

The `slope_deg > 15` filter is what stops the model collapsing to a slope threshold. Without it, every negative is valley floor and the model learns nothing else.

### Spatial blocks

```python
def spatial_blocks(cells, block_km=5, n_folds=5):
    """Assign each cell to a ~5 km block, then blocks to folds.
    A block is never split across folds."""
```

Write `data/processed/train.parquet` with `label`, `fold`, and `block_id` columns.

---

## 4. M1 — Training (`train_susceptibility.py`)

```python
params = {
    "objective": "binary",
    "metric": ["auc", "average_precision"],
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "is_unbalance": True,
    "verbosity": -1,
}
```

Train one model per spatial fold, evaluate on the held-out fold, then fit a final model on all data for deployment. Early stopping on the fold's validation AUC, 50 rounds patience.

Export `susceptibility_lgbm.txt`, plus:
- `feature_importance.json` — gain and split importance per feature
- `metrics.json` — AUC and average precision, mean and standard deviation across folds
- `spatial_cv_report.json` — per-fold scores and per-fold positive counts

### The check you must actually perform

```python
top = importances.sort_values("gain", ascending=False)
if top.iloc[0]["feature"] == "slope_deg" and top.iloc[0]["gain_frac"] > 0.40:
    raise ValueError(
        "Slope dominates. Negative sampling is wrong — "
        "fix sampling.py, do not tune the model."
    )
```

Make this a hard failure, not a warning. A model where slope carries 70% of the gain has learned nothing you did not already know from the DEM, and it will be obvious to any geologist in the room.

**What good looks like:** slope, curvature, `dist_road_m`, and lithology all appearing in the top six, with no single feature above ~35%. If `dist_road_m` or `is_cut_slope` ranks highly, say so in the pitch — the problem statement names unplanned hill cutting, and the model finding it independently is a strong moment.

---

## 5. M2 — Trigger index (`trigger.py`)

No training. This is a physical index, deliberately.

```
trigger = 0.35*norm(rain_15d)      # sustained saturation
        + 0.30*norm(rain_3d)       # recent accumulation
        + 0.20*norm(rain_intensity_max)   # the spike
        + 0.15*norm(soil_moisture)
```

Slope failure typically follows sustained saturation and then an intensity spike. A model with only a 24-hour window misses the mechanism entirely, which is why the 15-day term carries the most weight.

Composite:

```
risk = susceptibility × normalise(trigger)
```

Both components exposed separately through the API. A cell can be highly susceptible and dry, and the officer must be able to see which.

**Why not learn this too:** it would require event-matched rainfall for each inventory point, at hourly resolution, historically. That data does not exist at usable coverage for this region. An index that can be explained beats a model that cannot be trained.

---

## 6. Fallback — no learned model

If positives fall below the threshold in §3, ship this and label every cell `provenance: index`:

```
susceptibility = 0.30*norm(slope_deg)
               + 0.20*norm(-curv_prof)      # concave concentrates flow
               + 0.20*is_cut_slope
               + 0.15*lithology_weight
               + 0.10*norm(1 - forest_frac)
               + 0.05*norm(ls_factor)
```

Say plainly that it is a heuristic. This is a better position than a model trained on forty points, and a ministry panel will recognise the difference.

---

## 7. M3 — Photo classifier

Four classes: `crack`, `slope_movement`, `road_blocked`, `no_hazard`.

### The honest problem

**There is no public dataset for landslide-precursor photographs.** You are assembling one. Options, in order of preference:

1. **Public crack datasets** — SDNET2018, Mendeley concrete/pavement crack sets. These are concrete cracks, not soil cracks, but the visual features transfer partially. Good for the `crack` class.
2. **Hand-curated web images** — 100-200 per class, manually verified. Slow but it is the only source for `slope_movement`.
3. **Heavy augmentation** — rotation, crop, brightness, blur. Necessary at this dataset size.

Target: 200-400 images per class. That is small, and the model will be mediocre.

### Training

MobileNetV3-Small, ImageNet weights, freeze the backbone, train the head, then unfreeze the last block at a low learning rate. 224x224. Roughly 20 epochs, early stopping on validation accuracy.

Export to ONNX with `opset_version=13`, verify it loads in `onnxruntime-web`, and **check the exported model size is under 10 MB** — it ships to a phone over a poor connection.

### The framing

Report real accuracy in `metrics.json` and present it as **triage assistance, not detection.** Its job is to pre-sort the admin queue so a human is not scrolling through unsorted photographs. If accuracy is 70%, say 70%.

Do not suppress it for being imperfect, and do not describe it as detecting landslides. A ministry panel has seen overclaimed CV before.

---

## 8. What to report in the pitch

| Metric | Where |
|---|---|
| Spatial CV AUC, mean ± sd | `metrics.json` |
| Positive count, and whether the region was expanded | `spatial_cv_report.json` |
| Top six feature importances | `feature_importance.json` |
| Photo classifier accuracy | `photo/metrics.json` |
| Provenance split — cells from model vs index | API |

**Say the AUC out loud, and say it was spatially cross-validated.** A team that reports 0.81 with spatial blocks understands more than a team reporting 0.97 with random folds, and the second number is almost certainly wrong.
