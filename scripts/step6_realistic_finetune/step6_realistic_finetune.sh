#!/bin/bash

# the GTX 1080 Ti partition (sm_61) is too old for this torch, needs sm_70+.
# use the RTX 2080 (sm_75) or 3080 (sm_86) ones
#SBATCH --partition alldlc_gpu-rtx3080
#SBATCH --job-name step6_finetune
#SBATCH --time=1-00:00:00
#SBATCH --output %x-%A.out
#SBATCH --error %x-%A.err
#SBATCH --mem 32GB
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:1

# realistic formation fine tune, chained 1 day jobs.
#   drill_realistic (50-70 MPa), Detournay model
#   UCS randomised per episode, continuous [UCS_MIN, UCS_MAX], default 0.2-1.0
#   completion shaped reward (cfg.DEPTH_PROGRESS_WEIGHT etc)
#   reuses the hardening hps, no new hpo
#
# each call runs ONE ~1 day job (TIMESTEPS) into its own folder, so nothing
# ever overwrites an earlier job.
#
# job 1, weights only from step 2 since the reward changed, fresh buffer:
#   RESUME_MODEL=logs/step2_baseline_20260416-115710/tqc_drilling_final.zip \
#   NO_BUFFER=1 sbatch scripts/step6_realistic_finetune/step6_realistic_finetune.sh
# jobs 2+, resume the previous job together with its buffer:
#   RESUME_MODEL=logs/<prev step6 run>/tqc_drilling_final.zip \
#   sbatch scripts/step6_realistic_finetune/step6_realistic_finetune.sh

set -euo pipefail

find_digi_root() {
    local candidate
    local -a candidates=()
    if [[ -n "${DIGI_REPO_ROOT:-}" ]]; then candidates+=("${DIGI_REPO_ROOT}"); fi
    if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
        candidates+=("${SLURM_SUBMIT_DIR}" "${SLURM_SUBMIT_DIR}/.." "${SLURM_SUBMIT_DIR}/../..")
    fi
    candidates+=("${PWD}" "${PWD}/.." "${PWD}/../..")
    for candidate in "${candidates[@]}"; do
        candidate="$(cd "${candidate}" 2>/dev/null && pwd -P)" || continue
        if [[ -f "${candidate}/train.py" && -d "${candidate}/scripts" ]]; then
            printf '%s\n' "${candidate}"; return 0
        fi
    done
    return 1
}

DIGI_ROOT="$(find_digi_root)" || { echo "Could not determine digi repo root." >&2; exit 1; }
STEP_NAME="step6_realistic_finetune"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
JOB_LOG_DIR="${DIGI_ROOT}/logs/slurm/${STEP_NAME}"
mkdir -p "${JOB_LOG_DIR}" "${DIGI_ROOT}/wandb_logs/${STEP_NAME}"

echo "Workingdir: ${DIGI_ROOT}"
echo "Started at $(date)"
echo "Running ${SLURM_JOB_NAME} JID ${SLURM_JOB_ID} on ${SLURM_JOB_PARTITION}"

source ~/miniconda3/bin/activate
conda activate digi

export MUJOCO_GL=egl
export WANDB_START_METHOD=thread
export WANDB_DIR="${DIGI_ROOT}/wandb_logs/${STEP_NAME}"
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-6}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-6}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-6}
export PYTHONUNBUFFERED=1

cd "${DIGI_ROOT}"

TIMESTEPS="${TIMESTEPS:-170000}"          # sized to fit ~1 day at ~7.5k steps/h
HPO_CONFIG="${HPO_CONFIG:-hpo_results/best_config_harden.json}"
BASE_CONFIG="${BASE_CONFIG:-drill_realistic}"
UCS_MIN="${UCS_MIN:-0.2}"
UCS_MAX="${UCS_MAX:-1.0}"
NO_BUFFER="${NO_BUFFER:-0}"
REVISED_REWARD="${REVISED_REWARD:-0}"     # 1 -> gated-torque revised reward (PI request)
USE_WANDB="${USE_WANDB:-1}"
RESUME_MODEL="${RESUME_MODEL:-}"
RUN_NAME="${RUN_NAME:-${STEP_NAME}_${TIMESTAMP}}"
TRAIN_LOG_DIR="${DIGI_ROOT}/logs/${RUN_NAME}"
STEP_LOG="${JOB_LOG_DIR}/${STEP_NAME}-${TIMESTAMP}.log"

if [[ -z "${RESUME_MODEL}" ]]; then
    echo "RESUME_MODEL is required (Step 2 final for job 1, or prior step6 run for jobs 2+)."
    exit 1
fi
if [[ -e "${TRAIN_LOG_DIR}" ]]; then
    echo "Refusing to reuse existing run folder ${TRAIN_LOG_DIR} (would risk overwrite)."
    exit 1
fi
mkdir -p "${TRAIN_LOG_DIR}"

# free stored sim slots from earlier jobs, the env only knows about its own process
python -u prune_training_sims.py || echo "[prune] non-fatal failure, continuing"

CMD=(
    python -u train.py
    --timesteps "${TIMESTEPS}"
    --log-dir "${TRAIN_LOG_DIR}"
    --resume "${RESUME_MODEL}"
    --base-config "${BASE_CONFIG}"
    --ucs-random continuous
    --ucs-min "${UCS_MIN}"
    --ucs-max "${UCS_MAX}"
    --use-detournay
    --hpo-config "${HPO_CONFIG}"
)

if [[ "${NO_BUFFER}" == "1" ]]; then
    CMD+=(--no-buffer)
fi
if [[ "${REVISED_REWARD}" == "1" ]]; then
    CMD+=(--revised-reward)
fi
if [[ "${USE_WANDB}" != "1" ]]; then
    CMD+=(--no-wandb)
fi

printf 'Command: '
printf '%q ' "${CMD[@]}"
echo
"${CMD[@]}" 2>&1 | tee -a "${STEP_LOG}"

echo "Job execution complete. Output: ${TRAIN_LOG_DIR}"
