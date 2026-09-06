"""figures for the paper. pdf, vector, no titles inside the plots, the words
go in the latex captions.

only reads cached local data, no api:
  ../paper_trajectories.npz   the target reaching runs + the mixed section
  ../vibration_data.npz       torque traces, default MSE model vs Detournay
  ../finetune_curve.json      per episode returns during fine tuning
  ../eval_results/*.json      eval summaries

writes figs/*.pdf
"""
import os, sys, json, io
import numpy as np
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config as cfg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figs")
os.makedirs(OUT, exist_ok=True)

DT = cfg.STEP_DURATION
INIT = cfg.INITIAL_BIT_DEPTH
TARGET = cfg.TARGET_BIT_DEPTH - INIT          # 11 m
Ab = cfg.BIT_AREA_M2

# plot style
plt.rcParams.update({
    "font.family": "serif",
    "mathtext.fontset": "cm",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.linewidth": 0.7,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "legend.fontsize": 8,
    "legend.frameon": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.5,
    "lines.linewidth": 1.2,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
    "pdf.fonttype": 42,
})
# okabe-ito, colorblind safe
C = {"0.2": "#009E73", "0.4": "#0072B2", "1.0": "#D55E00",
     "old": "#999999", "new": "#009E73", "mse": "#0072B2", "det": "#D55E00"}

# formation strength colours. the env rounds m to one decimal so the 33 fine
# tune episodes only ever hit 9 formations, hence a discrete ramp. one hue,
# light = soft, dark = hard
from matplotlib.colors import ListedColormap, BoundaryNorm
MCMAP = ListedColormap(plt.cm.Blues(np.linspace(0.28, 0.95, 9)))
MNORM = BoundaryNorm(np.arange(0.15, 1.06, 0.1), MCMAP.N)

Z = np.load(os.path.join(ROOT, "paper_trajectories.npz"), allow_pickle=True)
VZ = np.load(os.path.join(ROOT, "vibration_data.npz"), allow_pickle=True)

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

def traj(label):
    st = Z[f"{label}__step"]; bv = Z[f"{label}__bitdepth"]
    d = {"step": st, "dep": bv - INIT, "rop": np.gradient(bv, DT) * 3600.0,
         "tq": Z[f"{label}__torque"], "rpm": Z[f"{label}__rpm"] * 60.0,
         "wob": Z[f"{label}__wob"] / 1000.0, "flow": Z[f"{label}__flow"] * 60000.0,
         "rpmhz": Z[f"{label}__rpm"], "wobkg": Z[f"{label}__wob"]}
    d["tmin"] = st * DT / 60.0
    return d

def mse_series(d):
    rop_ms = np.gradient(d["dep"] + INIT, DT)
    out = np.full(len(d["step"]), cfg.MSE_REF_PA)
    m = (rop_ms > 1e-6) & (d["rpmhz"] > 0)
    out[m] = d["wobkg"][m] * 9.81 / Ab + 2 * np.pi * d["tq"][m] * d["rpmhz"][m] / (Ab * rop_ms[m])
    return out / 1e6  # MPa

UCS = ["0.2", "0.4", "1.0"]
T = {u: traj(f"target_{u}") for u in UCS}
MIX = traj("mixed_full")
MIX["ecd"] = Z["mixed_full__ecd"] / 1000.0     # sg
LAYERS_REal = [5, 6, 9, 10]                    # realistic-formation boundaries (m)
LAYERS_MIX = [(0, 5), (5, 7), (7, 11)]         # mixed-formation layers (m)
MIX_SHADE = ["#e8f5e9", "#fff8e1", "#fdecea"]

