"""CLI for the failure-analysis harness (wrapped by scripts/08_failure_analysis.py).

  extract --results_subdir eval --tracker_name peg [--data_root datasets/real] [--no_images]
  extract --results_subdir eval_recovery --tracker_name peg_rcv --recovery
  show    --run eval__peg [--type IDSW] [--seq S] [--tag glare] [--top 20] [--unreviewed]
  render  --run eval__peg (--event ID | --top N [--type T] | --sample N --seed 0) [--mp4]
  diag    --seq S [--tracker beacon] [--data_root ..]
  review  --run R --event ID --label L --confidence 0.7 --evidence "..." [--note ".."]
  report  --run R
  diff    --a RUN --b RUN
"""
import argparse
import os
import random

from . import io as aio


def _dataset_of(args):
    if args.dataset:
        return args.dataset
    return "synth" if args.recovery or "synth" in str(args.data_root or "") else "real"


def cmd_extract(a):
    from .extract import extract_run
    ds = _dataset_of(a)
    root = aio.resolve(a.data_root) if a.data_root else aio.cfg_data_root(ds)
    run, evs, ok = extract_run(a.results_subdir, a.tracker_name, root, ds, a.split,
                               images=not a.no_images, recovery=a.recovery)
    print(f"\nrun {run}: {len(evs)} events | reconciliation {'ALL MATCH' if ok else 'MISMATCH'}")
    print(f"-> {os.path.join(aio.run_dir(run), 'summary.md')}")
    return 0 if ok else 1


def _filter(evs, a, run):
    if getattr(a, "type", None):
        evs = [e for e in evs if e["type"] == a.type]
    if getattr(a, "seq", None):
        evs = [e for e in evs if a.seq in e["seq"] or a.seq == aio.short_name(e["seq"])]
    if getattr(a, "tag", None):
        evs = [e for e in evs if e["tags"].get(a.tag)]
    if getattr(a, "unreviewed", False):
        from .casebook import review_path
        evs = [e for e in evs if not os.path.exists(review_path(run, e["event_id"]))]
    return evs


def cmd_show(a):
    from .extract import load_events
    evs = sorted(_filter(load_events(a.run), a, a.run), key=lambda e: -e["severity"])
    print(f"{len(evs)} events")
    print(f"{'event_id':<34}{'subtype':<15}{'frames':<12}{'sev':>6}  tags")
    for e in evs[:a.top]:
        tg = ",".join(k for k, v in e["tags"].items() if v is True)
        print(f"{e['event_id']:<34}{e['subtype']:<15}{str(e['frame_start']) + '-' + str(e['frame_end']):<12}"
              f"{e['severity']:>6.0f}  {tg}")


def cmd_render(a):
    from .extract import load_events
    from .render import render_events
    evs = load_events(a.run)
    if a.event:
        sel = [e for e in evs if e["event_id"] == a.event]
        if not sel:
            raise SystemExit(f"no such event: {a.event}")
    else:
        pool = _filter(evs, a, a.run)
        if a.sample:
            random.Random(a.seed).shuffle(pool)
            sel = pool[:a.sample]
        else:
            sel = sorted(pool, key=lambda e: -e["severity"])[:a.top]
    for p in render_events(a.run, sel, mp4=a.mp4):
        print(p)


def cmd_diag(a):
    from .diag import run_diag
    run_diag(a.seq, a.data_root, a.results_subdir, a.tracker_name, a.tracker)


def cmd_review(a):
    from .casebook import write_review
    print(write_review(a.run, a.event, a.label, a.confidence, a.evidence, a.note, a.reviewer))


def cmd_report(a):
    from .casebook import report
    print(report(a.run))


def cmd_diff(a):
    from .casebook import diff_runs
    print(diff_runs(a.a, a.b))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("extract")
    p.add_argument("--results_subdir", default="eval")
    p.add_argument("--tracker_name", default="peg")
    p.add_argument("--data_root", default=None, help="default: data.tracking (real) / data.glare (synth)")
    p.add_argument("--dataset", choices=["real", "synth"], default=None)
    p.add_argument("--split", default="test")
    p.add_argument("--no_images", action="store_true", help="skip photometric tags (fast)")
    p.add_argument("--recovery", action="store_true", help="BURN_EP family (Table III, synth)")
    p.set_defaults(fn=cmd_extract)

    def filt(p):
        p.add_argument("--type")
        p.add_argument("--seq")
        p.add_argument("--tag")
        p.add_argument("--unreviewed", action="store_true")

    p = sub.add_parser("show")
    p.add_argument("--run", required=True)
    filt(p)
    p.add_argument("--top", type=int, default=20)
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("render")
    p.add_argument("--run", required=True)
    p.add_argument("--event")
    filt(p)
    p.add_argument("--top", type=int, default=3)
    p.add_argument("--sample", type=int, default=0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--mp4", action="store_true", help="also write clip.mp4 (humans only)")
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("diag")
    p.add_argument("--seq", required=True)
    p.add_argument("--data_root", default=None)
    p.add_argument("--results_subdir", default="eval", help="where the stored MOT txt lives")
    p.add_argument("--tracker_name", default="peg", help="stored run to compare determinism against")
    p.add_argument("--tracker", default="beacon", help="GMOT_TRACKER value")
    p.set_defaults(fn=cmd_diag)

    p = sub.add_parser("review")
    p.add_argument("--run", required=True)
    p.add_argument("--event", required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--confidence", type=float, required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--note", default="")
    p.add_argument("--reviewer", default="agent")
    p.set_defaults(fn=cmd_review)

    p = sub.add_parser("report")
    p.add_argument("--run", required=True)
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("diff")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.set_defaults(fn=cmd_diff)

    a = ap.parse_args(argv)
    raise SystemExit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
