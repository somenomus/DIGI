"""all the knobs in one place: openlab login, sim setup, action ranges, limits,
reward weights. SI units unless a comment says otherwise, thats what the
simulator returns. the numbers come from the domain expert spec, see info.md
"""
import os

# openlab login. set these as env vars, dont put them in the file
OPENLAB_EMAIL = os.environ.get("OPENLAB_EMAIL", "")
OPENLAB_API_KEY = os.environ.get("OPENLAB_API_KEY", "")
OPENLAB_LICENSE_GUID = os.environ.get("OPENLAB_LICENSE_GUID", "")

# sim setup

# openlab caps stored sims at 20 per account now. we create one sim per episode,
# so the env deletes its own old finished ones and keeps just the last few.
# results get pulled during the episode so deleting after is fine. stay well
# under 20, concurrent sims need room too
MAX_STORED_SIMS_KEEP = 8

CONFIG_NAME = "drill"                  # base config name on openlab
# formation override, None = CONFIG_NAME. "drill_realistic" is the 50-70 MPa one
# (NORCE guidance), the original "drill" is 50-200 MPa and left as is. per run:
# --base-config in evaluate.py or BASE_CONFIG=name in the step5 script
BASE_CONFIG_NAME = None
INITIAL_BIT_DEPTH = 2497               # m
TARGET_BIT_DEPTH = 2508                # m, episode ends when the bit gets here (11 m section)
STEP_DURATION = 0.1                    # s, transient T&D needs 0.1
# episode caps. a normal completion is ~4200 steps, 30k was way too loose and
# bad policies just burned quota
TRAIN_MAX_EPISODE_STEPS = 15000
HPO_MAX_EPISODE_STEPS = 10000          # tighter so hpo fails fast
MAX_EPISODE_STEPS = TRAIN_MAX_EPISODE_STEPS
WARMUP_STEPS = 300                     # steps at mid setpoints before the policy takes over (was 30 when steps were 1 s)

# dont log every step to wandb, the client overhead adds up. api time should stay the bottleneck
WANDB_STEP_LOG_INTERVAL = 10

# transient torque and drag, real torque/rop/wob dynamics
USE_TRANSIENT_MECHANICAL = True

# Detournay bit-rock model instead of the default MSE based one. much more
# realistic vibration (torque variance, mse, wob jitter). False keeps the old
# runs reproducible. per run: --use-detournay or USE_DETOURNAY=1
USE_DETOURNAY_ROP = False

# Kp for openlabs WOB autodriller, None = their default (1e-5). higher = downhole
# WOB tracks the setpoint faster. was a diagnostic knob for the low-rop-on-soft-rock
# question. per run: --wob-gain or WOB_GAIN=
WOB_PROPORTIONAL_GAIN = None

# action space. engineering units here, the env converts to SI. ranges from info.md sec 2

# rpm
RPM_MIN = 80.0
RPM_MAX = 120.0

# tonnes
WOB_MIN = 8.0
WOB_MAX = 12.0

# l/min
FLOW_RATE_MIN = 1800.0
FLOW_RATE_MAX = 2200.0

# m/s, not an agent action, just a setpoint we have to give the sim
TOP_OF_STRING_VELOCITY_MIN = 0.02
TOP_OF_STRING_VELOCITY_MAX = 0.05
TOP_OF_STRING_VELOCITY_DEFAULT = 0.03

# unit helpers, engineering -> SI for the api
def rpm_to_hz(rpm):
    """RPM (rev/min) -> Hz (rev/s)"""
    return rpm / 60.0

def tonnes_to_kg(tonnes):
    """Tonnes -> kg"""
    return tonnes * 1000.0

def lpm_to_m3s(lpm):
    """Liters/min -> m³/s"""
    return lpm / 60000.0

def bar_to_pa(bar):
    """Bar -> Pa"""
    return bar * 1e5

def pa_to_bar(pa):
    """Pa -> bar"""
    return pa / 1e5

def sg_to_kgm3(sg):
    """Specific gravity -> kg/m³"""
    return sg * 1000.0

def kgm3_to_sg(kgm3):
    """kg/m³ -> specific gravity"""
    return kgm3 / 1000.0

def rop_ms_to_mh(rop_ms):
    """ROP m/s -> m/h"""
    return rop_ms * 3600.0

def kn_to_n(kn):
    """kN -> N"""
    return kn * 1000.0

def nm_to_knm(nm):
    """Nm -> kN·m"""
    return nm / 1000.0


# tags pulled from the sim each step, in this order they make the first 10 obs
OBSERVATION_TAGS = [
    "InstantaneousROP",       # m/s. api gives 0 in transient mode, env recomputes it from BitDepth
    "TopOfStringVelocity",    # m/s. stands in for WOB, which also reads 0 in transient mode
    "SPP",                    # Pa
    "SurfaceTorque",          # Nm
    "DownholePressure",       # Pa
    "DownholeECD",            # kg/m3
    "FlowRateOut",            # m3/s
    "HookLoad",               # N
    "BitDepth",               # m
    "Connection",             # 0/1
]

