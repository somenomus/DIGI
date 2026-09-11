# Deep Reinforcement Learning for Rate-of-Penetration Control and Optimization in Drilling

Code, configuration and cached results for the paper *Deep reinforcement learning for
rate-of-penetration control and optimization for drilling* (Geoenergy Science and
Engineering, submitted 2026).

A TQC agent sets rotary speed, weight on bit and mud flow rate in NORCE's OpenLab
simulator and drills an 11 m section under hard operating limits. This repo has the
environment, training, hyperparameter search, evaluation, the offline-to-online
pipeline, and the scripts that produce every figure in the paper.

## What is here

```
config.py                    every knob: sim setup, action ranges, limits, reward weights
drilling_env.py              the gymnasium env around OpenLab (obs, reward, constraints)
train.py                     TQC training, checkpoint + replay buffer saving, resume
hpo.py                       optuna search, several episodes per trial
evaluate.py                  deterministic evaluation on a set of formations
baseline_fixed.py            same protocol with constant setpoints (Table 3, Fig. 9)
test_env.py, test_resume.py  sanity checks (random actions / save-resume round trip)
verify_api.py                first thing to run on a new machine: login + tag listing
make_realistic_formation.py  creates the drill_realistic config (50-70 MPa) on OpenLab
make_mixed_formation.py      creates the mixed 12/30/65 MPa section
model_comparison.py          MSE vs Detournay bit-rock model comparison
vibration_analysis.py        torque vibration analysis from stored sims
cleanup_sims.py, prune_training_sims.py   stored-sim housekeeping (cap is 20)
prune_aborted_sims.py        lists stored sims, deletes the aborted ones with --yes
scripts/step0 .. step7/      the slurm jobs that ran the whole pipeline, in order
                             (step7 = the fixed-setpoint baselines)
offline_rl/                  dataset build, TD3+BC / IQL pretraining, TD3 handoff and
                             online fine tuning, online evaluation, slurm jobs
paper_figures/               make_paper_figs.py + make_new_figs.py -> figs/*.pdf
                             (original-reward agent), make_gated_figs.py ->
                             figs_gated/*.pdf (torque-gated agent, the paper's
                             agent), tradeoff_table.py -> Table D.1
drill-2.json                 export of the base OpenLab configuration ("drill")
info.md                      the domain expert spec the reward is built from
eval_results/                evaluation summaries (json) behind the tables
baseline_results/            the eight fixed-setpoint episodes, summary json +
                             per-step npz trace each (Table 3, Fig. 9)
hpo_results/                 the two optuna studies and their best configs
paper_trajectories.npz       cached trajectories behind the figures
vibration_data.npz           cached torque traces, MSE vs Detournay
finetune_curve.json          per episode returns during fine tuning
openlab/                     NORCE's python client, v2.5.7, vendored (see below)
```

## Setup

```
conda env create -f environment.yml     # or: pip install -r requirements.txt
conda activate digi
```

