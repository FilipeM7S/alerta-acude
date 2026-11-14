# Alerta Açude
**Track:** Climate
**Team:** (to be filled in)

> This project is a prototype. It does not replace laboratory testing of drinking water.

## The problem

The semi-arid interior of Ceará, Brazil, drinks from **açudes** (reservoirs). Heat and drought concentrate nutrients and warm the water, which feeds **cyanobacteria blooms**, and many cyanobacteria produce toxins. Brazil's drinking-water rule (Portaria GM/MS 888/2021, Annex XX, art. 43) requires **weekly cyanotoxin testing when cyanobacteria exceed 20,000 cells/mL** at the intake.

The state water agency COGERH measures about 150 reservoirs, but only **once per quarter**. Between campaigns a bloom can grow for three months unseen. In the Jaguaribe Valley, where cities such as Tabuleiro do Norte, Limoeiro do Norte and Russas have depended on the Castanhão reservoir, 80% of lab samples since 2016 were above the legal threshold.

**User:** a COGERH water-quality technician, or the operator of a Jaguaribe Valley water service.
**Decision:** *which reservoirs do I sample first this week, and where do I start toxin testing before the next lab campaign?*
Today their best guess is the **last lab result**, up to three months old.

## What we built

A weekly risk map. For each of the 65 reservoirs of the Jaguaribe system it takes the most recent clear **Sentinel-2** image, the **weather** of the days before it and today's **stored volume**, and returns the **probability that cyanobacteria exceed 20,000 cells/mL**, a risk band, the **top three reasons in plain language**, and the last lab result for comparison.

## What we added

- **Our own ground truth:** we parsed all 28 COGERH trophic-state reports (Feb/2016 to Feb/2025, PDF) into a clean table, with a parser test, and cross-checked every value against COGERH's own online database. The two official sources agree on 99.6% of counts; we found and documented errors in both (a shifted table in one report; counts stored ÷1,000 in the database for two campaigns).
- **Our own user and question:** a technician deciding where to sample, compared against what they know today (the last lab result).
- **Our own questions:** does it still work in drought (volume < 20%)? On reservoirs it never saw? When the image is within 2 days of the lab visit?

## How it works

**Data** (all public):
- Lab results: COGERH IET reports (28 campaigns), checked against the Portal Hidrológico database. A sample is used only if the two sources do not contradict each other. *(counts: to be filled in)*
- Reservoir locations and basins: Portal Hidrológico do Ceará. Water polygons: OpenStreetMap.
- Satellite: Sentinel-2 L2A (Microsoft Planetary Computer). For each lab sample, the closest image within ±5 days; only pixels that are water (scene classification) **and** have MNDWI > 0, eroded 2 pixels from the shore, within 1 km of the reservoir's reference point.
- Weather: NASA POWER daily (heat, rain, wind, sunlight over 7 to 90 days). Stored volume: COGERH.

**Features (15):** chlorophyll index NDCI, turbidity NDTI, MNDWI, share of the area that is water; max temperature (7 and 30 days), rain (30 and 90 days), wind, sunlight; volume % and its change; month and rainy season. No location or reservoir ID, so the model cannot memorise reservoirs.

**Model:** logistic regression on standardized features (its coefficients are the explanation), compared with a small LightGBM. *(choice and reason: to be filled in)*

**Testing:** time split by campaign, never shuffled. *(date ranges: to be filled in)* The decision threshold is chosen on validation to catch at least 80% of blooms, because a missed bloom is worse than an extra sample.

## Results

*(to be filled in after the final run)*

## What we'd do next

*(to be filled in)*

## Sources

*(to be completed)*
