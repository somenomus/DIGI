"""MSE vs Detournay vibration comparison, from sims already stored on openlab.

no new simulation. pulls SurfaceTorque and BitDepth from sims that already
ran, and reading results doesnt cost api steps, only simulating does.

vibration = 10 step rolling variance of SurfaceTorque, same as the env
(cfg.TORQUE_HISTORY_WINDOW=10, threshold 1e5 (Nm)^2).

which sims (from the sims listing, 2026-05-28):
  Detournay eval, may 28:  UCS 0.2/0.3/0.4/0.5
  MSE eval, may 17:        UCS 0.5/0.7/1.0/1.3/1.6
  both have 0.5, thats the matched comparison

Usage:
  python vibration_analysis.py            # pull (or use cache) + plot
  python vibration_analysis.py --refresh  # force re-pull from OpenLab
"""
import os
import sys
import argparse

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "openlab"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg

OUT_DIR = "plots"
CACHE = "vibration_data.npz"
WARMUP = cfg.WARMUP_STEPS                 # skip warmup steps (fixed setpoints, not policy)
WINDOW = cfg.TORQUE_HISTORY_WINDOW        # 10
VAR_THRESHOLD = cfg.TORQUE_VARIANCE_THRESHOLD  # 1e5 (Nm)^2

# sim name -> (model, ucs), from the sims listing
DETOURNAY = {0.2: "RL_ep1_277421", 0.3: "RL_ep1_115733",
             0.4: "RL_ep1_214464", 0.5: "RL_ep1_353689"}
MSE = {0.5: "RL_ep1_133307", 0.7: "RL_ep1_286503", 1.0: "RL_ep1_412089",
       1.3: "RL_ep1_985135", 1.6: "RL_ep1_80586"}

os.makedirs(OUT_DIR, exist_ok=True)
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 180, "axes.grid": True,
                     "grid.alpha": 0.3, "font.size": 11})

C_MSE = "#2563eb"        # blue
C_DET = "#dc2626"        # red


def rolling_var(torque, window=WINDOW):
    """10-step trailing variance — matches env's np.var(self._torque_history)."""
    t = np.asarray(torque, dtype=float)
    n = len(t)
    out = np.full(n, np.nan)
    for i in range(n):
        lo = max(0, i - window + 1)
        seg = t[lo:i + 1]
        if len(seg) >= 3:
            out[i] = np.var(seg)
    return out


def pull_all():
    """Pull SurfaceTorque + BitDepth for all 9 sims from OpenLab. Returns dict."""
    import openlab
    openlab.login.switch_user(new_user=cfg.OPENLAB_EMAIL, new_key=cfg.OPENLAB_API_KEY,
                              new_licenseguid=cfg.OPENLAB_LICENSE_GUID, environment="prod")
    sess = openlab.http_client(username=cfg.OPENLAB_EMAIL, apikey=cfg.OPENLAB_API_KEY,
                               licenseguid=cfg.OPENLAB_LICENSE_GUID)
    sims = sess.simulations()
    by_name = {s["Name"]: s for s in sims}

    data = {}
    plan = [("Detournay", ucs, nm, True) for ucs, nm in DETOURNAY.items()] + \
           [("MSE", ucs, nm, None) for ucs, nm in MSE.items()]

    for model, ucs, name, expect_det in plan:
        s = by_name.get(name)
        if s is None:
            print(f"  [WARN] {model} UCS={ucs} sim '{name}' not found — skipping")
            continue
        sid = s["SimulationID"]
        mc = s.get("ModelConfiguration", {})
        got_det = mc.get("UseDetournayROPModel")
        cfg_name = s.get("ConfigurationName", "")
        last = int(s.get("CurrentStep", 0))
        # check its the model we think it is
        flag_ok = "OK" if got_det == expect_det else f"MISMATCH(expected {expect_det})"
        print(f"  {model:9s} UCS={ucs}: {name} cfg={cfg_name} "
              f"UseDetournay={got_det} [{flag_ok}] steps={last}")

        # torque and depth in chunks, the api wont hand it over in one go
        torque, depth, steps = {}, {}, []
        lo = WARMUP + 1
        CHUNK = 5000
        while lo <= last:
            hi = min(lo + CHUNK - 1, last)
            res = sess.get_simulation_results(sid, lo, hi, False,
                                              ["SurfaceTorque", "BitDepth"])
            torque.update(res.get("SurfaceTorque", {}) or {})
            depth.update(res.get("BitDepth", {}) or {})
            lo = hi + 1
        if not torque:
            print(f"    [WARN] no torque returned for {name}")
            continue
        steps = sorted(int(k) for k in torque.keys())
        tq = np.array([torque[k] for k in steps], dtype=float)
        bd_steps = sorted(int(k) for k in depth.keys())
        bd = np.array([depth[k] for k in bd_steps], dtype=float)
        key = f"{model}_{ucs}"
        data[f"{key}__step"] = np.array(steps)
        data[f"{key}__torque"] = tq
        data[f"{key}__bd_step"] = np.array(bd_steps)
        data[f"{key}__bitdepth"] = bd
        print(f"    pulled torque n={len(tq)} (mean={tq.mean():.0f} Nm, std={tq.std():.0f} Nm)")

    np.savez_compressed(CACHE, **data)
    print(f"\n  Cached to {CACHE}")
    return data