# training curve
def fig_training_curve():
    """return per fine tune episode. broken y axis, 31 of 33 episodes sit in
    [-2.5k, 3.3k] and two early collapses are at -12.5k, one linear axis would
    squash everything into the top quarter."""
    jobs = json.load(open(os.path.join(ROOT, "finetune_curve.json")))
    rets, idx, ucs, bounds, k = [], [], [], [], 0
    for j in jobs:
        seq = j.get("per_episode") or j["rew_means"]
        um = j["ucs"]   # per episode formation multiplier, scraped from the slurm logs
        for n, r in enumerate(seq):
            k += 1; idx.append(k); rets.append(r); ucs.append(um[n])
        bounds.append(k + 0.5)
    bounds = bounds[:-1]                      # no divider after the last job
    idx = np.asarray(idx, float); rets = np.asarray(rets, float)
    ucs = np.asarray(ucs, float)

    fig, (hi, lo) = plt.subplots(
        2, 1, sharex=True, figsize=(5.83, 3.05),
        gridspec_kw={"height_ratios": [5.0, 1.0], "hspace": 0.07})

    for ax in (hi, lo):
        for b in bounds:                       # chained-job restarts
            ax.axvline(b, color="#C4C4C4", lw=0.6, ls=(0, (3.5, 2.5)), zorder=0)
        ax.plot(idx, rets, "-", color="#9AA5AD", lw=1.0, zorder=3)
        sc = ax.scatter(idx, rets, c=np.round(ucs, 1), cmap=MCMAP, norm=MNORM,
                        s=28, edgecolors="white", linewidths=0.6, zorder=4)
        ax.set_axisbelow(True)

    hi.set_ylim(-3400, 3850);  hi.set_yticks([-2000, 0, 2000])
    lo.set_ylim(-13100, -8000); lo.set_yticks([-12500, -8600])
    hi.axhline(0, color="k", lw=0.8, ls=":", zorder=2)
    hi.annotate("break-even", xy=(idx.max(), 0), xytext=(-1, 3),
                textcoords="offset points", ha="right", va="bottom",
                fontsize=7.5, color="#555555", zorder=5)

    # axis break
    hi.spines["bottom"].set_visible(False)
    lo.spines["top"].set_visible(False)
    hi.tick_params(bottom=False, labelbottom=False)
    kw = dict(marker=[(-1, -0.5), (1, 0.5)], markersize=6, linestyle="none",
              color="k", mec="k", mew=0.8, clip_on=False)
    hi.plot([0, 1], [0, 0], transform=hi.transAxes, **kw)
    lo.plot([0, 1], [1, 1], transform=lo.transAxes, **kw)

    edges = [0.5] + bounds + [idx.max() + 0.5]
    for n, (a, b) in enumerate(zip(edges[:-1], edges[1:]), start=1):
        hi.annotate(f"J{n}", xy=(0.5 * (a + b), 0.975), xycoords=("data", "axes fraction"),
                    ha="center", va="top", fontsize=7.5, color="#8A8A8A")

    lo.set_xlabel("Training episode")
    lo.set_xlim(0.2, idx.max() + 0.8)
    fig.supylabel("Episode return", fontsize=9, x=0.005)
    cb = fig.colorbar(sc, ax=[hi, lo], pad=0.015, fraction=0.040,
                      ticks=np.arange(0.2, 1.01, 0.1), spacing="proportional")
    cb.set_label("formation multiplier $m$", fontsize=8.5)
    cb.ax.tick_params(labelsize=8)
    cb.ax.set_yticklabels([f"{v:.1f}" for v in np.arange(0.2, 1.01, 0.1)])
    cb.outline.set_linewidth(0.7)
    fig.savefig(os.path.join(OUT, "fig_training_curve.pdf")); plt.close(fig)

