"""offline pretraining on the dataset, no simulator needed.

IQL by default, CQL or TD3+BC with --algo. saves the policy for the online
eval and fine tuning.

Usage:
  python offline_rl/pretrain.py --algo iql --steps 200000 --gpu
  python offline_rl/pretrain.py --algo td3bc --steps 200000
"""
import os, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "dataset", "digi_drilling_v1.h5")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--algo", choices=["iql", "cql", "td3bc"], default="iql")
    ap.add_argument("--steps", type=int, default=200_000, help="gradient steps")
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--top-k", type=int, default=None,
                    help="Keep only the K highest-return episodes "
                         "(WARNING: return is confounded with formation hardness; "
                         "prefer --min-return for diversity-preserving filtering)")
    ap.add_argument("--min-return", type=float, default=None,
                    help="Keep only episodes with return above this threshold "
                         "(e.g. 0 drops the early pathological episodes while "
                         "preserving full UCS coverage)")
    args = ap.parse_args()

    import d3rlpy
    d3rlpy.seed(42)

    with open(DATASET, "rb") as f:
        dataset = d3rlpy.dataset.ReplayBuffer.load(f, d3rlpy.dataset.InfiniteBuffer())
    print(f"dataset: {dataset.transition_count} transitions, "
          f"{len(dataset.episodes)} episodes")

    if args.top_k or args.min_return is not None:
        import numpy as np
        eps = sorted(dataset.episodes, key=lambda e: -float(np.sum(e.rewards)))
        if args.min_return is not None:
            keep = [e for e in eps if float(np.sum(e.rewards)) > args.min_return]
            tag = f"return>{args.min_return}"
        else:
            keep = eps[:args.top_k]
            tag = f"top-{args.top_k}"
        dataset = d3rlpy.dataset.ReplayBuffer(
            d3rlpy.dataset.InfiniteBuffer(), episodes=keep)
        print(f"filtered ({tag}): {len(keep)} episodes, "
              f"{dataset.transition_count} transitions, "
              f"min kept return {float(np.sum(keep[-1].rewards)):.0f}")

    device = "cuda:0" if args.gpu else "cpu:0"
    if args.algo == "iql":
        algo = d3rlpy.algos.IQLConfig(batch_size=args.batch).create(device=device)
    elif args.algo == "cql":
        algo = d3rlpy.algos.CQLConfig(batch_size=args.batch).create(device=device)
    else:
        algo = d3rlpy.algos.TD3PlusBCConfig(batch_size=args.batch).create(device=device)

    out = args.out or os.path.join(HERE, "models", f"{args.algo}_{args.steps // 1000}k")
    os.makedirs(out, exist_ok=True)

    algo.fit(
        dataset,
        n_steps=args.steps,
        n_steps_per_epoch=10_000,
        experiment_name=f"digi_{args.algo}",
        with_timestamp=False,
        logger_adapter=d3rlpy.logging.FileAdapterFactory(root_dir=os.path.join(out, "logs")),
    )
    algo.save(os.path.join(out, "policy.d3"))
    print("saved:", os.path.join(out, "policy.d3"))


if __name__ == "__main__":
    main()
