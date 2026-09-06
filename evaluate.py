"""run a trained TQC agent deterministically (mean action, no noise) on a few
formations and print per formation and overall numbers. writes a json.

Usage:
    python evaluate.py --model logs/<run>/tqc_drilling_final.zip
    python evaluate.py --model logs/<run>/tqc_drilling_final.zip --ucs 1.0 1.3 0.7
    python evaluate.py --model logs/<run>/tqc_drilling_final.zip --episodes 3
"""
import sys
import os
import argparse
import json
from datetime import datetime

_cwd = os.path.dirname(os.path.abspath(__file__))
_openlab_parent = os.path.join(_cwd, "openlab")
if _openlab_parent not in sys.path:
    sys.path.insert(0, _openlab_parent)
if _cwd not in sys.path:
    sys.path.insert(0, _cwd)

import numpy as np
from sb3_contrib import TQC
from drilling_env import DrillingEnv
import config as cfg


def evaluate_one_episode(model, ucs_val: float, max_steps: int = 5000,
                         verbose: bool = True,
                         use_detournay_rop: bool = False,
                         wob_proportional_gain: float = None,
                         base_config_name: str = None) -> dict:
    """Run one deterministic episode on a specific UCS formation."""
    env = DrillingEnv(ucs_multiplier=ucs_val, max_steps=max_steps,
                      use_detournay_rop=use_detournay_rop,
                      wob_proportional_gain=wob_proportional_gain,
                      base_config_name=base_config_name)

    obs, info = env.reset()
    total_reward = 0.0
    steps = 0
    rops = []
    perf_scores = []
    safety_margins = []
    stability_scores = []
    violations_total = 0
    depth = 0.0
    target = False

    for step in range(1, max_steps + 1):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        steps += 1

        if "rop" in info:
            rops.append(info["rop"] * 1000)  # mm/s
        if "performance_score" in info:
            perf_scores.append(info["performance_score"])
        if "safety_margin" in info:
            safety_margins.append(info["safety_margin"])
        if "stability_score" in info:
            stability_scores.append(info["stability_score"])
        if "safety_violations" in info:
            violations_total += len(info["safety_violations"])
        if "depth_progress" in info:
            depth = info["depth_progress"]
        if "target_reached" in info:
            target = info["target_reached"]

        if verbose and step % 500 == 0:
            eng = info.get("action_engineering", {})
            print(f"    Step {step}: ROP={rops[-1] if rops else 0:.2f} mm/s, "
                  f"depth={depth:.2f}m, "
                  f"RPM={eng.get('rpm', 0):.0f}, WOB={eng.get('wob_tonnes', 0):.1f}t, "
                  f"Flow={eng.get('flow_lpm', 0):.0f} L/min")

        if terminated or truncated:
            break

    env.close()

    result = {
        "ucs": ucs_val,
        "total_reward": total_reward,
        "steps": steps,
        "depth_progress_m": depth,
        "target_reached": target,
        "avg_rop_mm_s": float(np.mean(rops)) if rops else 0.0,
        "max_rop_mm_s": float(np.max(rops)) if rops else 0.0,
        "avg_rop_m_h": float(np.mean(rops) * 3.6) if rops else 0.0,
        "avg_perf_score": float(np.mean(perf_scores)) if perf_scores else 0.0,
        "avg_safety_margin": float(np.mean(safety_margins)) if safety_margins else 0.0,
        "min_safety_margin": float(np.min(safety_margins)) if safety_margins else 0.0,
        "avg_stability_score": float(np.mean(stability_scores)) if stability_scores else 0.0,
        "safety_violations": violations_total,
    }

    return result


