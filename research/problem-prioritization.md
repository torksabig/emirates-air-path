# Industry problem research & prioritization

**Date:** 2026-09-21  
**Method:** Knockout filters → score A–V (1–5) with confidence (1–5) → weighted total → research output blocks  
**Primary sources:** `CRITERIA.md`, `THESIS.md`, `research/market-solutions.md`, `PROJECT.md`, `README.md`, plus cited web sources  
**Honesty rule:** Most confidence scores are 1–3 without Emirates customer interviews. Fuel savings are literature or peer-PoC ranges, not proven Emirates network savings.

---

## Weighting formula (transparent)

Emphasis: high pain × economic value × WTP × accessible buyer × technical advantage × feasible delivery × scalable market.

| Dimension | Weight % | Why |
|-----------|----------|-----|
| A Problem severity | 5 | Pain signal |
| B Cost of problem | 6 | Economic pain |
| C Value creation | 8 | Value if solved |
| D Willingness to pay | 10 | Must convert to revenue |
| E ROI / payback | 5 | Buyer math |
| F Decision leverage | 4 | Can a champion move it |
| G Technical advantage | 10 | White-space wedge |
| H Technical feasibility | 6 | Can we deliver |
| I Time to MVP / pilot | 4 | Speed to proof |
| J Data availability | 5 | Evidence engine |
| K Integration complexity | 3 | **Scale: 5 = easy, 1 = hard** |
| L Regulatory burden | 3 | **Scale: 5 = light, 1 = heavy** |
| M Sales cycle | 3 | **Scale: 5 = short, 1 = long** |
| N Buyer clarity | 5 | Accessible buyer |
| O Urgency / triggers | 2 | Timing |
| P Competitive intensity | 4 | **Scale: 5 = open / differentiated, 1 = crowded undifferentiated** |
| Q Switching / status quo | 3 | **Scale: 5 = easy adopt beside stack, 1 = locked replace-only** |
| R Market size | 4 | TAM/SAM realism |
| S Market concentration | 2 | Buyer/vendor shape |
| T Expansion potential | 2 | After beachhead |
| U Repeatability / scalability | 3 | Same play elsewhere |
| V Strategic fit | 3 | Matches this repo |
| **Total** | **100** | |

**Weighted score** = Σ (weight_i / 100 × score_i), range 1.00–5.00.

**Go thresholds (working):**
- **≥ 3.8** and knockouts clear + problem cost + WTP numbers → commercial GO  
- **3.2–3.79** → conditional GO (pilot / proof pack only)  
- **&lt; 3.2** or hard knockout fail → NO-GO or reframe  

---

## Primary problem

### Problem statement (narrow)

Airline ops and dispatch cannot verify whether pre-departure wind forecasts held true on flown tracks before ranking fuel-optimal path alternatives, so path ranking on untrustworthy weather can increase fuel burn and erase planned savings on long-haul city pairs (example: Emirates OMDB origins).

### Knockout filters

| Filter | Result | Notes |
|--------|--------|-------|
| Regulatory / compliance | **PASS** (conditional) | Stay advisory; human final say; do not replace certified OFP. Vendor cyber/onboarding still unknown for Emirates. |
| Technical feasibility | **PASS** (conditional) | Phase 1/2 code and free extracts exist. Forecast uncertainty and ATC/granted-FL realism remain hard. |
| Delivery cost | **PASS** | Desk pilot with ADS-B + archive weather is low cost. Airline-grade ops integration costs more later. |
| Data availability | **PASS** (conditional) | ADS-B + free/archive weather workable for proof. QAR / preferred vendor weather preferred but gated by airline contracts. |
| Sales-cycle viability | **PASS** (conditional) | Fuel tools already sell into airlines (long cycles). No named Emirates champion yet. |
| Deployment / integration | **PASS** | Design is wedge beside Lido + GE FlightPulse, not rip-and-replace. |
| Buyer accessibility | **PASS** (fragile) | Entry path is fuel/ops/digital + city-pair demo. Without a warm intro this filter fails in practice. |
| Dependency risk | **PASS** (conditional) | Depends on ADS-B coverage, weather products, and incumbents not blocking partnership. |

