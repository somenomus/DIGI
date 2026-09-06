"""run a d3rlpy policy on openlab, deterministic. same idea as evaluate.py
but for d3rlpy policies. costs api steps.

Usage:
  python offline_rl/eval_online.py --policy offline_rl/models/iql_200k/policy.d3 \
      --ucs 0.4 --max-steps 25000
"""
import os, sys, json, argparse
from datetime import datetime
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "openlab"))
sys.path.insert(0, ROOT)
import config as cfg
from drilling_env import DrillingEnv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--ucs", type=float, nargs="+", default=[0.4])
    ap.add_argument("--max-steps", type=int, default=25000)
    ap.add_argument("--base-config", type=str, default="drill_realistic")
    args = ap.parse_args()

    import d3rlpy
    algo = d3rlpy.load_learnable(args.policy)

    results = []
    for ucs in args.ucs:
        env = DrillingEnv(ucs_multiplier=ucs, max_steps=args.max_steps,
                          base_config_name=args.base_config, use_detournay_rop=True)
        obs, _ = env.reset()
        total, depth, target, steps, err = 0.0, 0.0, False, 0, None
        try:
            for t in range(args.max_steps):
                action = algo.predict(obs[None].astype(np.float32))[0]
                obs, r, term, trunc, info = env.step(action)
                total += r; steps += 1
                depth = info.get("depth_progress", depth)
                target = info.get("target_reached", target)
                if t % 1000 == 0:
                    print(f"  step {t}: depth={depth:.2f} m")
                if term or trunc:
                    break
        except Exception as e:
            # api flaked. keep what we have instead of losing the episode
            err = str(e)[:200]
            print(f"  [WARN] episode interrupted at step {steps}: {err}")
        finally:
            try:
                env.close()
            except Exception:
                pass
        rec = {"ucs": ucs, "return": total, "depth_m": depth,
               "target": bool(target), "steps": steps, "error": err}
        print("RESULT:", rec)
        results.append(rec)

    out = os.path.join(ROOT, "eval_results",
                       f"offline_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    json.dump({"policy": args.policy, "results": results}, open(out, "w"), indent=1)
    print("saved:", out)


if __name__ == "__main__":
    main()
