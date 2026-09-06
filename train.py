"""train a TQC agent on the openlab drilling env. TQC from sb3-contrib.

Usage:
    python train.py                     # for default training
    python train.py --timesteps 50000   # custom total timesteps
    python train.py --no-wandb          # disable W&B, use TensorBoard only
    python train.py --ucs 1.3           # harder formation (UCS x1.3)
    python train.py --hpo-config path/to/best_config.json   # use HPO-tuned hyperparameters
    python train.py --hpo-config auto   # auto-detect hpo_results/best_config.json
"""
import sys
import os
import json
import argparse
from datetime import datetime

# our own modules and the vendored openlab first
_cwd = os.path.dirname(os.path.abspath(__file__))
_openlab_parent = os.path.join(_cwd, "openlab")
if _openlab_parent not in sys.path:
    sys.path.insert(0, _openlab_parent)
if _cwd not in sys.path:
    sys.path.insert(0, _cwd)

import numpy as np
from sb3_contrib import TQC
from stable_baselines3.common.callbacks import (
    CheckpointCallback,
    BaseCallback,
)
from stable_baselines3.common.monitor import Monitor

# importing the env also registers it with gymnasium
from drilling_env import DrillingEnv
import config as cfg


# replay buffer save/load next to the model

def save_with_buffer(model, path: str, verbose: bool = True):
    """Save model weights AND replay buffer together.

    SB3's .save() only stores network weights + optimizer state.
    The replay buffer must be saved separately for seamless resume.

    Files created:
        {path}.zip           — model weights (SB3 default)
        {path}_buffer.pkl    — replay buffer
    """
    model.save(path)
    buffer_path = f"{path}_buffer.pkl"
    model.save_replay_buffer(buffer_path)
    if verbose:
        buf_size = model.replay_buffer.size()
        buf_mb = os.path.getsize(buffer_path) / (1024 * 1024)
        print(f"  Saved model to {path}.zip")
        print(f"  Saved replay buffer to {buffer_path} ({buf_size} transitions, {buf_mb:.1f} MB)")


def load_with_buffer(path: str, env, tensorboard_log: str = None,
                     verbose: bool = True):
    """Load model weights AND replay buffer if available.

    Looks for:
        {path}.zip           — model weights (required)
        {path}_buffer.pkl    — replay buffer (optional, loaded if exists)

    Returns the loaded TQC model with buffer restored.
    """
    model = TQC.load(path, env=env, tensorboard_log=tensorboard_log)

    # buffer too, if its there
    buffer_path = f"{path}_buffer.pkl"
    # path may already end in .zip
    if path.endswith(".zip"):
        buffer_path = path.replace(".zip", "_buffer.pkl")

    if os.path.exists(buffer_path):
        model.load_replay_buffer(buffer_path)
        if verbose:
            buf_size = model.replay_buffer.size()
            print(f"  Replay buffer loaded from {buffer_path} ({buf_size} transitions)")
    else:
        if verbose:
            print(f"  No replay buffer found at {buffer_path} — starting with empty buffer")
            print(f"  (This is normal for models saved before buffer persistence was added)")

    return model


class ReplayBufferCheckpointCallback(BaseCallback):
    """Save replay buffer alongside each model checkpoint.

    Works in tandem with SB3's CheckpointCallback. When CheckpointCallback
    saves `tqc_drilling_2000_steps.zip`, this callback saves
    `tqc_drilling_2000_steps_buffer.pkl` at the same frequency.
    """

    def __init__(self, save_freq: int, save_path: str, name_prefix: str = "tqc_drilling",
                 verbose: int = 0):
        super().__init__(verbose)
        self.save_freq = save_freq
        self.save_path = save_path
        self.name_prefix = name_prefix

    def _on_step(self) -> bool:
        if self.num_timesteps % self.save_freq == 0:
            buffer_path = os.path.join(
                self.save_path,
                f"{self.name_prefix}_{self.num_timesteps}_steps_buffer.pkl"
            )
            self.model.save_replay_buffer(buffer_path)
            if self.verbose > 0:
                buf_size = self.model.replay_buffer.size()
                print(f"  [Checkpoint] Replay buffer saved ({buf_size} transitions)")
        return True


# wandb callback