def evaluate(model_path: str, ucs_values: list, episodes_per_ucs: int = 1,
             max_steps: int = 5000, verbose: bool = True,
             use_wandb: bool = True, use_detournay_rop: bool = False,
             wob_proportional_gain: float = None, base_config_name: str = None):
    """Evaluate a trained model across multiple UCS formations."""

    print("=" * 70)
    print("DRILLING AGENT EVALUATION")
    print("=" * 70)
    print(f"  Model: {model_path}")
    print(f"  Base formation: {base_config_name if base_config_name else 'default (config.py)'}")
    print(f"  UCS formations: {ucs_values}")
    print(f"  Episodes per UCS: {episodes_per_ucs}")
    print(f"  Max steps per episode: {max_steps}")
    print(f"  ROP model: {'Detournay (realistic vibration)' if use_detournay_rop else 'default (MSE-based)'}")
    print(f"  WOB proportional gain: {wob_proportional_gain if wob_proportional_gain is not None else 'OpenLab default (1e-5)'}")
    print()

    if use_wandb:
        import wandb
        wandb.init(
            project="digi-drilling",
            job_type="evaluation",
            name=f"eval_{datetime.now().strftime('%m%d_%H%M')}",
            config={
                "model_path": model_path,
                "ucs_values": ucs_values,
                "episodes_per_ucs": episodes_per_ucs,
                "max_steps": max_steps,
                "use_detournay_rop": use_detournay_rop,
                "wob_proportional_gain": wob_proportional_gain,
                "base_config_name": base_config_name,
            },
        )

    print("Loading model...")
    model = TQC.load(model_path)
    print(f"  Policy: {model.policy.__class__.__name__}")
    print()

    all_results = []

    for ucs_val in ucs_values:
        print(f"{'─' * 60}")
        print(f"UCS = {ucs_val:.1f}  ({episodes_per_ucs} episode{'s' if episodes_per_ucs > 1 else ''})")
        print(f"{'─' * 60}")

        ucs_episode_results = []

        for ep in range(1, episodes_per_ucs + 1):
            if episodes_per_ucs > 1:
                print(f"  Episode {ep}/{episodes_per_ucs}:")

            result = evaluate_one_episode(model, ucs_val, max_steps, verbose,
                                          use_detournay_rop=use_detournay_rop,
                                          wob_proportional_gain=wob_proportional_gain,
                                          base_config_name=base_config_name)
            ucs_episode_results.append(result)
            all_results.append(result)

            if use_wandb:
                import wandb
                wandb.log({
                    "eval/ucs": ucs_val,
                    "eval/episode": ep,
                    "eval/total_reward": result["total_reward"],
                    "eval/depth_progress_m": result["depth_progress_m"],
                    "eval/target_reached": float(result["target_reached"]),
                    "eval/avg_rop_m_h": result["avg_rop_m_h"],
                    "eval/avg_perf_score": result["avg_perf_score"],
                    "eval/min_safety_margin": result["min_safety_margin"],
                    "eval/safety_violations": result["safety_violations"],
                })

            target_str = "🎯 TARGET REACHED!" if result["target_reached"] else f"{result['depth_progress_m']:.2f}m"
            safe_str = "✓ safe" if result["safety_violations"] == 0 else f"✗ {result['safety_violations']} violations"
            print(f"  {'→' if episodes_per_ucs > 1 else '→'} "
                  f"reward={result['total_reward']:.1f}, "
                  f"depth={target_str}, "
                  f"ROP={result['avg_rop_m_h']:.1f} m/h, "
                  f"perf={result['avg_perf_score']:.3f}, "
                  f"safety={result['min_safety_margin']:.3f}, "
                  f"{safe_str}")

        # per formation, when theres more than one episode
        if episodes_per_ucs > 1:
            avg_reward = np.mean([r["total_reward"] for r in ucs_episode_results])
            targets = sum(1 for r in ucs_episode_results if r["target_reached"])
            print(f"  Summary: avg_reward={avg_reward:.1f}, targets={targets}/{episodes_per_ucs}")

    # overall
    print()
    print("=" * 70)
    print("OVERALL RESULTS")
    print("=" * 70)

    rewards = [r["total_reward"] for r in all_results]
    depths = [r["depth_progress_m"] for r in all_results]
    targets = sum(1 for r in all_results if r["target_reached"])
    rops = [r["avg_rop_m_h"] for r in all_results]
    perfs = [r["avg_perf_score"] for r in all_results]
    safeties = [r["min_safety_margin"] for r in all_results]
    violations = sum(r["safety_violations"] for r in all_results)

    print(f"  Episodes:           {len(all_results)}")
    print(f"  Targets reached:    {targets}/{len(all_results)} ({100*targets/len(all_results):.0f}%)")
    print(f"  Avg reward:         {np.mean(rewards):.1f} ± {np.std(rewards):.1f}")
    print(f"  Avg depth:          {np.mean(depths):.2f} ± {np.std(depths):.2f} m")
    print(f"  Avg ROP:            {np.mean(rops):.1f} ± {np.std(rops):.1f} m/h")
    print(f"  Avg perf score:     {np.mean(perfs):.3f} ± {np.std(perfs):.3f}")
    print(f"  Min safety margin:  {np.min(safeties):.3f}")
    print(f"  Total violations:   {violations}")

    # per formation table
    print()
    print(f"  {'UCS':>5} | {'Reward':>8} | {'Depth (m)':>9} | {'ROP (m/h)':>9} | {'Perf':>7} | {'Safety':>7} | {'Target':>6}")
    print(f"  {'─'*5}─┼─{'─'*8}─┼─{'─'*9}─┼─{'─'*9}─┼─{'─'*7}─┼─{'─'*7}─┼─{'─'*6}")
    for ucs_val in ucs_values:
        ucs_results = [r for r in all_results if r["ucs"] == ucs_val]
        avg_r = np.mean([r["total_reward"] for r in ucs_results])
        avg_d = np.mean([r["depth_progress_m"] for r in ucs_results])
        avg_rop = np.mean([r["avg_rop_m_h"] for r in ucs_results])
        avg_p = np.mean([r["avg_perf_score"] for r in ucs_results])
        min_s = np.min([r["min_safety_margin"] for r in ucs_results])
        tgt = sum(1 for r in ucs_results if r["target_reached"])
        print(f"  {ucs_val:>5.1f} | {avg_r:>8.1f} | {avg_d:>9.2f} | {avg_rop:>9.1f} | {avg_p:>7.3f} | {min_s:>7.3f} | {tgt:>3}/{len(ucs_results)}")

    print()

    # dump json
    eval_dir = os.path.join(_cwd, "eval_results")
    os.makedirs(eval_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = os.path.join(eval_dir, f"eval_{timestamp}.json")

    save_data = {
        "model_path": model_path,
        "timestamp": datetime.now().isoformat(),
        "ucs_values": ucs_values,
        "episodes_per_ucs": episodes_per_ucs,
        "max_steps": max_steps,
        "use_detournay_rop": use_detournay_rop,
        "wob_proportional_gain": wob_proportional_gain,
        "base_config_name": base_config_name,
        "summary": {
            "total_episodes": len(all_results),
            "targets_reached": targets,
            "target_rate": targets / len(all_results),
            "avg_reward": float(np.mean(rewards)),
            "std_reward": float(np.std(rewards)),
            "avg_depth_m": float(np.mean(depths)),
            "avg_rop_m_h": float(np.mean(rops)),
            "avg_perf_score": float(np.mean(perfs)),
            "min_safety_margin": float(np.min(safeties)),
            "total_violations": violations,
        },
        "per_episode": all_results,
    }

    with open(results_path, "w") as f:
        json.dump(save_data, f, indent=2)

    print(f"  Results saved to: {results_path}")
    print("=" * 70)

    if use_wandb:
        import wandb
        wandb.log({
            "eval_summary/total_episodes": len(all_results),
            "eval_summary/targets_reached": targets,
            "eval_summary/target_rate": targets / len(all_results),
            "eval_summary/avg_reward": float(np.mean(rewards)),
            "eval_summary/avg_depth_m": float(np.mean(depths)),
            "eval_summary/avg_rop_m_h": float(np.mean(rops)),
            "eval_summary/avg_perf_score": float(np.mean(perfs)),
            "eval_summary/min_safety_margin": float(np.min(safeties)),
            "eval_summary/total_violations": violations,
        })
        artifact = wandb.Artifact("evaluation_results", type="evaluation")
        artifact.add_file(results_path)
        wandb.log_artifact(artifact)
        wandb.finish()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate trained drilling agent")
    parser.add_argument("--model", type=str, required=True,
                        help="Path to trained model (.zip)")
    parser.add_argument("--ucs", type=float, nargs="+",
                        default=[1.0, 0.7, 1.3, 0.5, 1.6],
                        help="UCS formations to test on (default: [1.0, 0.7, 1.3, 0.5, 1.6])")
    parser.add_argument("--episodes", type=int, default=1,
                        help="Episodes per UCS formation (default: 1)")
    parser.add_argument("--max-steps", type=int, default=5000,
                        help="Max steps per evaluation episode (default: 5000)")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress per-step output")
    parser.add_argument("--no-wandb", action="store_true",
                        help="Disable Weights & Biases logging")
    parser.add_argument("--use-detournay", action="store_true",
                        help="Use Detournay ROP model in OpenLab (realistic vibration). "
                             "Default: off (MSE-based model, matches all prior training/eval).")
    parser.add_argument("--wob-gain", type=float, default=None,
                        help="Override OpenLab WOBAutoDriller proportional gain (Kp). "
                             "Default: OpenLab default (1e-5). Higher = faster WOB tracking.")
    parser.add_argument("--base-config", type=str, default=None,
                        help="Override base formation config name (e.g. 'drill_realistic' "
                             "for the 50-70 MPa formation). Default: config.py CONFIG_NAME.")
    args = parser.parse_args()

    evaluate(args.model, args.ucs, episodes_per_ucs=args.episodes,
             max_steps=args.max_steps, verbose=not args.quiet,
             use_wandb=not args.no_wandb,
             use_detournay_rop=args.use_detournay,
             wob_proportional_gain=args.wob_gain,
             base_config_name=args.base_config)
