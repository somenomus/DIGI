#!/bin/bash

#SBATCH --partition ml_gpu-rtx2080
#SBATCH --job-name ft_eval
#SBATCH --time=1-00:00:00
#SBATCH --output %x-%A.out
#SBATCH --error %x-%A.err
#SBATCH --mem 32GB
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:1

# deterministic eval of the fine tuned TD3. 0.4x first (the comparison against
# offline only and the TQC reference), then 0.2x and 1.0x like the online agent

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"

source ~/miniconda3/bin/activate
conda activate digi
export PYTHONUNBUFFERED=1

python -u prune_training_sims.py || echo "[prune] non-fatal, continuing"

python -u offline_rl/eval_online.py \
    --policy offline_rl/models/td3_finetuned/policy_finetuned.d3 \
    --ucs 0.4 0.2 1.0 --max-steps 42000

echo "Fine-tuned evaluation complete."
