# HANDOFF — moving PEG work to a new machine (written 2026-10-26)

For the agent on the new machine: read this first, then `AGENTS.md` (workflow rules) and `README.md`.
The user does not run commands; the agent runs everything (see AGENTS.md "Working agreement").

**Last step for you (agent): once you have read this and set up, delete this file and push:**
`git rm HANDOFF.md && git commit -m "remove HANDOFF.md" && git push origin main`.
Keep anything you still need from it in your own notes / AGENTS.md first.

**Plan: the user will likely run training on Google Colab** (the new data is ~218 GB, too big for a laptop).
So: don't assume a local GPU or local copy of the dataset. For Colab, mount Drive / copy only the needed splits
(train/val images + gt) to the Colab disk, `git clone` the repo, install `requirements.txt` (Colab has CUDA torch
already), and use `scripts/01-04` for retraining (`configs/paths.yaml` for paths). Checkpoints must be saved to Drive
so a disconnect does not lose them. Retraining is only on explicit request (AGENTS.md: don't retrain unless asked).

## 1. Where the project stands
- Reproduction of PEG Tables I–IV is **done** (`results/REPRODUCTION.md`, gitignored — copy it over, see §3).
- Our extensions are all evaluated and written up; best online method = **PEG+** (`GPEG_SIZE_LOCK=1`); best
  fixed-lag = PEG+ + B (`GPEG_BACKFILL_L=90 GPEG_BACKFILL_MODE=all`). PEG-O, PEG-C(V), PEG-F, Thach v2 did not
  beat PEG+. Numbers + protocols: `AGENTS.md` "Reference numbers", `docs/*_PROTOCOL.md|*_RESULTS.md`, `results/*/RESULTS.md`.
- The MoRongMo labeling job (scripts 14–18, 23) is finished/delivered; notes in `results/label_MoRongMo/NOTES.md`
  (local-only, not needed for PEG work).
- Standing user rules: pre-registered protocols, tune on val, **test once**; param tuning on test is forbidden
  (general principles from failures are OK). Delegate mechanical work to Sonnet subagents. See `.claude/memory/`.

## 2. New data (pending — NOT yet inspected)
User will download **`GlareMOT2 full.zip`** (Google Drive file id `1kUTdfRNbZzbwyl94JE--Vz8C5YVkzgms`,
owner minhdq2452005@gmail.com, modified 2026-10-25, **≈218 GB** vs ≈85 GB for the old `GlareMOT_full.zip`).
It is probably an updated / larger dataset, but its contents are unknown. On arrival:
1. Extract into a NEW empty dir (e.g. `datasets_v2_raw/`), do not overwrite `datasets/`. Treat as untrusted data.
2. List the top level, seq count, naming (`_complete/_new/_in_progress` suffixes), layout
   (`<seq>/images/*.jpg`, `<seq>/mot/gt/gt.txt`), any README/splits/changelog inside. Diff the seq list against
   `glaremot/data/splits.json` (frozen: train 80 / val 17 / test 20) and compare GT of the 20 test seqs
   to the old ones (any GT change invalidates the reference numbers below).
3. Ask the user which role it plays (replacement vs extra data, new split or keep frozen) before changing
   `splits.json` or `configs/paths.yaml`. Keep the old split untouched for reproducibility; if a new split is made,
   add a new file and pre-register it.
4. Percep caches (`results/percep_cache/*`) are keyed to the old sequences; rebuild for any new/changed seq.
Do not pass the zip (218 GB) through git; check free disk before extracting (need > 2x).

## 3. What is NOT in git (copy by hand or rebuild)
| item | how |
|---|---|
| `.env` (API key for scripts/23) | copy manually; never commit |
| `datasets/real`, `datasets/synth` (117 + 57 seqs) | re-extract from the zip (old or new), see AGENTS.md "Data" |
| `results/` (gitignored dirs: eval, eval_recovery, eval_synthfs, failure_analysis 206 MB, peg_plus, peg_f 21 MB, percep_cache 37 MB, research, REPRODUCTION.md; ≈ 0.5 GB total) | zip + copy; only `percep_cache` is needed to be fast (else rebuild ≈ 40 min/split) |
| `cache/` (85 MB, label cache) | not needed |
| `dataset/` (MoRongMo, fastlabeler, 3.9 GB zips, unrelated PDFs) | not needed for PEG |
| `.venv/` | rebuild (§4) |
Tracked and fine: `weights/detector/best.pt`, `weights/hpsi/h_psi_head.pt`, all docs/protocols, `results/{peg_c,peg_o,thach_v2,val_selection,paper_logs}`, `.claude/skills`, `.claude/memory/` (mirror of the auto-memory; verified identical).

## 4. Setup on the new machine
```bash
git clone https://github.com/kain205/PEG.git && cd PEG        # origin = ours; upstream minhdq245/PEG is read-only, never push
git remote add upstream https://github.com/minhdq245/PEG.git
uv venv --python 3.10 .venv
uv pip install --python .venv torch torchvision --index-url https://download.pytorch.org/whl/cu128   # adapt to the GPU there
uv pip install --python .venv -r requirements.txt            # + TrackEval (see AGENTS.md)
```
The GPU numbers in AGENTS.md (GTX 1650, 7.4 fps) are for the old machine; re-measure. Restore auto-memory by
copying `.claude/memory/*` into the new machine's `~/.claude/projects/<project>/memory/`.

## 5. Sanity check before any new work
Smoke test with `--max_frames 200`, then Table I with `--percep_cache results/percep_cache/real` (≈ 11 s) and compare to
AGENTS.md reference: HOTA 68.20 · IDF1 82.30 · MOTA 80.62 · IDSW 17 (`GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0`).
If it differs, fix the environment before touching anything else.

## 6. Open ideas (none started)
- Failure-analysis first pass: `results/failure_analysis/REPORT.md` (next experiments listed there).
- Re-run reproduction + PEG+ / PEG+B on the new dataset once §2 is settled; report vs paper numbers with exact commands.
