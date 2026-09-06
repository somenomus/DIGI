"""Build the digi-drilling-v1 dataset from the SB3 replay buffer.

Reads the completion-shaped fine-tune buffer (a pickled SB3 ReplayBuffer) and
writes three files into dataset/: the d3rlpy .h5, a plain .npz, and the
metadata json with the per-episode table.

Two things about that buffer. Only the first `pos` entries are real, it never
wrapped. And training ran as chained slurm jobs, so a crash and resume can glue
two episode fragments together with no done flag in between. We catch those by
comparing next_obs[i] with obs[i+1] and mark them as timeouts, so no bogus
(s, s') pair ends up in the release. The UCS multiplier per episode is scraped
from the job logs ("Ep N: UCS=x.xx"), in job order.

Needs the original buffer pickle and the slurm logs, neither of which is in
the repo. Kept here for provenance.
"""
import os, sys, json, glob, re, pickle
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config as cfg

BUFFER = os.path.join(ROOT, "logs/step6_realistic_finetune_j5_20260616-125910/tqc_drilling_final_buffer.pkl")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
os.makedirs(OUT, exist_ok=True)
NAME = "digi_drilling_v1"


def load_buffer(path):
    with open(path, "rb") as f:
        buf = pickle.load(f)
    n = buf.pos if not buf.full else buf.buffer_size
    obs = buf.observations[:n, 0].astype(np.float32)
    nxt = buf.next_observations[:n, 0].astype(np.float32)
    act = buf.actions[:n, 0].astype(np.float32)
    rew = buf.rewards[:n, 0].astype(np.float32)
    done = buf.dones[:n, 0].astype(bool)
    tout = buf.timeouts[:n, 0].astype(bool)
    return obs, nxt, act, rew, done, tout


def find_discontinuities(obs, nxt, done):
    """Crash/resume glue points: next_obs[i] != obs[i+1] with no done at i."""
    mismatch = ~np.all(np.isclose(nxt[:-1], obs[1:], atol=1e-6), axis=1)
    glue = np.where(mismatch & ~done[:-1])[0]
    return glue


def ucs_from_logs():
    """Per-episode UCS multipliers in chronological training order."""
    logs = sorted(glob.glob(os.path.join(ROOT, "logs/slurm/step6_realistic_finetune/*.log")))
    ucs = []
    for lg in logs:
        txt = open(lg, errors="ignore").read()
        ucs += [float(x) for x in re.findall(r"Ep \d+: continuous.*?UCS=([\d.]+)|Ep \d+: UCS=([\d.]+)", txt.replace("→", " "))
                and [float(a or b) for a, b in re.findall(r"Ep \d+:.*?UCS=([\d.]+)()", txt)] or []]
        # simpler robust pass:
    ucs = []
    for lg in logs:
        for m in re.finditer(r"Ep \d+:.*?UCS=([\d.]+)", open(lg, errors="ignore").read()):
            ucs.append(float(m.group(1)))
    return ucs