class DrillingWandbCallback(BaseCallback):

    def __init__(self, use_wandb=True, verbose=0):
        super().__init__(verbose)
        self._use_wandb = use_wandb
        self._ep_rops = []
        self._ep_mses = []
        self._ep_perf_scores = []
        self._ep_safety_margins = []
        self._ep_stability_scores = []
        self._ep_ucs = 1.0
        self._ep_len = 0

    def _on_step(self):
        infos = self.locals.get("infos", [])
        for info in infos:
            step_log = {}

            # drilling
            if "rop" in info:
                step_log["drilling/rop_mm_s"] = info["rop"] * 1000
                self._ep_rops.append(info["rop"])
            if "rop_mh" in info:
                step_log["drilling/rop_m_h"] = info["rop_mh"]
            if "torque" in info:
                step_log["drilling/torque_Nm"] = info["torque"]
            if "torque_knm" in info:
                step_log["drilling/torque_kNm"] = info["torque_knm"]
            if "ecd_sg" in info:
                step_log["drilling/ecd_sg"] = info["ecd_sg"]
            if "spp_bar" in info:
                step_log["drilling/spp_bar"] = info["spp_bar"]
            if "bhp" in info:
                step_log["drilling/bhp_bar"] = info["bhp"] / 1e5
            if "bit_depth" in info:
                step_log["drilling/bit_depth_m"] = info["bit_depth"]
            if "depth_progress" in info:
                step_log["drilling/depth_progress_m"] = info["depth_progress"]
            if "flow_out_m3s" in info:
                step_log["drilling/flow_out_m3s"] = info["flow_out_m3s"]

            # mse
            if "mse_mpa" in info:
                step_log["drilling/mse_MPa"] = info["mse_mpa"]
                self._ep_mses.append(info["mse_mpa"])

            # the 3 levels
            if "performance_score" in info:
                step_log["eval/performance_score"] = info["performance_score"]
                self._ep_perf_scores.append(info["performance_score"])
            if "safety_margin" in info:
                step_log["eval/safety_margin"] = info["safety_margin"]
                self._ep_safety_margins.append(info["safety_margin"])
            if "stability_score" in info:
                step_log["eval/stability_score"] = info["stability_score"]
                self._ep_stability_scores.append(info["stability_score"])

            # stability
            if "ecd_std_sg" in info:
                step_log["stability/ecd_std_sg"] = info["ecd_std_sg"]
            if "spp_std_bar" in info:
                step_log["stability/spp_std_bar"] = info["spp_std_bar"]
            if "ecd_slope_sg_per_min" in info:
                step_log["stability/ecd_slope_sg_per_min"] = info["ecd_slope_sg_per_min"]

            # constraints
            if "all_safe" in info:
                step_log["safety/all_safe"] = float(info["all_safe"])
            if "safety_violations" in info:
                step_log["safety/violation_count"] = len(info["safety_violations"])

            # vibration
            if "torque_variance" in info:
                step_log["drilling/torque_variance"] = info["torque_variance"]
            if "vibration_penalty" in info:
                step_log["drilling/vibration_penalty"] = info["vibration_penalty"]

            # actions, engineering units
            if "action_engineering" in info:
                ae = info["action_engineering"]
                step_log["actions/rpm"] = ae.get("rpm", 0)
                step_log["actions/wob_tonnes"] = ae.get("wob_tonnes", 0)
                step_log["actions/flow_lpm"] = ae.get("flow_lpm", 0)

            # reward parts
            if "reward_breakdown" in info:
                for k, v in info["reward_breakdown"].items():
                    step_log[f"reward/{k}"] = v
                    self.logger.record(f"reward/{k}", v)

            # throttled. every step and wandb becomes the bottleneck instead of the api
            if self._use_wandb and step_log and self.num_timesteps % cfg.WANDB_STEP_LOG_INTERVAL == 0:
                import wandb
                wandb.log(step_log)

            # same to tensorboard through the sb3 logger
            for key in ["drilling/rop_mm_s", "drilling/torque_kNm",
                        "drilling/ecd_sg", "drilling/spp_bar",
                        "drilling/mse_MPa", "drilling/depth_progress_m",
                        "eval/performance_score", "eval/safety_margin",
                        "eval/stability_score"]:
                if key in step_log:
                    self.logger.record(key, step_log[key])

            self._ep_len += 1

            # episode summary
            if "episode" in info:
                ep_log = {}
                if self._ep_rops:
                    avg_rop = np.mean(self._ep_rops) * 1000
                    max_rop = np.max(self._ep_rops) * 1000
                    ep_log["episode/avg_rop_mm_s"] = avg_rop
                    ep_log["episode/max_rop_mm_s"] = max_rop
                    self.logger.record("episode/avg_rop_mm_s", avg_rop)
                if self._ep_mses:
                    ep_log["episode/avg_mse_MPa"] = np.mean(self._ep_mses)
                    ep_log["episode/min_mse_MPa"] = np.min(self._ep_mses)
                if self._ep_perf_scores:
                    ep_log["episode/avg_performance_score"] = np.mean(self._ep_perf_scores)
                if self._ep_safety_margins:
                    ep_log["episode/avg_safety_margin"] = np.mean(self._ep_safety_margins)
                    ep_log["episode/min_safety_margin"] = np.min(self._ep_safety_margins)
                if self._ep_stability_scores:
                    ep_log["episode/avg_stability_score"] = np.mean(self._ep_stability_scores)
                if "target_reached" in info:
                    ep_log["episode/target_reached"] = float(info["target_reached"])
                if "depth_progress" in info:
                    ep_log["episode/final_depth_progress_m"] = info["depth_progress"]
                ep_log["episode/length"] = self._ep_len

                if self._use_wandb and ep_log:
                    import wandb
                    wandb.log(ep_log)

                # reset for the next episode
                self._ep_rops = []
                self._ep_mses = []
                self._ep_perf_scores = []
                self._ep_safety_margins = []
                self._ep_stability_scores = []
                self._ep_len = 0

        return True