**Knockout verdict:** No hard fail. Fragile buyeron access and unproven WTP keep this below commercial GO.

### Scores A–V (primary)

| Dim | Score | Conf | One-line evidence |
|-----|-------|------|-------------------|
| A Severity | 4 | 3 | Fuel is a top airline cost; bad wind trust can reverse path advice on long haul. |
| B Cost of problem | 3 | 2 | Literature shows ~2–4% wind-optimal headroom vs flown tracks; EK-specific waste from *forecast failure* not measured. |
| C Value creation | 4 | 3 | Trip fuel kg maps to cash; gate that blocks bad ranking protects planned savings. |
| D Willingness to pay | 3 | 2 | Fuel tools get budget (SITA, SkyBreathe, GE); WTP for a *verification gate* product unproven. |
| E ROI / payback | 3 | 2 | If a small fraction of wind headroom is recovered, software can pay back; no held-out EK win number yet. |
| F Decision leverage | 3 | 2 | Multi-stakeholder (ops, fuel, IT, safety); needs a fuel-kg champion. |
| G Technical advantage | 4 | 3 | Public incumbent claims thin on hard forecast-vs-flown-track gate before ranking. |
| H Technical feasibility | 3 | 3 | Pipeline exists; weather trust + ATC realism still dominate difficulty. |
| I Time to MVP / pilot | 4 | 3 | Demo + live extracts + Phase 1/2 CLI already in repo. |
| J Data availability | 4 | 3 | Free ADS-B/weather extracts in project; QAR gap remains. |
| K Integration complexity | 3 | 2 | Advisory lowers bar; still airline IT, EFB/ops workflows, vendor onboarding. *(5=easy)* |
| L Regulatory burden | 4 | 3 | Advisory + human authority keeps certification burden lower than OFP replace. *(5=light)* |
| M Sales cycle | 2 | 3 | Enterprise aviation software typically many months; multi-signatory. *(5=short)* |
| N Buyer clarity | 3 | 2 | Fuel savings owner vs flight ops vs digital not pinned for Emirates. |
| O Urgency / triggers | 3 | 2 | Persistent fuel/ESG pressure; no single acute trigger identified. |
| P Competitive intensity | 3 | 3 | Crowded planners (Lido, Jeppesen, NAVBLUE, SITA); white space on verification gate. *(5=open)* |
| Q Switching / status quo | 3 | 2 | Emirates already Lido + GE; wedge-beside is easier than replace, still status-quo heavy. *(5=easy adopt)* |
| R Market size | 3 | 2 | Broad route-planning software category is large; *verification-first* slice is much smaller (customers × ACV below). |
| S Market concentration | 3 | 2 | Few mega planning vendors; airline buyers fragmented by region/fleet. |
| T Expansion potential | 4 | 3 | After EK: other Gulf, then EU/Asia long-haul hubs. |
| U Repeatability / scalability | 4 | 3 | Same Phase 1 gate + Phase 2 rank method ports to other carriers/city pairs. |
| V Strategic fit | 4 | 4 | Matches thesis, criteria T1–T8, and existing airpath code. |

**Weighted score (primary): 3.40 / 5.00**

Calculation:  
0.05·4 + 0.06·3 + 0.08·4 + 0.10·3 + 0.05·3 + 0.04·3 + 0.10·4 + 0.06·3 + 0.04·4 + 0.05·4 + 0.03·3 + 0.03·4 + 0.03·2 + 0.05·3 + 0.02·3 + 0.04·3 + 0.03·3 + 0.04·3 + 0.02·3 + 0.02·4 + 0.03·4 + 0.03·4  
= **3.40**

### Research output block (primary)

