"""the other paper figures. blue #0072B2 = original/before, vermillion #D55E00
= revised/after, the UCS trio is #009E73/#0072B2/#D55E00. no grey series,
it fails the contrast check.

builds fig_completion.pdf, fig_reward_study.pdf and fig_reward_comparison.pdf
into figs/
"""
import os, sys
import numpy as np
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config as cfg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figs")
DT = cfg.STEP_DURATION; INIT = cfg.INITIAL_BIT_DEPTH; TARGET = 11.0
C_OLD, C_NEW = "#0072B2", "#D55E00"
C = {"0.2": "#009E73", "0.4": "#0072B2", "1.0": "#D55E00"}

plt.rcParams.update({
    "font.family": "serif", "mathtext.fontset": "cm", "font.size": 9,
    "axes.labelsize": 9, "axes.linewidth": 0.7, "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5, "legend.fontsize": 8, "legend.frameon": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5,
    "lines.linewidth": 1.2, "savefig.bbox": "tight", "pdf.fonttype": 42,
})
Z = np.load(os.path.join(ROOT, "paper_trajectories.npz"), allow_pickle=True)

def sm(y, w=300):
    """centred rolling mean with proper edge handling. np.convolve mode="same"
    zero pads, so the first/last w/2 samples got divided by the full window and
    RPM dropped to ~50, WOB to ~5 at the trace ends, under the action bounds
    drawn in the same panel. dividing by the real per sample support fixes it."""
    y = np.asarray(y, float)
    if len(y) <= w:
        return y
    k = np.ones(w)
    return np.convolve(y, k, "same") / np.convolve(np.ones(len(y)), k, "same")


UCS = ["0.2", "0.4", "1.0"]
LAYERS_REAL = [5, 6, 9, 10]           # realistic-formation layer boundaries (m)

def _traj(label):
    st = Z[f"{label}__step"]; bv = Z[f"{label}__bitdepth"]
    return {"t": st * DT / 60.0, "dep": bv - INIT,
            "rop": np.gradient(bv, DT) * 3600.0}

# completion: depth vs time + ROP vs depth
def fig_completion():
    """both completion panels in one pdf. they used to be two files placed as
    latex subfigures at different authored widths, so one had 6.8pt text and
    the other 9pt, and the heights differed. one figure fixes that by
    construction. authored ~1 in wider than the column, the tight bbox crops
    it back."""
    mins = {"0.2": 23.9, "0.4": 32.7, "1.0": 61.6}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.55, 2.35),
                                 gridspec_kw={"wspace": 0.27})

    for u in UCS:                                   # (a) depth vs time
        d = _traj(f"target_{u}")
        a1.plot(d["t"], d["dep"], color=C[u], label=rf"${u}\times$")
        a1.plot(d["t"][-1], d["dep"][-1], "*", color=C[u], ms=10, zorder=5)
        # time above each star. the strip between the target line and the frame is
        # empty so a label cant land on another curve
        a1.annotate(f"{mins[u]:.1f}", (d["t"][-1], d["dep"][-1]),
                    xytext=(0, 8), textcoords="offset points",
                    fontsize=8, color=C[u], ha="center", fontweight="bold")
    a1.legend(loc="upper left", ncol=1, handlelength=1.2,
              handletextpad=0.5, labelspacing=0.3)
    a1.axhline(TARGET, color="k", ls="--", lw=0.9)
    a1.set_xlabel("Time (min)"); a1.set_ylabel("Depth drilled (m)")
    a1.set_ylim(0, 12.3); a1.set_xlim(0, 71)

    # (b) ROP vs depth from bit engagement. before ~3.5 m the bit is running to
    # bottom through open hole at ~100 m/h, thats not penetration, and on this
    # axis it shot off the top with nothing explaining it. shade that bit and
    # start each trace where the smoothed rate enters the axis. the 0.2x
    # overshoot peaks at 56 so the axis is 60
    ENGAGE, YTOP = 3.5, 60.0
    for u in UCS:
        d = _traj(f"target_{u}")
        r = sm(d["rop"]); dep = d["dep"]
        i0 = int(np.argmax((dep >= ENGAGE) & (r <= YTOP)))
        a2.plot(dep[i0:], r[i0:], color=C[u], label=rf"${u}\times$")
    a2.axvspan(0, ENGAGE, color="#9AA5AD", alpha=0.20, lw=0, zorder=0)
    a2.text(ENGAGE / 2, 0.5 * YTOP, "run to\nbottom", ha="center", va="center",
            fontsize=7, color="#5A6570")
    for x in LAYERS_REAL:
        a2.axvline(x, color="gray", ls="--", lw=0.6, alpha=0.6)
    a2.axhline(3, color="k", ls=":", lw=0.8)
    a2.set_xlabel("Depth drilled (m)"); a2.set_ylabel("ROP (m/h)")
    a2.set_xlim(0, 11.2); a2.set_ylim(0, YTOP)
    a2.legend(loc="upper right", ncol=1, handlelength=1.2,
              handletextpad=0.5, labelspacing=0.3)

    for ax, tag in ((a1, "(a)"), (a2, "(b)")):
        ax.set_title(tag, fontsize=9, loc="left", pad=3)
    fig.savefig(os.path.join(OUT, "fig_completion.pdf")); plt.close(fig)
    print("fig_completion.pdf (merged)")

