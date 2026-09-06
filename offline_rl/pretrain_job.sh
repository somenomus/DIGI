#!/bin/bash

#SBATCH --partition ml_gpu-rtx2080
#SBATCH --job-name offline_pretrain
#SBATCH --time=1-00:00:00
#SBATCH --output %x-%A.out
#SBATCH --error %x-%A.err
#SBATCH --mem 48GB
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1

# offline pretraining on digi_drilling_v1. gpu only, no api.
# arm A : IQL on everything (the advantage weighting filters on its own)
# arm B : TD3+BC on the positive return episodes (drops the 8 early bad ones,
#         keeps the full 0.24-1.0 UCS range)
# arm B': TD3+BC on everything (does the filter matter at all)

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"

source ~/miniconda3/bin/activate
conda activate digi
export PYTHONUNBUFFERED=1

STEPS="${STEPS:-200000}"

echo "=== Arm B: TD3+BC (positive-return episodes) ==="
python -u offline_rl/pretrain.py --algo td3bc --steps "${STEPS}" --gpu \
    --min-return 0 --out offline_rl/models/td3bc_posret_${STEPS}

echo "=== Arm B': TD3+BC (full dataset) ==="
python -u offline_rl/pretrain.py --algo td3bc --steps "${STEPS}" --gpu \
    --out offline_rl/models/td3bc_full_${STEPS}

echo "=== Arm A: IQL (full dataset) ==="
python -u offline_rl/pretrain.py --algo iql --steps "${STEPS}" --gpu \
    --out offline_rl/models/iql_full_${STEPS}

echo "Offline pretraining complete."
ls -la offline_rl/models/*/policy.d3