class DrillingEvalCallback(BaseCallback):
    """Periodically evaluate the agent deterministically on fixed formations.

    Every `eval_freq` training steps:
      1. Pauses training
      2. Creates temporary DrillingEnv(s) with fixed UCS values
      3. Runs the current policy WITHOUT exploration noise (deterministic=True)
      4. Logs mean reward, depth, performance score, safety margin
      5. Resumes training

    This shows true policy quality, separate from exploration noise.
    """

    def __init__(self, eval_freq: int = None, eval_ucs_values: list = None,
                 eval_max_steps: int = None, use_wandb: bool = True,
                 verbose: int = 0):
        super().__init__(verbose)
        self._eval_freq = eval_freq or cfg.EVAL_FREQ_STEPS
        self._eval_ucs = eval_ucs_values or cfg.EVAL_UCS_VALUES
        self._eval_max_steps = eval_max_steps or cfg.EVAL_MAX_STEPS
        self._use_wandb = use_wandb
        self._eval_count = 0

    def _on_step(self) -> bool:
        if self.num_timesteps % self._eval_freq == 0 and self.num_timesteps > 0:
            self._run_evaluation()
        return True

    def _run_evaluation(self):
        """Run deterministic evaluation on each fixed UCS formation."""
        self._eval_count += 1
        print(f"\n{'='*50}")
        print(f"[EVAL #{self._eval_count}] Step {self.num_timesteps} — "
              f"Deterministic evaluation on {len(self._eval_ucs)} formations")
        print(f"{'='*50}")

        all_rewards = []
        all_depths = []
        all_perf = []
        all_safety = []

        for ucs_val in self._eval_ucs:
            try:
                result = self._eval_one_formation(ucs_val)
                all_rewards.append(result["reward"])
                all_depths.append(result["depth"])
                all_perf.append(result["perf_score"])
                all_safety.append(result["safety_margin"])

                target_str = "TARGET!" if result["target"] else f"{result['depth']:.1f}m"
                print(f"  UCS={ucs_val:.1f}: reward={result['reward']:.1f}, "
                      f"{target_str}, perf={result['perf_score']:.3f}, "
                      f"safety={result['safety_margin']:.3f}")

            except Exception as e:
                print(f"  UCS={ucs_val:.1f}: FAILED — {e}")

        if all_rewards:
            summary = {
                "eval_det/mean_reward": np.mean(all_rewards),
                "eval_det/mean_depth": np.mean(all_depths),
                "eval_det/mean_perf_score": np.mean(all_perf),
                "eval_det/mean_safety_margin": np.mean(all_safety),
                "eval_det/min_safety_margin": np.min(all_safety),
                "eval_det/eval_step": self.num_timesteps,
            }

            # tensorboard
            for k, v in summary.items():
                self.logger.record(k, v)

            # wandb
            if self._use_wandb:
                import wandb
                wandb.log(summary)

            print(f"  → Mean: reward={np.mean(all_rewards):.1f}, "
                  f"depth={np.mean(all_depths):.1f}m, "
                  f"perf={np.mean(all_perf):.3f}")

        print(f"{'='*50}\n")

    def _eval_one_formation(self, ucs_val: float) -> dict:
        """Run one deterministic episode on a specific UCS formation."""
        eval_env = DrillingEnv(
            ucs_multiplier=ucs_val,
            max_steps=self._eval_max_steps,
            cleanup_on_reset=False,
        )

        obs, info = eval_env.reset()
        total_reward = 0.0
        perf_scores = []
        safety_margins = []
        depth = 0.0
        target = False

        for _ in range(self._eval_max_steps):
            action, _ = self.model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = eval_env.step(action)
            total_reward += reward

            if "performance_score" in info:
                perf_scores.append(info["performance_score"])
            if "safety_margin" in info:
                safety_margins.append(info["safety_margin"])
            if "depth_progress" in info:
                depth = info["depth_progress"]
            if "target_reached" in info:
                target = info["target_reached"]

            if terminated or truncated:
                break

        eval_env.close()

        return {
            "reward": total_reward,
            "depth": depth,
            "target": target,
            "perf_score": np.mean(perf_scores) if perf_scores else 0.0,
            "safety_margin": np.mean(safety_margins) if safety_margins else 0.0,
        }


