#!/bin/bash

#SBATCH --partition alldlc2_gpu-l40s
#SBATCH --job-name step5_evaluate
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
    echo "Submit from the repo root, or pass DIGI_REPO_ROOT=$PWD to sbatch." >&2
    exit 1
}
STEP_NAME="step5_final_evaluation"
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

MODEL_PATH="${MODEL_PATH:-}"
EPISODES="${EPISODES:-3}"
MAX_STEPS="${MAX_STEPS:-5000}"
QUIET="${QUIET:-0}"
USE_WANDB="${USE_WANDB:-1}"
UCS_VALUES="${UCS_VALUES:-1.0 0.7 1.3 0.5 1.6}"
USE_DETOURNAY="${USE_DETOURNAY:-0}"
WOB_GAIN="${WOB_GAIN:-}"
BASE_CONFIG="${BASE_CONFIG:-}"
STEP_LOG="${JOB_LOG_DIR}/${STEP_NAME}-${TIMESTAMP}.log"

if [[ -z "${MODEL_PATH}" ]]; then
    echo "MODEL_PATH is required. Example:"
    echo "  sbatch --export=MODEL_PATH=logs/<step4_run>/tqc_drilling_final.zip ${BASH_SOURCE[0]}"
    exit 1
fi

read -r -a UCS_ARRAY <<< "${UCS_VALUES}"

CMD=(
    python -u evaluate.py
    --model "${MODEL_PATH}"
    --episodes "${EPISODES}"
    --max-steps "${MAX_STEPS}"
    --ucs "${UCS_ARRAY[@]}"
)

if [[ "${QUIET}" == "1" ]]; then
    CMD+=(--quiet)
fi

if [[ "${USE_WANDB}" != "1" ]]; then
    CMD+=(--no-wandb)
fi

if [[ "${USE_DETOURNAY}" == "1" ]]; then
    CMD+=(--use-detournay)
fi

if [[ -n "${WOB_GAIN}" ]]; then
    CMD+=(--wob-gain "${WOB_GAIN}")
fi

if [[ -n "${BASE_CONFIG}" ]]; then
    CMD+=(--base-config "${BASE_CONFIG}")
fi

printf 'Command: '
printf '%q ' "${CMD[@]}"
echo
"${CMD[@]}" 2>&1 | tee -a "${STEP_LOG}"

echo "Job execution complete."
