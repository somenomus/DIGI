"""List (and optionally delete) aborted OpenLab simulations to free stored slots.

The account's stored-simulation cap is 20. Aborted runs sit in that quota with
almost no steps. This lists every stored simulation, marks the ones below a step
threshold as prunable, and deletes them ONLY when --yes is passed.

Simulations at or above the threshold are never touched: several are cited in the
paper (e.g. the MSE bit-rock run and the mixed-section runs).

  python prune_aborted_sims.py                 # dry run, lists everything
  python prune_aborted_sims.py --yes           # delete the ones marked PRUNE
  python prune_aborted_sims.py --max-steps 500 # change the threshold
"""
import os, sys, argparse

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "openlab"))
sys.path.insert(0, ROOT)

import config as cfg
import openlab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-steps", type=int, default=1000,
                    help="simulations with fewer steps than this are prunable (default 1000)")
    ap.add_argument("--yes", action="store_true", help="actually delete; otherwise dry run")
    ap.add_argument("--end-created", action="store_true",
                    help="also end simulations stuck in 'Created' before deleting them")
    args = ap.parse_args()

    sess = openlab.http_client(username=cfg.OPENLAB_EMAIL, apikey=cfg.OPENLAB_API_KEY,
                               licenseguid=cfg.OPENLAB_LICENSE_GUID)
    lim = sess.user_limits()
    sims = sess.simulations()
    print(f"stored {len(sims)}/{lim.get('MaxStoredSimulations')}   "
          f"active {lim.get('ActiveSimulationCount')}/{lim.get('MaxConcurrentSimulations')}   "
          f"steps {lim.get('UsedStepCount')}/{lim.get('MaxStepCount')}\n")

    prunable = []
    for s in sims:
        steps = int(s.get("CurrentStep") or 0)
        active = s["Status"] in ("Running", "Created")
        if steps < args.max_steps and active and not args.end_created:
            # A live simulation with few steps is most likely a job that just
            # started, not residue. Never delete one unless asked explicitly.
            mark = "SKIP  "
        elif steps < args.max_steps:
            mark = "PRUNE "
            prunable.append(s)
        else:
            mark = "keep  "
        print(f"  {mark} {s['Status']:10s} {steps:>7d} steps  {s.get('ConfigurationName','?'):26s} "
              f"{s.get('Name','?')}")

    print(f"\n{len(prunable)} prunable, would free {len(prunable)} of "
          f"{lim.get('MaxStoredSimulations')} slots.")
    if not args.yes:
        print("Dry run. Re-run with --yes to delete the ones marked PRUNE.")
        return

    for s in prunable:
        sid = s["SimulationID"]
        if s["Status"] in ("Running", "Created") and args.end_created:
            try:
                sess.end_simulation(sid)
                print(f"  ended {sid}")
            except Exception as e:
                print(f"  [note] end failed for {sid}: {e}")
        try:
            sess.delete_simulation(sid)
            print(f"  deleted {sid}  ({s.get('Name')})")
        except Exception as e:
            print(f"  [note] delete failed for {sid}: {e}")

    lim = sess.user_limits()
    print(f"\nnow stored {len(sess.simulations())}/{lim.get('MaxStoredSimulations')}")


if __name__ == "__main__":
    main()
