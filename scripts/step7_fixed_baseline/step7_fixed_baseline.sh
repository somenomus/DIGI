#!/bin/bash

#SBATCH --partition alldlc2_gpu-l40s
#SBATCH --job-name step7_baseline
#SBATCH --time=1-00:00:00
#SBATCH --output %x-%A.out
#SBATCH --error %x-%A.err
#SBATCH --mem 32GB
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1

set -euo pipefail

find_digi_root() {
    local candidate
    local -a candidates=()

    if [[ -n "${DIGI_REPO_ROOT:-}" ]]; then
        candidates+=("${DIGI_REPO_ROOT}")
    fi
    if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
        candidates+=("${SLURM_SUBMIT_DIR}" "${SLURM_SUBMIT_DIR}/.." "${SLURM_SUBMIT_DIR}/../..")
    fi
    candidates+=("${PWD}" "${PWD}/.." "${PWD}/../..")

    for candidate in "${candidates[@]}"; do
        candidate="$(cd "${candidate}" 2>/dev/null && pwd -P)" || continue
        if [[ -f "${candidate}/train.py" && -d "${candidate}/scripts" ]]; then
            printf '%s\n' "${candidate}"
            return 0
        fi
    done

    return 1
}

DIGI_ROOT="$(find_digi_root)" || {
    echo "Could not determine digi repo root." >&2
    echo "Submit from the repo root, or pass DIGI_REPO_ROOT=/path/to/digi to sbatch." >&2
    exit 1
}
STEP_NAME="step7_fixed_baseline"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
JOB_LOG_DIR="${DIGI_ROOT}/logs/slurm/${STEP_NAME}"

mkdir -p "${JOB_LOG_DIR}" "${DIGI_ROOT}/wandb_logs/${STEP_NAME}"

echo "Workingdir: ${DIGI_ROOT}"
echo "Started at $(date)"
echo "Running job ${SLURM_JOB_NAME} with JID ${SLURM_JOB_ID} on ${SLURM_JOB_PARTITION}"

source ~/miniconda3/bin/activate
conda activate digi

export MUJOCO_GL=egl
export WANDB_START_METHOD=thread
export WANDB_DIR="${DIGI_ROOT}/wandb_logs/${STEP_NAME}"
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-4}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-4}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-4}
export PYTHONUNBUFFERED=1

cd "${DIGI_ROOT}"

# ---- fixed-setpoint baseline (PI request) ----
# usage: sbatch --export=RPM=80,WOB=12,FLOW=1800,UCS_VALUES="0.2 0.4 1.0",BASE_CONFIG=drill_realistic,MAX_STEPS=50000,TAG=lowrpm scripts/step7_fixed_baseline/step7_fixed_baseline.sh
RPM="${RPM:?set RPM}"; WOB="${WOB:?set WOB (t)}"; FLOW="${FLOW:?set FLOW (L/min)}"
UCS_VALUES="${UCS_VALUES:-0.2 0.4 1.0}"
BASE_CONFIG="${BASE_CONFIG:-drill_realistic}"
MAX_STEPS="${MAX_STEPS:-50000}"
TAG="${TAG:-fixed}"
STEP_LOG="${JOB_LOG_DIR}/${STEP_NAME}-${TAG}-${TIMESTAMP}.log"

python baseline_fixed.py --rpm "${RPM}" --wob "${WOB}" --flow "${FLOW}" \
    --ucs ${UCS_VALUES} --base-config "${BASE_CONFIG}" --max-steps "${MAX_STEPS}" \
    --tag "${TAG}" 2>&1 | tee "${STEP_LOG}"

echo "Finished at $(date)"
