"""Step 08 — failure analysis: events, contact sheets, timelines, casebook.

Examples:
  python scripts/08_failure_analysis.py extract --results_subdir eval --tracker_name peg
  python scripts/08_failure_analysis.py show    --run eval__peg --type IDSW
  python scripts/08_failure_analysis.py render  --run eval__peg --top 3 --type FN_RUN
  python scripts/08_failure_analysis.py review  --run eval__peg --event ID --label gate_miss \\
         --confidence 0.7 --evidence "tile 4: person fully saturated, no pred box"
  python scripts/08_failure_analysis.py report  --run eval__peg
See .claude/skills/failure-analysis/SKILL.md for the full procedure.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glaremot.analysis.cli import main

if __name__ == "__main__":
    main()
