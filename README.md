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
test_env.py, test_resume.py  sanity checks (random actions / save-resume round trip)
verify_api.py                first thing to run on a new machine: login + tag listing
make_realistic_formation.py  creates the drill_realistic config (50-70 MPa) on OpenLab
make_mixed_formation.py      creates the mixed 12/30/65 MPa section
model_comparison.py          MSE vs Detournay bit-rock model comparison
vibration_analysis.py        torque vibration analysis from stored sims
cleanup_sims.py, prune_training_sims.py   stored-sim housekeeping (cap is 20)
scripts/step0 .. step6/      the slurm jobs that ran the whole pipeline, in order
offline_rl/                  dataset build, TD3+BC / IQL pretraining, TD3 handoff and
                             online fine tuning, online evaluation, slurm jobs
paper_figures/               make_paper_figs.py + make_new_figs.py -> figs/*.pdf
drill-2.json                 export of the base OpenLab configuration ("drill")
info.md                      the domain expert spec the reward is built from
eval_results/                evaluation summaries (json) behind the tables
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
python make_paper_figs.py     # training curve, control strategy, ECD envelope, bit-rock
python make_new_figs.py       # completion, reward study, original vs torque-gated
```

The seven PDFs in `paper_figures/figs/` are the ones in the paper.

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

## Dataset and trained policies

The `digi-drilling-v1` dataset (510,339 transitions, 37 episodes) and the trained
policies are archived on Zenodo: https://doi.org/10.5281/zenodo.22537645. The dataset's metadata card is
here at `offline_rl/dataset/digi_drilling_v1_meta.json`; the arrays and the policy
files are not. `offline_rl/build_dataset.py` documents how the dataset was built from
the replay buffer; it needs the raw buffer and the slurm logs, which are not included.


## About the vendored OpenLab client

`openlab/` is NORCE's `openlab` package (2.5.7) with two local changes:
`UseDetournayROPModel` is passed through to the simulator (the paper depends on it),
and the login has a keyring-less fallback described above. NORCE's terms apply to
that code.
