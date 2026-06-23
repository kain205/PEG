# PEG — A Photometric Emission Gate for Tracking Through Sensor Saturation

Reference implementation for the paper *"Burnt, Not Gone: A Photometric Emission Gate
for Tracking Through Sensor Saturation."*

**[📄 Paper (PDF)](paper/PEG_paper.pdf)** · **[💻 GitHub](https://github.com/minhdq245/PEG)** · **[🎬 Demo videos (Google Drive)](https://drive.google.com/drive/folders/1DEk0QK1hT9mvxjWl1a_bop5dj8di-ifs?usp=sharing)**

When a worker's helmet lamp points into a fixed mine camera it saturates (blooms) the
sensor and erases the body in place: the detector returns nothing and the track is
dropped. A constant-velocity coast still predicts the near-static body, but a *blind*
coast cannot tell a worker who is **burnt** (still there, washed out) from one who has
**departed**, so it recovers burns only at a heavy false-positive cost. PEG decides this
from the destroying signal itself — the fraction of the predicted body box that is
photometrically saturated — and emits the coasting box only while that fraction is high.

## What PEG is (and is not)

PEG has three parts:

1. **Glare-aware perception front-end.** A shared YOLO11m detector produces body boxes; a
   small **learned visibility head** (`glaremot/perception/h_psi.py`) reads the detector's
   frozen P3 features per box and predicts a *presence* probability and a photometric
   *reliability* `m∈[0,1]`. The backbone uses these to gate track birth/confirmation/
   re-entry so glare artefacts do not spawn identities.
   **This front-end is learned**, so PEG as a whole is *not* a learning-free system.
2. **OC-SORT motion backbone.** Kalman constant-velocity prediction with
   observation-centric association. Appearance-free: no re-identification embedding.
3. **The photometric emission gate (the contribution).** On a missed detection, after a
   short brief-miss floor `δ`, the coasting box is emitted **iff** the saturated fraction
   `φ_t = |Ω_t ∩ b_t| / |b_t| ≥ h`. This decision is a single **analytic** threshold — no
   learning — and is the part the paper claims as analytic. The same evidence gate also
   replaces the blind fixed-age coast (the *evidence-gated coast*,
   `GBEACON_COAST_FLOOR`).

Note on attribution: under a *total* burn the body features are destroyed, so the learned
head is uninformative; the recovery of fully burnt workers reported in the paper is
therefore due to the analytic gate, not the head. See `glaremot/tracking/beacon_tracker.py`.

## Repository layout

```
glaremot/
  tracking/beacon_tracker.py   # PEG: the photometric emission gate + evidence-gated coast
  tracking/tracker.py          # OC-SORT backbone, Perception (detector + h_psi head)
  perception/h_psi.py          # learned visibility head: architecture + training loss
  perception/analytic.py       # analytic m_glare target the head regresses to
  perception/synth_glare.py    # physically-motivated synthetic burns (for the twins)
  external/ocsort/             # OC-SORT association + Kalman (vendored)
  eval/eval_mot.py             # full-scene MOT eval (Tables I, II, IV)
  eval/eval_recovery.py        # burnt-target recovery eval (Table III)
  config.py, data/, photometric.py
scripts/                       # entry points (see below)
configs/paths.yaml             # all paths; edit or override with $GLAREMOT_CONFIG
weights/                       # shipped: detector/best.pt, hpsi/h_psi_head.pt
```

The deployed tracker uses no learned-motion module; the IMLE/flow-matching research code
of the broader project is intentionally **not** included here.

## Install

```bash
python -m venv .venv && source .venv/bin/activate    # Python 3.10
pip install -r requirements.txt
```

A CUDA GPU is recommended (the paper reports ~26 fps end-to-end on an RTX 5070 Ti).

## Demo

Qualitative tracking-through-burn clips: **[demo videos (Google Drive)](https://drive.google.com/drive/folders/1DEk0QK1hT9mvxjWl1a_bop5dj8di-ifs?usp=sharing)**.
Each clip shows a worker burnt out by a helmet lamp, the box held through the burn by the
photometric emission gate, and the identity recovered when the glare clears.

## Data layout

The mine footage is access-controlled and is **not** shipped, but is **available to
researchers on request** (contact the authors). Point `configs/paths.yaml` at your own
sequences in MOTChallenge format:

```
<data.tracking>/<seq>/images/*.jpg
<data.tracking>/<seq>/mot/gt/gt.txt        # 9-column MOTChallenge
```

`data.glare` holds the synthetic-burn twins (same layout) used for Tables II–IV. The twin
generator is included (`glaremot/perception/synth_glare.py`), so the synthetic burns can be
regenerated from any clean sequence.

## Reproduce the paper

PEG is selected with `GMOT_TRACKER=beacon`; the deployed configuration is the default
(gate `h=0.40`, brief-miss floor `δ=3`, grace window 5).

```bash
export GMOT_TRACKER=beacon

# Table I  — real held-out test (20 sequences)
python scripts/12_eval_mot.py --split test --tracker_name peg

# Tables II & IV — full-scene MOT on the synthetic glare twins (FP/FN, operating point)
python scripts/12_eval_mot.py --split test --data_root <data.glare> \
       --results_subdir eval_synthfs --tracker_name peg_fs

# Table III — recovery on burnt targets only
python scripts/13_eval_recovery.py --split test --tracker_name peg_rcv
```

Operating-point and ablation knobs (all optional, default off / deployed):
`GBEACON_CUSUM_H` (the gate threshold `h`), `GBEACON_COAST_FLOOR` (`δ`, default 3),
`GBEACON_MF_CONFIRM` / `GBEACON_CUSUM` / `GBEACON_NIS` (the matched-filter / sequential /
innovation refinements shown not to help).

## Retrain the visibility head (optional; weights are shipped)

```bash
python scripts/05_preprocess_hpsi.py        # precompute frozen ROI features
python scripts/07_mine_hard_negatives.py    # mine lamp-like hard negatives
python scripts/06_train_hpsi.py --hardneg   # train the head (frozen backbone)
```

The head minimises `L = 2·focal_BCE(present) + 1·Huber(m, m_analytic) + 0.5·GaussianNLL(Σ)`
(AdamW, lr 1e-3, cosine, 100 epochs); the detector backbone is never updated. See
`glaremot/perception/h_psi.py` (`Stage1HeadLoss`) and the paper, Section IV-A.

## Citation

```bibtex
@inproceedings{peg2026,
  title  = {Burnt, Not Gone: A Photometric Emission Gate for Tracking Through Sensor Saturation},
  author = {<authors>},
  booktitle = {ICICSP},
  year   = {2026}
}
```