def load_or_pull(refresh=False):
    if os.path.exists(CACHE) and not refresh:
        print(f"Loading cached data from {CACHE} (use --refresh to re-pull)")
        npz = np.load(CACHE, allow_pickle=True)
        return {k: npz[k] for k in npz.files}
    print("Pulling from OpenLab (read-only, no step-budget cost)…")
    return pull_all()


def metrics(data, model, ucs):
    """Return dict of vibration metrics for one sim, or None if missing."""
    key = f"{model}_{ucs}"
    if f"{key}__torque" not in data:
        return None
    tq = data[f"{key}__torque"]
    rv = rolling_var(tq)
    rv_valid = rv[~np.isnan(rv)]
    return {
        "step": data[f"{key}__step"],
        "torque": tq,
        "rolling_var": rv,
        "mean_torque": float(np.mean(tq)),
        "std_torque": float(np.std(tq)),
        "mean_rolling_var": float(np.mean(rv_valid)),
        "median_rolling_var": float(np.median(rv_valid)),
        "frac_above_thresh": float(np.mean(rv_valid > VAR_THRESHOLD)),
        "bitdepth": data.get(f"{key}__bitdepth"),
        "bd_step": data.get(f"{key}__bd_step"),
    }


def fig5_matched(data):
    """MSE vs Detournay at UCS=0.5 — matched formation, same policy."""
    m = metrics(data, "MSE", 0.5)
    d = metrics(data, "Detournay", 0.5)
    if m is None or d is None:
        print("  [skip] Fig5 — missing UCS=0.5 data")
        return

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    fig.suptitle("Vibration: MSE vs Detournay ROP model  (matched at UCS=0.5, same trained policy)",
                 fontsize=13, fontweight="bold")

    # (0,0) torque traces, zoomed so the sawtooth shows
    ax = axes[0, 0]
    w0, w1 = 1000, 2000
    for res, c, lab in [(m, C_MSE, "Default (MSE)"), (d, C_DET, "Detournay (realistic)")]:
        st = res["step"]
        mask = (st >= w0) & (st <= w1)
        ax.plot(st[mask], res["torque"][mask] / 1000.0, color=c, linewidth=0.8, label=lab)
    ax.set_title(f"Surface torque trace (steps {w0}–{w1})")
    ax.set_xlabel("Simulation step (0.1 s each)")
    ax.set_ylabel("Surface torque (kNm)")
    ax.legend()

    # (0,1) torque histogram
    ax = axes[0, 1]
    ax.hist(m["torque"] / 1000.0, bins=60, color=C_MSE, alpha=0.55, label="Default (MSE)", density=True)
    ax.hist(d["torque"] / 1000.0, bins=60, color=C_DET, alpha=0.55, label="Detournay (realistic)", density=True)
    ax.set_title("Surface torque distribution")
    ax.set_xlabel("Surface torque (kNm)")
    ax.set_ylabel("Density")
    ax.legend()

    # (1,0) rolling variance
    ax = axes[1, 0]
    for res, c, lab in [(m, C_MSE, "Default (MSE)"), (d, C_DET, "Detournay (realistic)")]:
        st = res["step"]
        ax.plot(st, res["rolling_var"], color=c, linewidth=0.5, alpha=0.7, label=lab)
    ax.axhline(VAR_THRESHOLD, color="black", linestyle="--", alpha=0.6,
               label=f"vibration threshold ({VAR_THRESHOLD:.0e})")
    ax.set_yscale("log")
    ax.set_title(f"{WINDOW}-step rolling torque variance (env vibration metric)")
    ax.set_xlabel("Simulation step")
    ax.set_ylabel("Torque variance (Nm²), log scale")
    ax.legend(fontsize=8)

    # (1,1) summary bars
    ax = axes[1, 1]
    labels = ["mean torque\n(kNm)", "torque std\n(kNm)", "mean rolling\nvar (×1e5 Nm²)",
              "% steps above\nthreshold"]
    mse_vals = [m["mean_torque"]/1000, m["std_torque"]/1000,
                m["mean_rolling_var"]/1e5, m["frac_above_thresh"]*100]
    det_vals = [d["mean_torque"]/1000, d["std_torque"]/1000,
                d["mean_rolling_var"]/1e5, d["frac_above_thresh"]*100]
    x = np.arange(len(labels)); bw = 0.38
    b1 = ax.bar(x - bw/2, mse_vals, bw, color=C_MSE, label="Default (MSE)")
    b2 = ax.bar(x + bw/2, det_vals, bw, color=C_DET, label="Detournay (realistic)")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
    ax.set_title("Vibration summary (UCS=0.5)")
    ax.legend()
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x()+b.get_width()/2, b.get_height(),
                    f"{b.get_height():.2f}", ha="center", va="bottom", fontsize=8)

    fig.tight_layout()
    out = os.path.join(OUT_DIR, "fig5_vibration_mse_vs_detournay.png")
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)
    print(f"  Saved {out}")

    # headline numbers
    print(f"\n  UCS=0.5 matched comparison:")
    print(f"    {'metric':28s} {'MSE':>14s} {'Detournay':>14s}")
    print(f"    {'mean torque (Nm)':28s} {m['mean_torque']:>14.0f} {d['mean_torque']:>14.0f}")
    print(f"    {'torque std (Nm)':28s} {m['std_torque']:>14.0f} {d['std_torque']:>14.0f}")
    print(f"    {'mean rolling var (Nm^2)':28s} {m['mean_rolling_var']:>14.0f} {d['mean_rolling_var']:>14.0f}")
    print(f"    {'% steps above threshold':28s} {m['frac_above_thresh']*100:>13.1f}% {d['frac_above_thresh']*100:>13.1f}%")


