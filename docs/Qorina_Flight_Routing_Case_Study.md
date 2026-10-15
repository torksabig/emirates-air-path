# Qorina flight route optimisation

**Wind-aware routing under forecast uncertainty**

*An Aether Applied case study · Proof of concept results for partners*

---

## The opportunity

**Long-haul fuel still depends on imperfect weather**

Airlines already plan wind-aware routes. The harder question is whether the forecast available before departure is trustworthy enough to act on.

On a busy North Atlantic city pair, a path that looks optimal on a stale forecast can lose the advantage, or reverse it. Forecast age, ensemble disagreement, and comparison choice therefore belong in the fuel conversation, not only path geometry.

Aether Applied set out to test whether Qorina, a quantum-inspired decision model, could turn the forecast actually available before departure into a stable, inspectable route recommendation, with the human flight team keeping the final say.

## The challenge

**Exact maths can look strong when the forecast is fresh, and fail when it is old**

Certified flight planning already uses weather as an input. Classical learners can also be trained on the same fields. What the PoC needed to show was not a new map drawer, but an honest ranking against clear yardsticks:

- a wind-blind plan (great circle with a standard altitude profile)
- exact optimisation on the forecast used for decisions
- classical machine learning (MLP and Set Transformer) with the same inputs
- a hindsight optimum as a ceiling, not a live operating target

The trial had to stay advisory. It was not airline live operations, not a certified operational flight plan replacement, and not a claim of quantum hardware advantage.

## The approach

**One real route, real forecasts, frozen weights on unseen days**

| Scope item | PoC choice |
|---|---|
| Route / aircraft | London Heathrow (LHR) to New York JFK, Airbus A330-200 |
| Weather truth | ECMWF ERA5 reanalysis |
| Forecasts | Archived NOAA GFS and 11-member GEFS ensemble, from three weeks ahead to the morning of departure |
| Execution | GPU simulation of an approximately 14-qubit circuit (12 decision + 2 environment); not quantum hardware |
| Evaluation | Frozen weights on days and seasons never used for training |

Qorina encodes candidate lateral track, flight level, and Mach choices, with wind and procedural constraints, into the circuit. Forecast ensemble members are held as uncertainty inside the quantum state. Physics is the only hard veto: a move is refused only if the aircraft cannot fly it. Confidence and disagreement signals are logged for audit.

## The solution

**Trust-checked path choice from the forecast available at the time**

Value is created as a short ladder:

1. **Forecast** - start with the wind field issued before the flight  
2. **Trust check** - make uncertainty visible so the recommendation can be judged  
3. **Path choice** - compare candidate tracks and select a practical route  
4. **Fuel result** - the human flight team decides whether to use the recommendation  

The product framing is robust decision support under forecast uncertainty: show the fuel result against the right comparison, then leave the operational decision with people.

## The results

**Measured savings vs wind-blind, with forecast age as the key condition**

On ten unseen days covering every season, with no retraining, Qorina saved fuel against a wind-blind plan at every forecast age tested, on 9 of 10 days:

| Forecast age | Mean saving vs wind-blind | Share of available saving |
|---|---|---|
| 21 days | ~291 kg | ~34% |
| 10 days | ~430 kg | ~50% |
| 4 days | ~492 kg | ~57% |
| Freshest | ~555 kg | ~65% |

**Headline comparisons (same PoC set)**

- **vs wind-blind:** ~291 / 430 / 492 / 555 kg by forecast age; fuel saved on 9 of 10 days at every age.  
- **vs exact optimisation on the forecast:** exact wins when the forecast is freshest (~97% of available saving vs Qorina ~65%). At about 10 days, in this small sample, Qorina was competitive and was the best method tested.  
- **vs MLP / Set Transformer:** on a larger winter set (35 unseen days) with a ~10.5-day-old forecast, Qorina was on par with MLP and Set Transformer (~1.07-1.18% above the theoretical optimum).  

All Qorina figures are GPU simulations. Quantum hardware was not used. Fuel is from a physics model of the A330-200, not airline fuel records. Ten days at the 10-day horizon is a small sample; intervals are indicative.

### At a glance

| Metric | Observed result |
|---|---|
| Saving vs wind-blind (freshest) | ~555 kg per flight |
| Saving vs wind-blind (~10-day) | ~430 kg per flight |
| Days with a saving (all ages tested) | 9 of 10 |
| Fresh-forecast capture (exact / Qorina) | ~97% / ~65% |
| Winter set at ~10.5 days | On par with MLP and Set Transformer |

## What this does not claim

- Not airline live operations or a production dispatch tool  
- Not a replacement for certified operational flight plans (OFP)  
- Not proven network-wide airline savings  
- Not quantum hardware advantage (GPU simulation of ~14 qubits)  
- Not automatic decision-making; a human decides  

## Outlook

**Close the fresh-forecast gap; keep the long-range steadiness**

Next work aims at the bar exact optimisation sets on fresh forecasts (~97% of available saving), confirms the indicative 10-day lead on a larger all-season set, and extends toward problems exact single-aircraft optimisation cannot solve alone, such as shared tracks and levels.

For partners, the PoC already delivers a validated end-to-end pipeline on real flights, real weather, and real archived forecasts; a measured picture of how forecast age changes the value of routing advice; and an architecture that reached parity with established machine-learning methods in its first application, with decisions that can be audited part by part.

---

*Source: Qorina flight-routing proof of concept (LHR→JFK, A330-200). Aether Applied partner results. Indicative route-level evidence, not a network-wide operating result.*