# control strategy
def fig_control():
    # full width, minimal height. the shared depth axis is the whole point (one
    # vertical read gives RPM/WOB/ROP/torque at the same depth) so keep the stack,
    # just squash it. the ROP row gets a broken axis: while the bit runs to bottom
    # ROP is several times the steady rate, one linear axis either clips that or
    # squashes the 5-25 m/h band the result lives in. nested gridspec keeps the
    # two ROP halves tight
    ROP_SPLIT = 45.0
    fig = plt.figure(figsize=(7.55, 4.10))
    outer = fig.add_gridspec(4, 1, height_ratios=[1.0, 1.0, 1.18, 1.0],
                             hspace=0.18)
    a_rpm = fig.add_subplot(outer[0])
    a_wob = fig.add_subplot(outer[1], sharex=a_rpm)
    inner = outer[2].subgridspec(2, 1, height_ratios=[0.34, 0.78], hspace=0.08)
    a_hi = fig.add_subplot(inner[0], sharex=a_rpm)
    a_lo = fig.add_subplot(inner[1], sharex=a_rpm)
    a_tq = fig.add_subplot(outer[3], sharex=a_rpm)
    axs = [a_rpm, a_wob, a_hi, a_lo, a_tq]

    peak = 0.0
    for u in UCS:
        d = T[u]
        a_rpm.plot(d["dep"], sm(d["rpm"]), color=C[u], label=rf"UCS ${u}\times$")
        a_wob.plot(d["dep"], sm(d["wob"]), color=C[u])
        r = sm(d["rop"]); peak = max(peak, float(np.nanmax(r)))
        a_hi.plot(d["dep"], r, color=C[u])
        a_lo.plot(d["dep"], r, color=C[u])
        a_tq.plot(d["dep"], sm(d["tq"] / 1000.0), color=C[u])

    a_rpm.axhline(cfg.RPM_MAX, color="k", ls=":", lw=0.7); a_rpm.axhline(cfg.RPM_MIN, color="k", ls=":", lw=0.7)
    a_rpm.set_ylabel("RPM"); a_rpm.set_ylim(70, 128)

    a_wob.axhline(cfg.WOB_MAX, color="k", ls=":", lw=0.7); a_wob.axhline(cfg.WOB_MIN, color="k", ls=":", lw=0.7)
    a_wob.set_ylabel("WOB (t)"); a_wob.set_ylim(7, 13)

    a_hi.set_ylim(ROP_SPLIT, peak * 1.06)
    a_lo.set_ylim(0, ROP_SPLIT)
    a_lo.set_ylabel("ROP\n(m/h)")
    a_hi.spines["bottom"].set_visible(False)
    a_lo.spines["top"].set_visible(False)
    a_hi.tick_params(bottom=False, labelbottom=False)
    _bk = dict(marker=[(-1, -0.5), (1, 0.5)], markersize=5, linestyle="none",
               color="k", mec="k", mew=0.7, clip_on=False)
    a_hi.plot([0, 1], [0, 0], transform=a_hi.transAxes, **_bk)
    a_lo.plot([0, 1], [1, 1], transform=a_lo.transAxes, **_bk)

    a_tq.axhline(cfg.TORQUE_LIMIT / 1000.0, color="#B00020", ls="--", lw=0.9)
    a_tq.set_ylabel("Torque\n(kN·m)"); a_tq.set_ylim(0, 65)
    a_tq.set_xlabel("Depth drilled (m)")
    for a in (a_rpm, a_wob, a_lo):
        a.tick_params(labelbottom=False)
    # policy only takes over after the 300 step warmup, which already moved the
    # bit ~1.45 m. shade it so the empty strip doesnt look like missing data
    wu = float(T[UCS[0]]["dep"][0])
    for a in axs:
        a.set_xlim(0, 11.2)
        a.axvspan(0, wu, color="#9AA5AD", alpha=0.16, lw=0, zorder=0)
    # between the 80 and 120 guides so it doesnt sit on either dotted line
    a_rpm.annotate("warmup", (wu / 2, 0.52), xycoords=("data", "axes fraction"),
                   ha="center", va="center", fontsize=7, color="#5A6570", rotation=90)
    _h, _l = a_rpm.get_legend_handles_labels()
    a_lo.legend(_h, _l, ncol=1, loc="upper left", handlelength=1.2,
                handletextpad=0.5, labelspacing=0.25, fontsize=7.5,
                borderaxespad=0.3)
    a_rpm.set_yticks([80, 100, 120]); a_wob.set_yticks([8, 10, 12])
    a_lo.set_yticks([0, 20, 40]);     a_tq.set_yticks([0, 30, 60])
    for a in axs: a.tick_params(labelsize=8)
    fig.align_ylabels([a_rpm, a_wob, a_lo, a_tq])
    fig.savefig(os.path.join(OUT, "fig_control.pdf")); plt.close(fig)