def main():
    obs, nxt, act, rew, done, tout = load_buffer(BUFFER)
    n = len(obs)
    glue = find_discontinuities(obs, nxt, done)
    print(f"transitions: {n} | episode ends (dones): {int(done.sum())} | "
          f"true terminations: {int((done & ~tout).sum())} | glue points: {len(glue)} at {glue.tolist()}")

    # terminal = reached target depth. everything else that ends an episode
    # (step cap, glue point) is a timeout
    terminals = (done & ~tout).astype(np.float32)
    timeouts = tout.copy()
    timeouts[glue] = True
    # the buffer may end mid-episode, close it
    if not (terminals[-1] or timeouts[-1]):
        timeouts[-1] = True

    # plain npz, readable without d3rlpy
    np.savez_compressed(os.path.join(OUT, f"{NAME}.npz"),
                        observations=obs, actions=act, rewards=rew,
                        terminals=terminals, timeouts=timeouts.astype(np.float32))

    # d3rlpy format
    import d3rlpy
    dataset = d3rlpy.dataset.MDPDataset(
        observations=obs, actions=act, rewards=rew,
        terminals=terminals, timeouts=timeouts,
        action_space=d3rlpy.constants.ActionSpace.CONTINUOUS,
    )
    eps = dataset.episodes
    with open(os.path.join(OUT, f"{NAME}.h5"), "w+b") as f:
        dataset.dump(f)

    # data card
    ucs = ucs_from_logs()
    ep_table = []
    for i, ep in enumerate(eps):
        ep_table.append({
            "episode": i,
            "length": int(ep.size()),
            "return": float(np.sum(ep.rewards)),
            "terminated": bool(ep.terminated),
            "ucs_multiplier": ucs[i] if i < len(ucs) else None,
        })
    meta = {
        "name": NAME,
        "description": "Offline RL dataset for autonomous drilling ROP control, "
                       "collected during TQC fine-tuning on the OpenLab simulator "
                       "(transient torque-and-drag, Detournay bit-rock model) on a "
                       "realistic layered formation (50-70 MPa UCS) with per-episode "
                       "strength multiplier ~ U[0.2, 1.0].",
        "num_transitions": int(n),
        "num_episodes": len(eps),
        "observation_space": {
            "dim": 15,
            "components": ["10 normalized simulator channels (ROP, ToS velocity, SPP, "
                            "surface torque, downhole pressure, downhole ECD, flow out, "
                            "hook load, bit depth, connection)",
                           "2 ECD stability features (rolling std, trend slope)",
                           "3 previous actions"],
        },
        "action_space": {
            "dim": 3, "range": "[-1, 1]",
            "mapping": {"a0": "RPM in [80, 120] rpm", "a1": "WOB in [8, 12] t",
                        "a2": "flow in [1800, 2200] L/min"},
            "note": "WOB delivered via simulator auto-driller",
        },
        "reward": {
            "type": "three-tier (safety > stability > performance) + completion shaping",
            "shaping": {"depth_progress_weight_per_m": cfg.DEPTH_PROGRESS_WEIGHT,
                        "time_step_penalty": cfg.TIME_STEP_PENALTY,
                        "completion_bonus": cfg.DEPTH_COMPLETION_BONUS},
        },
        "environment": {
            "simulator": "OpenLab (live.openlab.app)",
            "mechanical_model": "transient torque-and-drag, 0.1 s step",
            "bit_rock_model": "Detournay (UseDetournayROPModel=True)",
            "formation": "drill_realistic: 50/57/63/70/63/57 MPa at MD 2497/2502/2503/2506/2507/2508 m, "
                         "scaled per episode by multiplier in [0.2, 1.0]",
            "section": "2497 m -> 2508 m (11 m)",
            "warmup": "300 neutral-setpoint steps per episode (included in data? NO - "
                      "buffer records policy-controlled steps only)",
        },
        "provenance": {
            "source_buffer": os.path.relpath(BUFFER, ROOT),
            "collection_policy": "TQC training policy (exploratory, improving over time)",
            "glue_points_marked_as_timeouts": [int(g) for g in glue],
            "notes": "Transitions collected across chained training jobs; crash/resume "
                     "points are marked as episode breaks so all (s,a,r,s') pairs are valid.",
        },
        "episodes": ep_table,
    }
    with open(os.path.join(OUT, f"{NAME}_meta.json"), "w") as f:
        json.dump(meta, f, indent=1)

    print(f"episodes in MDPDataset: {len(eps)}")
    print(f"returns: min {min(e['return'] for e in ep_table):.0f} "
          f"max {max(e['return'] for e in ep_table):.0f}")
    print(f"UCS metadata recovered for {sum(1 for e in ep_table if e['ucs_multiplier'] is not None)}"
          f"/{len(eps)} episodes")
    print("wrote:", os.listdir(OUT))


if __name__ == "__main__":
    main()
