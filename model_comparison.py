"""default (MSE) vs Detournay bit-rock model, same trained agent under both.

reads the two eval jsons and the cached torque data (vibration_data.npz),
no api calls.

  default MSE eval : eval_20260517_041412.json   UCS 0.5-1.6
  Detournay eval   : eval_20260528_203829.json   UCS 0.2-0.5
  overlap at 0.5, thats the like for like point
"""
import os
import sys
import json

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg

OUT_DIR = "plots"
TARGET_DEPTH = 11.0
ROP_THRESHOLD = 3.0
WINDOW = cfg.TORQUE_HISTORY_WINDOW
VAR_THRESHOLD = cfg.TORQUE_VARIANCE_THRESHOLD
CACHE = "vibration_data.npz"

MSE_JSON = "eval_results/eval_20260517_041412.json"
DET_JSON = "eval_results/eval_20260528_203829.json"

C_MSE = "#2563eb"   # blue  = default model
C_DET = "#dc2626"   # red   = Detournay (realistic)

plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 190, "axes.grid": True,
                     "grid.alpha": 0.3, "font.size": 11})


def load_eval(path):
    with open(path) as f:
        d = json.load(f)
    rows = sorted(d["per_episode"], key=lambda e: e["ucs"])
    return {
        "ucs": [e["ucs"] for e in rows],
        "depth": [e["depth_progress_m"] for e in rows],
        "rop": [e["avg_rop_m_h"] for e in rows],
        "viol": [e["safety_violations"] for e in rows],
    }


def rolling_var(t, window=WINDOW):
    t = np.asarray(t, float); n = len(t); out = np.full(n, np.nan)
    for i in range(n):
        seg = t[max(0, i - window + 1):i + 1]
        if len(seg) >= 3:
            out[i] = np.var(seg)
    return out


def vibration_by_ucs(npz, model):
    """Return {ucs: mean_rolling_var} for a model from cached torque."""
    out = {}
    for k in npz.files:
        if k.startswith(f"{model}_") and k.endswith("__torque"):
            ucs = float(k[len(model) + 1:].split("__")[0])
            rv = rolling_var(npz[k])
            out[ucs] = float(np.nanmean(rv))
    return dict(sorted(out.items()))


def main():
    mse = load_eval(MSE_JSON)
    det = load_eval(DET_JSON)
    npz = np.load(CACHE, allow_pickle=True)
    vib_mse = vibration_by_ucs(npz, "MSE")
    vib_det = vibration_by_ucs(npz, "Detournay")

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9))
    fig.suptitle("Same trained agent under two bit–rock physics models\n"
                 "Default (MSE)  vs  Detournay (realistic)",
                 fontsize=14, fontweight="bold")

    # (0,0) depth vs ucs, 11 m target
    ax = axes[0, 0]
    ax.plot(mse["ucs"], mse["depth"], "s-", color=C_MSE, label="Default (MSE)")
    ax.plot(det["ucs"], det["depth"], "o-", color=C_DET, label="Detournay (realistic)")
    ax.axhline(TARGET_DEPTH, color="black", linestyle="--", label=f"Target = {TARGET_DEPTH} m")
    ax.set_title("Depth achieved — never reaches target under either model")
    ax.set_xlabel("Formation strength (UCS multiplier; softer ← → harder)")
    ax.set_ylabel("Depth progress (m)")
    ax.set_ylim(0, TARGET_DEPTH + 1)
    ax.legend()

    # (0,1) rop vs ucs
    ax = axes[0, 1]
    ax.plot(mse["ucs"], mse["rop"], "s-", color=C_MSE, label="Default (MSE)")
    ax.plot(det["ucs"], det["rop"], "o-", color=C_DET, label="Detournay (realistic)")
    ax.axhline(ROP_THRESHOLD, color="gray", linestyle=":", label=f"min useful ROP = {ROP_THRESHOLD} m/h")
    ax.set_title("Rate of penetration — well above minimum in both")
    ax.set_xlabel("Formation strength (UCS multiplier)")
    ax.set_ylabel("Avg ROP (m/h)")
    ax.legend()

    # (1,0) violations vs ucs
    ax = axes[1, 0]
    ax.plot(mse["ucs"], mse["viol"], "s-", color=C_MSE, label="Default (MSE)")
    ax.plot(det["ucs"], det["viol"], "o-", color=C_DET, label="Detournay (realistic)")
    ax.set_title("Safety violations — far fewer under realistic model")
    ax.set_xlabel("Formation strength (UCS multiplier)")
    ax.set_ylabel("Violations per episode")
    ax.legend()

    # (1,1) torque vibration vs ucs, log
    ax = axes[1, 1]
    ax.plot(list(vib_mse.keys()), list(vib_mse.values()), "s-", color=C_MSE, label="Default (MSE)")
    ax.plot(list(vib_det.keys()), list(vib_det.values()), "o-", color=C_DET, label="Detournay (realistic)")
    ax.axhline(VAR_THRESHOLD, color="black", linestyle="--", label=f"vibration threshold ({VAR_THRESHOLD:.0e})")
    ax.set_yscale("log")
    ax.set_title("Torque vibration — MSE oscillation is a model artifact")
    ax.set_xlabel("Formation strength (UCS multiplier)")
    ax.set_ylabel(f"{WINDOW}-step torque variance (Nm²), log")
    ax.legend(fontsize=9)

    # mark the matched 0.5 point everywhere
    for ax in axes.flat:
        ax.axvline(0.5, color="green", linestyle=":", alpha=0.5, linewidth=1)
    axes[0, 0].text(0.5, 0.4, " matched\n point", color="green", fontsize=8, va="bottom")

    fig.tight_layout()
    out = os.path.join(OUT_DIR, "fig7_model_comparison.png")
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)
    print(f"Saved {out}")

    # the 0.5 numbers
    def at(d, key, u=0.5):
        i = d["ucs"].index(u); return d[key][i]
    print("\nMatched comparison at UCS=0.5:")
    print(f"  {'metric':22s} {'Default(MSE)':>14s} {'Detournay':>14s}")
    print(f"  {'depth (m)':22s} {at(mse,'depth'):>14.2f} {at(det,'depth'):>14.2f}")
    print(f"  {'ROP (m/h)':22s} {at(mse,'rop'):>14.1f} {at(det,'rop'):>14.1f}")
    print(f"  {'violations':22s} {at(mse,'viol'):>14d} {at(det,'viol'):>14d}")
    print(f"  {'torque variance':22s} {vib_mse[0.5]:>14.0f} {vib_det[0.5]:>14.0f}")


if __name__ == "__main__":
    main()
