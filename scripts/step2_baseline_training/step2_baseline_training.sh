#!/bin/bash

#SBATCH --partition bosch_gpu-rtx2080
#SBATCH --job-name step2_baseline
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
STEP_NAME="step2_baseline_training"
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

TIMESTEPS="${TIMESTEPS:-500000}"
EVAL_FREQ="${EVAL_FREQ:-50000}"
HPO_CONFIG="${HPO_CONFIG:-hpo_results/best_config_learn.json}"
USE_WANDB="${USE_WANDB:-1}"
RESUME_MODEL="${RESUME_MODEL:-}"
RUN_NAME="${RUN_NAME:-step2_baseline_${TIMESTAMP}}"
TRAIN_LOG_DIR="${DIGI_ROOT}/logs/${RUN_NAME}"
STEP_LOG="${JOB_LOG_DIR}/${STEP_NAME}-${TIMESTAMP}.log"

mkdir -p "${TRAIN_LOG_DIR}"

CMD=(
    python -u train.py
    --timesteps "${TIMESTEPS}"
    --log-dir "${TRAIN_LOG_DIR}"
    --hpo-config "${HPO_CONFIG}"
    --eval-freq "${EVAL_FREQ}"
)

if [[ -n "${RESUME_MODEL}" ]]; then
    CMD+=(--resume "${RESUME_MODEL}")
fi

if [[ "${USE_WANDB}" != "1" ]]; then
    CMD+=(--no-wandb)
fi

printf 'Command: '
printf '%q ' "${CMD[@]}"
echo
"${CMD[@]}" 2>&1 | tee -a "${STEP_LOG}"

echo "Job execution complete."
