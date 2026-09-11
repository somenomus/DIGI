"""figures for the torque-gated agent, the paper's agent since sept 2026.

regenerates figs 4-6 (completion, control, ECD envelope) from the gated_0.2/0.4/1.0
traces cached in ../paper_trajectories.npz and builds the fixed-setpoint comparison
(fig 9) from ../baseline_results/*.json. writes to figs_gated/ so the original-agent
pdfs in figs/ are left alone. a png goes next to every pdf for on-screen review.

  cd paper_figures && python make_gated_figs.py
"""
import os, sys, json, glob
os.environ["FIG_PREFIX"] = "gated"          # must precede the imports below
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.colors import to_rgb
import make_paper_figs as MP
import make_new_figs as MN
import config as cfg

OUT = os.path.join(HERE, "figs_gated"); os.makedirs(OUT, exist_ok=True)

# No pdftoppm on this box: write a PNG beside every PDF for on-screen review.
from matplotlib.figure import Figure
_savefig = Figure.savefig
def _savefig_with_png(self, fname, *a, **k):
    _savefig(self, fname, *a, **k)
    if isinstance(fname, str) and fname.endswith(".pdf"):
        k2 = {kk: v for kk, v in k.items() if kk != "dpi"}
        _savefig(self, fname[:-4] + ".png", *a, dpi=170, **k2)
Figure.savefig = _savefig_with_png
MP.OUT = OUT; MN.OUT = OUT
Z = MP.Z; DT = cfg.STEP_DURATION; WU = cfg.WARMUP_STEPS

# Palette: vermillion is already the torque-gated agent in Fig. 7; the two
# corner hues are new to the paper. Validated with the dataviz checker
# (all pairs, light surface): CVD dE >= 8.4, normal-vision dE >= 16.6, all
# three above 3:1 contrast on white.
C_AGENT, C_HEAVY, C_SPEED = "#D55E00", "#3D96CF", "#B8629A"
INK, MUTED = "#222222", "#555555"
HALO = [pe.withStroke(linewidth=2.2, foreground="white")]   # keeps cap labels legible over a taller neighbour


def _gated_steps(u):
    return len(Z[f"gated_{u}__step"])


def load_comparison():
    """One row per (condition, policy): minutes, peak torque, outcome."""
    B = [json.load(open(f)) for f in glob.glob(os.path.join(ROOT, "baseline_results", "*.json"))]
    def fixed(cond, rpm):
        cfgname, ucs = ("drill_mixed", 1.0) if cond == "mixed" else ("drill_realistic", float(cond))
        b = [b for b in B if b["base_config"] == cfgname and abs(b["ucs"] - ucs) < 1e-9
             and abs(b["setpoints"]["rpm"] - rpm) < 1e-9][0]
        return dict(minutes=b["minutes_incl_warmup"], torque=b["max_torque_knm"],
                    done=bool(b["target_reached"]), depth=b["depth_progress_m"], steps=b["steps"])
    rows = {}
    for cond in ["0.2", "0.4", "1.0", "mixed"]:
        key = "mixed_rev" if cond == "mixed" else f"gated_{cond}"
        n = len(Z[f"{key}__step"])
        rows[(cond, "agent")] = dict(minutes=(n + WU) * DT / 60.0,
                                     torque=float(np.nanmax(Z[f"{key}__torque"])) / 1000.0,
                                     done=True, depth=11.0, steps=n)
        rows[(cond, "heavy")] = fixed(cond, 80.0)
        rows[(cond, "speed")] = fixed(cond, 120.0)
    return rows


