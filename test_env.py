"""quick sanity check. runs the env a few steps with random actions and prints
everything it reports: the KPIs, the 3 levels, regime, constraint status.
"""
import sys
import os
import argparse

_cwd = os.path.dirname(os.path.abspath(__file__))
_openlab_parent = os.path.join(_cwd, "openlab")
if _openlab_parent not in sys.path:
    sys.path.insert(0, _openlab_parent)
if _cwd not in sys.path:
    sys.path.insert(0, _cwd)

import numpy as np
from drilling_env import DrillingEnv
import config as cfg


def main(use_wandb: bool = True):
    print("=" * 70)
    print("DRILLING ENVIRONMENT SANITY CHECK (info.md aligned)")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  RPM range:  {cfg.RPM_MIN}-{cfg.RPM_MAX} rpm")
    print(f"  WOB range:  {cfg.WOB_MIN}-{cfg.WOB_MAX} tonnes")
    print(f"  Flow range: {cfg.FLOW_RATE_MIN}-{cfg.FLOW_RATE_MAX} L/min")
    print(f"  Initial depth: {cfg.INITIAL_BIT_DEPTH} m")
    print(f"  Target depth:  {cfg.TARGET_BIT_DEPTH} m")
    print(f"  Performance weights: {cfg.PERFORMANCE_WEIGHTS}")

    if use_wandb:
        import wandb
        wandb.init(
            project="digi-drilling",
            job_type="smoke-test",
            name=f"smoke_{os.path.basename(_cwd)}",
            config={
                "rpm_range": [cfg.RPM_MIN, cfg.RPM_MAX],
                "wob_range": [cfg.WOB_MIN, cfg.WOB_MAX],
                "flow_range": [cfg.FLOW_RATE_MIN, cfg.FLOW_RATE_MAX],
                "warmup_steps": cfg.WARMUP_STEPS,
                "step_duration": cfg.STEP_DURATION,
            },
        )

    env = DrillingEnv(render_mode="human", max_steps=600)

    print(f"\nResetting environment (creates sim + {cfg.WARMUP_STEPS} warmup steps)...")
    obs, info = env.reset()
    print(f"Initial observation shape: {obs.shape}")
    print(f"Initial observation: {obs}")
    print(f"Observation space: {env.observation_space}")
    print(f"Action space: {env.action_space}")
    print(f"Starting after warmup at timestep: {info.get('timestep', '?')}")

    print(f"\n{'=' * 70}")
    print(f"Running 20 steps with random actions")
    print(f"{'=' * 70}")
    total_reward = 0.0
    steps_run = 0
    for step in range(1, 21):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)

        steps_run = step
        eng_raw = info.get("action_engineering", {})
        eng = eng_raw if isinstance(eng_raw, dict) else {}
        print(f"\n{'─' * 60}")
        print(f"Step {step}:")
        print(f"  Action (normalized): [{action[0]:.2f}, {action[1]:.2f}, {action[2]:.2f}]")
        print(f"  Action (engineering): RPM={eng.get('rpm', 0):.0f}, "
              f"WOB={eng.get('wob_tonnes', 0):.1f}t, Flow={eng.get('flow_lpm', 0):.0f} L/min")

        # drilling
        print(f"\n  --- KPIs (info.md §3) ---")
        print(f"  ROP:    {info.get('rop', 0) * 1000:.3f} mm/s  ({info.get('rop_mh', 0):.2f} m/h)")
        print(f"  ECD:    {info.get('ecd_sg', 0):.4f} sg  ({info.get('ecd_kgm3', 0):.1f} kg/m³)")
        print(f"  SPP:    {info.get('spp_bar', 0):.1f} bar")
        print(f"  Torque: {info.get('torque_knm', 0):.2f} kN·m")
        print(f"  MSE:    {info.get('mse_mpa', 0):.1f} MPa")
        print(f"  Depth:  {info.get('bit_depth', 0):.3f} m  (progress: {info.get('depth_progress', 0):.4f} m)")

        # stability
        print(f"\n  --- Stability ---")
        print(f"  σ_ECD:     {info.get('ecd_std_sg', 0):.5f} sg  (lim: 0.02)")
        print(f"  σ_SPP:     {info.get('spp_std_bar', 0):.2f} bar  (lim: 5.0)")
        print(f"  slope(ECD):{info.get('ecd_slope_sg_per_min', 0):.5f} sg/min  (lim: 0.02)")
        print(f"  Torque var:{info.get('torque_variance', 0):.0f} Nm²")

        # the 3 levels
        print(f"\n  --- 3-Level Evaluation (info.md §8) ---")
        print(f"  Level 1 - Performance Score: {info.get('performance_score', 0):.4f}")
        perf_raw = info.get("performance_components", {})
        perf = perf_raw if isinstance(perf_raw, dict) else {}
        if perf:
            print(f"    ROP_s={perf.get('rop_s', 0):.3f}  T_s={perf.get('t_s', 0):.3f}  "
                  f"MSE_s={perf.get('mse_s', 0):.3f}  ECD_s={perf.get('ecd_s', 0):.3f}  "
                  f"HC_s={perf.get('hc_s', 0):.3f}  RPM_s={perf.get('rpm_s', 0):.3f}")

        print(f"  Level 2 - Safety Margin:     {info.get('safety_margin', 0):.4f}")
        margins_raw = info.get("safety_margins", {})
        margins = margins_raw if isinstance(margins_raw, dict) else {}
        if margins:
            print(f"    ECD_high={margins.get('margin_ecd_high_sg', 0):.3f} sg  "
                  f"ECD_low={margins.get('margin_ecd_low_sg', 0):.3f} sg  "
                  f"SPP={margins.get('margin_spp_bar', 0):.1f} bar  "
                  f"Torque={margins.get('margin_torque_knm', 0):.1f} kN·m")

        print(f"  Level 3 - Stability Score:   {info.get('stability_score', 0):.4f}")

        # constraints
        safe = info.get("all_safe", True)
        print(f"\n  --- Safety: {'✓ ALL SAFE' if safe else '✗ VIOLATIONS!'} ---")
        for v in info.get("safety_violations", []):
            print(f"    ✗ {v}")
        for w in info.get("stability_warnings", []):
            print(f"    ⚠ {w}")

        # reward parts
        print(f"\n  Reward: {reward:.4f}")
        reward_breakdown = info.get("reward_breakdown", {})
        if isinstance(reward_breakdown, dict):
            for k, v in reward_breakdown.items():
                print(f"    {k}: {v:.4f}")

        if use_wandb:
            import wandb
            wandb.log({
                "smoke/step": step,
                "smoke/reward": reward,
                "smoke/rop_m_h": info.get("rop_mh", 0),
                "smoke/depth_progress_m": info.get("depth_progress", 0),
                "smoke/performance_score": info.get("performance_score", 0),
                "smoke/safety_margin": info.get("safety_margin", 0),
                "smoke/stability_score": info.get("stability_score", 0),
            })

        total_reward += reward
        env.render()

        if terminated:
            print("  🎯 TARGET DEPTH REACHED!")
            break
        if truncated:
            print("  ⏱ Episode truncated (max steps).")
            break

    print(f"\n{'=' * 70}")
    print(f"Total reward over {steps_run} steps: {total_reward:.4f}")
    avg_reward = total_reward / steps_run if steps_run else 0.0
    print(f"Average reward per step: {avg_reward:.4f}")

    if use_wandb:
        import wandb
        wandb.log({
            "smoke_summary/total_reward": total_reward,
            "smoke_summary/avg_reward": avg_reward,
            "smoke_summary/steps": steps_run,
        })

    env.close()
    print("\nSanity check complete!")

    if use_wandb:
        import wandb
        wandb.finish()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smoke-test the drilling environment")
    parser.add_argument("--no-wandb", action="store_true",
                        help="Disable Weights & Biases logging")
    args = parser.parse_args()
    main(use_wandb=not args.no_wandb)