# ECD envelope
def fig_ecd():
    """ECD and standpipe pressure against their limits. was ECD only, three flat
    traces and an 80% empty panel. the empty space is the result (nothing gets
    near a limit) but one constraint doesnt earn a whole figure, so two panels
    cover C1/C2 (ECD) and C4 (SPP), torque is already in fig_control."""
    # both panels get a broken y axis. zooming into the operating band alone
    # would push C2 (1.50 sg) and C4 (200 bar) off scale, and the distance to
    # those is the whole claim. the break keeps the limit visible and still gives
    # the band some room
    fig = plt.figure(figsize=(7.55, 2.60))
    outer = fig.add_gridspec(1, 2, wspace=0.26)
    ge = outer[0].subgridspec(2, 1, height_ratios=[3.2, 1.0], hspace=0.10)
    gp = outer[1].subgridspec(2, 1, height_ratios=[1.0, 3.2], hspace=0.10)
    ae_hi = fig.add_subplot(ge[0]); ae_lo = fig.add_subplot(ge[1], sharex=ae_hi)
    ap_hi = fig.add_subplot(gp[0]); ap_lo = fig.add_subplot(gp[1], sharex=ap_hi)

    def _break(top, bot):
        top.spines["bottom"].set_visible(False)
        bot.spines["top"].set_visible(False)
        top.tick_params(bottom=False, labelbottom=False)
        kw = dict(marker=[(-1, -0.5), (1, 0.5)], markersize=5, linestyle="none",
                  color="k", mec="k", mew=0.7, clip_on=False)
        top.plot([0, 1], [0, 0], transform=top.transAxes, **kw)
        bot.plot([0, 1], [1, 1], transform=bot.transAxes, **kw)

    # (a) ECD, operating band with C1 above, C2 in the strip below
    ecd_hi = 0.0
    for u in UCS:
        st = Z[f"target_{u}__ecd_step"]; e = Z[f"target_{u}__ecd"] / 1000.0
        ecd_hi = max(ecd_hi, float(e.max()))
        for a in (ae_hi, ae_lo):
            a.plot(st * DT / 60.0, e, color=C[u], lw=0.9,
                   label=rf"UCS ${u}\times$" if a is ae_hi else None)
    for a in (ae_hi, ae_lo):
        a.axhspan(1.50, 1.78, color="#009E73", alpha=0.08, zorder=0)
    ae_hi.axhline(1.78, color="#B00020", ls="--", lw=0.9)
    ae_lo.axhline(1.50, color="#E69F00", ls="--", lw=0.9)
    ae_hi.set_ylim(1.706, 1.792); ae_hi.set_yticks([1.72, 1.75, 1.78])
    ae_lo.set_ylim(1.488, 1.512); ae_lo.set_yticks([1.50])
    ae_hi.annotate("", xy=(52, 1.78), xytext=(52, ecd_hi),
                   arrowprops=dict(arrowstyle="<->", lw=0.8, color="#555555"))
    ae_hi.text(50, (1.78 + ecd_hi) / 2, f"{1.78 - ecd_hi:.2f} sg", fontsize=7.5,
               ha="right", va="center", color="#555555")
    ae_hi.text(2, 1.7755, "C1 fracture", fontsize=7, color="#B00020", va="top")
    ae_lo.text(2, 1.503, "C2 kick floor", fontsize=7, color="#8A6D00", va="bottom")
    ae_lo.set_xlabel("Time (min)")
    ae_hi.set_ylabel("Downhole ECD (sg)"); ae_hi.yaxis.set_label_coords(-0.13, 0.34)
    # in the gap between the traces (~1.727) and C1 (1.78), under the C1 label
    ae_hi.legend(loc="center left", bbox_to_anchor=(0.02, 0.52), ncol=1,
                 handlelength=1.2, handletextpad=0.5, labelspacing=0.25,
                 fontsize=7.5)
    _break(ae_hi, ae_lo)

    # (b) SPP, C4 in the top strip, operating band below
    spp_hi = 0.0
    for u in UCS:
        st = Z[f"target_{u}__step"]; p = Z[f"target_{u}__spp"] / 1e5
        spp_hi = max(spp_hi, float(p.max()))
        for a in (ap_hi, ap_lo):
            a.plot(st * DT / 60.0, p, color=C[u], lw=0.9)
    for a in (ap_hi, ap_lo):
        a.axhspan(0, 200, color="#009E73", alpha=0.08, zorder=0)
    ap_hi.axhline(200, color="#B00020", ls="--", lw=0.9)
    ap_hi.set_ylim(193, 207); ap_hi.set_yticks([200])
    ap_lo.set_ylim(92, 128);  ap_lo.set_yticks([100, 110, 120])
    ap_hi.text(2, 201, "C4 pump limit", fontsize=7, color="#B00020", va="bottom")
    ap_lo.annotate(f"{200 - spp_hi:.0f} bar headroom", xy=(52, spp_hi),
                   xytext=(0, 6), textcoords="offset points", fontsize=7.5,
                   ha="right", va="bottom", color="#555555")
    ap_lo.set_xlabel("Time (min)")
    ap_lo.set_ylabel("Standpipe pressure (bar)")
    ap_lo.yaxis.set_label_coords(-0.13, 0.66)
    _break(ap_hi, ap_lo)

    for a, tag in ((ae_hi, "(a)"), (ap_hi, "(b)")):
        a.set_title(tag, fontsize=9, loc="left", pad=3)
    for a in (ae_hi, ae_lo, ap_hi, ap_lo):
        a.set_xlim(-1, 64); a.tick_params(labelsize=8)
    fig.savefig(os.path.join(OUT, "fig_ecd.pdf")); plt.close(fig)

