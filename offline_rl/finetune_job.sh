#!/bin/bash

#SBATCH --partition ml_gpu-rtx2080
#SBATCH --job-name td3_finetune
#SBATCH --time=1-00:00:00
#SBATCH --output %x-%A.out
#SBATCH --error %x-%A.err
#SBATCH --mem 48GB
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1

# online fine tune, td3bc_posret -> TD3 handoff, 50k live steps.
# ~2-3 steps/s so 5-7 h. checkpoint every 10k (save_interval=1)

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"

source ~/miniconda3/bin/activate
conda activate digi
export PYTHONUNBUFFERED=1

# free stored sim slots first
python -u prune_training_sims.py || echo "[prune] non-fatal, continuing"

python -u offline_rl/finetune_online.py \
    --policy offline_rl/models/td3bc_posret_200000/policy.d3 \
    --steps "${STEPS:-50000}" --gpu

echo "Fine-tune complete."