def fig6_vs_ucs(data):
    """Vibration vs formation hardness for both models."""
    det_ucs = sorted(DETOURNAY.keys())
    mse_ucs = sorted(MSE.keys())
    det = [(u, metrics(data, "Detournay", u)) for u in det_ucs]
    mse = [(u, metrics(data, "MSE", u)) for u in mse_ucs]
    det = [(u, r) for u, r in det if r]
    mse = [(u, r) for u, r in mse if r]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("Vibration & torque vs formation hardness (per-episode, deterministic policy)",
                 fontsize=13, fontweight="bold")

    # mean rolling variance vs ucs
    ax = axes[0]
    ax.plot([u for u, _ in det], [r["mean_rolling_var"] for _, r in det],
            "o-", color=C_DET, label="Detournay")
    ax.plot([u for u, _ in mse], [r["mean_rolling_var"] for _, r in mse],
            "s-", color=C_MSE, label="MSE")
    ax.axhline(VAR_THRESHOLD, color="black", linestyle="--", alpha=0.6, label="threshold")
    ax.set_title(f"Mean {WINDOW}-step rolling torque variance")
    ax.set_xlabel("UCS multiplier (softer ← → harder)")
    ax.set_ylabel("Torque variance (Nm²)")
    ax.legend()

    # torque std vs ucs
    ax = axes[1]
    ax.plot([u for u, _ in det], [r["std_torque"]/1000 for _, r in det],
            "o-", color=C_DET, label="Detournay")
    ax.plot([u for u, _ in mse], [r["std_torque"]/1000 for _, r in mse],
            "s-", color=C_MSE, label="MSE")
    ax.set_title("Surface torque std")
    ax.set_xlabel("UCS multiplier")
    ax.set_ylabel("Torque std (kNm)")
    ax.legend()

    # mean torque vs ucs
    ax = axes[2]
    ax.plot([u for u, _ in det], [r["mean_torque"]/1000 for _, r in det],
            "o-", color=C_DET, label="Detournay")
    ax.plot([u for u, _ in mse], [r["mean_torque"]/1000 for _, r in mse],
            "s-", color=C_MSE, label="MSE")
    ax.set_title("Mean surface torque")
    ax.set_xlabel("UCS multiplier")
    ax.set_ylabel("Mean torque (kNm)")
    ax.legend()

    fig.tight_layout()
    out = os.path.join(OUT_DIR, "fig6_vibration_vs_ucs.png")
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)
    print(f"  Saved {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="Force re-pull from OpenLab")
    args = ap.parse_args()

    data = load_or_pull(refresh=args.refresh)
    print("\nBuilding Fig5 (matched MSE vs Detournay at UCS=0.5)…")
    fig5_matched(data)
    print("\nBuilding Fig6 (vibration vs UCS)…")
    fig6_vs_ucs(data)
    print("\nDone.")