# rough normalisation ranges, from poking the api. obs end up roughly in [-1, 1].
# openlab gives ECD in kg/m3
OBS_RANGES = {
    "InstantaneousROP":   (0.0,       0.05),       # m/s
    "TopOfStringVelocity": (0.0,      0.06),       # m/s, api returns ~0.03
    "SPP":                (0.0,       2.0e7),       # Pa, 200 bar = C4
    "SurfaceTorque":      (0.0,       60000.0),     # Nm, 60 kNm = C5
    "DownholePressure":   (3.0e7,     4.5e7),       # Pa
    "DownholeECD":        (1400.0,    1800.0),      # kg/m3
    "FlowRateOut":        (-0.001,    0.05),        # m3/s
    "HookLoad":           (0.0,       2e5),         # N
    "BitDepth":           (2400.0,    3000.0),      # m
    "Connection":         (0.0,       1.0),
}


# hard limits, info.md sec 6. any violation = penalty. SI
SAFETY_CONSTRAINTS = {
    "C1": {"kpi": "ECD_max",     "limit": sg_to_kgm3(1.78), "op": "<=", "reason": "Fracture risk"},
    "C2": {"kpi": "ECD_min",     "limit": sg_to_kgm3(1.50), "op": ">=", "reason": "Kick risk"},  # pore pressure is ~1.566 sg here, so this sits below it
    "C3": {"kpi": "dECD_dt",     "limit": sg_to_kgm3(0.05), "op": "<=", "reason": "ECD rate"},  # sg/min -> kg/m3/min
    "C4": {"kpi": "SPP_max",     "limit": bar_to_pa(200),    "op": "<=", "reason": "Pump limit"},
    "C5": {"kpi": "Torque_max",  "limit": 60000.0,           "op": "<=", "reason": "Drive limit"},
    "C6": {"kpi": "FlowRate",    "limit": lpm_to_m3s(2200),  "op": "<=", "reason": "Pump capacity"},
    "C7": {"kpi": "RPM",         "limit": rpm_to_hz(180),    "op": "<=", "reason": "Motor limit"},
    "C8": {"kpi": "WOB",         "limit": kn_to_n(140),      "op": "<=", "reason": "Structural"},
}

# same limits as flat names, the env uses these
ECD_MAX_KGM3 = sg_to_kgm3(1.78)      # C1
ECD_MIN_KGM3 = sg_to_kgm3(1.50)      # C2
SPP_LIMIT = bar_to_pa(200)            # C4
TORQUE_LIMIT = 60000.0                # C5, Nm
WOB_LIMIT_N = kn_to_n(140)           # C8
RPM_LIMIT_HZ = rpm_to_hz(180)        # C7
FLOW_LIMIT_M3S = lpm_to_m3s(2200)    # C6


# safety margin refs (info.md sec 8 level 2). margin = ref - measured, other way
# round for the lower bound. SI
ECD_MARGIN_HIGH_KGM3 = sg_to_kgm3(1.76)   # bit under the 1.78 C1 limit
ECD_MARGIN_LOW_KGM3 = sg_to_kgm3(1.48)    # bit under the 1.50 C2 limit
SPP_MARGIN_PA = bar_to_pa(200)
TORQUE_MARGIN_NM = 60000.0


# stability warnings S1-S4 (info.md sec 6). warnings, not hard kills
ECD_STD_LIM_KGM3 = sg_to_kgm3(0.02)      # S1 sigma_ECD > 0.02 sg
SPP_STD_LIM_PA = bar_to_pa(5)             # S2 sigma_SPP > 5 bar
ECD_SLOPE_LIM_KGM3_PER_S = sg_to_kgm3(0.02) / 60.0  # S3 |slope| > 0.02 sg/min, stored per second
ROP_VARIANCE_THRESHOLD = 1e-6             # S4 (m/s)^2, picked from sim data

# rolling window for the stats, in steps
ECD_HISTORY_WINDOW = 30
SPP_HISTORY_WINDOW = 30


# ECD regime classification (info.md sec 4). only logged, not in the reward. SI
REGIME_THRESHOLDS = {
    "stable_ecd_std": sg_to_kgm3(0.01),
    "stable_slope_abs": sg_to_kgm3(0.005) / 60.0,
    "drift_up_slope": sg_to_kgm3(0.02) / 60.0,      # sg/min -> per second
    "drift_down_slope": -sg_to_kgm3(0.02) / 60.0,
    "oscillation_ecd_std": sg_to_kgm3(0.02),
    "jump_delta_ecd": sg_to_kgm3(0.05),             # one step jump
}


