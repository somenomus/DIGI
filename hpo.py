"""hyperparameter search with optuna, several episodes per trial.

one episode not tells you about learning, and with a different UCS per
episode its noisy on top of that. so every trial trains a fresh TQC for N
episodes across a set of formations, and the objective is a composite over
the last episodes: mean reward + a bonus for reaching target + a bonus for
safety margin. that picks hps that learn fast, not hps that had one good
episode.

Usage:
    python hpo.py                  # Runs 20 trials with W&B
    python hpo.py --n-trials 10     # Custom trial count
    python hpo.py --no-wandb           # Disable W&B logging
    python hpo.py --study-name my_exp    # Custom study name (for resuming)
    python hpo.py --episodes 5          # Episodes per trial (default: 3)

Results are saved to hpo_results/optuna_study.db (SQLite) so you can resume
interrupted runs. Best config saved to hpo_results/best_config.json.
"""
import sys
import os
import json
import argparse
from datetime import datetime

_cwd = os.path.dirname(os.path.abspath(__file__))
_openlab_parent = os.path.join(_cwd, "openlab")
if _openlab_parent not in sys.path:
    sys.path.insert(0, _openlab_parent)
if _cwd not in sys.path:
    sys.path.insert(0, _cwd)

import numpy as np
import gymnasium as gym
import optuna
from sb3_contrib import TQC
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor

from drilling_env import DrillingEnv
import config as cfg

# where the hpo output goes
HPO_DIR = os.path.join(_cwd, "hpo_results")

# hpo settings
HPO_LEARNING_STARTS = 2000      # lower than train.py to allow updates in early episodes
N_EVAL_EPISODES_DEFAULT = 3     # episodes per trial (trades off quality vs API cost)

# formations the eval episodes cycle through, one per episode
HPO_UCS_CYCLE = [1.0, 1.3, 0.7, 1.6, 0.5]

# per phase: 'baseline' = every episode at 1.0, hps for the learning stage.
# 'cycle' = walk through HPO_UCS_CYCLE, hps for the hardening stage
HPO_UCS_BASELINE = [1.0, 1.0, 1.0, 1.0, 1.0]


class NEpisodeEnv(gym.Wrapper):
    """Wrapper that runs exactly N episodes then blocks further resets.

    After N episodes, it returns dummy observations to prevent additional
    API simulations from being created by SB3's auto-reset.
    """

    def __init__(self, env, max_episodes: int, ucs_cycle: list = None):
        super().__init__(env)
        self._max_episodes = max_episodes
        self._ucs_cycle = ucs_cycle or HPO_UCS_CYCLE
        self._episode_count = 0
        self._all_done = False

    def step(self, action):
        if self._all_done:
            # sb3 wants a step back
            dummy = np.zeros(self.observation_space.shape, dtype=np.float32)
            return dummy, 0.0, False, True, {}
        obs, reward, terminated, truncated, info = self.env.step(action)
        if terminated or truncated:
            self._episode_count += 1
            if self._episode_count >= self._max_episodes:
                self._all_done = True
        return obs, reward, terminated, truncated, info

    def reset(self, **kwargs):
        if self._all_done:
            dummy = np.zeros(self.observation_space.shape, dtype=np.float32)
            return dummy, {}

        # UCS for this episode. has to go through _ucs_multiplier, reset() rebuilds
        # _current_ucs from it. and _ucs_random_mode must be None or the env overrides us
        ucs_idx = self._episode_count % len(self._ucs_cycle)
        ucs_val = self._ucs_cycle[ucs_idx]
        self.env._ucs_multiplier = ucs_val
        self.env._ucs_random_mode = None  # prevent env from overriding our UCS

        return self.env.reset(**kwargs)


