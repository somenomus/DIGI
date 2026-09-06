Run from the repo root: `digi/`

If you submit from somewhere else, add:

```bash
--export=DIGI_REPO_ROOT=/path/to/digi
```

W&B is enabled by default for the scripted workflow.
If you want to disable it for one run, add:

```bash
--export=USE_WANDB=0
```

## 1. Step 0

Run:

```bash
sbatch scripts/step0_verify_transient/step0_verify_transient.sh
```

Check:

- `logs/slurm/step0_verify_transient/` has a new `.log`
- the log shows `test_env.py` completed without error
- depth is progressing and the simulation did not fail early

Optional smoke test first:

```bash
sbatch --export=RUN_VERIFY_API=1 scripts/step0_verify_transient/step0_verify_transient.sh
```

## 2. Step 1

Run:

```bash
sbatch scripts/step1_hpo_learning/step1_hpo_learning.sh
```

Check:

- `hpo_results/best_config_learn.json` exists
- `hpo_results/hpo_learn.db` exists

If both are there, continue.

## 3. Step 2

Run: 

```bash
sbatch scripts/step2_baseline_training/step2_baseline_training.sh   
```
If fail, 
```bash
sbatch --export=RESUME_MODEL=logs/step2_baseline_20260414-111759/checkpoints/tqc_drilling_180000_steps.zip,TIMESTEPS=30000 scripts/step2_baseline_training/step2_baseline_training.sh
```

Check the newest run folder:

```bash
ls -td logs/step2_baseline_* | head -1
```

In that folder, confirm these files exist:

- `tqc_drilling_final.zip`
- `tqc_drilling_final_buffer.pkl`

If both are there, continue.

## 4. Step 3

Run:

```bash
sbatch scripts/step3_hpo_hardening/step3_hpo_hardening.sh
```

Check:

- `hpo_results/best_config_harden.json` exists
- `hpo_results/hpo_harden.db` exists

If both are there, continue.

## 5. Step 4

First get the Step 2 folder path:

```bash
ls -td logs/step2_baseline_* | head -1
```

Use that path as `<STEP2_RUN>` below:

```bash
sbatch --export=RESUME_MODEL=logs/<STEP2_RUN>/tqc_drilling_final.zip scripts/step4_curriculum_hardening/step4_curriculum_hardening.sh
```

Example: Resubmit

```bash
sbatch --export=RESUME_MODEL=logs/step4_hardening_20260421-104123/checkpoints/tqc_drilling_100000_steps.zip,TIMESTEPS=900000 scripts/step4_curriculum_hardening/step4_curriculum_hardening.sh

100K before, 2.4, then. So, 340,000 is done. so, 660.000 left. 

sbatch --export=RESUME_MODEL=logs/step4_hardening_20260506-184355/checkpoints/tqc_drilling_240000_steps.zip,TIMESTEPS=660000 scripts/step4_curriculum_hardening/step4_curriculum_hardening.sh

420 000 done out of 660 000. so, 240000 left. runed

sbatch --export=RESUME_MODEL=logs/step4_hardening_20260508-185007/checkpoints/tqc_drilling_420000_steps.zip,TIMESTEPS=240000 scripts/step4_curriculum_hardening/step4_curriculum_hardening.sh

60 000 done out of 240000. so, 180000 left + 500K more. on hardening 



sbatch --export=RESUME_MODEL=logs/step4_hardening_20260511-125352/checkpoints/tqc_drilling_60000_steps.zip,TIMESTEPS=680000,EVAL_FREQ=25000 scripts/step4_curriculum_hardening/step4_curriculum_hardening.sh

```

Check the newest Step 4 folder:

```bash
ls -td logs/step4_hardening_* | head -1
```

In that folder, confirm these files exist:

- `tqc_drilling_final.zip`
- `tqc_drilling_final_buffer.pkl`

If both are there, continue.

## 6. Step 5

First get the Step 4 folder path:

```bash
ls -td logs/step4_hardening_* | head -1
```

Use that path as `<STEP4_RUN>` below:

```bash
sbatch --export=MODEL_PATH=logs/<STEP4_RUN>/tqc_drilling_final.zip scripts/step5_final_evaluation/step5_final_evaluation.sh
```

Example:

```bash
sbatch --export=MODEL_PATH=logs/step4_hardening_20260410-140000/tqc_drilling_final.zip scripts/step5_final_evaluation/step5_final_evaluation.sh
```

Check:

- `eval_results/` has a new `eval_*.json`
- `logs/slurm/step5_final_evaluation/` has a new `.log`

### Step 5 — optional env-var overrides

Pre-set these before `sbatch` and use `--export=ALL`. Values with spaces (like `UCS_VALUES`) won't work via `--export=A=...,B=...,...` so always use this pattern when overriding `UCS_VALUES`.

| Variable | Default | Effect |
|----------|---------|--------|
| `MODEL_PATH` | (required) | Model `.zip` to evaluate |
| `UCS_VALUES` | `1.0 0.7 1.3 0.5 1.6` | Space-separated UCS multipliers |
| `EPISODES` | `3` | Episodes per UCS (use `1` — eval is deterministic, reps are redundant) |
| `MAX_STEPS` | `5000` | Per-episode step cap; use `15000` to match training horizon |
| `USE_DETOURNAY` | `0` | Set `1` to use the Detournay ROP model (realistic vibration) instead of the default MSE model |
| `USE_WANDB` | `1` | Set `0` to disable W&B logging |
| `QUIET` | `0` | Set `1` to suppress per-step output |

Example — easier formations with Detournay model:

```bash
MODEL_PATH=logs/<STEP4_RUN>/tqc_drilling_final.zip \
UCS_VALUES="0.2 0.3 0.4 0.5" \
EPISODES=1 MAX_STEPS=15000 USE_DETOURNAY=1 \
sbatch --partition=mldlc2_gpu-l40s --time=1-00:00:00 --export=ALL \
  scripts/step5_final_evaluation/step5_final_evaluation.sh
```

The `USE_DETOURNAY=1` flag is modular and orthogonal to everything else — toggling it does not require retraining or any other config change.

## Notes

- Do not run `verify_api.py` while Step 2 or Step 4 is active.
- If Step 2 or Step 4 is interrupted, resume from the latest checkpoint `.zip` only if the matching `_buffer.pkl` is in the same folder.
- The only path updates you need are `<STEP2_RUN>` in Step 4 and `<STEP4_RUN>` in Step 5.
- Step 2 trains on the baseline formation only.
- Step 3 HPO uses the full ordered UCS cycle `1.0 -> 1.3 -> 0.7 -> 1.6 -> 0.5`.
- Step 4 resumes the Step 2 model and trains with curriculum randomization over the UCS range, not a fixed repeating order.