| Field | Content |
|-------|---------|
| **Problem statement** | Ops/dispatch cannot verify pre-departure wind forecast honesty on flown tracks before ranking fuel-optimal path alternatives, so ranking on bad weather can raise fuel burn and erase planned savings on long-haul city pairs (e.g. Emirates OMDB). |
| **Industry / segment** | Airline flight operations / dispatch fuel efficiency; long-haul hub carriers; wind-aware route advice layer. |
| **Who experiences it** | Dispatch, flight ops engineering, fuel efficiency teams; secondarily pilots via briefing/EFB culture tools. |
| **Economic buyer** | Likely fuel efficiency / ops performance budget holder (with IT and safety gatekeepers). Exact Emirates signer unknown. |
| **Current solution / status quo** | Certified planners (Lido Flight 4D, Jeppesen, NAVBLUE) use weather as an input; SITA OptiFlight verifies *fuel outcomes*; Boeing Wind Updates fights *forecast age*; SkyBreathe/GE FlightPulse drive post-flight culture. Hard “forecast failed on *our* tracks → do not rank” gate is thin in public claims. |
| **Annual cost per customer** | **Estimate only.** Not the full fuel bill. Relevant slice is waste from ranking paths when forecast trust is wrong. Using ~2–4% literature wind headroom vs tracks ([NASA EWR–FRA](https://ntrs.nasa.gov/api/citations/20180004216/downloads/20180004216.pdf); [Wells et al. LHR–JFK ~4.2%](https://doi.org/10.1016/j.trd.2023.103660)), only a **fraction** is attributable to forecast-trust failure. Illustrative: if 0.2–0.5% of long-haul trip fuel is at risk on material wind days, that is meaningful cash at ME jet prices (~USD 700–850/t early 2025 regional bands, [Simple Flying / IATA table](https://simpleflying.com/how-much-jet-fuel-prices-vary/)) but **not** measured for Emirates here. |
| **Estimated value if solved** | **Estimate:** Protect or recover a small slice of wind-routing headroom on gate-eligible flights (order of hundreds of kg on strong-wind long-haul examples in peer PoC context; do not claim EK network %). Value = proven kg × fuel price × eligible flights. |
| **Expected WTP** | **Estimate:** Pilot fee USD 50–150k; production advisory USD 150–400k ACV/year **or** shared savings if kg proven. Confidence low until pricing talks. |
| **Expected ACV** | **Estimate:** USD 150–300k for a verification + ranking advisory seat at one major carrier (beside Lido/GE). |
| **Sales cycle** | **Estimate:** 9–18 months from first meeting to paid pilot/production for Emirates-class carriers. |
| **TAM** | **Estimate (customers × ACV):** ~80–120 long-haul-heavy airlines that buy third-party fuel/weather planning tools × USD 200–400k = **~USD 16–48M** product TAM for verification-first advisory. Broader “airline route planning software” category cited ~USD 8.36B (2025) growing toward ~USD 12B ([Yahoo/market summary](https://finance.yahoo.com/news/12-25-bn-airline-route-145800078.html)) is **not** this product’s TAM. |
| **SAM** | **Estimate:** ~30–50 hub long-haul carriers (ME/EU/Asia) with wind exposure and third-party tool budgets × USD 200–350k = **~USD 6–18M**. |
| **3–5 year SOM** | **Estimate:** 1 Emirates-class beachhead + 2–5 peers × USD 150–300k = **~USD 0.5–1.8M ARR**. Do not claim network-wide airline savings from one pilot. |
| **Technical approach** | Phase 1: forecast vs truth on ADS-B/QAR tracks (suitability ≥ 0.55, n ≥ 6). Phase 2 only if gate passes: rank parallel tracks × FLs by trip fuel kg. Human keeps final say. |
| **Technical complexity** | High on weather trust; medium on ranking once gate passes; high again for ATC/granted-level realism. |
| **Data requirements** | Flown tracks (ADS-B minimum; QAR preferred); forecast products (GFS/IFS/etc.); independent truth (ERA5/METAR/PIREP/QAR); aircraft performance assumptions for fuel kg. |
| **Integration requirements** | Advisory export beside dispatcher workflow / fuel team review; optional EFB later. Must not auto-file OFP. |
| **Regulatory barriers** | Avoid claiming certified plan replacement; data licenses; airline cyber vendor onboarding (GCAA/ops manuals TBD). |
| **Competitors / alternatives** | Lido, Jeppesen + Boeing Wind Updates, NAVBLUE NFP, SITA OptiFlight, Sabre, SkyBreathe, GE Fuel Insight/FlightPulse (Emirates deployed). |
| **Why existing solutions fail (for this narrow problem)** | They optimize *with* weather or verify *fuel outcomes* / freshen winds; they rarely sell a hard flown-track forecast honesty gate that *blocks* path ranking when trust fails. |
| **Our potential advantage** | Verification-first product narrative + working Phase 1/2 evidence engine on EK city-pair extracts; partner-beside incumbents. |
| **Time / cost to pilot** | **Estimate:** weeks–few months for held-out Phase 1 + written win number on OMDB long haul using free extracts; low five figures internal effort if no paid data. Airline data-room pilot higher. |
| **Scalability** | Method scales across city pairs and carriers once data access exists; ops integration is the bottleneck. |
| **Expansion potential** | Gulf peers → European long haul → Asian long haul; later more weather products / in-flight gate refresh. |
| **Key risks** | No champion; incumbent bundles a “good enough” trust feature; ADS-B ≠ QAR truth; ATC makes ranked paths unusable; WTP stays R&D curiosity without kg proof. |
| **Evidence** | Project criteria/thesis/market scan; NASA ~2.2–2.4% mean EWR–FRA wind-optimal vs tracks; Wells et al. ~4.2% LHR–JFK cruise; Boeing wind-age narrative; Emirates Lido+GE stack; airpath Phase 1/2 code + extracts. |
| **Confidence** | Overall commercial confidence **2/5** (no interviews, no EK problem-cost measurement). Technical confidence **3/5** for desk pilot. |
| **Weighted score** | **3.40 / 5.00** |

### Why has this not already been solved?

1. **Incumbents monetize certified planning and fuel culture, not a fail-closed weather gate.** Selling “we optimize with weather” is easier than selling “sometimes refuse to rank.”  
2. **Forecast trust is scientifically hard and airline-specific.** A gate needs flown-track truth, sample counts, and product-by-product scoring; that is awkward inside OFP engines built for compliance and ATC.  
3. **Status quo absorbs the pain.** Dispatch conservatism, contingency fuel, and fresher wind uplinks (e.g. Boeing Wind Updates) reduce urgency without solving pre-departure ranking under bad forecasts.  
4. **Proof bar is high and political.** Claiming kg savings next to Lido/GE needs held-out evidence; airlines already paid for large suites, so a wedge must partner, not threaten replace.  
5. **Data walls.** Best truth (QAR) sits behind airline contracts; public ADS-B proofs are weaker for closing a CFO deal.

### Go / no-go (primary)

**CONDITIONAL GO — pilot / proof pack only.**  
Not commercial GO until: measured problem-cost slice (or agreed proxy), written win number on held-out OMDB long haul, and a reachable economic buyer/champion.

---

## Secondary candidate 1 (grounded): forecast-age robust planning

### Problem statement

Pre-departure path ranking that looks good on fresh weather can lose most of its advantage when the same optimizer is fed older forecast fields, so ops cannot tell which advice is robust to forecast age vs which only works with near-real-time winds.

### Knockouts

Same advisory path as primary → **PASS** with same buyer-access fragility. Differentiator partially overlapped by [Boeing Wind Updates](https://www.boeing.com/content/dam/boeing/boeingdotcom/commercial/services/assets/brochure/fs-windupdates.pdf) (fresher FMC winds), so white space is narrower than the primary gate story.

### Scores A–V (abbreviated table)

| Dim | Score | Conf | Note |
|-----|-------|------|------|
| A | 3 | 3 | Real pain when OFP weather ages before departure/cruise. |
| B | 3 | 2 | Peer PoC (Qorina LHR–JFK) showed large kg swings by forecast age; not EK-measured. |
| C | 3 | 2 | Value = robustness labels + age-aware ranking, not always more kg. |
| D | 2 | 2 | May be seen as feature of wind uplink, not standalone budget. |
| E | 3 | 2 | Payback if age-aware advice avoids false savings; unproven. |
| F | 3 | 2 | Same multi-stakeholder map. |
| G | 3 | 3 | Some differentiation; Boeing already attacks age with fresher data. |
| H | 3 | 3 | Feasible as extension of Phase 1 (report forecast age; split success stories). |
| I | 4 | 3 | Can ship as Phase 1 report enrichment quickly. |
| J | 4 | 3 | Same data stack; age metadata needed. |
| K | 3 | 2 | Same advisory integration. *(5=easy)* |
| L | 4 | 3 | Advisory. *(5=light)* |
| M | 2 | 3 | Same long cycle. *(5=short)* |
| N | 3 | 2 | Same buyer ambiguity. |
| O | 3 | 2 | Chronic, not crisis. |
| P | 2 | 3 | More overlap with wind-uplink vendors. *(5=open)* |
| Q | 3 | 2 | Add-on possible. *(5=easy adopt)* |
| R | 2 | 2 | Smaller standalone market than full verification gate. |
| S | 3 | 2 | Same industry shape. |
| T | 3 | 3 | Expands into primary product naturally. |
| U | 4 | 3 | Repeatable scoring by age bucket. |
| V | 4 | 4 | Explicit in criteria “strong pilot extras” / thesis. |

**Weighted score: 3.05 / 5.00**  
(same weights; calculation: 0.05·3+0.06·3+0.08·3+0.10·2+0.05·3+0.04·3+0.10·3+0.06·3+0.04·4+0.05·4+0.03·3+0.03·4+0.03·2+0.05·3+0.02·3+0.04·2+0.03·3+0.04·2+0.02·3+0.02·3+0.03·4+0.03·4 = **3.05**)

### Research output (secondary 1, condensed)

| Field | Content |
|-------|---------|
| Industry | Same long-haul ops / fuel advice |
| Who / buyer | Same; fuel team cares about “does this tip survive old weather?” |
| Status quo | Fresher wind uplinks; planners still often treat weather as usable without age robustness reporting |
| Annual cost / value / WTP / ACV | Treat as **feature of primary**, not separate ACV; standalone WTP likely lower |
| TAM/SAM/SOM | Fold into primary SOM; do not double-count |
| Technical approach | Score and report forecast age; split win criteria (robust-under-old vs fresh-OFP bar) |
| Why unsolved | Age is treated as a data freshness ops issue, not a ranking-eligibility product |
| Weighted score | **3.05** |
| Verdict | **Support primary as a Phase 1 evidence dimension; not a separate lead problem** |

---

## Secondary candidate 2 (grounded): granted FL / ATC constraint realism

### Problem statement

Fuel-optimal path and flight-level rankings that ignore granted levels and ATC routings look good on paper but cannot be flown, so ops discount optimizer advice and stick to conservative filed tracks.

### Knockouts

| Filter | Result |
|--------|--------|
| Technical feasibility | **PASS** only if constrained search uses real ATM/route structures — hard without airline/ATM data |
| Data availability | **CONDITIONAL FAIL** without AIP/ATM/company route databases or partner feed |
| Buyer accessibility | Same fragile path |
| Dependency risk | **High** — Lido/Jeppesen already own this layer |

**Knockout note:** Not a hard reject as a *technical quality bar* for our Phase 2, but weak as a *standalone commercial problem* because incumbents already sell ATC-aware planning.

### Scores A–V (abbreviated)

| Dim | Score | Conf | Note |
|-----|-------|------|------|
| A | 4 | 3 | Ops pain is real when advice is unflyable. |
| B | 3 | 2 | Cost is wasted analyst trust + missed savings; hard to meter. |
| C | 3 | 2 | Value mostly accrues to certified planners already. |
| D | 2 | 2 | Airlines already pay Lido/Jeppesen for this. |
| E | 2 | 2 | Poor standalone ROI for a new vendor. |
| F | 2 | 2 | Dispatch systems owned by incumbents. |
| G | 2 | 3 | Low advantage vs Lido/JetPlan. |
| H | 2 | 2 | Hard without ATM databases. |
| I | 2 | 2 | Slow to MVP that ops trusts. |
| J | 2 | 2 | Critical data behind vendors. |
| K | 1 | 2 | Deep integration. *(5=easy)* |
| L | 2 | 2 | Closer to ops procedure / ATM. *(5=light)* |
| M | 2 | 3 | Long. *(5=short)* |
| N | 3 | 2 | Clear pain owner (dispatch) but locked vendor. |
| O | 3 | 2 | Chronic. |
| P | 1 | 3 | Dominated by planning suites. *(5=open)* |
| Q | 1 | 3 | High status-quo lock. *(5=easy adopt)* |
| R | 2 | 2 | Not a net-new budget line. |
| S | 4 | 3 | Concentrated vendor power. |
| T | 2 | 2 | Expansion fights incumbents head-on. |
| U | 2 | 2 | Scales only with deep data deals. |
| V | 3 | 4 | Important as Phase 2 quality gate, not wedge. |

**Weighted score: 2.33 / 5.00**  
(0.05·4+0.06·3+0.08·3+0.10·2+0.05·2+0.04·2+0.10·2+0.06·2+0.04·2+0.05·2+0.03·1+0.03·2+0.03·2+0.05·3+0.02·3+0.04·1+0.03·1+0.04·2+0.02·4+0.02·2+0.03·2+0.03·3 = **2.33**)

### Verdict (secondary 2)

**NO-GO as lead commercial problem.** Keep as a **delivery risk / Phase 2 realism requirement** inside the primary product (rank only among flyable candidates when data exists).

---

## Comparison summary

| Problem | Weighted | Knockouts | Decision |
|---------|----------|-----------|----------|
| **P1 Forecast honesty gate before path ranking** | **3.40** | Pass (fragile buyer) | **Conditional GO — proof pack** |
| P2 Forecast-age robustness | 3.05 | Pass | Feature under P1 |
| P3 Granted FL / ATC realism | 2.33 | Data/dependency weak as standalone | Technical bar, not wedge |

---

## Recommended next proof pack (from criteria)

1. Run Phase 1 on held-out EK long-haul extracts; publish suitability / severity / age.  
2. Write win number (beat no-wind plan by X kg on Y flights) **before** Phase 2 claims.  
3. One-pager for Emirates: gate charts + ranked kg delta vs baseline on OMDB city pairs.  
4. Identify one fuel/ops champion path (partner-beside Lido/GE, not replace).  
5. Revisit D/B/R with interview numbers before claiming commercial GO.

---

## Sources

- Project: `CRITERIA.md`, `THESIS.md`, `research/market-solutions.md`, `PROJECT.md`, `README.md`  
- [Lido Flight 4D](https://www.lhsystems.com/product-brands/lido/lido-flight-4d)  
- [SITA OptiFlight](https://www.sita.aero/solutions/sita-for-aircraft/in-flight-efficiency/optiflight/)  
- [Boeing Wind Updates PDF](https://www.boeing.com/content/dam/boeing/boeingdotcom/commercial/services/assets/brochure/fs-windupdates.pdf)  
- [GE / Emirates FlightPulse](https://www.ge.com/news/press-releases/emirates-extends-sustainability-efforts-with-ge-digital-aviation-software)  
- [Emirates FlightPulse + Lido mBriefing](https://www.emirates.com/media-centre/empowering-pilots-with-data-emirates-leverages-ge-flightpulse-app-to-connect-pilot-community-reduce-fuel-burn-and-enhance-flight-safety/)  
- [NASA wind-optimal EWR–FRA](https://ntrs.nasa.gov/api/citations/20180004216/downloads/20180004216.pdf)  
- [Wells et al. wind-optimal LHR–JFK](https://doi.org/10.1016/j.trd.2023.103660)  
- [Airline route planning software market summary](https://finance.yahoo.com/news/12-25-bn-airline-route-145800078.html)  
- [IATA jet fuel price context / ME regional table via Simple Flying](https://simpleflying.com/how-much-jet-fuel-prices-vary/)  
- [IATA Global Outlook June 2025 (jet ~USD 86/bbl forecast)](https://www.iata.org/en/iata-repository/publications/economic-reports/global-outlook-for-air-transport-june-2025/)  