# performance score (info.md sec 8 level 1)
# score = w1*ROP_s - w2*T_s - w3*MSE_s - w4*ECD_s + w5*HC_s - w6*RPM_s
PERFORMANCE_WEIGHTS = {
    "rop":    0.30,
    "torque": 0.20,
    "mse":    0.20,
    "ecd":    0.15,   # sigma_ECD
    "hc":     0.10,   # hole cleaning, flow out
    "rpm":    0.05,   # distance from RPM_OPTIMAL
}

# torque gated reward. the default torque term above punishes torque at every
# level, even 13 of 60 kNm, and that trained the agent to sit at min RPM. so
# (a) gate the torque penalty, zero until torque gets near the limit, and
# (b) shift weight to ROP and RPM. hard limits untouched. toggle per run so the
# original agent is still around for the before/after
USE_REVISED_REWARD = False
# no torque penalty below this fraction of the limit, ramps to full at the limit
# t_s = clip((T - g*Tlim) / ((1-g)*Tlim), 0, 2)
TORQUE_GATE_FRACTION = 0.75           # 45 of 60 kNm
PERFORMANCE_WEIGHTS_REVISED = {
    "rop":    0.40,   # was 0.30
    "torque": 0.15,   # gated, only bites near the limit
    "mse":    0.15,   # was 0.20, saturated anyway
    "ecd":    0.15,
    "hc":     0.10,
    "rpm":    0.15,   # was 0.05
}

# scaling refs (info.md sec 9 example), SI
ROP_REF = 50.0 / 3600.0              # 50 m/h
TORQUE_REF_NM = 60000.0
MSE_REF_PA = 100e6                   # 100 MPa
ECD_STD_REF_KGM3 = sg_to_kgm3(0.02)
FLOW_REF_M3S = lpm_to_m3s(2000)
RPM_OPTIMAL_HZ = rpm_to_hz(120)

# not in info.md, just keeps training from twitching
SMOOTHNESS_WEIGHT = 0.05

# per violated constraint per step
SAFETY_VIOLATION_PENALTY = 5.0

# completion shaping (june 2026 retrain). the problem: the per step survival
# income (mostly the stability bonus, ~0.38/step) grows with episode length, so
# a long episode beat finishing and the old +10 bonus was noise. the agent had
# no reason to reach target. fix: pay per metre drilled (11 m -> +5500), charge
# per step (roughly cancels the survival income), and a real bonus at target.
# set these to 0 / 0 / 10 and you get the old reward back exactly
DEPTH_PROGRESS_WEIGHT = 500.0  # per metre drilled this step
TIME_STEP_PENALTY = 0.4        # per step
DEPTH_COMPLETION_BONUS = 1000.0  # once, at target depth

# tier weights, safety > stability > performance (PI directive). violations get
# the big penalties on top of this
SAFETY_MARGIN_WEIGHT = 1.0
STABILITY_BONUS_WEIGHT = 0.5
PERFORMANCE_WEIGHT = 0.3


# torque vibration check, rolling window
TORQUE_HISTORY_WINDOW = 10             # steps
TORQUE_VARIANCE_THRESHOLD = 1e5        # (Nm)^2, above this counts as vibration


# MSE, Teales equation. MSE = W/Ab + 2*pi*T*f/(Ab*v), in Pa
BIT_DIAMETER_INCHES = 8.5              # from drill-2.json
BIT_DIAMETER_M = BIT_DIAMETER_INCHES * 0.0254
BIT_AREA_M2 = 3.14159265359 * (BIT_DIAMETER_M / 2) ** 2
MSE_NORMALIZATION = MSE_REF_PA


# per episode UCS randomisation, every episode gets a multiplier on the whole
# formation. modes: "profiles" pick from the list, "continuous" uniform in
# [min, max], "curriculum" widen the range over training
UCS_PROFILES = [
    1.0,    # the formation as configured
    0.7,
    1.3,
    1.6,
    0.5,
]

# continuous mode range
UCS_RANDOM_MIN = 0.5
UCS_RANDOM_MAX = 1.6

# default mode, None = off
UCS_RANDOM_MODE = None

# curriculum stages, (start_episode, ucs_min, ucs_max)
'''
CURRICULUM_STAGES = [
    (0,   1.0, 1.0),     # Episodes 0–19:  baseline only (learn to drill)
    (20,  0.8, 1.2),     # Episodes 20–49: mild variation (±20%)
    (50,  0.6, 1.4),     # Episodes 50–79: moderate variation (±40%)
    (80,  0.5, 1.6),     # Episodes 80+:   full range (max difficulty)
]
'''


CURRICULUM_STAGES = [
    (0, 0.5, 1.6),
]


# eval callback during training, deterministic runs on fixed formations
EVAL_FREQ_STEPS = 50000         # every N training steps
EVAL_UCS_VALUES = [1.0, 1.3]   # keep short, api budget
EVAL_MAX_STEPS = 6000           # per eval episode, ~40% over a typical completion

