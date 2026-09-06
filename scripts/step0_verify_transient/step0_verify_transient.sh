#!/bin/bash

#SBATCH --partition ml_gpu-rtx2080
#SBATCH --job-name step0_transient
#SBATCH --time=6-00:00:00
#SBATCH --output %x-%A.out
#SBATCH --error %x-%A.err
#SBATCH --mem 32GB
#SBATCH --cpus-per-task=4
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
STEP_NAME="step0_verify_transient"
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

RUN_VERIFY_API="${RUN_VERIFY_API:-0}"
USE_WANDB="${USE_WANDB:-1}"
STEP_LOG="${JOB_LOG_DIR}/${STEP_NAME}-${TIMESTAMP}.log"

if [[ "${RUN_VERIFY_API}" == "1" ]]; then
    VERIFY_CMD=(python -u verify_api.py)
    printf 'Command: '
    printf '%q ' "${VERIFY_CMD[@]}"
    echo
    "${VERIFY_CMD[@]}" 2>&1 | tee -a "${STEP_LOG}"
fi

TEST_CMD=(python -u test_env.py)
if [[ "${USE_WANDB}" != "1" ]]; then
    TEST_CMD+=(--no-wandb)
fi
printf 'Command: '
printf '%q ' "${TEST_CMD[@]}"
echo
"${TEST_CMD[@]}" 2>&1 | tee -a "${STEP_LOG}"

echo "Job execution complete."
