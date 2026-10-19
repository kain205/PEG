#!/usr/bin/env bash
# GPU queue: live perception caches for Thach v2 (dg0 = no de-glare, dg1 = M6). Each first run records the cache.
set -u
cd /d/PROJECT/PEG
PY=.venv/Scripts/python.exe
R="$PY results/thach_v2/run.py"
$R --split test --tables t2 t3 --configs base full+M6      # synth test caches (Tables II-IV)
$R --split val  --tables t1 t2 t3 --configs base full+M6   # val real + synth caches
# live check of Thach's shipped Table I test caches: same configs, own cache dir
for c in base full+M6; do
  GLAREMOT_CONFIG_OVERRIDE=1 $PY - "$c" <<'PYEOF'
import os, subprocess, sys, importlib.util
spec = importlib.util.spec_from_file_location("run", "results/thach_v2/run.py"); run = importlib.util.module_from_spec(spec); spec.loader.exec_module(run)
c = sys.argv[1]; REPO = run.REPO
env = {k: v for k, v in os.environ.items() if k not in run.CLEAR}; env.update(run.CONFIGS[c][0])
env.update(GMOT_TRACKER="beacon", PYTHONIOENCODING="utf-8", GLAREMOT_CONFIG=REPO + "/configs/ours_real_live.yaml")
n = run.name(c, "t1", "test", False)
with open(f"results/thach_v2/logs/live_t1_test_{n}.log", "w", encoding="utf-8") as f:
    r = subprocess.run([run.PY, "scripts/06_eval_mot.py", "--split", "test", "--det_cache", "--tracker_name", n], cwd=REPO, env=env, stdout=f, stderr=subprocess.STDOUT)
print("live t1", c, "exit", r.returncode, flush=True)
PYEOF
done
echo DONE