# bit-rock model comparison
def fig_vibration():
    """MSE vs Detournay, full column width. both panels key the same two models
    so one legend above both. authored on a 7.71 in canvas so the saved pdf
    comes out ~6.44 in wide and renders at column width without font scaling."""
    ms = VZ["MSE_0.5__torque"]; ds = VZ["Detournay_0.5__torque"]
    mstep = VZ["MSE_0.5__step"]; dstep = VZ["Detournay_0.5__step"]
    def rollvar(t, w=cfg.TORQUE_HISTORY_WINDOW):
        out = np.full(len(t), np.nan)
        for i in range(len(t)):
            seg = t[max(0, i - w + 1):i + 1]
            if len(seg) >= 3: out[i] = np.var(seg)
        return out

    fig = plt.figure(figsize=(7.71, 2.24))
    gs = fig.add_gridspec(1, 2, wspace=0.235, top=0.795, bottom=0.205)
    ax0 = fig.add_subplot(gs[0]); ax1 = fig.add_subplot(gs[1])

    # (a) 100 s of raw torque
    w0, w1 = 1000, 2000
    m = (mstep >= w0) & (mstep <= w1); dmask = (dstep >= w0) & (dstep <= w1)
    h_m, = ax0.plot(mstep[m] * DT, ms[m] / 1000.0, color=C["mse"], lw=0.8,
                    label="MSE-based")
    h_d, = ax0.plot(dstep[dmask] * DT, ds[dmask] / 1000.0, color=C["det"],
                    lw=0.8, label="Detournay")
    ax0.set_xlim(w0 * DT, w1 * DT)
    ax0.set_xlabel("Time (s)"); ax0.set_ylabel("Surface torque (kN·m)")

    # (b) rolling torque variance, whole episode
    ax1.plot(mstep * DT / 60.0, rollvar(ms), color=C["mse"], lw=0.5, alpha=0.85)
    ax1.plot(dstep * DT / 60.0, rollvar(ds), color=C["det"], lw=0.5, alpha=0.85)
    # threshold goes in the shared legend, not a label in the plot. the MSE trace
    # fills everything above the line for 21 of 25 min and the gap under it is
    # too thin for text
    h_t = ax1.axhline(cfg.TORQUE_VARIANCE_THRESHOLD, color="k", ls="--", lw=0.8,
                      label="vibration-penalty threshold")
    ax1.set_yscale("log"); ax1.set_ylim(5, 1.2e7)
    # on a panel this short the auto locator thins the decade ticks to every
    # second one starting at 1e2, which leaves the 1e5 threshold unlabelled.
    # start at 1e1 instead so a tick lands on it
    ax1.set_yticks([1e1, 1e3, 1e5, 1e7])
    ax1.set_yticks([10.0 ** k for k in range(1, 8)], minor=True)
    ax1.set_yticklabels([], minor=True)
    ax1.set_xlim(0, 25.6)
    ax1.set_xlabel("Time (min)")
    ax1.set_ylabel(r"Torque variance [(N·m)$^2$]")

    for a, tag in ((ax0, "(a)"), (ax1, "(b)")):
        a.set_title(tag, fontsize=9, loc="left", pad=3)
        a.tick_params(labelsize=8)
    fig.legend(handles=[h_m, h_d, h_t], loc="upper center",
               bbox_to_anchor=(0.5, 1.005), ncol=3, handlelength=1.8,
               handletextpad=0.5, columnspacing=1.8)
    fig.savefig(os.path.join(OUT, "fig_bitrock.pdf")); plt.close(fig)

if __name__ == "__main__":
    for f in [fig_training_curve, fig_control, fig_ecd, fig_vibration]:
        f(); print("done:", f.__name__)
    print("PDFs in", OUT)
