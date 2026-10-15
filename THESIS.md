# Thesis: Emirates air path / Qorina wedge

Plain language. Built from: understand → 9 commercial criteria → market scan → gaps.

## 1. Understand

Emirates burns less fuel when long haul paths catch better wind. The hard problem is not drawing a clever line on a map. It is trusting the weather.

This project (emirates-air-path / Intensity) checks forecast honesty on real flown tracks first (Phase 1). Only if the weather gate passes does it rank nearby paths by trip fuel in kilograms (Phase 2). A human still decides. It does not replace certified flight plans.

## 2. Criteria model (9 commercial dimensions)

Main scorecard is commercial, not only technical:

1. TAM  
2. SAM  
3. SOM  
4. Technical complexity (nested weather gate + fuel kg rules T1 to T8)  
5. Compliance  
6. Sales cycle  
7. How to reach  
8. Willingness to pay  
9. Problem cost  

Full definitions, know now vs research gaps: `CRITERIA.md`.

Nested technical one line rule: no weather pass, no path ranking. No written win number, no success claim.

## 3. Market map (what exists)

| Player | Role | Weather / fuel stance |
|--------|------|------------------------|
| Lido Flight 4D | Dispatch flight planning | Weather as planning input; Emirates uses Lido mBriefing |
| SITA OptiFlight | In flight / full flight fuel advice | QAR digital twin + 4D weather; verifies fuel savings outcomes |
| NAVBLUE N-Flight Planning + Optimize | Planning + aircraft performance factors | Least fuel routes; hazard avoidance; not OptiFlight brand |
| Jeppesen JetPlan + Boeing Wind Updates | Planning + fresher FMC winds | Weather optimised routes; uplink fights forecast age |
| Sabre Flight Explorer / planning | Ops awareness + plans | Weather overlays and reroutes |
| SkyBreathe (OpenAirlines) | Post flight fuel analytics | Initiative tracking; large fuel team footprint |
| GE Fuel Insight / FlightPulse | Pilot and fuel analytics | Already deployed at Emirates |

Research detail and citations: `research/market-solutions.md`. Deep research used web fallback (parallel-cli present but not authenticated).

## 4. Gaps (white space)

Incumbents cover:

- Compliant OFP generation and ATC friendly routes  
- Fresher wind uplinks and in flight trajectory tips  
- Post flight fuel culture and pilot scorecards  

They rarely sell, in public, a hard gate that says: score this forecast on your flown tracks; if it fails, do not rank paths. That gap matches our nested technical rules and the core finding that forecast uncertainty is the biggest hard problem.

Emirates already cares about fuel (GE + Lido). The wedge is not awareness. The wedge is trusted weather before path advice.

## 5. Thesis one-pager

**Thesis (one sentence)**  
Win by selling forecast verification on Emirates flown tracks as the gate before fuel path ranking, as an advisory layer beside Lido and GE, not as a certified planner replacement.

**Why now**  
Fuel tools are funded. Emirates already runs fuel culture apps. Market size for route planning software is large. Weather trust is still the weak link when path math meets old or wrong forecasts.

**What we sell**  
1. Phase 1 weather gate reports (suitability, severity, MOS only if it helps).  
2. Phase 2 ranked path suggestions in trip fuel kg when the gate passes.  
3. Along track weather change evidence for ops review.

**What we do not sell**  
Auto filed plans. Quantum advantage. Network wide savings from one demo. Calm short haul as main proof.

**Commercial bet on the 9**  
- Problem cost and willingness to pay become the close, once kg proof exists.  
- SOM is a wedge seat at Emirates, then a few long haul peers.  
- How to reach is a fuel / ops champion with a EK city pair demo, partnering with the existing stack.  
- Compliance stays advisory and human led.  
- Technical complexity is high but already partially built in this repo.

**Pass conditions**  
- Commercial: numbers on problem cost, willingness to pay, and SOM (not vibes).  
- Technical: T1 to T8 plus pre written win number on held out Dubai long haul flights.

**Next proof pack**  
1. Run Phase 1 on held out EK long haul extracts.  
2. Fill X / Y kg win number before Phase 2 claims.  
3. One page for Emirates: gate charts + ranked kg delta vs no wind plan.  
4. Revisit TAM/SAM with a sharper verification first slice once pricing talks start.
