# Environment and Rule-Based Model

## 1. Environment Idea
A live well, open-hole section near the bit, here Flow, RPM, and WOB changes will affect ECD, ROP, torque, and stability most clearly.

## 2. Starting Setup
* **Open-hole interval:** 1800–2200m
* **Initial bit depth:** 2497 m
* **Baseline Flow:** 1800-2200 L/min
* **Baseline RPM:** 80 - 120 rpm
* **WOB:** 8-12 ton
* **ROP:** Check
* **Top of string velocity:** 0.02 – 0.05 m/s

## 3. KPIs

| KPI | Symbol | Unit | Statistic Used | Tier |
| :--- | :--- | :--- | :--- | :--- |
| Equivalent Circulating Density | ECD | sg | mean, max | Safety |
| ECD rate | dECD/dt | sg/min | max | Safety |
| Stand pipe pressure | SPP | bar | max | Safety |
| Surface torque | T | kN·m | max | Safety |
| Flowout | Q_out | L/min | mean | Safety |
| Rate of penetration | ROP | m/h | mean | Performance |
| Mechanical Specific Energy | MSE | MPa | mean | Performance |
| ECD standard deviation | $\sigma_{ECD}$ | sg | std | Stability |
| SPP standard deviation | $\sigma_{SPP}$ | bar | std | Stability |
| ECD trend slope | slope(ECD) | sg/min | slope | Stability |

**Tier Definitions**
| Tier | Meaning |
| :--- | :--- |
| Safety | Hard constraints |
| Stability | Warning Constraints |
| Performance | Optimization |

## 4. Regime Classification
*Simple regimes:*

**Detection Rules**
| Regime | Detection Rule |
| :--- | :--- |
| Stable | $\sigma_{ECD} < 0.01$ and $\text{slope}(ECD) \approx 0$ |
| Drift Up | $\text{slope}(ECD) > 0.02$ sg/min |
| Drift Down | $\text{slope}(ECD) < -0.02$ sg/min |
| Oscillation | $\sigma_{ECD} > 0.02$ sg and periodic variation detected |
| Jump | Sudden $\Delta ECD > 0.05$ sg |

**Action Policies**
| Regime | Action Policy |
| :--- | :--- |
| Stable | Allow optimization |
| Drift Up | Small adjustments only |
| Drift Down | Restrict RPM changes |
| Oscillation | Only diagnostic actions |
| Jump | No action |

## 5. Scenarios Generation

## 6. Constraints Validation

**Safety Constraints Check**
| ID | KPI | Constraints | Reason |
| :--- | :--- | :--- | :--- |
| C1 | ECD max | $ECD_{max} \le 1.78$ | Fracture risk |
| C2 | ECD min | $ECD_{min} \le 1.50$ | Kick risk |
| C3 | dECD / dt | | Decd/dt |
| C4 | SPP max | $SPP_{max} \le 200$ bar | Pump limit |
| C5 | Torque max | $T_{max} \le 60$ kN·m | Drive limit |
| C6 | Flowrate | $Q \le 2200$ L/min | Pump capacity |
| C7 | RPM | $RPM \le 180$ rpm | Motor limit |
| C8 | WOB | $WOB \le 140$ kN | Structural |

**Stability Constraints Check**
| ID | KPI | Condition | Effect |
| :--- | :--- | :--- | :--- |
| S1 | $\sigma_{ECD}$ | >0.02 sg | oscillation warning |
| S2 | $\sigma_{SPP}$ | >5 bar | unstable hydraulics |
| S3 | Slope (ECD) | >0.02 sg/min | drift warning |
| S4 | ROP Variance | High Fluctuations | bit dysfunction |

## 7. Performance KPIs
$ROP_{mean}$ , MSE

## 8. Rule-Based Model Design

### Level 1: Performance Evaluation
*(Evaluated only if the candidate passes safety)*

| KPI | Objectives | Scale Versions |
| :--- | :--- | :--- |
| ROP | Maximize | $ROP_s = \frac{ROP}{ROP_{ref}}$ |
| Torque | Minimize | $T_s = \frac{Torque}{T_{lim}}$ |
| ECD Stability | ECD Stability | $ECD_s = \frac{ECD}{ECD_{lim}}$ |
| RPM | Efficient RPM | $RPM_{optimal} = \frac{|RPM - RPM_{opt}|}{RPM_{opt}}$ |
| Hole cleaning | Maximize | $HC_s = \frac{Flow}{Flow_{ref}}$ |
| MSE | Minimize | $MSE_s = \frac{MSE}{MSE_{ref}}$ |

**Scoring Equation:**
$$Score = w_1 \cdot ROP_s - w_2 \cdot T_s - w_3 \cdot MSE_s - w_4 \cdot ECD_s + w_5 \cdot HC_s - w_6 \cdot RPM_s$$
$$Score = 0.30 \cdot ROP_s - 0.20 \cdot T_s - 0.20 \cdot MSE_s - 0.15 \cdot ECD_s + 0.10 \cdot HC_s - 0.05 \cdot RPM_s$$

**Typical Weights:**
* $w_1$ = 0.30
* $w_2$ = 0.20
* $w_3$ = 0.20
* $w_4$ = 0.15
* $w_5$ = 0.10
* $w_6$ = 0.05

### Level 2: Safety Margin
We calculate:
$$Margin_{ECD,high} = 1.76 - ECD_{max}$$
$$Margin_{ECD,low} = ECD_{min} - 1.48$$
$$Margin_{SPP} = 200 - SPP_{max}$$
$$Margin_{Torque} = 60 - Torque_{max}$$

Then:
$$SafetyMargin = \min(Margin_{ECD,high}, Margin_{ECD,low}, Margin_{SPP}, Margin_{Torque})$$
*Rank 1st by highest Safety Margin.*

