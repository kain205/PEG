"""Step 06 — Run the tracker on a sequence or a raw video (annotated mp4 out).

Select PEG with GMOT_TRACKER=beacon (default is the bare glare-aware backbone).

Examples:
  GMOT_TRACKER=beacon python scripts/06_run_tracker.py --video path/to/clip.mp4
  GMOT_TRACKER=beacon python scripts/06_run_tracker.py --seq 204_sequence_81q_complete
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glaremot.tracking.tracker import main

if __name__ == "__main__":
    main()
