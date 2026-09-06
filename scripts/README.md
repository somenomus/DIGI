Cluster job scripts for the execution plan live in one folder per step.

These scripts resolve the repo root from Slurm's submit directory.
If you submit from outside the repo, pass `DIGI_REPO_ROOT=/path/to/digi` with `sbatch --export`.

All scripts keep the sample cluster settings unchanged:
- partition: `ml_gpu-rtx2080`
- time: `6-00:00:00`
- memory: `32GB`
- CPUs: `4`
- GPU: `1`

Default sequence:

1. `sbatch scripts/step0_verify_transient/step0_verify_transient.sh`
2. `sbatch scripts/step1_hpo_learning/step1_hpo_learning.sh`
3. `sbatch scripts/step2_baseline_training/step2_baseline_training.sh`
4. `sbatch scripts/step3_hpo_hardening/step3_hpo_hardening.sh`
5. `sbatch --export=RESUME_MODEL=logs/<step2_run>/tqc_drilling_final.zip scripts/step4_curriculum_hardening/step4_curriculum_hardening.sh`
6. `sbatch --export=MODEL_PATH=logs/<step4_run>/tqc_drilling_final.zip scripts/step5_final_evaluation/step5_final_evaluation.sh`

Useful overrides:

- Step 0 optional smoke test:
  `sbatch --export=RUN_VERIFY_API=1 scripts/step0_verify_transient/step0_verify_transient.sh`
- Resume HPO with additional trials:
  `sbatch --export=N_TRIALS=6 scripts/step1_hpo_learning/step1_hpo_learning.sh`
- Disable W&B on any scripted run:
  `sbatch --export=USE_WANDB=0 <script>`
- Resume Step 2 after interruption:
  `sbatch --export=RESUME_MODEL=logs/<step2_run>/checkpoints/tqc_drilling_<n>_steps.zip scripts/step2_baseline_training/step2_baseline_training.sh`
- Resume Step 4 after interruption:
  `sbatch --export=RESUME_MODEL=logs/<step4_run>/checkpoints/tqc_drilling_<n>_steps.zip scripts/step4_curriculum_hardening/step4_curriculum_hardening.sh`

Budget allocation in the revised plan:

- Step 2 baseline training defaults to `500000` timesteps.
- Step 3 hardening HPO defaults to `5` episodes so each trial sees the full ordered UCS cycle.
- Step 4 hardening training defaults to `1000000` timesteps.
- Step 2 is baseline-only UCS.
- Step 4 uses curriculum randomization, not a fixed ordered UCS loop.
- W&B is enabled by default for scripted runs.
