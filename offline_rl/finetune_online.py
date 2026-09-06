"""Fine-tune the offline-pretrained TD3+BC policy online on OpenLab.

The BC term only makes sense against a fixed dataset, so the weights go into
a plain TD3 first: same architecture, copy the policy, both Q functions and
the optimizers. TD3+BC is just TD3 with one extra actor loss term, so nothing
is lost in the copy. The online buffer starts out filled with the
positive-return offline episodes, so the critic has something to train on
from the first step. Then fine-tune with small exploration noise and a low
learning rate.

Every env step is one simulator API step, so keep --steps small.

  python offline_rl/finetune_online.py \
      --policy offline_rl/models/td3bc_posret_200000/policy.d3 --steps 50000
"""
import os, sys, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "openlab"))
sys.path.insert(0, ROOT)
import config as cfg
from drilling_env import DrillingEnv

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "dataset", "digi_drilling_v1.h5")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True, help="pretrained TD3+BC policy.d3")
    ap.add_argument("--steps", type=int, default=50_000, help="online env steps")
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--noise", type=float, default=0.1)
    ap.add_argument("--buffer-limit", type=int, default=250_000)
    ap.add_argument("--preload-min-return", type=float, default=0.0)
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    import numpy as np
    import d3rlpy
    d3rlpy.seed(7)
    device = "cuda:0" if args.gpu else "cpu:0"

    # same env setting the dataset was collected in
    env = DrillingEnv(ucs_random_mode="continuous", ucs_random_min=0.2,
                      ucs_random_max=1.0, base_config_name="drill_realistic",
                      use_detournay_rop=True, max_steps=cfg.TRAIN_MAX_EPISODE_STEPS)

    # hand off to plain TD3
    td3bc = d3rlpy.load_learnable(args.policy, device=device)
    td3 = d3rlpy.algos.TD3Config(
        batch_size=256,
        actor_learning_rate=args.lr,
        critic_learning_rate=args.lr,
    ).create(device=device)
    td3.build_with_env(env)
    td3.copy_policy_from(td3bc)
    td3.copy_q_function_from(td3bc)
    try:
        td3.copy_policy_optim_from(td3bc)
        td3.copy_q_function_optim_from(td3bc)
    except Exception as e:
        print(f"[note] optimizer copy skipped ({e}); fresh optimizers used")
    print("TD3 handoff complete (policy + Q-functions copied from TD3+BC)")

    # preload the online buffer with the good offline episodes
    with open(DATASET, "rb") as f:
        offline = d3rlpy.dataset.ReplayBuffer.load(f, d3rlpy.dataset.InfiniteBuffer())
    keep = [e for e in offline.episodes
            if float(np.sum(e.rewards)) > args.preload_min_return]
    # d3rlpy's default cache (10k) is smaller than our 15k episode cap and
    # overflows the writer mid-episode. size it to the cap plus some margin
    cache = cfg.TRAIN_MAX_EPISODE_STEPS + 1000
    buffer = d3rlpy.dataset.ReplayBuffer(
        d3rlpy.dataset.FIFOBuffer(limit=args.buffer_limit),
        episodes=keep, env=env, cache_size=cache)
    print(f"online buffer preloaded: {buffer.transition_count} transitions "
          f"from {len(keep)} positive-return episodes (limit {args.buffer_limit})")

    # NormalNoise moved between d3rlpy versions, hence the fallback
    try:
        explorer = d3rlpy.algos.NormalNoise(mean=0.0, std=args.noise)
    except AttributeError:
        from d3rlpy.algos import NormalNoise
        explorer = NormalNoise(mean=0.0, std=args.noise)

    out = args.out or os.path.join(HERE, "models", "td3_finetuned")
    os.makedirs(out, exist_ok=True)

    td3.fit_online(
        env,
        buffer,
        explorer=explorer,
        n_steps=args.steps,
        n_steps_per_epoch=10_000,
        update_start_step=2_000,
        experiment_name="digi_td3_finetune",
        with_timestamp=False,
        logger_adapter=d3rlpy.logging.FileAdapterFactory(root_dir=os.path.join(out, "logs")),
        save_interval=1,  # every epoch, in case the job dies
    )
    td3.save(os.path.join(out, "policy_finetuned.d3"))
    print("saved:", os.path.join(out, "policy_finetuned.d3"))


if __name__ == "__main__":
    main()