def make_env(ucs_multiplier=None, ucs_random_mode=None, base_config_name=None,
             ucs_random_min=None, ucs_random_max=None, use_detournay_rop=None,
             use_revised_reward=None):
    """Create and wrap the drilling environment."""
    env = DrillingEnv(
        ucs_multiplier=ucs_multiplier,
        ucs_random_mode=ucs_random_mode,
        max_steps=cfg.TRAIN_MAX_EPISODE_STEPS,
        base_config_name=base_config_name,
        ucs_random_min=ucs_random_min,
        ucs_random_max=ucs_random_max,
        use_detournay_rop=use_detournay_rop,
        use_revised_reward=use_revised_reward,
    )
    env = Monitor(env)
    return env


def load_hpo_config(hpo_config_path: str) -> dict:
    """Load HPO best params from a JSON file. Returns only the tunable params."""
    if hpo_config_path == "auto":
        auto_path = os.path.join(_cwd, "hpo_results", "best_config.json")
        if os.path.exists(auto_path):
            hpo_config_path = auto_path
        else:
            print(f"[INFO] No HPO config found at {auto_path}, using defaults.")
            return {}

    if not os.path.exists(hpo_config_path):
        print(f"[WARNING] HPO config not found: {hpo_config_path}, fix path. Now using defaults.")
        return {}

    with open(hpo_config_path) as f:
        data = json.load(f)

    params = data.get("best_params", {})
    print(f"[HPO] Loaded config from {hpo_config_path}")
    print(f"[HPO]   Trial #{data.get('best_trial_number', '?')}, "
          f"reward={data.get('best_value', '?')}")
    for k, v in params.items():
        print(f"[HPO]   {k}: {v}")

    return params


