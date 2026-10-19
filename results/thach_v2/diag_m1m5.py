"""Diagnostic (not selection): which part of M1 breaks Table III together with M5?
full (M1-M5) with one M1 sub-switch off: Q inflation, cone, interaction damping. T3 on test and val."""
import importlib.util, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("run", os.path.join(HERE, "run.py")); run = importlib.util.module_from_spec(spec); spec.loader.exec_module(run)
full_env = dict(run.CONFIGS["full"][0])
DX = {"dxfull-Q": {"GMOT_ADAPTIVE_Q": "0"}, "dxfull-cone": {"GMOT_CONE": "0"}, "dxfull-damp": {"GMOT_INTERACT_DAMP": "0"},
      "dxbase+M5+Q": None}
for k, extra in DX.items():
    if extra is None:  # base + M5 + only the Q inflation of M1
        env = dict(run.CONFIGS["base+M5"][0]); env.update(GMOT_ADAPTIVE_MOTION="1", GMOT_ADAPTIVE_Q="1", GMOT_CONE="0", GMOT_INTERACT_DAMP="0")
    else:
        env = dict(full_env); env.update(extra)
    run.CONFIGS[k] = (env,) + tuple(run.CONFIGS["full"][1:])
for sp in ("test", "val"):
    for k in DX:
        rep = run.run(k, "t3", sp, False)
        print(sp, k, re.search(r"^all-burn\s+\S+\s+\d+\s+([\d.]+)%", open(rep, encoding="utf-8").read(), re.M)[1], flush=True)