Anything that talks to the simulator needs an OpenLab account and licence
(https://openlab.app). Credentials are read from the environment, nothing is stored
in the repo:

```
export OPENLAB_EMAIL=you@example.com
export OPENLAB_API_KEY=...
export OPENLAB_LICENSE_GUID=...
python verify_api.py
```

One thing to know: the vendored client falls back to writing your credentials into
`openlab/openlab/account.py` when no keyring backend is available (headless machines,
clusters). That file ships empty. If you run on such a machine, do not commit it
afterwards.

## Reproduce the paper figures

No simulator needed, everything reads the cached data in the repo:

```
cd paper_figures
python make_gated_figs.py                # figs 4-6 (completion, control, ECD) for the
                                         # torque-gated agent and fig 9 (fixed setpoints)
                                         # -> figs_gated/
python make_new_figs.py                  # fig 3 (reward study), fig 7 (original vs
                                         # torque-gated on the mixed section) -> figs/
python -c "import make_paper_figs as m; m.fig_training_curve()"   # figs 2 and 8
python tradeoff_table.py --check         # Table D.1, checked against the printed values
```

The paper's agent is the torque-gated one, so figs 4-6 and 9 come
from `figs_gated/`; `figs/` keeps the original-reward versions of the same figures.
`FIG_PREFIX=target` (the default) draws the original-reward runs and `FIG_PREFIX=gated`
the torque-gated runs in both figure scripts; `make_gated_figs.py` sets it for you.
Call single functions of `make_paper_figs.py` rather than running it whole, its own
`fig_reward_study` is the older version and would overwrite the one `make_new_figs.py`
writes.

## Simulator configuration

`drill-2.json` is the full export of the base `drill` configuration. The paper's
formation is derived from it:

```
python make_realistic_formation.py   # uploads drill-2.json's layers squeezed to 50-70 MPa as drill_realistic
python make_mixed_formation.py       # the mixed 12/30/65 MPa section
```

The per-strength variants (`drill_realistic_ucs0.4` etc.) are created on the fly by
the env. `base_config_name` is a runtime argument everywhere, so fine tuning on a
different well is a matter of pointing it at another configuration.

## Training

`scripts/step0_verify_transient` through `scripts/step6_realistic_finetune` are the
slurm jobs in the order they were run; the `.sh` files carry the exact arguments.
The offline route is `offline_rl/pretrain_job.sh` -> `eval_job.sh` ->
`finetune_job.sh` -> `finetune_eval_job.sh`. Every online step costs simulator API
time (2-3 steps/s), so read the caps in `config.py` before launching anything.

## Fixed-setpoint baselines

Table 3 and Fig. 9 compare the agent with two constant setpoints run under the same
protocol (Detournay model, default auto-driller gain, same warm-up, same cap):

```
python baseline_fixed.py --rpm 80  --wob 12 --flow 1800 --ucs 0.2 0.4 1.0 --base-config drill_realistic --max-steps 50000 --tag lowrpm
python baseline_fixed.py --rpm 120 --wob 10 --flow 2200 --ucs 0.2 0.4 1.0 --base-config drill_realistic --max-steps 50000 --tag highrpm
python baseline_fixed.py --rpm 80  --wob 12 --flow 1800 --ucs 1.0 --base-config drill_mixed --max-steps 40000 --tag lowrpm_mixed
```

or `sbatch --export=RPM=80,WOB=12,FLOW=1800,UCS_VALUES="0.2 0.4 1.0",BASE_CONFIG=drill_realistic,MAX_STEPS=50000,TAG=lowrpm scripts/step7_fixed_baseline/step7_fixed_baseline.sh`.
Each episode writes `baseline_results/<tag>_<config>_ucs<u>_<stamp>.json` (summary) and
`.npz` (per-step trace); the eight runs behind the paper are in there. The simulator's own
per-simulation maximum of 48,000 steps is the effective cap, whatever `--max-steps` says,
which is why the 120 rpm run at 1.0x stops at 9.8 m.

Running several evaluation jobs at the same time needs `--no-cleanup` (`NO_CLEANUP=1`
for the step5 script), otherwise each env reset ends every other running simulation on
the account. `--delete-sims` (`DELETE_SIMS=1`) drops each episode's stored sim
afterwards so the 20-sim cap does not fill. `prune_aborted_sims.py` lists what is
stored and deletes aborted runs with `--yes`.

## Dataset and trained policies

The `digi-drilling-v1` dataset (510,339 transitions, 37 episodes) and the trained
policies are archived on Zenodo: https://doi.org/10.5281/zenodo.22537645. The dataset's metadata card is
here at `offline_rl/dataset/digi_drilling_v1_meta.json`; the arrays and the policy
files are not. `offline_rl/build_dataset.py` documents how the dataset was built from
the replay buffer; it needs the raw buffer and the slurm logs, which are not included.

## Evaluation records

One row per result file, read from the file's own metadata. The `logs/...` policy
paths are where the checkpoints lived on the training machine; the archived policies
are on Zenodo.

## About the vendored OpenLab client

`openlab/` is NORCE's `openlab` package (2.5.7) with two local changes:
`UseDetournayROPModel` is passed through to the simulator (the paper depends on it),
and the login has a keyring-less fallback described above. NORCE's terms apply to
that code.