def train(total_timesteps: int, log_dir: str, use_wandb: bool = True,
          ucs_multiplier: float = None, ucs_random_mode: str = None,
          hpo_overrides: dict = None, resume_path: str = None,
          eval_freq: int = None, base_config_name: str = None,
          ucs_random_min: float = None, ucs_random_max: float = None,
          load_buffer: bool = True, use_detournay_rop: bool = None,
          use_revised_reward: bool = None):
    """Train a TQC agent."""
    print(f"Starting TQC training for {total_timesteps} timesteps")
    print(f"Logs: {log_dir}")
    print(f"W&B: {'enabled' if use_wandb else 'disabled'}")
    if resume_path:
        print(f"Resuming from: {resume_path}  (buffer: {'loaded' if load_buffer else 'FRESH / weights-only'})")
    print(f"Base formation: {base_config_name or cfg.BASE_CONFIG_NAME or cfg.CONFIG_NAME}")
    print(f"Reward shaping: progress_weight={cfg.DEPTH_PROGRESS_WEIGHT}, "
          f"time_penalty={cfg.TIME_STEP_PENALTY}, completion_bonus={cfg.DEPTH_COMPLETION_BONUS}")
    if ucs_multiplier:
        print(f"UCS multiplier: {ucs_multiplier}")
    if ucs_random_mode:
        print(f"UCS domain randomization: {ucs_random_mode}")
        if ucs_random_mode == 'continuous':
            _lo = ucs_random_min if ucs_random_min is not None else cfg.UCS_RANDOM_MIN
            _hi = ucs_random_max if ucs_random_max is not None else cfg.UCS_RANDOM_MAX
            print(f"  Range: [{_lo}, {_hi}]")
        elif ucs_random_mode == 'profiles':
            print(f"  Profiles: {cfg.UCS_PROFILES}")
        elif ucs_random_mode == 'curriculum':
            print(f"  Curriculum stages:")
            for start_ep, ucs_min, ucs_max in cfg.CURRICULUM_STAGES:
                if ucs_min == ucs_max:
                    print(f"    Ep {start_ep}+: UCS = {ucs_min:.1f} (baseline only)")
                else:
                    print(f"    Ep {start_ep}+: UCS ∈ [{ucs_min:.1f}, {ucs_max:.1f}]")
    if eval_freq:
        print(f"Eval callback: every {eval_freq} steps on UCS={cfg.EVAL_UCS_VALUES}")

    # default hps, the one place they live
    hyperparams = {
        "algorithm": "TQC",
        "total_timesteps": total_timesteps,
        "learning_rate": 3e-4,
        "buffer_size": 1_000_000,
        "learning_starts": 5000,
        "batch_size": 256,
        "tau": 0.005,
        "gamma": 0.99,
        "n_quantiles": 25,
        "n_critics": 2,
        "top_quantiles_to_drop": 2,
        "net_arch": [256, 256],
        "performance_weights": cfg.PERFORMANCE_WEIGHTS,
        "reward_priority": "Safety > Stability > Performance",
        "safety_margin_weight": cfg.SAFETY_MARGIN_WEIGHT,
        "stability_bonus_weight": cfg.STABILITY_BONUS_WEIGHT,
        "performance_weight": cfg.PERFORMANCE_WEIGHT,
        "safety_violation_penalty": cfg.SAFETY_VIOLATION_PENALTY,
        "transient_mechanical_model": cfg.USE_TRANSIENT_MECHANICAL,
        "step_duration_s": cfg.STEP_DURATION,
        "train_max_episode_steps": cfg.TRAIN_MAX_EPISODE_STEPS,
        "warmup_steps": cfg.WARMUP_STEPS,
        "target_depth": cfg.TARGET_BIT_DEPTH,
        "initial_depth": cfg.INITIAL_BIT_DEPTH,
        "bit_diameter_inches": cfg.BIT_DIAMETER_INCHES,
        "mse_reference_MPa": cfg.MSE_REF_PA / 1e6,
        "rop_ref_m_h": cfg.rop_ms_to_mh(cfg.ROP_REF),
        "ucs_multiplier": ucs_multiplier or 1.0,
        "ucs_random_mode": ucs_random_mode or "disabled",
        "rpm_range": f"{cfg.RPM_MIN}-{cfg.RPM_MAX} rpm",
        "wob_range": f"{cfg.WOB_MIN}-{cfg.WOB_MAX} tonnes",
        "flow_range": f"{cfg.FLOW_RATE_MIN}-{cfg.FLOW_RATE_MAX} L/min",
    }

    # hpo overrides
    if hpo_overrides:
        hyperparams.update(hpo_overrides)
        print(f"[HPO] Overridden params: {list(hpo_overrides.keys())}")

    # wandb
    if use_wandb:
        import wandb
        wandb.init(
            project="digi-drilling",
            config=hyperparams,
            sync_tensorboard=True,
            name=f"tqc_{datetime.now().strftime('%m%d_%H%M')}",
            save_code=True,
        )

    env = make_env(ucs_multiplier=ucs_multiplier, ucs_random_mode=ucs_random_mode,
                   base_config_name=base_config_name,
                   ucs_random_min=ucs_random_min, ucs_random_max=ucs_random_max,
                   use_detournay_rop=use_detournay_rop,
                   use_revised_reward=use_revised_reward)

    if resume_path:
        # resume. load_buffer=False means weights only, fresh buffer. thats the one
        # to use when the reward changed, a buffer saved under the old reward has
        # stale rewards in it and they poison the critic
        print(f"\nLoading pre-trained model from: {resume_path}")
        if load_buffer:
            model = load_with_buffer(resume_path, env=env, tensorboard_log=log_dir)
        else:
            from sb3_contrib import TQC as _TQC
            model = _TQC.load(resume_path, env=env, tensorboard_log=log_dir)
            print("  Weights-only resume (fresh replay buffer; reward change safe)")
        # push every hpo override into the loaded model, the hardening stage needs that
        if hpo_overrides:
            if "learning_rate" in hpo_overrides:
                model.learning_rate = hpo_overrides["learning_rate"]
                model._setup_lr_schedule()  # rebuild schedule so optimizer actually uses new LR
            if "tau" in hpo_overrides:
                model.tau = hpo_overrides["tau"]
            if "gamma" in hpo_overrides:
                model.gamma = hpo_overrides["gamma"]
            if "batch_size" in hpo_overrides:
                model.batch_size = hpo_overrides["batch_size"]
            print(f"  HPO overrides applied: {list(hpo_overrides.keys())}")
        print(f"  Resume ready! Buffer size: {model.replay_buffer.size()}")
    else:
        # fresh model
        model = TQC(
            "MlpPolicy",
            env,
            learning_rate=hyperparams["learning_rate"],
            buffer_size=hyperparams["buffer_size"],
            learning_starts=hyperparams["learning_starts"],
            batch_size=hyperparams["batch_size"],
            tau=hyperparams["tau"],
            gamma=hyperparams["gamma"],
            top_quantiles_to_drop_per_net=hyperparams["top_quantiles_to_drop"],
            policy_kwargs=dict(
                net_arch=hyperparams["net_arch"],
                n_quantiles=hyperparams["n_quantiles"],
                n_critics=hyperparams["n_critics"],
            ),
            verbose=1,
            tensorboard_log=log_dir,
        )

    checkpoint_cb = CheckpointCallback(
        save_freq=20000,
        save_path=os.path.join(log_dir, "checkpoints"),
        name_prefix="tqc_drilling",
    )

    # buffer goes with every checkpoint
    buffer_checkpoint_cb = ReplayBufferCheckpointCallback(
        save_freq=20000,
        save_path=os.path.join(log_dir, "checkpoints"),
        name_prefix="tqc_drilling",
    )

    wandb_drilling_cb = DrillingWandbCallback(use_wandb=use_wandb)

    print("\nModel architecture:")
    print(f"  Policy: MlpPolicy [256, 256]")
    print(f"  Algorithm: TQC (25 quantiles, 2 critics, drop 2)")
    print(f"  Observation dim: {env.observation_space.shape}")
    print(f"  Action dim: {env.action_space.shape}")
    print(f"  Action range: {env.action_space.low} to {env.action_space.high}")
    print(f"\nSimulation config:")
    print(f"  Transient T&D model: {cfg.USE_TRANSIENT_MECHANICAL}")
    print(f"  Step duration: {cfg.STEP_DURATION}s")
    print(f"  Train max episode steps: {cfg.TRAIN_MAX_EPISODE_STEPS}")
    print(f"  W&B step log interval: {cfg.WANDB_STEP_LOG_INTERVAL}")
    print(f"  Warmup steps: {cfg.WARMUP_STEPS}")
    print(f"\ninfo.md aligned config:")
    print(f"  RPM: {cfg.RPM_MIN}-{cfg.RPM_MAX} rpm")
    print(f"  WOB: {cfg.WOB_MIN}-{cfg.WOB_MAX} tonnes")
    print(f"  Flow: {cfg.FLOW_RATE_MIN}-{cfg.FLOW_RATE_MAX} L/min")
    print(f"  Reward priority: Safety ({cfg.SAFETY_MARGIN_WEIGHT}) > "
          f"Stability ({cfg.STABILITY_BONUS_WEIGHT}) > "
          f"Performance ({cfg.PERFORMANCE_WEIGHT})")
    print(f"  Safety violation penalty: {cfg.SAFETY_VIOLATION_PENALTY}")

    callbacks = [checkpoint_cb, buffer_checkpoint_cb, wandb_drilling_cb]

    # deterministic eval every so often
    if eval_freq:
        eval_cb = DrillingEvalCallback(
            eval_freq=eval_freq,
            use_wandb=use_wandb,
        )
        callbacks.append(eval_cb)
        print(f"  Eval callback: every {eval_freq} steps")

    # wandb keeps the model artifact
    if use_wandb:
        from wandb.integration.sb3 import WandbCallback
        wandb_sb3_cb = WandbCallback(
            model_save_path=os.path.join(log_dir, "wandb_models"),
            verbose=1,
        )
        callbacks.append(wandb_sb3_cb)

    try:
        model.learn(
            total_timesteps=total_timesteps,
            callback=callbacks,
            progress_bar=True,
            log_interval=1,
        )
    except KeyboardInterrupt:
        print("\nTraining interrupted by user.")
    finally:
        # final model + buffer
        final_path = os.path.join(log_dir, "tqc_drilling_final")
        print(f"\nSaving model + replay buffer...")
        save_with_buffer(model, final_path)
        env.close()
        if use_wandb:
            import wandb
            wandb.finish()

    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train TQC on OpenLab Drilling")
    parser.add_argument("--timesteps", type=int, default=100000,
                        help="Total training timesteps (default: 100000)")
    parser.add_argument("--log-dir", type=str, default=None,
                        help="Tensorboard log directory")
    parser.add_argument("--no-wandb", action="store_true",
                        help="Disable Weights & Biases logging")
    parser.add_argument("--ucs", type=float, default=None,
                        help="UCS formation strength multiplier (e.g., 1.3 for 30%% harder)")
    parser.add_argument("--ucs-random", type=str, default=None,
                        choices=["profiles", "continuous", "curriculum"],
                        help="UCS randomization mode: 'profiles', 'continuous', or 'curriculum'")
    parser.add_argument("--resume", type=str, default=None,
                        help="Path to a saved model (.zip) to resume training from")
    parser.add_argument("--eval-freq", type=int, default=None,
                        help=f"Deterministic eval every N steps (default: disabled, suggested: {cfg.EVAL_FREQ_STEPS})")
    parser.add_argument("--hpo-config", type=str, default=None,
                        help="Path to HPO best_config.json, or 'auto' to find it automatically")
    parser.add_argument("--base-config", type=str, default=None,
                        help="Override base formation config (e.g. 'drill_realistic' for 50-70 MPa). "
                             "Default: config.py CONFIG_NAME.")
    parser.add_argument("--no-buffer", action="store_true",
                        help="Weights-only resume: do NOT load the saved replay buffer "
                             "(use a fresh buffer). Required when the reward function changed.")
    parser.add_argument("--ucs-min", type=float, default=None,
                        help="Min UCS multiplier for --ucs-random continuous (default: config.py).")
    parser.add_argument("--ucs-max", type=float, default=None,
                        help="Max UCS multiplier for --ucs-random continuous (default: config.py).")
    parser.add_argument("--revised-reward", action="store_true",
                        help="Use the gated-torque revised reward (PI request)")
    parser.add_argument("--use-detournay", action="store_true",
                        help="Train under the Detournay ROP model (realistic vibration). "
                             "Default: config.py USE_DETOURNAY_ROP (False = MSE model).")
    args = parser.parse_args()

    if args.log_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.log_dir = os.path.join(_cwd, "logs", f"tqc_{timestamp}")

    # hpo config
    hpo_overrides = {}
    if args.hpo_config:
        hpo_overrides = load_hpo_config(args.hpo_config)

    os.makedirs(args.log_dir, exist_ok=True)
    train(args.timesteps, args.log_dir, use_wandb=not args.no_wandb,
          ucs_multiplier=args.ucs, ucs_random_mode=args.ucs_random,
          hpo_overrides=hpo_overrides, resume_path=args.resume,
          eval_freq=args.eval_freq, base_config_name=args.base_config,
          ucs_random_min=args.ucs_min, ucs_random_max=args.ucs_max,
          load_buffer=not args.no_buffer,
          use_detournay_rop=(True if args.use_detournay else None),
          use_revised_reward=(True if args.revised_reward else None))
