# Market scan: wind aware / fuel route optimisation

Research method: web fallback (parallel-cli installed v0.9.3 but not authenticated; `PARALLEL_API_KEY` / login required for deep research). All claims cite URLs from search and fetch. Plain language.

## Question

Who already sells wind aware or fuel saving flight route tools, and how does that compare to a forecast verification first approach (Phase 1 weather gate on flown tracks, then Phase 2 path ranking)?

## Top commercial solutions

### 1. Lido Flight 4D (Lufthansa Systems)

**What it solves**
Certified style flight planning for dispatch: routes and profiles using weather, NOTAMs, AIP, ATM restrictions, aircraft performance, and ATC charges. Trusted by 125+ operators and 7,700+ aircraft per vendor pages. ([Lido Flight 4D](https://www.lhsystems.com/product-brands/lido/lido-flight-4d))

**Fuel / wind angle**
Optimises for fuel, time, or cost using weather among many inputs. Older Lido materials cite fuel savings of up to 5% as possible. ([Lido / FPLS brochure](https://cdn.lhsystems.com/2020-11/pb-lido-flight-and-lido-fpls_1.pdf))

**Emirates link**
Emirates uses Lido mBriefing on pilot iPads for paperless OFP and briefing, with enroute weather including turbulence forecasts. ([Emirates FlightPulse / mBriefing](https://www.emirates.com/media-centre/empowering-pilots-with-data-emirates-leverages-ge-flightpulse-app-to-connect-pilot-community-reduce-fuel-burn-and-enhance-flight-safety/))

**Vs our criteria**
Strong on compliance, sales cycle maturity, and reach. Weak on explicit forecast vs flown track verification as a hard gate before ranking. Weather is an input, not a scored trust product.

### 2. SITA OptiFlight (often confused with NAVBLUE)

**What it solves**
In flight and pre flight fuel recommendations from climb through cruise and descent. Tail specific digital twins from QAR data, ML, and 4D weather. ACARS or EFB delivery. Vendor claims ≤3% average full flight fuel savings and 2,500+ aircraft. ([SITA OptiFlight](https://www.sita.aero/solutions/sita-for-aircraft/in-flight-efficiency/optiflight/))

**Verification angle**
Post flight comparison of actual fuel vs predictions for CFO style savings reports. That is fuel outcome verification, not independent forecast honesty scoring (forecast vs ERA5 / PIREP / QAR wind on the track). ([SITA OptiFlight](https://www.sita.aero/solutions/sita-for-aircraft/in-flight-efficiency/optiflight/))

**Note on naming**
Market talk often says "NAVBLUE OptiFlight". Public product pages show OptiFlight as SITA. NAVBLUE sells N-Flight Planning (least fuel / time / cost routes with weather and hazard avoidance) and Airbus Optimize Suite (performance / idle factors). ([N-Flight Planning route analysis](https://n-flightplanning.support.navblue.aero/support/solutions/articles/35000214210-route-analysis)); ([NAVBLUE / easyJet IFO](https://www.skywise.com/en/newsroom/press-releases/navblue-and-easyjet-united-to-improve-efficiency-and-fuel-savings))

### 3. Jeppesen JetPlan + Boeing Wind Updates

**What it solves**
JetPlan: first time flyable routes optimised for cost, time, and fuel with weather optimised routes and regulatory compliance. ([JetPlan Engine](https://digitalsuccess.jeppesen.com/article/JetPlan-Engine))

**Wind uplink**
Boeing Wind Updates sends fresher winds to the FMC in flight because pre departure weather can be many hours old; claims up to hundreds of pounds of fuel per flight. ([Boeing Wind Updates PDF](https://www.boeing.com/content/dam/boeing/boeingdotcom/commercial/services/assets/brochure/fs-windupdates.pdf))

**Vs our criteria**
Addresses forecast age with fresher wind data. Does not publish a Phase 1 style suitability gate that blocks path ranking when the weather product fails on that airline's flown tracks.

### 4. Sabre Flight Plan / Flight Explorer

**What it solves**
Ops control and planning: weather overlays (including GFS winds), reroutes around weather and airspace, fuel monitoring, integration with flight plan manager. ([Sabre Flight Explorer news](https://www2.flightexplorer.com/about/readNews.aspx?id=98))

**Market size context**
Analyst summaries put airline route planning software around $8.36B in 2025 growing toward ~$12.3B by 2030 (treat as order of magnitude for TAM, not precise SOM). ([Yahoo / market report summary](https://finance.yahoo.com/news/12-25-bn-airline-route-145800078.html))

### 5. OpenAirlines SkyBreathe

**What it solves**
Post flight fuel analytics: initiatives, pilot engagement, potential vs achieved savings using FDR and ops data. Large airline customer base; vendor claims hundreds of millions of kg fuel saved across customers. ([SkyBreathe](https://www.openairlines.com/fuel-management-software/))

**Vs our criteria**
Strong on problem cost storytelling and willingness to pay for fuel teams. Focus is initiative tracking and eco flying practices, not a pre departure weather gate that unlocks path ranking.

### 6. GE Fuel Insight / FlightPulse (Emirates deployed)

**What it solves**
Merges flight data with flight plans for fuel insight; FlightPulse gives pilots personal and peer fuel and safety metrics. Emirates uses FlightPulse fleet wide and contracted Fuel Insight / Pre Flight. ([GE Emirates announcement](https://www.ge.com/news/press-releases/emirates-extends-sustainability-efforts-with-ge-digital-aviation-software)); ([Emirates FlightPulse](https://www.emirates.com/media-centre/empowering-pilots-with-data-emirates-leverages-ge-flightpulse-app-to-connect-pilot-community-reduce-fuel-burn-and-enhance-flight-safety/))

**Vs our criteria**
Emirates already has pilot facing fuel culture tools and Lido briefing. White space is not "does Emirates care about fuel" (they do). White space is "does anyone gate path advice on forecast honesty scored on EK flown tracks".

## Map to our 9 commercial dimensions

| Dimension | Market signal | Gap for airpath / Qorina |
|-----------|---------------|---------------------------|
| TAM | Large route planning / fuel software category (~$8B+ cited) | Need sharper slice: verification first path advice |
| SAM | Long haul + fuel tools buyers overlap with Lido / SITA / GE customers | ME long haul beachhead still open for a wedge product |
| SOM | Emirates already Lido + GE; hard for a full stack replace | Realistic SOM = advisory wedge beside incumbents |
| Technical | Incumbents optimise with weather inputs; some verify fuel outcomes | Few sell forecast vs truth suitability on flown tracks as a hard gate |
| Compliance | Incumbents are certified planning or cockpit integrated | Our path must stay advisory; human final say |
| Sales cycle | Multi year vendor relationships | Need champion + kg proof pack, not a rip and replace pitch |
| How to reach | Emirates digital / ops already live with GE and Lido | Best entry: weather gate demo on EK city pairs, partner not replace |
| Willingness to pay | Proven fuel tools get budget (SITA, SkyBreathe, GE) | Price unknown; shared savings possible if kg proven |
| Problem cost | Wind age and bad weather erase path wins; Boeing states old winds hurt | Quantify EK specific $ from wind miss still open |

## White space (one paragraph)

Incumbents win at compliant planning (Lido, Jeppesen, NAVBLUE NFP), in flight trajectory advice (SITA OptiFlight, Boeing Wind Updates), and post flight fuel culture (SkyBreathe, GE FlightPulse). What is thin in public product claims is a hard weather trust gate: score forecast honesty on the airline's own flown tracks, refuse to rank paths when the gate fails, then rank only with corrected wind for trip fuel in kilograms. That is the emirates-air-path / Qorina wedge beside Emirates' existing Lido + GE stack.

## Sources

- [Lido Flight 4D](https://www.lhsystems.com/product-brands/lido/lido-flight-4d) (Lufthansa Systems product page)
- [Lido Flight / FPLS brochure](https://cdn.lhsystems.com/2020-11/pb-lido-flight-and-lido-fpls_1.pdf) (up to 5% fuel savings claim)
- [SITA OptiFlight](https://www.sita.aero/solutions/sita-for-aircraft/in-flight-efficiency/optiflight/)
- [NAVBLUE N-Flight Planning route analysis](https://n-flightplanning.support.navblue.aero/support/solutions/articles/35000214210-route-analysis)
- [NAVBLUE / easyJet Optimize IFO](https://www.skywise.com/en/newsroom/press-releases/navblue-and-easyjet-united-to-improve-efficiency-and-fuel-savings)
- [Jeppesen JetPlan Engine](https://digitalsuccess.jeppesen.com/article/JetPlan-Engine)
- [Boeing Wind Updates](https://www.boeing.com/content/dam/boeing/boeingdotcom/commercial/services/assets/brochure/fs-windupdates.pdf)
- [Sabre Flight Explorer weather release](https://www2.flightexplorer.com/about/readNews.aspx?id=98)
- [Airline route planning software market summary](https://finance.yahoo.com/news/12-25-bn-airline-route-145800078.html)
- [OpenAirlines SkyBreathe](https://www.openairlines.com/fuel-management-software/)
- [GE Emirates Fuel Insight / FlightPulse](https://www.ge.com/news/press-releases/emirates-extends-sustainability-efforts-with-ge-digital-aviation-software)
- [Emirates FlightPulse and Lido mBriefing](https://www.emirates.com/media-centre/empowering-pilots-with-data-emirates-leverages-ge-flightpulse-app-to-connect-pilot-community-reduce-fuel-burn-and-enhance-flight-safety/)