def fig_fixed_setpoints(rows):
    """Two panels, one measure each: time to target and peak surface torque,
    four conditions x three policies. The DNF bar is hatched at 45 deg and
    labelled with its final depth. Direct labels only on the agent bars; the
    other values are in Table 3 (the figure's table twin)."""
    conds = ["0.2", "0.4", "1.0", "mixed"]
    xt = [r"$0.2\times$", r"$0.4\times$", r"$1.0\times$", "mixed"]
    pol = [("agent", "Torque-gated agent", C_AGENT),
           ("heavy", "Fixed 80 rpm / 12 t / 1800 L/min", C_HEAVY),
           ("speed", "Fixed 120 rpm / 10 t / 2200 L/min", C_SPEED)]
    w, gap = 0.25, 0.03                       # bar width and the surface gap
    x = np.arange(len(conds))
    # authored so the tight bbox comes out at the cas-sc text width (6.50 in)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.7, 1.95), gridspec_kw={"wspace": 0.24})
    for ax in (a1, a2):
        ax.grid(True, axis="y"); ax.grid(False, axis="x")
        ax.set_axisbelow(True); ax.set_xticks(x); ax.set_xticklabels(xt)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
    for j, (k, lab, col) in enumerate(pol):
        xs = x + (j - 1) * (w + gap)
        for ax, field in ((a1, "minutes"), (a2, "torque")):
            for i, c in enumerate(conds):
                r = rows[(c, k)]
                if r["done"]:
                    ax.bar(xs[i], r[field], w, color=col, label=lab if i == 0 else None, zorder=3)
                else:                              # did not finish: hatched, lighter
                    # opaque light tint of the series colour for the face, full
                    # colour for the hatch and edge. The PDF backend fills the
                    # hatch tile with the face RGB and applies any alpha to the
                    # whole tile, so an alpha-faded face in the same hue hides
                    # the hatch lines in the PDF (Agg shows them). A real tint
                    # renders the same in both.
                    tint = tuple(1 - 0.35 * (1 - c) for c in to_rgb(col))
                    ax.bar(xs[i], r[field], w, facecolor=tint, hatch="////",
                           edgecolor=col, lw=0.6, label=lab if i == 0 else None, zorder=3)
                    if field == "minutes":
                        ax.annotate(f"DNF\n{r['depth']:.1f} m", (xs[i], r[field]),
                                    xytext=(0, 3), textcoords="offset points",
                                    ha="center", va="bottom", fontsize=7, color=INK,
                                    path_effects=HALO)
                if k == "agent":                   # the story series gets the value on the cap
                    ax.annotate(f"{r[field]:.1f}", (xs[i], r[field]), xytext=(0, 2.5),
                                textcoords="offset points", ha="center", va="bottom",
                                fontsize=7.2, color=INK, path_effects=HALO)
    a1.set_ylabel("Time to target (min)"); a1.set_ylim(0, 100)
    a2.set_ylabel("Peak surface torque (kN·m)"); a2.set_ylim(0, 33)
    a2.text(0.99, 0.97, "C5 limit 60 kN·m", transform=a2.transAxes, ha="right", va="top",
            fontsize=7, color=MUTED)
    # one legend row above both panels; the hatched DNF bar is labelled in
    # place and explained in the caption, so it needs no legend entry
    h, l = a1.get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, 1.11), ncol=3,
               handlelength=1.6, handletextpad=0.5, columnspacing=1.6, fontsize=7.6)
    for ax, tag in ((a1, "(a)"), (a2, "(b)")):
        ax.set_title(tag, fontsize=9, loc="left", pad=3); ax.tick_params(labelsize=8)
    fig.savefig(os.path.join(OUT, "fig_fixed_setpoints.pdf"))
    plt.close(fig); print("fig_fixed_setpoints.pdf/png")


if __name__ == "__main__":
    print("gated steps:", {u: _gated_steps(u) for u in ["0.2", "0.4", "1.0"]})
    MN.fig_completion(); print("fig_completion.pdf")
    MP.fig_control();    print("fig_control.pdf")
    MP.fig_ecd();        print("fig_ecd.pdf")
    rows = load_comparison()
    for k, v in sorted(rows.items()):
        print(f"  {k[0]:<6}{k[1]:<7} {v['steps']:>6} steps  {v['minutes']:5.1f} min  {v['torque']:4.1f} kNm  {'target' if v['done'] else 'DNF'}")
    fig_fixed_setpoints(rows)
    print("written to", OUT)