# reward study
def fig_reward_study():
    before = [10.44, 9.12, 5.53]; after = [11.00, 9.26, 6.81]
    viol = [126, 8]
    # authored at the rendered width so 9pt stays 9pt
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.30, 2.70),
                                 gridspec_kw={"width_ratios": [2.5, 1], "wspace": 0.26})
    x = np.arange(3); bw = 0.34
    b1 = a1.bar(x - bw / 2, before, bw, color=C_OLD, label="baseline reward")
    b2 = a1.bar(x + bw / 2, after, bw, color=C_NEW, label="completion-shaped")
    a1.axhline(TARGET, color="k", ls="--", lw=0.9, zorder=1)
    a1.text(-0.44, TARGET + 0.15, "target", fontsize=8, ha="left", va="bottom")
    for bars in (b1, b2):                       # inside the bars: never collides with the target rule
        a1.bar_label(bars, fmt="%.1f", label_type="center", fontsize=7.5, color="white")
    a1.set_xticks(x); a1.set_xticklabels([r"$0.2\times$", r"$0.4\times$", r"$1.0\times$"])
    a1.set_xlabel("Formation strength multiplier"); a1.set_ylabel("Depth drilled (m)")
    a1.set_ylim(0, 13.9)
    a1.grid(axis="x", visible=False)            # categorical axis: x gridlines are noise
    a1.legend(loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=2,
              handlelength=1.1, handletextpad=0.5, columnspacing=1.4,
              borderaxespad=0.4)

    a2.bar([0, 1], viol, 0.5, color=[C_OLD, C_NEW])
    for i, v in enumerate(viol):
        a2.text(i, v + 3, str(v), ha="center", fontsize=8.5, color="#333333")
    a2.annotate("", xy=(0.5, 22), xytext=(0.5, 104),
                arrowprops=dict(arrowstyle="->", lw=0.9, color="#777777"))
    a2.text(0.58, 62, r"$-94\%$", ha="left", va="center", fontsize=8.5, color="#555555")
    a2.set_xticks([0, 1]); a2.set_xticklabels(["baseline", "shaped"], fontsize=8)
    a2.set_ylabel("Constraint flags / episode"); a2.set_ylim(0, 152)
    a2.set_xlim(-0.6, 1.6)
    a2.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_reward_study.pdf")); plt.close(fig)
    print("fig_reward_study.pdf (upgraded)")

