"""gymnasium env around the openlab drilling simulator.

agent sets RPM, WOB and flow rate, goal is to get through the section fast
without tripping any limit. reward is the 3 level thing from the domain expert
spec (info.md sec 8): performance score, safety margin, stability score, with
safety > stability > performance. hard limits C1-C8 and stability warnings
S1-S4 are sec 6 of the same doc.

runs the transient torque and drag model. in transient mode the api returns 0
for InstantaneousROP and WOB, so ROP gets recomputed from BitDepth deltas, the
WOB obs slot holds TopOfStringVelocity instead, and the commanded WOB is
injected into the raw dict for MSE and the C8 check.

normal gymnasium api, reset() -> (obs, info), step(a) -> (obs, r, term, trunc, info)
"""
import sys
import os

# vendored openlab first so a pip install cant shadow it
_project_dir = os.path.dirname(os.path.abspath(__file__))
_openlab_parent = os.path.join(_project_dir, "openlab")
if _openlab_parent not in sys.path:
    sys.path.insert(0, _openlab_parent)
if _project_dir not in sys.path:
    sys.path.insert(0, _project_dir)

import gymnasium as gym
import numpy as np
from gymnasium import spaces

import openlab
import config as cfg


class DrillingEnv(gym.Env):
    """action Box(3) in [-1,1] -> RPM, WOB, flow. obs Box(15): 10 normalised
    feedback tags + 2 ECD stats + the previous action."""

    metadata = {"render_modes": ["human"], "render_fps": 1}

    # every sim id any DrillingEnv in this process created, oldest first. used
    # to delete old finished sims and stay under the servers 20 stored sim cap.
    # shared between the training env and the eval callback envs
    _sim_registry = []

    def __init__(self, render_mode=None, max_steps=None, ucs_multiplier=None,
                 ucs_random_mode=None, cleanup_on_reset=True,
                 use_detournay_rop=None, wob_proportional_gain=None,
                 base_config_name=None, ucs_random_min=None, ucs_random_max=None,
                 use_revised_reward=None):
        super().__init__()

        self.render_mode = render_mode
        self.max_steps = max_steps or cfg.MAX_EPISODE_STEPS
        self._ucs_multiplier = ucs_multiplier  # None = base config as is
        self._cleanup_on_reset = cleanup_on_reset  # False for the eval envs during training

        # per episode UCS randomisation, modes are in cfg
        self._ucs_random_mode = ucs_random_mode or cfg.UCS_RANDOM_MODE
        self._current_ucs = ucs_multiplier  # multiplier used this episode

        # Detournay bit-rock model, passed straight to openlab. None -> cfg
        self._use_detournay_rop = (
            cfg.USE_DETOURNAY_ROP if use_detournay_rop is None else use_detournay_rop
        )

        # autodriller Kp, None -> openlab default 1e-5
        self._wob_proportional_gain = (
            cfg.WOB_PROPORTIONAL_GAIN if wob_proportional_gain is None else wob_proportional_gain
        )

        # gated torque reward, None -> cfg
        self._use_revised_reward = (
            cfg.USE_REVISED_REWARD if use_revised_reward is None else use_revised_reward
        )

        # formation config: explicit arg, else cfg.BASE_CONFIG_NAME, else cfg.CONFIG_NAME
        self._base_config_name = (
            base_config_name or cfg.BASE_CONFIG_NAME or cfg.CONFIG_NAME
        )

        # continuous mode range, None -> cfg
        self._ucs_random_min = (
            cfg.UCS_RANDOM_MIN if ucs_random_min is None else ucs_random_min
        )
        self._ucs_random_max = (
            cfg.UCS_RANDOM_MAX if ucs_random_max is None else ucs_random_max
        )

        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(3,), dtype=np.float32
        )

        # 10 feedback tags + 2 ECD stats + our own last action = 15
        n_obs = len(cfg.OBSERVATION_TAGS) + 2 + 3
        self.observation_space = spaces.Box(
            low=-2.0, high=2.0, shape=(n_obs,), dtype=np.float32
        )

        self._session = None
        self._sim = None
        self._timestep = 0
        self._prev_action = np.zeros(3, dtype=np.float32)
        self._prev_rop = 0.0
        self._prev_bit_depth = cfg.INITIAL_BIT_DEPTH  # ROP comes from depth deltas
        self._episode_count = 0

        # rolling windows for the stats
        self._torque_history = []
        self._ecd_history = []       # kg/m3, raw
        self._spp_history = []       # Pa, raw
        self._rop_history = []       # m/s
        self._prev_ecd = None        # jump check

    def _map_action(self, action: np.ndarray):
        """[-1,1] -> engineering units -> SI. returns both."""
        a = np.clip(action, -1.0, 1.0)

        # -1 -> min, +1 -> max
        rpm = cfg.RPM_MIN + (a[0] + 1) / 2 * (cfg.RPM_MAX - cfg.RPM_MIN)
        wob = cfg.WOB_MIN + (a[1] + 1) / 2 * (cfg.WOB_MAX - cfg.WOB_MIN)
        flow = cfg.FLOW_RATE_MIN + (a[2] + 1) / 2 * (cfg.FLOW_RATE_MAX - cfg.FLOW_RATE_MIN)

        rpm_hz = cfg.rpm_to_hz(rpm)
        wob_kg = cfg.tonnes_to_kg(wob)
        flow_m3s = cfg.lpm_to_m3s(flow)

        return rpm_hz, wob_kg, flow_m3s, rpm, wob, flow

    def _get_obs(self, raw_feedback: dict, action_normalized: np.ndarray) -> np.ndarray:
        """obs vector: normalised feedback + ECD stats + the action."""
        obs_parts = []

        # 10 feedback tags
        for tag in cfg.OBSERVATION_TAGS:
            val = raw_feedback.get(tag, 0.0)
            lo, hi = cfg.OBS_RANGES[tag]
            if hi - lo > 0:
                normalized = 2.0 * (val - lo) / (hi - lo) - 1.0  # [lo, hi] -> [-1, 1]
            else:
                normalized = 0.0
            obs_parts.append(normalized)

        # 2 ECD stats. std/limit is ~[0,1], stretch to [-1,1]. slope/limit is already centred
        ecd_std = self._compute_ecd_std()
        ecd_slope = self._compute_ecd_slope()
        ecd_std_norm = np.clip(2.0 * ecd_std / cfg.ECD_STD_LIM_KGM3 - 1.0, -2.0, 2.0) if cfg.ECD_STD_LIM_KGM3 > 0 else 0.0
        ecd_slope_norm = np.clip(ecd_slope / (cfg.ECD_SLOPE_LIM_KGM3_PER_S + 1e-12), -2.0, 2.0)
        obs_parts.append(float(ecd_std_norm))
        obs_parts.append(float(ecd_slope_norm))

        # our last action, already in [-1,1]
        obs_parts.extend(action_normalized.tolist())

        obs = np.array(obs_parts, dtype=np.float32)
        return np.clip(obs, self.observation_space.low, self.observation_space.high)

    def _compute_ecd_std(self) -> float:
        """std of ECD over the window, kg/m3"""
        if len(self._ecd_history) < 3:
            return 0.0
        return float(np.std(self._ecd_history[-cfg.ECD_HISTORY_WINDOW:]))

    def _compute_ecd_slope(self) -> float:
        """least squares slope of ECD over the window, kg/m3 per second"""
        window = self._ecd_history[-cfg.ECD_HISTORY_WINDOW:]
        if len(window) < 3:
            return 0.0
        x = np.arange(len(window), dtype=np.float64)
        y = np.array(window, dtype=np.float64)
        x_mean = x.mean()
        y_mean = y.mean()
        num = np.sum((x - x_mean) * (y - y_mean))
        den = np.sum((x - x_mean) ** 2)
        if den < 1e-12:
            return 0.0
        slope_per_step = num / den
        # per step -> per second
        return slope_per_step / cfg.STEP_DURATION

    def _compute_spp_std(self) -> float:
        """std of SPP over the window, Pa"""
        if len(self._spp_history) < 3:
            return 0.0
        return float(np.std(self._spp_history[-cfg.SPP_HISTORY_WINDOW:]))

    def _classify_regime(self) -> str:
        """ECD regime from info.md sec 4. only logged, not in the reward."""
        thresholds = cfg.REGIME_THRESHOLDS
        ecd_std = self._compute_ecd_std()
        ecd_slope = self._compute_ecd_slope()

        # jump = big change in one step
        if self._prev_ecd is not None and len(self._ecd_history) >= 2:
            delta_ecd = abs(self._ecd_history[-1] - self._prev_ecd)
            if delta_ecd > thresholds["jump_delta_ecd"]:
                return "Jump"

        if ecd_std > thresholds["oscillation_ecd_std"]:
            return "Oscillation"

        if ecd_slope > thresholds["drift_up_slope"]:
            return "Drift Up"

        if ecd_slope < thresholds["drift_down_slope"]:
            return "Drift Down"

        if ecd_std < thresholds["stable_ecd_std"] and abs(ecd_slope) < thresholds["stable_slope_abs"]:
            return "Stable"

        # in between, call it stable
        return "Stable"

    def _get_regime_action_policy(self, regime: str) -> str:
        """what info.md sec 4 says to do per regime. only reported."""
        policies = {
            "Stable": "Allow optimization",
            "Drift Up": "Small adjustments only",
            "Drift Down": "Restrict RPM changes",
            "Oscillation": "Only diagnostic actions",
            "Jump": "No action",
        }
        return policies.get(regime, "Allow optimization")

    def _check_safety_constraints(self, raw_feedback: dict, rpm_hz: float,
                                   flow_m3s: float) -> tuple:
        """hard limits C1-C8. returns (all_safe, violations, penalty)"""
        ecd = raw_feedback.get("DownholeECD", 0.0)    # kg/m3
        spp = raw_feedback.get("SPP", 0.0)             # Pa
        torque = raw_feedback.get("SurfaceTorque", 0.0) # Nm
        wob_kg = raw_feedback.get("WOB", 0.0)          # kg, the commanded value, injected in step()
        wob_n = wob_kg * 9.81

        violations = []
        penalty = 0.0

        # C1
        if ecd > cfg.ECD_MAX_KGM3:
            violations.append(f"C1: ECD={cfg.kgm3_to_sg(ecd):.3f} sg > 1.78 sg (fracture risk)")
            penalty += cfg.SAFETY_VIOLATION_PENALTY

        # C2. pore pressure is ~1.566 sg so this limit sits below it
        if ecd < cfg.ECD_MIN_KGM3 and ecd > 0:  # 0 = no reading
            violations.append(f"C2: ECD={cfg.kgm3_to_sg(ecd):.3f} sg < 1.50 sg (kick risk)")
            penalty += cfg.SAFETY_VIOLATION_PENALTY

        # C3, ECD rate over a 5 step window, one step is too noisy
        C3_WINDOW = 5
        if len(self._ecd_history) >= C3_WINDOW:
            recent = self._ecd_history[-C3_WINDOW:]
            decd_dt = abs(recent[-1] - recent[0]) / ((C3_WINDOW - 1) * cfg.STEP_DURATION)  # kg/m3 per s
            if decd_dt > cfg.sg_to_kgm3(0.05) / 60.0:  # 0.05 sg/min
                violations.append(f"C3: dECD/dt={cfg.kgm3_to_sg(decd_dt * 60):.4f} sg/min (too fast)")
                penalty += cfg.SAFETY_VIOLATION_PENALTY * 0.5

        # C4
        if spp > cfg.SPP_LIMIT:
            violations.append(f"C4: SPP={cfg.pa_to_bar(spp):.1f} bar > 200 bar (pump limit)")
            penalty += cfg.SAFETY_VIOLATION_PENALTY

        # C5
        if torque > cfg.TORQUE_LIMIT:
            violations.append(f"C5: Torque={cfg.nm_to_knm(torque):.1f} kN·m > 60 kN·m (drive limit)")
            penalty += cfg.SAFETY_VIOLATION_PENALTY

        # C6-C8 cant actually trip, the action box is inside them
        if flow_m3s > cfg.FLOW_LIMIT_M3S:
            violations.append(f"C6: Flow > 2200 L/min (pump capacity)")
            penalty += cfg.SAFETY_VIOLATION_PENALTY

        if rpm_hz > cfg.RPM_LIMIT_HZ:
            violations.append(f"C7: RPM > 180 rpm (motor limit)")
            penalty += cfg.SAFETY_VIOLATION_PENALTY

        if wob_n > cfg.WOB_LIMIT_N:
            violations.append(f"C8: WOB={wob_n/1000:.1f} kN > 140 kN (structural)")
            penalty += cfg.SAFETY_VIOLATION_PENALTY

        all_safe = len(violations) == 0
        return all_safe, violations, penalty

    def _check_stability_constraints(self) -> tuple:
        """stability warnings S1-S4. returns (warnings, penalty). the penalty
        only gets logged, stability is already paid through the bonus."""
        warnings = []
        penalty = 0.0

        ecd_std = self._compute_ecd_std()
        spp_std = self._compute_spp_std()
        ecd_slope = self._compute_ecd_slope()

        # S1
        if ecd_std > cfg.ECD_STD_LIM_KGM3:
            warnings.append(f"S1: σ_ECD={cfg.kgm3_to_sg(ecd_std):.4f} sg > 0.02 sg (oscillation)")
            penalty += 0.3

        # S2
        if spp_std > cfg.SPP_STD_LIM_PA:
            warnings.append(f"S2: σ_SPP={cfg.pa_to_bar(spp_std):.2f} bar > 5 bar (unstable)")
            penalty += 0.3

        # S3
        ecd_slope_sgmin = abs(cfg.kgm3_to_sg(ecd_slope)) * 60  # sg/min
        if ecd_slope_sgmin > 0.02:
            warnings.append(f"S3: |slope(ECD)|={ecd_slope_sgmin:.4f} sg/min > 0.02 (drift)")
            penalty += 0.2

        # S4
        if len(self._rop_history) >= 5:
            rop_var = float(np.var(self._rop_history[-cfg.ECD_HISTORY_WINDOW:]))
            if rop_var > cfg.ROP_VARIANCE_THRESHOLD:
                warnings.append(f"S4: ROP variance={rop_var:.2e} (bit dysfunction)")
                penalty += 0.2

        return warnings, penalty

    def _compute_performance_score(self, raw_feedback: dict, rpm_hz: float) -> tuple:
        """6 KPI performance score, info.md sec 8 level 1. returns (score, components)"""
        w = cfg.PERFORMANCE_WEIGHTS_REVISED if self._use_revised_reward else cfg.PERFORMANCE_WEIGHTS
        rop = raw_feedback.get("InstantaneousROP", 0.0)        # m/s
        torque = raw_feedback.get("SurfaceTorque", 0.0)         # Nm
        flow_out = raw_feedback.get("FlowRateOut", 0.0)         # m3/s
        wob_kg = raw_feedback.get("WOB", 0.0)                   # kg, commanded

        # ROP_s
        rop_s = np.clip(rop / cfg.ROP_REF, 0.0, 2.0) if cfg.ROP_REF > 0 else 0.0

        # T_s. default is linear at every torque level. gated version is zero
        # below TORQUE_GATE_FRACTION of the limit and ramps to full at the limit
        if cfg.TORQUE_REF_NM <= 0:
            t_s = 0.0
        elif self._use_revised_reward:
            gate = cfg.TORQUE_GATE_FRACTION * cfg.TORQUE_REF_NM
            span = max((1.0 - cfg.TORQUE_GATE_FRACTION) * cfg.TORQUE_REF_NM, 1e-9)
            t_s = np.clip((torque - gate) / span, 0.0, 2.0)
        else:
            t_s = np.clip(torque / cfg.TORQUE_REF_NM, 0.0, 2.0)

        # MSE_s. MSE = W/Ab + 2 pi T f / (Ab v), Pa
        wob_n = wob_kg * 9.81
        if rop > 1e-6 and rpm_hz > 0:
            mse = (wob_n / cfg.BIT_AREA_M2
                   + 2.0 * np.pi * torque * rpm_hz / (cfg.BIT_AREA_M2 * rop))
        else:
            mse = cfg.MSE_REF_PA  # not drilling, mse is undefined, use the ref
        mse_s = np.clip(mse / cfg.MSE_REF_PA, 0.0, 3.0) if cfg.MSE_REF_PA > 0 else 0.0

        # ECD_s
        ecd_std = self._compute_ecd_std()
        ecd_s = np.clip(ecd_std / cfg.ECD_STD_REF_KGM3, 0.0, 2.0) if cfg.ECD_STD_REF_KGM3 > 0 else 0.0

        # HC_s, flow out as the hole cleaning proxy
        hc_s = np.clip(flow_out / cfg.FLOW_REF_M3S, 0.0, 2.0) if cfg.FLOW_REF_M3S > 0 else 0.0

        # RPM_s, distance from optimal
        rpm_dev = abs(rpm_hz - cfg.RPM_OPTIMAL_HZ)
        rpm_s = np.clip(rpm_dev / cfg.RPM_OPTIMAL_HZ, 0.0, 2.0) if cfg.RPM_OPTIMAL_HZ > 0 else 0.0

        score = (w["rop"] * rop_s
                 - w["torque"] * t_s
                 - w["mse"] * mse_s
                 - w["ecd"] * ecd_s
                 + w["hc"] * hc_s
                 - w["rpm"] * rpm_s)

        components = {
            "rop_s": float(rop_s),
            "t_s": float(t_s),
            "mse": float(mse),
            "mse_mpa": float(mse / 1e6),
            "mse_s": float(mse_s),
            "ecd_std_kgm3": float(ecd_std),
            "ecd_std_sg": float(cfg.kgm3_to_sg(ecd_std)),
            "ecd_s": float(ecd_s),
            "hc_s": float(hc_s),
            "rpm_s": float(rpm_s),
            "rop_component": float(w["rop"] * rop_s),
            "torque_component": float(-w["torque"] * t_s),
            "mse_component": float(-w["mse"] * mse_s),
            "ecd_component": float(-w["ecd"] * ecd_s),
            "hc_component": float(w["hc"] * hc_s),
            "rpm_component": float(-w["rpm"] * rpm_s),
        }

        return float(score), components

    def _compute_safety_margin(self, raw_feedback: dict) -> tuple:
        """min over the 4 normalised margins: ECD high (1.76 sg), ECD low
        (1.48 sg), SPP (200 bar), torque (60 kNm). returns (margin, dict)"""
        ecd = raw_feedback.get("DownholeECD", 0.0)     # kg/m3
        spp = raw_feedback.get("SPP", 0.0)               # Pa
        torque = raw_feedback.get("SurfaceTorque", 0.0)   # Nm

        # raw margins in readable units, for logging
        margin_ecd_high = cfg.kgm3_to_sg(cfg.ECD_MARGIN_HIGH_KGM3 - ecd)      # sg
        margin_ecd_low = cfg.kgm3_to_sg(ecd - cfg.ECD_MARGIN_LOW_KGM3)        # sg
        margin_spp = cfg.pa_to_bar(cfg.SPP_MARGIN_PA - spp)                    # bar
        margin_torque = cfg.nm_to_knm(cfg.TORQUE_MARGIN_NM - torque)           # kNm

        # relative margins, otherwise the min() is just whichever unit is biggest
        ecd_high_ref = cfg.kgm3_to_sg(cfg.ECD_MARGIN_HIGH_KGM3)
        ecd_low_ref = cfg.kgm3_to_sg(cfg.ECD_MARGIN_LOW_KGM3)
        spp_ref = cfg.pa_to_bar(cfg.SPP_MARGIN_PA)
        torque_ref = cfg.nm_to_knm(cfg.TORQUE_MARGIN_NM)

        rel_ecd_high = margin_ecd_high / ecd_high_ref if ecd_high_ref > 0 else 0.0
        rel_ecd_low = margin_ecd_low / ecd_low_ref if ecd_low_ref > 0 else 0.0
        rel_spp = margin_spp / spp_ref if spp_ref > 0 else 0.0
        rel_torque = margin_torque / torque_ref if torque_ref > 0 else 0.0

        safety_margin = min(rel_ecd_high, rel_ecd_low, rel_spp, rel_torque)

        margins = {
            "margin_ecd_high_sg": float(margin_ecd_high),
            "margin_ecd_low_sg": float(margin_ecd_low),
            "margin_spp_bar": float(margin_spp),
            "margin_torque_knm": float(margin_torque),
            "rel_ecd_high": float(rel_ecd_high),
            "rel_ecd_low": float(rel_ecd_low),
            "rel_spp": float(rel_spp),
            "rel_torque": float(rel_torque),
            "safety_margin": float(safety_margin),
        }

        return float(safety_margin), margins

    def _compute_stability_score(self) -> tuple:
        """-(sigma_ECD/lim + sigma_SPP/lim + |slope|/lim). 0 is perfectly
        stable. returns (score, components)"""
        ecd_std = self._compute_ecd_std()
        spp_std = self._compute_spp_std()
        ecd_slope = abs(self._compute_ecd_slope())

        ecd_std_ratio = ecd_std / cfg.ECD_STD_LIM_KGM3 if cfg.ECD_STD_LIM_KGM3 > 0 else 0.0
        spp_std_ratio = spp_std / cfg.SPP_STD_LIM_PA if cfg.SPP_STD_LIM_PA > 0 else 0.0
        slope_ratio = ecd_slope / cfg.ECD_SLOPE_LIM_KGM3_PER_S if cfg.ECD_SLOPE_LIM_KGM3_PER_S > 0 else 0.0

        stability_score = -(ecd_std_ratio + spp_std_ratio + slope_ratio)

        components = {
            "ecd_std_ratio": float(ecd_std_ratio),
            "spp_std_ratio": float(spp_std_ratio),
            "slope_ratio": float(slope_ratio),
        }

        return float(stability_score), components

    def _compute_reward(self, raw_feedback: dict, action: np.ndarray,
                         rpm_hz: float = None, flow_m3s: float = None) -> tuple:
        """the base reward. 0.3*performance + safety margin bonus + stability
        bonus - violation penalty - smoothness - vibration. returns (reward, info)"""
        # rolling windows
        ecd = raw_feedback.get("DownholeECD", 0.0)
        spp = raw_feedback.get("SPP", 0.0)
        rop = raw_feedback.get("InstantaneousROP", 0.0)
        torque = raw_feedback.get("SurfaceTorque", 0.0)

        self._ecd_history.append(ecd)
        if len(self._ecd_history) > cfg.ECD_HISTORY_WINDOW:
            self._ecd_history = self._ecd_history[-cfg.ECD_HISTORY_WINDOW:]

        self._spp_history.append(spp)
        if len(self._spp_history) > cfg.SPP_HISTORY_WINDOW:
            self._spp_history = self._spp_history[-cfg.SPP_HISTORY_WINDOW:]

        self._rop_history.append(rop)
        if len(self._rop_history) > cfg.ECD_HISTORY_WINDOW:
            self._rop_history = self._rop_history[-cfg.ECD_HISTORY_WINDOW:]

        self._torque_history.append(torque)
        if len(self._torque_history) > cfg.TORQUE_HISTORY_WINDOW:
            self._torque_history = self._torque_history[-cfg.TORQUE_HISTORY_WINDOW:]

        perf_score, perf_components = self._compute_performance_score(raw_feedback, rpm_hz)
        safety_margin, margin_info = self._compute_safety_margin(raw_feedback)
        stability_score, stability_components = self._compute_stability_score()

        # hard limits
        all_safe, violations, safety_penalty = self._check_safety_constraints(
            raw_feedback, rpm_hz or 0.0, flow_m3s or 0.0
        )

        # S1-S4 warnings. logged only, stability is already in the bonus, dont count it twice
        stability_warnings, stability_penalty = self._check_stability_constraints()

        action_diff = np.linalg.norm(action - self._prev_action)
        smoothness_penalty = np.clip(action_diff / 2.0, 0.0, 1.0)

        # torque vibration
        vibration_penalty = 0.0
        torque_var = 0.0
        if len(self._torque_history) >= 3:
            torque_var = float(np.var(self._torque_history))
            if torque_var > cfg.TORQUE_VARIANCE_THRESHOLD:
                vibration_penalty = np.clip(
                    (torque_var - cfg.TORQUE_VARIANCE_THRESHOLD)
                    / (4.0 * cfg.TORQUE_VARIANCE_THRESHOLD),
                    0.0, 1.0
                )

        # put it together, safety > stability > performance
        safety_margin_bonus = np.clip(safety_margin, 0.0, 1.0) * cfg.SAFETY_MARGIN_WEIGHT
        stability_bonus = np.clip(stability_score + 3.0, 0.0, 3.0) / 3.0 * cfg.STABILITY_BONUS_WEIGHT

        reward = (
            cfg.PERFORMANCE_WEIGHT * perf_score
            + safety_margin_bonus
            + stability_bonus
            - safety_penalty
            - cfg.SMOOTHNESS_WEIGHT * smoothness_penalty
            - 0.1 * vibration_penalty
        )

        self._prev_ecd = ecd  # for the jump check next step

        # everything for logging (info.md sec 3)
        info = {
            "rop": rop,
            "rop_mh": cfg.rop_ms_to_mh(rop),
            "torque": torque,
            "torque_knm": cfg.nm_to_knm(torque),
            "ecd_kgm3": ecd,
            "ecd_sg": cfg.kgm3_to_sg(ecd),
            "spp_pa": spp,
            "spp_bar": cfg.pa_to_bar(spp),
            "bhp": raw_feedback.get("DownholePressure", 0.0),
            "flow_out_m3s": raw_feedback.get("FlowRateOut", 0.0),

            "mse": perf_components["mse"],
            "mse_mpa": perf_components["mse_mpa"],

            "ecd_std_kgm3": self._compute_ecd_std(),
            "ecd_std_sg": cfg.kgm3_to_sg(self._compute_ecd_std()),
            "spp_std_pa": self._compute_spp_std(),
            "spp_std_bar": cfg.pa_to_bar(self._compute_spp_std()),
            "ecd_slope_kgm3_per_s": self._compute_ecd_slope(),
            "ecd_slope_sg_per_min": cfg.kgm3_to_sg(self._compute_ecd_slope()) * 60,

            "performance_score": perf_score,
            "safety_margin": safety_margin,
            "stability_score": stability_score,

            "performance_components": perf_components,
            "safety_margins": margin_info,
            "stability_components": stability_components,

            "all_safe": all_safe,
            "safety_violations": violations,
            "stability_warnings": stability_warnings,

            "torque_variance": torque_var,
            "vibration_penalty": vibration_penalty,

            "smoothness_penalty": float(smoothness_penalty),
            "safety_penalty": float(safety_penalty),
            "stability_penalty": float(stability_penalty),
            "safety_margin_bonus": float(safety_margin_bonus),
            "stability_bonus": float(stability_bonus),

            # what actually went into the reward
            "reward_breakdown": {
                "performance_score": float(cfg.PERFORMANCE_WEIGHT * perf_score),
                "safety_margin_bonus": float(safety_margin_bonus),
                "stability_bonus": float(stability_bonus),
                "safety_penalty": float(-safety_penalty),
                "smoothness_penalty": float(-cfg.SMOOTHNESS_WEIGHT * smoothness_penalty),
                "vibration_penalty": float(-0.1 * vibration_penalty),
            },
        }

        return float(reward), info

    def _get_curriculum_range(self) -> tuple:
        """(ucs_min, ucs_max) for this episode from cfg.CURRICULUM_STAGES"""
        ep = self._episode_count
        ucs_min, ucs_max = 1.0, 1.0

        for stage_start, stage_min, stage_max in cfg.CURRICULUM_STAGES:
            if ep >= stage_start:
                ucs_min, ucs_max = stage_min, stage_max
            else:
                break

        return ucs_min, ucs_max

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._episode_count += 1

        # stop the last sim
        if self._sim is not None:
            try:
                self._sim.stop()
            except Exception:
                pass
            self._sim = None

        # login once, reuse the session
        if self._session is None:
            openlab.login.switch_user(
                new_user=cfg.OPENLAB_EMAIL,
                new_key=cfg.OPENLAB_API_KEY,
                new_licenseguid=cfg.OPENLAB_LICENSE_GUID,
                environment='prod'
            )
            self._session = openlab.http_client(
                username=cfg.OPENLAB_EMAIL,
                apikey=cfg.OPENLAB_API_KEY,
                licenseguid=cfg.OPENLAB_LICENSE_GUID,
            )

        # kill leftover running sims, max concurrent is 2. eval envs skip this
        # or theyd kill the training sim
        if self._cleanup_on_reset:
            self._cleanup_old_sims()

        # UCS for this episode
        if self._ucs_random_mode == "profiles":
            self._current_ucs = float(np.random.choice(cfg.UCS_PROFILES))
        elif self._ucs_random_mode == "continuous":
            self._current_ucs = float(
                np.random.uniform(self._ucs_random_min, self._ucs_random_max)
            )
        elif self._ucs_random_mode == "curriculum":
            ucs_min, ucs_max = self._get_curriculum_range()
            if ucs_min == ucs_max:
                self._current_ucs = float(ucs_min)
            else:
                self._current_ucs = float(np.random.uniform(ucs_min, ucs_max))
        elif self._ucs_multiplier is not None:
            self._current_ucs = self._ucs_multiplier
        else:
            self._current_ucs = None

        config_name = self._base_config_name

        # scaled config if the multiplier isnt 1
        if self._current_ucs is not None and self._current_ucs != 1.0:
            config_name = self._get_or_create_ucs_config(self._current_ucs)
            if self._ucs_random_mode:
                if self._ucs_random_mode == "curriculum":
                    ucs_min, ucs_max = self._get_curriculum_range()
                    print(f"[DrillingEnv] Ep {self._episode_count}: "
                          f"curriculum [{ucs_min:.1f}–{ucs_max:.1f}] → UCS={self._current_ucs:.2f}")
                else:
                    print(f"[DrillingEnv] Ep {self._episode_count}: "
                          f"UCS={self._current_ucs:.2f} ({self._ucs_random_mode})")

        sim_name = f"RL_ep{self._episode_count}_{np.random.randint(int(1e6))}"
        self._sim = self._session.create_simulation(
            config_name,
            sim_name,
            cfg.INITIAL_BIT_DEPTH,
            StepDuration=cfg.STEP_DURATION,
            UseTransientMechanicalModel=cfg.USE_TRANSIENT_MECHANICAL,
            UseDetournayROPModel=self._use_detournay_rop,
        )

        # remember this sim, drop old finished ones (server cap, cfg.MAX_STORED_SIMS_KEEP)
        self._register_and_prune_sims(getattr(self._sim, "sim_id", None))

        self._timestep = 0
        self._prev_action = np.zeros(3, dtype=np.float32)
        self._prev_rop = 0.0
        self._torque_history = []
        self._ecd_history = []
        self._spp_history = []
        self._rop_history = []
        self._prev_ecd = None

        # warmup at mid setpoints so circulation settles before the policy touches anything
        self._apply_neutral_setpoints()
        for t in range(1, cfg.WARMUP_STEPS + 1):
            self._sim.step(t)
        self._timestep = cfg.WARMUP_STEPS

        raw = self._fetch_results(self._timestep)

        # depth tracking for the ROP calc
        self._prev_bit_depth = raw.get("BitDepth", cfg.INITIAL_BIT_DEPTH)

        obs = self._get_obs(raw, self._prev_action)
        info = {
            "raw_feedback": raw,
            "timestep": self._timestep,
            "ucs_multiplier": self._current_ucs or 1.0,
        }

        return obs, info

    def step(self, action: np.ndarray):
        action = np.asarray(action, dtype=np.float32)

        rpm_hz, wob_kg, flow_m3s, rpm_eng, wob_eng, flow_eng = self._map_action(action)

        # setpoints. plain floats, the client json-serialises them
        self._sim.setpoints.SurfaceRPM = float(rpm_hz)
        self._sim.setpoints.DesiredWOB = float(wob_kg)
        self._sim.setpoints.WOBAutoDriller = True
        if self._wob_proportional_gain is not None:
            self._sim.setpoints.WOBProportionalGain = float(self._wob_proportional_gain)
        self._sim.setpoints.FlowRateIn = float(flow_m3s)
        self._sim.setpoints.DesiredROP = 0.04  # ~144 m/h, just under the api max, so it never caps the autodriller
        self._sim.setpoints.TopOfStringVelocity = cfg.TOP_OF_STRING_VELOCITY_DEFAULT

        self._timestep += 1
        try:
            self._sim.step(self._timestep)
        except Exception as e:
            # sim died on us, end the episode
            print(f"[DrillingEnv] Simulation error at timestep {self._timestep}: {e}")
            obs = np.zeros(self.observation_space.shape, dtype=np.float32)
            return obs, -1.0, True, False, {"error": str(e)}

        raw = self._fetch_results(self._timestep)

        # transient model returns 0 for InstantaneousROP, recompute it from BitDepth
        bit_depth_now = raw.get("BitDepth", self._prev_bit_depth)
        computed_rop = max(0.0, (bit_depth_now - self._prev_bit_depth) / cfg.STEP_DURATION)
        raw["InstantaneousROP"] = computed_rop
        self._prev_bit_depth = bit_depth_now

        # WOB tag reads 0 in transient mode too. use the commanded value, the
        # autodriller tracks it. needed for MSE and C8
        raw["WOB"] = wob_kg

        obs = self._get_obs(raw, action)
        reward, reward_info = self._compute_reward(raw, action, rpm_hz=rpm_hz, flow_m3s=flow_m3s)

        # completion shaping, see cfg. both terms at 0 -> original reward
        delta_depth_m = computed_rop * cfg.STEP_DURATION   # m this step
        progress_reward = cfg.DEPTH_PROGRESS_WEIGHT * delta_depth_m
        reward += progress_reward - cfg.TIME_STEP_PENALTY
        reward_info["reward_breakdown"]["depth_progress"] = progress_reward
        reward_info["reward_breakdown"]["time_penalty"] = -cfg.TIME_STEP_PENALTY

        bit_depth = raw.get("BitDepth", cfg.INITIAL_BIT_DEPTH)
        terminated = bit_depth >= cfg.TARGET_BIT_DEPTH  # reached target
        truncated = (self._timestep >= self.max_steps) and not terminated

        # the sim has its own max step too
        if self._sim.max_timeStep and self._timestep >= self._sim.max_timeStep - 1:
            if not terminated:
                truncated = True

        if terminated:
            reward += cfg.DEPTH_COMPLETION_BONUS
            reward_info["reward_breakdown"]["depth_bonus"] = cfg.DEPTH_COMPLETION_BONUS

        info = {
            "raw_feedback": raw,
            "timestep": self._timestep,
            "bit_depth": bit_depth,
            "depth_progress": bit_depth - cfg.INITIAL_BIT_DEPTH,
            "target_reached": terminated,
            "ucs_multiplier": self._current_ucs or 1.0,
            "action_engineering": {"rpm": rpm_eng, "wob_tonnes": wob_eng, "flow_lpm": flow_eng},
            **reward_info,
        }

        self._prev_action = action.copy()
        self._prev_rop = raw.get("InstantaneousROP", 0.0)

        return obs, reward, terminated, truncated, info

    def _apply_neutral_setpoints(self):
        """mid range setpoints for the warmup"""
        mid_rpm = (cfg.RPM_MIN + cfg.RPM_MAX) / 2
        mid_wob = (cfg.WOB_MIN + cfg.WOB_MAX) / 2
        mid_flow = (cfg.FLOW_RATE_MIN + cfg.FLOW_RATE_MAX) / 2

        self._sim.setpoints.SurfaceRPM = cfg.rpm_to_hz(mid_rpm)
        self._sim.setpoints.DesiredWOB = cfg.tonnes_to_kg(mid_wob)
        self._sim.setpoints.WOBAutoDriller = True
        if self._wob_proportional_gain is not None:
            self._sim.setpoints.WOBProportionalGain = float(self._wob_proportional_gain)
        self._sim.setpoints.FlowRateIn = cfg.lpm_to_m3s(mid_flow)
        self._sim.setpoints.DesiredROP = 0.04
        self._sim.setpoints.TopOfStringVelocity = cfg.TOP_OF_STRING_VELOCITY_DEFAULT

    def _fetch_results(self, timestep: int) -> dict:
        """pull every obs tag for this timestep"""
        tags = list(cfg.OBSERVATION_TAGS)
        self._sim.get_results(timestep, tags)

        raw = {}
        for tag in cfg.OBSERVATION_TAGS:
            result_dict = getattr(self._sim.results, tag, {})
            raw[tag] = result_dict.get(timestep, 0.0)

        return raw

    def _register_and_prune_sims(self, sim_id):
        """remember the sim, delete old finished ones so we stay under the server
        cap. results are read live during the episode so old sims arent needed
        after. only the training env deletes, eval envs just register, otherwise
        they race the live training sim. delete failures are ignored"""
        if not sim_id:
            return
        cls = type(self)
        cls._sim_registry.append(sim_id)
        if not self._cleanup_on_reset:
            return
        keep = cfg.MAX_STORED_SIMS_KEEP
        while len(cls._sim_registry) > keep:
            old = cls._sim_registry.pop(0)
            try:
                self._session.delete_simulation(old)
            except Exception:
                pass  # already gone, fine

    def _cleanup_old_sims(self):
        """stop anything still running, frees the concurrent slots"""
        try:
            sims = self._session.simulations()
            for s in sims:
                if s['Status'] in ('Running', 'Created'):
                    try:
                        self._session.end_simulation(s['SimulationID'])
                    except Exception:
                        pass
        except Exception:
            pass

    def _get_or_create_ucs_config(self, multiplier: float) -> str:
        """config with every layer UCS scaled by the multiplier. reuses one
        with the same name if its already on the server"""
        base_name = self._base_config_name
        scaled_name = f"{base_name}_ucs{multiplier:.1f}"
        try:
            configs = self._session.configurations()
            for c in configs:
                if c.get("Name") == scaled_name:
                    return scaled_name
        except Exception:
            pass

        try:
            configs = self._session.configurations()
            base_id = None
            for c in configs:
                if c.get("Name") == base_name:
                    base_id = c.get("ConfigurationID") or c.get("Id")
                    break
            if base_id is None:
                print(f"[DrillingEnv] Base config '{base_name}' not found, using as-is")
                return base_name

            data = self._session.configuration_data(base_id)
            # api only takes UCS in [5, 200] MPa
            UCS_API_MIN = 5_000_000
            UCS_API_MAX = 200_000_000
            for fs in data.get("FormationStrength", []):
                scaled = fs["UCS"] * multiplier
                fs["UCS"] = max(UCS_API_MIN, min(UCS_API_MAX, scaled))
            self._session.create_configuration(scaled_name, data)
            print(f"[DrillingEnv] Created config '{scaled_name}' (UCS x{multiplier})")
            return scaled_name
        except Exception as e:
            print(f"[DrillingEnv] Failed to create UCS config: {e}, using base")
            return base_name

    def close(self):
        """stop the sim"""
        if self._sim is not None:
            try:
                self._sim.stop()
            except Exception:
                pass
            self._sim = None

    def render(self):
        if self.render_mode == "human" and self._timestep > 0:
            # recomputed rop, the raw tag is 0
            rop = self._prev_rop
            spp = getattr(self._sim.results, "SPP", {}).get(self._timestep, 0)
            torque = getattr(self._sim.results, "SurfaceTorque", {}).get(self._timestep, 0)
            ecd = getattr(self._sim.results, "DownholeECD", {}).get(self._timestep, 0)
            print(
                f"t={self._timestep:4d} | ROP={rop*1000:.2f} mm/s | "
                f"SPP={spp/1e5:.1f} bar | "
                f"Torque={torque/1000:.1f} kN·m | ECD={ecd/1000:.3f} sg"
            )


gym.register(
    id="DrillingROP-v0",
    entry_point="drilling_env:DrillingEnv",
    max_episode_steps=30000,
)
