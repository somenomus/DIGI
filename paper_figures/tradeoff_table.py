"""trade-off indicators behind Table D.1: pump power, mechanical power, energy
per metre and high frequency torque for the original-reward and torque-gated
agents on the three uniform formations. reads ../paper_trajectories.npz only.

  python tradeoff_table.py           # print the table
  python tradeoff_table.py --check   # and assert the values printed in the paper

pump power = SPP * flow, mechanical power = 2 pi N T + WOB g ROP. energy
integrates both over the policy interval (the 9.55 m the policy drills), the
per metre value divides by 9.55. powers and the torque residual (torque minus
a 51 sample = 5.1 s centred moving average) are averaged over steady drilling,
policy step >= 1000. the ECD / SPP standard deviations over the same window
back the "below 0.0012 sg and 0.6 bar" sentence in the caption.
"""
import os, sys, argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import config as cfg

Z = np.load(os.path.join(ROOT, "paper_trajectories.npz"), allow_pickle=True)
DT = cfg.STEP_DURATION; WU = cfg.WARMUP_STEPS; G = 9.81; L_POLICY = 9.55
UCS = ["0.2", "0.4", "1.0"]
AGENTS = [("target", "original"), ("gated", "torque-gated")]
STEADY_FROM = 1000      # policy steps
MA = 51                 # samples, 5.1 s

# the numbers as printed in Table D.1 (time, P_pump, P_mech, E, E/m, sigma_T^HF)
PAPER = {("0.2", "target"): (23.9, 304, 118, 594, 62.2, 303),
         ("0.2", "gated"): (20.6, 526, 155, 807, 84.5, 176),
         ("0.4", "target"): (32.7, 304, 119, 818, 85.7, 172),
         ("0.4", "gated"): (27.3, 527, 159, 1087, 113.8, 152),
         ("1.0", "target"): (61.6, 304, 118, 1548, 162.1, 103),
         ("1.0", "gated"): (55.5, 527, 156, 2244, 235.0, 104)}


def row(u, key):
    st = Z[f"{key}_{u}__step"]
    spp = Z[f"{key}_{u}__spp"]          # Pa
    flow = Z[f"{key}_{u}__flow"]        # m3/s
    rpm = Z[f"{key}_{u}__rpm"]          # rev/s
    tq = Z[f"{key}_{u}__torque"]        # N m
    wob = Z[f"{key}_{u}__wob"]          # kg
    dep = Z[f"{key}_{u}__bitdepth"]     # m
    ecd = Z[f"{key}_{u}__ecd"]          # kg/m3
    rop = np.clip(np.gradient(dep, DT), 0, None)            # m/s
    p_pump = spp * flow
    p_mech = 2 * np.pi * rpm * tq + wob * G * rop
    steady = (st - WU) >= STEADY_FROM
    minutes = (len(st) + WU) * DT / 60.0
    energy = np.sum(p_pump + p_mech) * DT / 1e6             # MJ
    resid = tq - np.convolve(tq, np.ones(MA) / MA, mode="same")
    return dict(minutes=minutes, p_pump=p_pump[steady].mean() / 1e3,
                p_mech=p_mech[steady].mean() / 1e3, energy=energy,
                per_m=energy / L_POLICY, hf=resid[steady].std(),
                sd_ecd=ecd[steady].std() / 1000.0, sd_spp=spp[steady].std() / 1e5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="assert the paper's values")
    args = ap.parse_args()
    print(f"{'m':>4} {'agent':<13}{'min':>6}{'Ppump kW':>10}{'Pmech kW':>10}{'E MJ':>8}"
          f"{'E/m MJ/m':>10}{'sdT_HF Nm':>11}{'sd ECD sg':>11}{'sd SPP bar':>12}")
    bad = 0
    for u in UCS:
        for key, name in AGENTS:
            r = row(u, key)
            got = (round(r["minutes"], 1), int(round(r["p_pump"])), int(round(r["p_mech"])),
                   int(round(r["energy"])), round(r["per_m"], 1), int(round(r["hf"])))
            print(f"{u:>4} {name:<13}{got[0]:>6.1f}{got[1]:>10d}{got[2]:>10d}{got[3]:>8d}"
                  f"{got[4]:>10.1f}{got[5]:>11d}{r['sd_ecd']:>11.4f}{r['sd_spp']:>12.2f}")
            if args.check and got != PAPER[(u, key)]:
                bad += 1; print(f"     MISMATCH, paper has {PAPER[(u, key)]}")
    if args.check:
        print("check:", "all 6 rows match Table D.1" if bad == 0 else f"{bad} rows differ")
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