class HPOMultiEpisodeCallback(BaseCallback):
    """Callback that tracks metrics across N episodes for HPO evaluation.

    Collects per-episode metrics and supports Optuna pruning:
    if early episodes show terrible performance, the trial can be
    pruned to save API budget.
    """

    def __init__(self, trial: optuna.Trial, trial_number: int,
                 n_episodes: int, use_wandb: bool = True, verbose: int = 0):
        super().__init__(verbose)
        self._trial = trial
        self._trial_number = trial_number
        self._n_episodes = n_episodes
        self._use_wandb = use_wandb

        # per episode
        self._ep_reward = 0.0
        self._ep_rops = []
        self._ep_mses = []
        self._ep_perf_scores = []
        self._ep_safety_margins = []
        self._ep_depth = 0.0
        self._ep_target = False
        self._ep_len = 0

        # across episodes
        self._episode_results = []
        self._current_episode = 0

    def _on_step(self) -> bool:
        infos = self.locals.get("infos", [])
        rewards = self.locals.get("rewards", [])

        for i, info in enumerate(infos):
            if i < len(rewards):
                self._ep_reward += float(rewards[i])

            if "rop" in info:
                self._ep_rops.append(info["rop"])
            if "mse_mpa" in info:
                self._ep_mses.append(info["mse_mpa"])
            if "performance_score" in info:
                self._ep_perf_scores.append(info["performance_score"])
            if "safety_margin" in info:
                self._ep_safety_margins.append(info["safety_margin"])
            if "depth_progress" in info:
                self._ep_depth = info["depth_progress"]
            if "target_reached" in info:
                self._ep_target = info["target_reached"]

            self._ep_len += 1

            # episode done
            if "episode" in info:
                ep_result = {
                    "episode": self._current_episode,
                    "reward": self._ep_reward,
                    "length": self._ep_len,
                    "depth_m": self._ep_depth,
                    "target_reached": self._ep_target,
                    "avg_rop_mh": np.mean(self._ep_rops) * 3600 if self._ep_rops else 0,
                    "avg_mse": np.mean(self._ep_mses) if self._ep_mses else 0,
                    "avg_perf_score": np.mean(self._ep_perf_scores) if self._ep_perf_scores else 0,
                    "avg_safety_margin": np.mean(self._ep_safety_margins) if self._ep_safety_margins else 0,
                    "min_safety_margin": np.min(self._ep_safety_margins) if self._ep_safety_margins else 0,
                    "ucs": info.get("ucs_multiplier", 1.0),
                }

                self._episode_results.append(ep_result)
                self._current_episode += 1

                ucs_str = f"UCS={ep_result['ucs']:.1f}" if ep_result['ucs'] != 1.0 else "UCS=1.0"
                target_str = "TARGET!" if ep_result['target_reached'] else f"depth={ep_result['depth_m']:.1f}m"
                print(f"    Ep {ep_result['episode']+1}/{self._n_episodes} "
                      f"({ucs_str}): reward={ep_result['reward']:.1f}, "
                      f"{target_str}, ROP={ep_result['avg_rop_mh']:.1f}m/h, "
                      f"perf={ep_result['avg_perf_score']:.3f}")

                # wandb
                if self._use_wandb:
                    import wandb
                    wandb.log({
                        f"hpo/trial_{self._trial_number}/ep_{self._current_episode}_reward": ep_result["reward"],
                        f"hpo/trial_{self._trial_number}/ep_{self._current_episode}_depth": ep_result["depth_m"],
                        f"hpo/trial_{self._trial_number}/ep_{self._current_episode}_rop": ep_result["avg_rop_mh"],
                        "hpo/trial_number": self._trial_number,
                    })

                # report after every episode so optuna can prune the hopeless trials early
                intermediate_score = self._compute_objective()
                self._trial.report(intermediate_score, self._current_episode)
                if self._trial.should_prune():
                    print(f"    ✂ Trial {self._trial_number} PRUNED by Optuna after ep {self._current_episode}")
                    raise optuna.TrialPruned()

                # reset
                self._ep_reward = 0.0
                self._ep_rops = []
                self._ep_mses = []
                self._ep_perf_scores = []
                self._ep_safety_margins = []
                self._ep_depth = 0.0
                self._ep_target = False
                self._ep_len = 0

                # done after N episodes
                if self._current_episode >= self._n_episodes:
                    return False

        return True

    def _compute_objective(self) -> float:
        """Compute composite objective from all episodes so far.

        Components:
          1. avg_reward: mean total reward across episodes (primary signal)
          2. depth_bonus: bonus for consistently reaching target depth
          3. safety_bonus: bonus for maintaining safe margins
          4. improvement_bonus: reward for episode-over-episode improvement
             (measures LEARNING, not just performance)

        This composite ensures HPO finds HPs that:
          - Give good overall performance (reward)
          - Reach target depth reliably (depth)
          - Maintain safety (safety margin)
          - Show learning progress across episodes (improvement)
        """
        if not self._episode_results:
            return float("-inf")

        results = self._episode_results

        # 1. mean reward per step, so long episodes dont win by default
        avg_reward = np.mean([r["reward"] for r in results])

        # 2. fraction that reached target
        target_rate = np.mean([1.0 if r["target_reached"] else 0.0 for r in results])
        depth_bonus = target_rate * 5.0  # up to +5.0

        # 3. mean of the min safety margin
        avg_min_safety = np.mean([r["min_safety_margin"] for r in results])
        safety_bonus = max(0, avg_min_safety) * 2.0  # scaled

        # 4. is it improving, later episodes vs earlier
        if len(results) >= 2:
            first_half = results[:len(results)//2]
            second_half = results[len(results)//2:]
            early_reward = np.mean([r["reward"] for r in first_half])
            late_reward = np.mean([r["reward"] for r in second_half])
            improvement = max(0, late_reward - early_reward)
        else:
            improvement = 0.0

        objective = avg_reward + depth_bonus + safety_bonus + improvement

        return float(objective)

    @property
    def objective_value(self) -> float:
        return self._compute_objective()


def run_trial(hyperparams: dict, trial: optuna.Trial, trial_number: int,
              n_episodes: int, use_wandb: bool = True,
              ucs_mode: str = "cycle") -> float:
    """
    Run one HPO trial: create TQC agent, train for N episodes
    across different UCS formations, return composite objective.
    
    Args:
        ucs_mode: 'cycle' (diverse UCS per episode) or 'baseline' (all UCS=1.0)
    """
    # formations for this mode
    if ucs_mode == "baseline":
        ucs_pool = HPO_UCS_BASELINE
    else:
        ucs_pool = HPO_UCS_CYCLE
    ucs_for_trial = [ucs_pool[i % len(ucs_pool)] for i in range(n_episodes)]

    env = Monitor(NEpisodeEnv(
        DrillingEnv(max_steps=cfg.HPO_MAX_EPISODE_STEPS),
        max_episodes=n_episodes,
        ucs_cycle=ucs_for_trial,
    ))

    model = TQC(
        "MlpPolicy",
        env,
        learning_rate=hyperparams["learning_rate"],
        buffer_size=1_000_000,
        learning_starts=HPO_LEARNING_STARTS,
        batch_size=hyperparams["batch_size"],
        tau=hyperparams["tau"],
        gamma=hyperparams["gamma"],
        top_quantiles_to_drop_per_net=2,
        policy_kwargs=dict(
            net_arch=[256, 256],
            n_quantiles=25,
            n_critics=2,
        ),
        verbose=0,
    )

    callback = HPOMultiEpisodeCallback(
        trial=trial,
        trial_number=trial_number,
        n_episodes=n_episodes,
        use_wandb=use_wandb,
    )

    ucs_str = ", ".join([f"{u:.1f}" for u in ucs_for_trial])
    print(f"\n  [Trial {trial_number}] {n_episodes} episodes (UCS: [{ucs_str}]) | "
          f"lr={hyperparams['learning_rate']:.2e}, "
          f"gamma={hyperparams['gamma']:.4f}, "
          f"tau={hyperparams['tau']:.4f}, "
          f"batch={hyperparams['batch_size']}")

    # big number, the callback stops it after N episodes anyway
    max_steps = cfg.HPO_MAX_EPISODE_STEPS * n_episodes

    try:
        model.learn(
            total_timesteps=max_steps,
            callback=callback,
            progress_bar=True,
            log_interval=None,
        )
    except optuna.TrialPruned:
        env.close()
        raise  # let Optuna handle pruned trials
    except Exception as e:
        print(f"  [Trial {trial_number}] Training error: {e}")
        env.close()
        return float("-inf")

    objective_val = callback.objective_value

    results = callback._episode_results
    rewards = [r["reward"] for r in results]
    depths = [r["depth_m"] for r in results]
    targets = sum(1 for r in results if r["target_reached"])

    print(f"  [Trial {trial_number}] RESULT: objective={objective_val:.2f}, "
          f"avg_reward={np.mean(rewards):.1f}, "
          f"targets={targets}/{len(results)}, "
          f"avg_depth={np.mean(depths):.1f}m")

    env.close()
    return objective_val


def objective(trial: optuna.Trial, n_episodes: int,
              use_wandb: bool = True, ucs_mode: str = "cycle") -> float:
    """Optuna objective: sample HPs, train N episodes, return composite score."""

    hyperparams = {
        "learning_rate": trial.suggest_float("learning_rate", 1e-5, 1e-3, log=True),
        "gamma": trial.suggest_float("gamma", 0.95, 0.999),
        "tau": trial.suggest_float("tau", 0.001, 0.02),
        "batch_size": trial.suggest_categorical("batch_size", [64, 128, 256, 512]),
    }

    # wandb
    if use_wandb:
        import wandb
        wandb.log({
            "hpo/trial_number": trial.number,
            "hpo/learning_rate": hyperparams["learning_rate"],
            "hpo/gamma": hyperparams["gamma"],
            "hpo/tau": hyperparams["tau"],
            "hpo/batch_size": hyperparams["batch_size"],
        })

    score = run_trial(hyperparams, trial, trial.number,
                      n_episodes=n_episodes, use_wandb=use_wandb,
                      ucs_mode=ucs_mode)

    if use_wandb:
        import wandb
        wandb.log({
            "hpo/trial_number": trial.number,
            "hpo/trial_objective": score,
        })

    return score


def run_hpo(n_trials: int = 20, n_episodes: int = N_EVAL_EPISODES_DEFAULT,
            study_name: str = "tqc_drilling_hpo", use_wandb: bool = True,
            ucs_mode: str = "cycle", output_name: str = "best_config"):
    """Run the HPO study.
    
    Args:
        ucs_mode: 'cycle' (diverse UCS) or 'baseline' (UCS=1.0 only)
        output_name: base name for output config file (e.g., 'best_config_learn')
    """
    os.makedirs(HPO_DIR, exist_ok=True)

    db_path = os.path.join(HPO_DIR, f"{study_name}.db")
    storage = f"sqlite:///{db_path}"

    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        direction="maximize",
        load_if_exists=True,
        sampler=optuna.samplers.TPESampler(seed=42),
        pruner=optuna.pruners.MedianPruner(
            n_startup_trials=3,       # don't prune the first 3 trials
            n_warmup_steps=1,         # allow at least 1 episode before pruning
        ),
    )

    # one wandb run for the whole study
    if use_wandb:
        import wandb
        wandb.init(
            project="digi-drilling-hpo",
            name=f"hpo_{study_name}_{datetime.now().strftime('%m%d_%H%M')}",
            config={
                "n_trials": n_trials,
                "n_episodes_per_trial": n_episodes,
                "study_name": study_name,
                "objective": "composite: avg_reward + depth_bonus + safety + learning",
                "tuned_params": ["learning_rate", "gamma", "tau", "batch_size"],
                "ucs_cycle": HPO_UCS_CYCLE,
                "max_episode_steps": cfg.HPO_MAX_EPISODE_STEPS,
                "performance_weights": cfg.PERFORMANCE_WEIGHTS,
                "hpo_learning_starts": HPO_LEARNING_STARTS,
            },
            save_code=True,
        )

    api_cost = n_trials * n_episodes
    print(f"{'=' * 60}")
    print(f"OPTUNA HPO — {study_name}")
    print(f"{'=' * 60}")
    print(f"  Trials: {n_trials}")
    print(f"  Episodes per trial: {n_episodes}")
    print(f"  Total API simulations: ~{api_cost} (trials × episodes)")
    print(f"  UCS cycle per trial: {HPO_UCS_CYCLE[:n_episodes]}")
    print(f"  Objective: composite (reward + depth + safety + learning)")
    print(f"  Parameters: learning_rate, gamma, tau, batch_size")
    print(f"  Pruner: MedianPruner (prune after 1 episode if below median)")
    print(f"  UCS mode: {ucs_mode}")
    print(f"  Storage: {db_path}")
    print(f"  W&B: {'enabled' if use_wandb else 'disabled'}")
    if len(study.trials) > 0:
        print(f"  Resuming from {len(study.trials)} existing trials")

    study.optimize(
        lambda trial: objective(trial, n_episodes=n_episodes,
                                use_wandb=use_wandb, ucs_mode=ucs_mode),
        n_trials=n_trials,
        show_progress_bar=True,
    )

    # best config to json
    best = study.best_trial
    ucs_tested = HPO_UCS_BASELINE[:n_episodes] if ucs_mode == "baseline" else HPO_UCS_CYCLE[:n_episodes]
    best_config = {
        "best_trial_number": best.number,
        "best_value": best.value,
        "best_params": best.params,
        "n_episodes_per_trial": n_episodes,
        "ucs_mode": ucs_mode,
        "ucs_profiles_tested": ucs_tested,
        "objective_components": "avg_reward + depth_bonus + safety_bonus + improvement",
        "timestamp": datetime.now().isoformat(),
        "total_trials": len(study.trials),
    }

    config_path = os.path.join(HPO_DIR, f"{output_name}.json")
    with open(config_path, "w") as f:
        json.dump(best_config, f, indent=2)

    # summary to wandb
    if use_wandb:
        import wandb
        wandb.log({
            "hpo/best_trial": best.number,
            "hpo/best_objective": best.value,
            "hpo/best_learning_rate": best.params["learning_rate"],
            "hpo/best_gamma": best.params["gamma"],
            "hpo/best_tau": best.params["tau"],
            "hpo/best_batch_size": best.params["batch_size"],
            "hpo/total_trials": len(study.trials),
        })
        artifact = wandb.Artifact("best_hpo_config", type="config")
        artifact.add_file(config_path)
        wandb.log_artifact(artifact)
        wandb.finish()

    print(f"\n{'=' * 60}")
    print(f"HPO COMPLETE!")
    print(f"{'=' * 60}")
    print(f"  Best trial: #{best.number}")
    print(f"  Best objective: {best.value:.2f}")
    print(f"  Best params:")
    for k, v in best.params.items():
        print(f"    {k}: {v}")
    print(f"\n  Config saved to: {config_path}")
    print(f"  Use: python train.py --hpo-config auto")

    return study


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optuna HPO for TQC Drilling")
    parser.add_argument("--n-trials", type=int, default=20,
                        help="Number of HPO trials (default: 20)")
    parser.add_argument("--episodes", type=int, default=N_EVAL_EPISODES_DEFAULT,
                        help=f"Episodes per trial (default: {N_EVAL_EPISODES_DEFAULT})")
    parser.add_argument("--study-name", type=str, default="tqc_drilling_hpo",
                        help="Optuna study name (for resuming)")
    parser.add_argument("--ucs-mode", type=str, default="cycle",
                        choices=["cycle", "baseline"],
                        help="UCS mode: 'baseline' (all UCS=1.0) or 'cycle' (diverse UCS)")
    parser.add_argument("--output-name", type=str, default="best_config",
                        help="Output config filename (without .json), e.g., 'best_config_learn'")
    parser.add_argument("--no-wandb", action="store_true",
                        help="Disable Weights & Biases logging")
    args = parser.parse_args()

    run_hpo(n_trials=args.n_trials, n_episodes=args.episodes,
            study_name=args.study_name, use_wandb=not args.no_wandb,
            ucs_mode=args.ucs_mode, output_name=args.output_name)