### Level 3: Stability
If two scenarios are both safe, compare their stability:
* $\sigma_{ECD} \rightarrow$ lower is better
* $\sigma_{SPP} \rightarrow$ lower is better
* $|\text{slope}(ECD)| \rightarrow$ lower is better
* *(Optionally)* $\sigma_{Torque}$ , $\sigma_{ROP} \rightarrow$ lower is better

**Stability Score:**
$$StabilityScore = - \frac{\sigma_{ECD}}{\sigma_{ECD,lim}} - \frac{\sigma_{SPP}}{\sigma_{SPP,lim}} - \frac{|\text{slope}(ECD)|}{\text{slope}_{lim}}$$
*A higher score means a more stable scenario.*

---

## 9. Example Scenario Evaluation
Suppose 3 scenarios give this output:

### Safety Margin Evaluation
| Scenario | $Margin_{ECD,high}$ | $Margin_{ECD,low}$ | $Margin_{SPP}$ | $Margin_{Torque}$ | Safety Margin Calculation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A** | $1.76 - 1.68 = 0.08$ | $1.52 - 1.48 = 0.04$ | $200 - 185 = 15$ | $60 - 48 = 12$ | $\min(0.08, 0.04, 15, 12) = 0.04$ |
| **B** | $1.76 - 1.70 = 0.06$ | $1.50 - 1.48 = 0.02$ | $200 - 190 = 10$ | $60 - 52 = 8$ | $\min(0.06, 0.02, 10, 8) = 0.02$ |
| **C** | $1.76 - 1.66 = 0.10$ | $1.55 - 1.48 = 0.07$ | $200 - 178 = 22$ | $60 - 44 = 16$ | $\min(0.10, 0.07, 22, 16) = 0.07$ |

**Safety Ranking:**
1.  **C** = 0.07
2.  **A** = 0.04
3.  **B** = 0.02
*Result:* C ranks above A, and A ranks above B.

### Stability Evaluation
| Scenario | $\frac{\sigma_{ECD}}{\sigma_{ECD,lim}}$ | $\frac{\sigma_{SPP}}{\sigma_{SPP,lim}}$ | $\frac{|\text{slope}(ECD)|}{\text{slope}_{lim}}$ | Stability Score Calculation |
| :--- | :--- | :--- | :--- | :--- |
| **A** | $0.010 / 0.02 = 0.50$ | $3 / 5 = 0.60$ | $0.008 / 0.02 = 0.40$ | $-(0.50 + 0.60 + 0.40) = -1.50$ |
| **B** | $0.012 / 0.02 = 0.60$ | $4 / 5 = 0.80$ | $0.010 / 0.02 = 0.50$ | $-(0.60 + 0.80 + 0.50) = -1.90$ |
| **C** | $0.009 / 0.02 = 0.45$ | $2.5 / 5 = 0.50$ | $0.006 / 0.02 = 0.30$ | $-(0.45 + 0.50 + 0.30) = -1.25$ |

**Stability Ranking:**
1.  **C** = -1.25 (best)
2.  **A** = -1.50
3.  **B** = -1.90
*Result:* Stability confirms C > A > B.

### Performance Evaluation
Using the simple scaled formula:
$$PerformanceScore = 0.30 \cdot \frac{ROP}{50} - 0.20 \cdot \frac{Torque}{60} - 0.20 \cdot \frac{MSE}{100} - 0.15 \cdot \frac{\sigma_{ECD}}{0.02} + 0.10 \cdot \frac{Flow}{2000} - 0.05 \cdot \frac{|RPM - 120|}{120}$$

**Scenario A**
* $ROP_s = 40/50 = 0.80$
* $Torque_s = 48/60 = 0.80$
* $MSE_s = 75/100 = 0.75$
* $ECD_s = 0.010/0.02 = 0.50$
* $Flow_s = 1800/2000 = 0.90$
* $RPM_{penalty} = |120-120|/120 = 0$
* $Score_A = 0.30(0.80) - 0.20(0.80) - 0.20(0.75) - 0.15(0.50) + 0.10(0.90) - 0.05(0)$
* $Score_A = 0.24 - 0.16 - 0.15 - 0.075 + 0.09 = -0.055$

**Scenario B**
* $ROP_s = 46/50 = 0.92$
* $Torque_s = 52/60 = 0.867$
* $MSE_s = 82/100 = 0.82$
* $ECD_s = 0.012/0.02 = 0.60$
* $Flow_s = 1890/2000 = 0.945$
* $RPM_{penalty} = |126-120|/120 = 0.05$
* $Score_B = 0.30(0.92) - 0.20(0.867) - 0.20(0.82) - 0.15(0.60) + 0.10(0.945) - 0.05(0.05)$
* $Score_B = 0.276 - 0.173 - 0.164 - 0.090 + 0.0945 - 0.0025 \approx -0.059$

**Scenario C**
* $ROP_s = 37/50 = 0.74$
* $Torque_s = 44/60 = 0.733$
* $MSE_s = 70/100 = 0.70$
* $ECD_s = 0.009/0.02 = 0.45$
* $Flow_s = 1800/2000 = 0.90$
* $RPM_{penalty} = |114-120|/120 = 0.05$
* $Score_C = 0.30(0.74) - 0.20(0.733) - 0.20(0.70) - 0.15(0.45) + 0.10(0.90) - 0.05(0.05)$
* $Score_C = 0.222 - 0.1466 - 0.14 - 0.0675 + 0.09 - 0.0025 \approx -0.0446$

**Performance Ranking:**
1.  **C** = -0.0446
2.  **A** = -0.055
3.  **B** = -0.059
*Result:* Performance confirms C > A > B.

### Final Conclusion
**Rank** = (Safety Margin, Stability Score, Performance Score)
