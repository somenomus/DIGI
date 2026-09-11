"""fixed-setpoint baseline, the constant-setpoint rows of Table 3 and Fig. 9.

Runs one deterministic episode with CONSTANT setpoints under exactly the
protocol used for the RL evaluations (Detournay model, default auto-driller
gain, same warm-up, same step cap), and saves per-step traces locally so the
figures do not depend on stored simulations that the server later prunes.

Examples
--------
  # torque-averse corner, uniform strengths, 50k cap
  python baseline_fixed.py --rpm 80 --wob 12 --flow 1800 --ucs 0.2 0.4 1.0 \
      --base-config drill_realistic --max-steps 50000 --tag lowrpm

  # performance corner on the mixed section (drill_mixed, 40k cap as in Table 2)
  python baseline_fixed.py --rpm 120 --wob 10 --flow 2200 --ucs 1.0 \
      --base-config drill_mixed --max-steps 40000 --tag highrpm

Outputs go to baseline_results/<tag>_<config>_ucs<u>_<timestamp>.{json,npz}
"""
import os, sys, json, argparse
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "openlab"))
sys.path.insert(0, ROOT)

import numpy as np
import config as cfg
from drilling_env import DrillingEnv


class FixedPolicy:
    """Always returns the same normalized action. Mimics model.predict()."""

    def __init__(self, rpm, wob_t, flow_lpm):
        def norm(x, lo, hi):
            return float(np.clip(2.0 * (x - lo) / (hi - lo) - 1.0, -1.0, 1.0))
        self.action = np.array([
            norm(rpm, cfg.RPM_MIN, cfg.RPM_MAX),
            norm(wob_t, cfg.WOB_MIN, cfg.WOB_MAX),
            norm(flow_lpm, cfg.FLOW_RATE_MIN, cfg.FLOW_RATE_MAX),
        ], dtype=np.float32)
        self.rpm, self.wob_t, self.flow_lpm = rpm, wob_t, flow_lpm

    def predict(self, obs, deterministic=True):
        return self.action.copy(), None


def run_episode(policy, ucs, max_steps, base_config, use_detournay, wob_gain, verbose,
                session=None, delete_sim=True):
    # cleanup_on_reset=False is REQUIRED here. With it True the env ends every
    # simulation running on the account at reset, including ones belonging to
    # other jobs, so parallel baseline runs would kill each other.
    env = DrillingEnv(ucs_multiplier=ucs, max_steps=max_steps,
                      use_detournay_rop=use_detournay,
                      wob_proportional_gain=wob_gain,
                      base_config_name=base_config,
                      cleanup_on_reset=False)
    if session is not None:
        env._session = session          # skip switch_user(); avoids account.py write races
    obs, info = env.reset()
    sim_id = getattr(env._sim, "sim_id", None)

    # per-step traces: every numeric field the env reports, plus flags
    traces = {}
    n_viol = []          # number of violated constraints this step
    c3 = []              # 1 if a C3 (ECD-rate advisory) flag was raised
    hard = []            # 1 if any C1/C2/C4/C5 violation
    total_reward = 0.0
    steps = 0
    depth = 0.0
    target = False

    # The server enforces its own MaxTimeStep (48,000 here) on top of max_steps,
    # and self._timestep starts at WARMUP_STEPS, so both caps include the warm-up.
    server_cap = getattr(env._sim, "max_timeStep", None)
    err = None
    try:
      for step in range(1, max_steps + 1):
        action, _ = policy.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        steps += 1

        for k, v in info.items():
            if isinstance(v, (int, float, np.floating, np.integer)) and not isinstance(v, bool):
                traces.setdefault(k, []).append(float(v))
        eng = info.get("action_engineering", {}) or {}
        for k in ("rpm", "wob_tonnes", "flow_lpm"):
            if k in eng:
                traces.setdefault("cmd_" + k, []).append(float(eng[k]))
        v = info.get("safety_violations", []) or []
        n_viol.append(len(v))
        c3.append(int(any(str(x).startswith("C3") for x in v)))
        hard.append(int(any(str(x).startswith(("C1", "C2", "C4", "C5")) for x in v)))
        depth = info.get("depth_progress", depth)
        target = info.get("target_reached", target)

        if verbose and step % 1000 == 0:
            print(f"    step {step}: depth={depth:.2f} m  RPM={eng.get('rpm', 0):.0f} "
                  f"WOB={eng.get('wob_tonnes', 0):.1f} t  flow={eng.get('flow_lpm', 0):.0f} L/min  "
                  f"torque={info.get('torque_knm', float('nan')):.1f} kN·m  ECD={info.get('ecd_sg', float('nan')):.3f} sg",
                  flush=True)
        if terminated or truncated:
            break
    except Exception as e:
        # A transient API failure (e.g. a 504) must not leave the simulation
        # running server-side, nor abort the remaining episodes of this job.
        err = f"{type(e).__name__}: {e}"
        print(f"  [ERROR] episode aborted after {steps} steps: {err}", flush=True)
    finally:
        try:
            env.close()
        except Exception:
            pass

    # Traces are saved locally, so the stored simulation is not needed. Delete it
    # to stay under the server's stored-simulation cap while jobs run in parallel.
    if delete_sim and sim_id is not None and session is not None:
        try:
            session.delete_simulation(sim_id)
            print(f"  deleted stored sim {sim_id}", flush=True)
        except Exception as e:
            print(f"  [note] could not delete sim {sim_id}: {e}", flush=True)

    rop = np.array(traces.get("rop", []))            # m/s
    summary = {
        "ucs": ucs,
        "base_config": base_config,
        "setpoints": {"rpm": policy.rpm, "wob_t": policy.wob_t, "flow_lpm": policy.flow_lpm},
        "normalized_action": policy.action.tolist(),
        "max_steps": max_steps,
        "server_max_timestep": server_cap,
        "effective_cap_steps": (min(max_steps, server_cap) if server_cap else max_steps),
        "aborted_with": err,
        "steps": steps,
        "minutes_incl_warmup": (steps + cfg.WARMUP_STEPS) * cfg.STEP_DURATION / 60.0,
        "depth_progress_m": float(depth),
        "target_reached": bool(target),
        "total_reward": float(total_reward),
        "avg_rop_m_h": float(rop.mean() * 3600) if rop.size else 0.0,
        "hard_violations": int(np.sum(hard)),
        "c3_flag_rate": float(np.mean(c3)) if c3 else 0.0,
        "c3_flags": int(np.sum(c3)),
        "min_safety_margin": float(np.min(traces["safety_margin"])) if "safety_margin" in traces else None,
        "max_torque_knm": float(np.max(traces["torque_knm"])) if "torque_knm" in traces else None,
        "ecd_min_sg": float(np.min(traces["ecd_sg"])) if "ecd_sg" in traces else None,
        "ecd_max_sg": float(np.max(traces["ecd_sg"])) if "ecd_sg" in traces else None,
        "spp_max_bar": float(np.max(traces["spp_bar"])) if "spp_bar" in traces else None,
    }
    arrays = {k: np.asarray(v) for k, v in traces.items()}
    arrays["n_violations"] = np.asarray(n_viol)
    arrays["c3_flag"] = np.asarray(c3)
    arrays["hard_flag"] = np.asarray(hard)
    # Every trace must have one entry per step, or per-step series would be
    # misaligned when the figures are built from them.
    ragged = {k: len(v) for k, v in arrays.items() if len(v) != steps}
    if ragged:
        print(f"  [WARN] trace length != {steps} steps for: {ragged}", flush=True)
    summary["traces_aligned"] = not ragged
    return summary, arrays