# original vs torque gated on the mixed section
def fig_reward_comparison():
    """original reward vs torque gated agent on the mixed section. same layout,
    same y limits, same broken ROP axis as fig_control, and the blue trace here
    is the same run the old fig_mixed showed, so the figures can sit side by
    side. full width, minimal height."""
    LAYERS = [(0, 5), (5, 7), (7, 11)]
    SHADE = ["#e8f5e9", "#fff8e1", "#fdecea"]
    ROP_SPLIT = 45.0
    old = {k: Z[f"mixed_full__{k}"] for k in ["step", "bitdepth", "torque", "rpm", "wob"]}
    new = {k: Z[f"mixed_rev__{k}"] for k in ["step", "bitdepth", "torque", "rpm", "wob"]}
    def prep(d):
        return {"dep": d["bitdepth"] - INIT, "rpm": d["rpm"] * 60.0,
                "wob": d["wob"] / 1000.0, "tq": d["torque"] / 1000.0,
                "rop": np.gradient(d["bitdepth"], DT) * 3600.0}
    o, n = prep(old), prep(new)

    fig = plt.figure(figsize=(7.55, 3.55))
    outer = fig.add_gridspec(4, 1, height_ratios=[1.0, 1.0, 1.18, 1.0],
                             hspace=0.18, top=0.90, bottom=0.115)
    a_rpm = fig.add_subplot(outer[0])
    a_wob = fig.add_subplot(outer[1], sharex=a_rpm)
    inner = outer[2].subgridspec(2, 1, height_ratios=[0.34, 0.78], hspace=0.08)
    a_hi = fig.add_subplot(inner[0], sharex=a_rpm)
    a_lo = fig.add_subplot(inner[1], sharex=a_rpm)
    a_tq = fig.add_subplot(outer[3], sharex=a_rpm)
    axs = [a_rpm, a_wob, a_hi, a_lo, a_tq]

    # policy only takes over after the 300 step warmup (~1.45 m). shade it like
    # fig_control so the empty strip doesnt look like missing data
    wu = float(o["dep"][0])
    for a in axs:
        for (x0, x1), c in zip(LAYERS, SHADE):
            a.axvspan(x0, x1, color=c, alpha=0.9, zorder=0)
        a.axvspan(0, wu, color="#9AA5AD", alpha=0.20, lw=0, zorder=0.5)
        a.set_xlim(0, 11.2)
    a_rpm.annotate("warmup", (wu / 2, 0.5), xycoords=("data", "axes fraction"),
                   ha="center", va="center", fontsize=7, color="#5A6570",
                   rotation=90)

    peak = 0.0
    for d, col, lab in ((o, C_OLD, "original reward"), (n, C_NEW, "torque-gated")):
        a_rpm.plot(d["dep"], sm(d["rpm"]), color=col, label=lab)
        a_wob.plot(d["dep"], sm(d["wob"]), color=col)
        r = sm(d["rop"]); peak = max(peak, float(np.nanmax(r)))
        a_hi.plot(d["dep"], r, color=col)
        a_lo.plot(d["dep"], r, color=col)
        a_tq.plot(d["dep"], sm(d["tq"]), color=col)

    a_rpm.set_ylabel("RPM"); a_rpm.set_ylim(70, 128); a_rpm.set_yticks([80, 100, 120])
    a_wob.set_ylabel("WOB (t)"); a_wob.set_ylim(7, 13); a_wob.set_yticks([8, 10, 12])
    a_hi.set_ylim(ROP_SPLIT, peak * 1.06)
    a_lo.set_ylim(0, ROP_SPLIT); a_lo.set_yticks([0, 20, 40])
    a_lo.set_ylabel("ROP\n(m/h)")
    a_hi.spines["bottom"].set_visible(False); a_lo.spines["top"].set_visible(False)
    a_hi.tick_params(bottom=False, labelbottom=False)
    _bk = dict(marker=[(-1, -0.5), (1, 0.5)], markersize=5, linestyle="none",
               color="k", mec="k", mew=0.7, clip_on=False)
    a_hi.plot([0, 1], [0, 0], transform=a_hi.transAxes, **_bk)
    a_lo.plot([0, 1], [1, 1], transform=a_lo.transAxes, **_bk)
    a_tq.set_ylabel("Torque\n(kN·m)"); a_tq.set_ylim(0, 32); a_tq.set_yticks([0, 15, 30])
    a_tq.set_xlabel("Depth drilled (m)")
    for a in (a_rpm, a_wob, a_lo):
        a.tick_params(labelbottom=False)
    for a in axs:
        a.tick_params(labelsize=8)
    # one legend for the whole stack, centred above it
    h, l = a_rpm.get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=2,
               handlelength=1.8, handletextpad=0.5, columnspacing=2.2)
    fig.align_ylabels([a_rpm, a_wob, a_lo, a_tq])
    fig.savefig(os.path.join(OUT, "fig_reward_comparison.pdf"), pad_inches=0.02)
    plt.close(fig)
    print("fig_reward_comparison.pdf (recolored)")

if __name__ == "__main__":
    fig_completion(); fig_reward_study(); fig_reward_comparison()
