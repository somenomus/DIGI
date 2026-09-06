#!/bin/bash

#SBATCH --partition ml_gpu-rtx2080
#SBATCH --job-name ft_eval_rerun
#SBATCH --time=1-00:00:00
#SBATCH --output %x-%A.out
#SBATCH --error %x-%A.err
#SBATCH --mem 32GB
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:1

# clean rerun of the fine tuned eval for the UCS values that got corrupted by
# running concurrently. UCS_LIST env var, default "0.4". run this on its own

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"

source ~/miniconda3/bin/activate
conda activate digi
export PYTHONUNBUFFERED=1

UCS_LIST="${UCS_LIST:-0.4}"
MAX_STEPS="${MAX_STEPS:-42000}"

python -u prune_training_sims.py || echo "[prune] non-fatal, continuing"

python -u offline_rl/eval_online.py \
    --policy offline_rl/models/td3_finetuned/policy_finetuned.d3 \
    --ucs ${UCS_LIST} --max-steps "${MAX_STEPS}"

echo "Fine-tuned re-eval complete (UCS: ${UCS_LIST})."