def main():
    ap = argparse.ArgumentParser(description="Fixed-setpoint baseline episodes")
    ap.add_argument("--rpm", type=float, required=True)
    ap.add_argument("--wob", type=float, required=True, help="tonnes")
    ap.add_argument("--flow", type=float, required=True, help="L/min")
    ap.add_argument("--ucs", type=float, nargs="+", default=[0.2, 0.4, 1.0])
    ap.add_argument("--base-config", type=str, default="drill_realistic")
    ap.add_argument("--max-steps", type=int, default=50000)
    ap.add_argument("--no-detournay", action="store_true", help="use the default MSE bit-rock model instead")
    ap.add_argument("--wob-gain", type=float, default=None)
    ap.add_argument("--tag", type=str, default="fixed")
    ap.add_argument("--out", type=str, default=os.path.join(ROOT, "baseline_results"))
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--keep-sims", action="store_true",
                    help="do not delete this run's stored simulations afterwards")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # One login per process. Passing the session into the env skips switch_user(),
    # which writes credentials to account.py and would race across parallel jobs.
    import openlab
    session = openlab.http_client(username=cfg.OPENLAB_EMAIL,
                                  apikey=cfg.OPENLAB_API_KEY,
                                  licenseguid=cfg.OPENLAB_LICENSE_GUID)
    lim = session.user_limits()
    print(f"  account: {lim.get('ActiveSimulationCount')}/{lim.get('MaxConcurrentSimulations')} active, "
          f"steps used {lim.get('UsedStepCount')}/{lim.get('MaxStepCount')}", flush=True)

    policy = FixedPolicy(args.rpm, args.wob, args.flow)
    print("=" * 70)
    print("FIXED-SETPOINT BASELINE")
    print(f"  setpoints: {args.rpm:.0f} rpm, {args.wob:.1f} t, {args.flow:.0f} L/min  -> a = {policy.action}")
    print(f"  base config: {args.base_config}   UCS multipliers: {args.ucs}")
    print(f"  cap: {args.max_steps} steps   bit-rock: {'MSE (default)' if args.no_detournay else 'Detournay'}")
    print("=" * 70, flush=True)

    for u in args.ucs:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"{args.tag}_{args.base_config}_ucs{u}_{stamp}"
        print(f"\n--- {name} ---", flush=True)
        try:
            summary, arrays = run_episode(policy, u, args.max_steps, args.base_config,
                                          not args.no_detournay, args.wob_gain, not args.quiet,
                                          session=session, delete_sim=not args.keep_sims)
        except Exception as e:
            # Isolate failures per formation so one bad episode does not cost the rest.
            print(f"  [ERROR] {name} failed to run: {type(e).__name__}: {e}", flush=True)
            continue
        with open(os.path.join(args.out, name + ".json"), "w") as f:
            json.dump(summary, f, indent=2)
        np.savez_compressed(os.path.join(args.out, name + ".npz"), **arrays)
        print(f"  steps={summary['steps']}  target={summary['target_reached']}  "
              f"depth={summary['depth_progress_m']:.2f} m  avgROP={summary['avg_rop_m_h']:.1f} m/h  "
              f"hard={summary['hard_violations']}  C3 rate={summary['c3_flag_rate']:.3f}  "
              f"maxT={summary['max_torque_knm']}  ECD=[{summary['ecd_min_sg']}, {summary['ecd_max_sg']}]",
              flush=True)


if __name__ == "__main__":
    main()
