#!/bin/bash

#SBATCH --partition ml_gpu-rtx2080
#SBATCH --job-name offline_eval
#SBATCH --time=1-00:00:00
#SBATCH --output %x-%A.out
#SBATCH --error %x-%A.err
#SBATCH --mem 32GB
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:1

# online check of the three offline policies. one deterministic episode each,
# drill_realistic at 0.4x, Detournay. up to 3 x 25k api steps, less if they finish early

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"

source ~/miniconda3/bin/activate
conda activate digi
export PYTHONUNBUFFERED=1

STEPS="${STEPS:-200000}"
UCS="${UCS:-0.4}"
MAX_STEPS="${MAX_STEPS:-25000}"

for ARM in td3bc_posret td3bc_full iql_full; do
    P="offline_rl/models/${ARM}_${STEPS}/policy.d3"
    if [[ ! -f "$P" ]]; then echo "MISSING: $P — skipping"; continue; fi
    echo "=== Online validation: ${ARM} (UCS ${UCS}, cap ${MAX_STEPS}) ==="
    # if one arm dies on the api the others still run
    python -u offline_rl/eval_online.py --policy "$P" --ucs "$UCS" --max-steps "$MAX_STEPS" \
        || echo "ARM ${ARM} FAILED — continuing"
done

echo "Validation complete. Results in eval_results/offline_eval_*.json"
