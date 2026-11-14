# CLAUDE.md: Alerta Açude (Veritas AI Hackathon 2026)

You are working with **Filipe Moura da Silva**, a high school student (informatics technical course, EEEP Avelino Magalhães, Tabuleiro do Norte, Ceará, Brazil) and independent researcher with experience in remote sensing and machine learning. We are building one project for a 48-hour hackathon. Read this whole file before doing anything. It is the single source of truth for the event, the rules and the plan.

---

## 1. The event

**Veritas AI International High School Hackathon 2026**, run by Veritas AI (part of the Lumiere Education family). It is online, free and open to high school students worldwide. Site: https://highschoolhackathon.org

| | US Eastern (official) | Brasília (our time) |
|---|---|---|
| Hacking starts | Sat 14 Nov 2026, 12:00 AM | Sat 14 Nov, 02:00 |
| **Submissions close** | **Sun 15 Nov 2026, 11:59 PM** | **Mon 16 Nov, 01:59** |
| Finalists emailed | Wed 18 Nov | |
| Live finals + awards | Sat 21 Nov, 11:00 AM ET | Sat 21 Nov, 13:00 |

- **Submission form:** https://airtable.com/appypCyHN77hElIcS/shrXA5VBFdugmoXl6. One person submits for the team. Resubmitting is allowed, and the latest version counts.
- **Contact (submission problems only):** contact@veritasai.com. The organizers give **no technical help**.
- **Prizes:**
  - Gold: an internship at Arecibo AI for each member.
  - Silver and Bronze: Veritas scholarships.
  - Special awards: Best Beginner Build, **Best AI for Good**, Judges' Choice.
  - Every complete submission gets a certificate.

## 2. The rules (follow them strictly)

1. Teams have 1 to 3 high school students. Everyone listed must have contributed.
2. **All project work happens inside the 48 hours.** Learning tools beforehand is fine, but nothing built before the hackathon may be extended. Filipe has an earlier desertification-forecasting project (ConvLSTM over Ceará). **Do not reuse or import any of its code, data or models.** Everything in this repo starts from scratch. Commit early and often, because the commit timestamps are our evidence.
3. **AI/ML must do the main job.** A plain app built with AI coding tools does not count on its own.
4. Allowed: public datasets, pretrained models, AI APIs, open-source libraries, tutorial code, and coding assistants (including you, Claude Code). **Everything must be cited**, and the team must be able to explain every part.
5. Not allowed: submitting someone else's project, collecting personal data without permission, or using non-public, non-synthetic data.
6. One project, one track. **Our track is AI + Climate.**
7. Health and finance projects need a disclaimer. We add a similar line anyway: *"This project is a prototype. It does not replace laboratory testing of drinking water."*
8. **Honest results.** Report what we actually got, including weak results.

## 3. What the judges score

Round 1 is a blind review by the Veritas AI team. Finalists then pitch live to AI researchers (Microsoft Research, Harvard, Stanford, Princeton).

| Criterion | What they look for | How we show it |
|---|---|---|
| Technical quality | It works, the approach is sound, the testing is fair | Baselines, unseen test data, failure cases |
| Impact | A real problem for real people | A named user, a named decision, a real place |
| Creativity | Not a repeated tutorial | Our own data, user and question |
| Clarity | Understandable in 2 minutes | A clean demo, a one-page write-up, one main takeaway |

**Official rubric** (https://highschoolhackathon.org/judges.html):
- **Round 1 (100 points):**
  - Technical execution: 30
  - Originality: 20
  - Impact and track fit: 20
  - **Testing and honesty: 15**
  - Communication: 15
- **Finals (100 points):**
  - Demo and clarity: 30
  - Technical depth: 30
  - Impact: 20
  - Q&A: 20
- **Final ranking:** 70% finals, 30% Round 1. Filipe must be ready for live questions on every design choice.

Every write-up and demo must answer four questions:
1. **Who is it for?** One specific user, and the moment they would reach for the tool.
2. **What goes in, and what comes out?** A real input producing a result.
3. **Does it beat a simple baseline?** Report the baseline score next to the model score.
4. **Where does it fail?** At least one wrong example, with an explanation of why.

**Climate track requirements:**
- One location or region.
- For forecasts, train on earlier dates and test on later ones. **Never shuffle across time.**
- Compare against the **persistence baseline** ("the next value equals the current one").
- Explain **what decision the prediction supports and who makes it**.

Judges also note:
- "A small project tied to a real place usually scores better than tackling the whole planet."
- "If your results look too good to be true, test data has usually leaked into training. An honest, modest result scores higher than an unexplained high one."

**Our design principle: explainability over black boxes.** Use simple, defensible models. Filipe must be able to explain every line to the judges live.

## 4. The problem

The interior of Ceará depends on **açudes**, the reservoirs that supply drinking water to cities like Tabuleiro do Norte. Drought and heat concentrate nutrients and warm the water, which drives **cyanobacteria blooms**. Many species produce toxins (microcystins, saxitoxins, cylindrospermopsins). The water agency COGERH monitors 155 reservoirs, but its lab campaigns are **quarterly**. Between campaigns, a bloom can grow for up to three months without anyone measuring it. In the Nov/2020 campaign, 118 of 144 sampled reservoirs were eutrophic or hypereutrophic, and Orós had 313,603 cells/mL.

**The legal threshold** comes from Brazil's drinking-water rule, Portaria GM/MS 888/2021, Annex XX, art. 43:
- **More than 20,000 cells/mL** at the intake requires **weekly cyanotoxin testing**.
- More than 10,000 cells/mL requires weekly cyanobacteria monitoring (Annex 12).
- Chlorophyll-a of 10 µg/L or more triggers a new phytoplankton sample.

**Climate framing:** semi-arid Ceará is getting hotter and its droughts longer, and blooms are one of the most direct local climate impacts on water security. The tool helps a community **measure and predict** that impact.

## 5. The solution: Alerta Açude

**User:** a COGERH water-quality technician, or the operator of a municipal water service (SAAE/Cagece) for a Jaguaribe Valley city. **Decision:** *"Which reservoirs do I sample first this week, and where do I start toxin testing before the next lab campaign?"*

**Input:** the latest Sentinel-2 image of each reservoir, plus recent weather and stored volume.
**Output:** for each reservoir, the **probability that cyanobacteria exceed 20,000 cells/mL**, a ranked list, a map, and a plain-language reason (for example, "high NDCI, volume at 12%, hottest 30 days of the year").

**Core task (classification nowcast):**
- `y = 1` if the COGERH lab count is above 20,000 cells/mL on the sample date, else `0`.
- Predict `y` from satellite, weather and volume features available around that date.

**Secondary output:** regression of `log10(cells/mL)`, for the map colours. This is optional and only done if time allows.

**Why this beats what the technician has today:** without the tool, the technician's best guess is the result of the **last lab campaign** (persistence). If our model beats persistence on future, unseen campaigns, satellites can fill the 3-month gaps.

## 6. Data

Put raw files in `data/raw/` and generated tables in `data/processed/`. **Never invent or hand-type data values.** Every number must come from a file or an API.

### 6.1 Ground truth: COGERH trophic-state reports (IET)
- These are PDF reports, one per quarterly campaign (Feb, May, Aug, Nov), covering 155 reservoirs.
- **Table 3:** reservoir name, sample date, total N (mg/L), total P (mg/L), **chlorophyll-a (µg/L)**, **cyanobacteria (cells/mL)**, transparency (m).
- **Table 2:** reservoir name, **stored volume (%)**, trophic class.
- Known URLs on the Funceme CDN:
  - http://cdn.funceme.br/hidro-ce/uploads/documentos/estado-trofico/Relatorio_IET_Nov_2020_10022021.pdf
  - http://cdn.funceme.br/hidro-ce/uploads/documentos/Relat%C3%B3rio_iet_ago_2021_Funceme.pdf
  - http://cdn.funceme.br/hidro-ce/uploads/documentos/estado-trofico/relatorio-iet-agosto.pdf
- Filipe will download more campaigns by hand from https://www.portalhidrologico.ce.gov.br (Qualidade da água / Estado trófico) into `data/raw/cogerh/`. **Do not crawl sites whose robots.txt disallows it.** Ask Filipe for the files instead.
- **Parser test (it must reproduce these exact values from the Nov/2020 report):**

  | Reservoir | Date | Chl-a (µg/L) | Cyano (cells/mL) | Transparency (m) |
  |---|---|---|---|---|
  | Castanhão | 19/11/2020 | 9.64 | 32,209 | 2.40 |
  | Orós | 18/11/2020 | 43.41 | 313,603 | 0.80 |
  | Banabuiú | 04/11/2020 | 15.40 | 60,880 | 1.50 |
  | Santo Antônio de Russas | 24/11/2020 | 30.13 | 138,927 | 0.50 |

- Use `pdfplumber`. Some rows are shifted or missing in the PDFs, so validate the column types, log every row that fails, and **never guess a value**. Normalize names (strip accents, lower-case) so they join across campaigns.
- Output: `data/processed/samples.csv` with columns `reservoir, date, chla, cyano, n_total, p_total, transparency, volume_pct, campaign`.

### 6.2 Backup and extra target: the UFC chlorophyll-a dataset
- 1,399 Chl-a samples from 149 Ceará reservoirs, 2015–2021 (COGERH data). From Santos et al., *Remote Sensing* 2024, 16(11), 1870.
- Folder: https://drive.google.com/drive/folders/1ALvoqdtj1nbfdNWmna0PpJnD1xUgzLqw
- If too few COGERH campaigns can be parsed, switch the target to **Chl-a ≥ 10 µg/L** (Portaria 888, §1 I). Everything else in the plan stays the same.

### 6.3 Reservoir geometry
- First choice: OpenStreetMap water polygons through the Overpass API (`natural=water`, with names matching the COGERH names inside Ceará).
- Fallback: a centroid plus a buffer, with water pixels masked per image (see 6.4).
- Save to `data/processed/reservoirs.geojson` with `reservoir, basin, lat, lon, geometry`. Start with the **Jaguaribe basins** (Alto, Médio and Baixo Jaguaribe, Banabuiú, Salgado). Add the rest of the state only if it helps sample size.

### 6.4 Satellite: Sentinel-2 L2A (Microsoft Planetary Computer)
- STAC: https://planetarycomputer.microsoft.com/api/stac/v1, collection `sentinel-2-l2a`. Use `pystac-client`, `planetary-computer` (to sign URLs, no key needed) and `odc-stac`.
- For each sample, find the closest acquisition within **±5 days** of the sample date. Record `day_gap` (in absolute days) and keep it for a sensitivity check, not as a feature.
- **Water pixels:**
  - Use SCL class 6 (water) AND MNDWI = (B03 − B11)/(B03 + B11) > 0.
  - Remove cloud, shadow and cirrus (SCL 3, 8, 9, 10).
  - **Erode the mask by 2 pixels** to avoid land contamination at the shore.
  - Require at least 30 clean water pixels, otherwise drop the sample and log why.
- **Reflectance scale:** divide by 10,000. **For scenes with processing baseline ≥ 04.00 (dates from 25 Jan 2022 on), subtract the 1,000 offset first.** Check the `s2:processing_baseline` property. If you skip this, 2022+ data shifts and the time-based test becomes meaningless.
- Bands: B02, B03, B04, B05, B06, B07, B08, B8A, B11, B12. Aggregate with the **median** over water pixels.
- Indices (compute from the median reflectances):
  - `NDCI = (B05 − B04) / (B05 + B04)`. Normalized Difference Chlorophyll Index (Mishra & Mishra, 2012).
  - `3BSI = (1/B04 − 1/B05) × B06`. Three-band chlorophyll index, as used for Castanhão, Orós and Gavião in Water 2022, 14(3), 451, where it reached R² 0.77. Check the exact form in that paper before finalizing.
  - `MCI = B05 − B04 − (B06 − B04) × (705 − 665)/(740 − 665)`. Maximum Chlorophyll Index.
  - `NDTI = (B04 − B03) / (B04 + B03)`. Turbidity.
  - `MNDWI`. Also log the water area in km² as a feature, since it is a proxy for shrinkage.
- Cache every query result to disk (`data/processed/s2_cache/`), so nothing is downloaded twice.

### 6.5 Weather: Open-Meteo historical API
- https://archive-api.open-meteo.com/v1/archive, no key, queried at each reservoir centroid.
- Features for the window before the sample date:
  - mean daily max temperature (7 and 30 days);
  - rain sum (30 and 90 days);
  - mean wind speed (7 days);
  - shortwave radiation sum (7 days).

### 6.6 Other features
- `volume_pct` from COGERH Table 2, and its change since the previous campaign.
- `month` (as sin and cos), and a `rainy_season` flag for Feb–May.
- **Do not use** lat/lon or the reservoir ID as features. They let the model memorize reservoirs instead of learning water conditions.

## 7. Model formulation

Keep it simple and explainable. No deep learning.

### 7.1 Splits (no leakage)
- **Time split by campaign:**
  - oldest ~60% of campaigns for **train**;
  - next ~20% for **validation** (threshold and hyperparameter choice);
  - most recent ~20% for **test**, used once at the end.
  - Print the exact date ranges.
- Do not tune anything on the test set. Fit scalers and imputers on train only.
- Persistence needs the previous campaign, so build the `prev_cyano` and `prev_class` columns **before** splitting, and only from earlier campaigns.

### 7.2 Baselines (always report them next to the model)
1. **Persistence:** predict the class from the reservoir's **previous lab campaign**. This is the Climate-track baseline and what the technician knows today.
2. **Majority class:** always predict the most common class.
3. **Single-index rule:** `NDCI > t`, with `t` chosen on validation to maximize F1.

### 7.3 Models
1. **Logistic regression** on standardized features, with class weights balanced. This is the **primary interpretable model**: its coefficients are the explanation.
2. **LightGBM**, kept small: `max_depth=3`, about 200 trees, `learning_rate=0.05`, `class_weight='balanced'`. Try monotone constraints (+ for NDCI, 3BSI, temperature; − for volume) if they don't hurt validation.
3. **Optional:** add `prev_class` as a feature ("satellite + last lab result"), and report whether it beats persistence alone.

**Model choice:** pick on **validation**. If logistic regression is within about 0.02 PR-AUC of LightGBM, **choose logistic regression** for clarity. State the choice and the reason in the write-up.

### 7.4 Threshold and metrics
- Missing a bloom (a false negative) is worse than a false alarm (an extra sample). Choose the decision threshold on validation to reach **recall ≥ 0.80** with the best precision, and report it.
- On test, report for every baseline and model:
  - recall (missed blooms);
  - precision and **false alarm count**;
  - F1;
  - PR-AUC;
  - balanced accuracy;
  - the confusion matrix.
- Report false negatives and false positives **separately**.

### 7.5 Explainability
- Logistic regression: a bar chart of the standardized coefficients.
- LightGBM: SHAP summary plus one SHAP waterfall for a single reservoir.
- Every map pin shows its **top 3 reasons** in plain language.

### 7.6 Our own questions (the "make it your own" part, required)
1. **Drought:** does performance drop when `volume_pct < 20%`? Show recall and precision for low vs normal volume.
2. **Unseen reservoirs:** train on some reservoirs and test on others (grouped split) to check generalization. Report it next to the time split.
3. **Date gap:** do the results change if we only keep samples with `day_gap ≤ 2`?

### 7.6b Global transfer test (stretch goal, Sunday morning, only if the core is done)
- The aim is to show the method is not only local. Every input we use (Sentinel-2, Open-Meteo) is global, so the same pipeline can run on any reservoir in the world.
- Test it on outside data with the **same unit and threshold**. Use NASA's *Tick Tick Bloom* challenge labels (DrivenData): US inland waters, cyanobacteria cells/mL, 2013–2021. Check the licence and the access terms first, and cite them.
- Apply the **Ceará-trained model unchanged** to a sample of those points. Report recall and precision next to a model retrained on them. Explain what transfers and what doesn't (climate, depth, sensor dates).
- If access or time fails, skip it, and in the write-up state honestly that this is the next step.
- In the write-up and video, frame the result as **"built and validated where we live; designed to run on any reservoir with a satellite pass."** Semi-arid reservoirs facing drought and heat exist across Northeast Brazil, Spain, the Sahel, India and Australia.

### 7.7 Failure analysis (required)
- List the 5 worst false negatives and false positives in the test set, each with an RGB thumbnail of the reservoir.
- Write a short hypothesis for each. Likely causes:
  - macrophytes covering the water;
  - inorganic turbidity;
  - small reservoirs with mixed pixels;
  - haze;
  - a long gap between satellite and lab dates;
  - low biomass (the indices are known to be weak below 10 µg/L);
  - the sample point not representing the whole reservoir.

## 8. The product (the demo)

- `notebooks/05_risk_map.ipynb`:
  - pull the **most recent clear Sentinel-2 image (Nov 2026)** for each Jaguaribe reservoir;
  - compute features with the current weather;
  - run the chosen model.
- Output a **Folium HTML map** (`outputs/risk_map.html`) and a ranked table. Each pin shows the reservoir name, probability, risk band and top 3 reasons.
- Optional: a minimal Gradio app where you pick a reservoir and date and get the risk and reasons. Only build it if the core is done.
- Highlight the reservoirs that supply **Tabuleiro do Norte** and the Jaguaribe Valley cities. Confirm the supply sources from a public source before stating them.

## 9. Repository layout

```
alerta-acude/
  CLAUDE.md
  README.md                 # the write-up (template in section 10)
  requirements.txt
  data/raw/cogerh/          # PDFs (Filipe adds them)
  data/raw/ufc/             # UFC dataset (backup)
  data/processed/           # samples.csv, reservoirs.geojson, features.csv, s2_cache/
  notebooks/
    01_ground_truth.ipynb   # parse PDFs -> samples.csv (with parser test)
    02_reservoirs.ipynb     # geometry
    03_features.ipynb       # Sentinel-2 + weather + volume -> features.csv
    04_model.ipynb          # splits, baselines, models, metrics, explainability, failures, own questions
    05_risk_map.ipynb       # current risk map (the demo)
  outputs/                  # figures, risk_map.html
```

- **Notebooks:** save them with **outputs visible**. Put a short markdown cell before each step saying what it does and why. Keep code comments minimal. Fix random seeds.
- **requirements.txt:** pystac-client, planetary-computer, odc-stac, rioxarray, geopandas, shapely, pdfplumber, pandas, numpy, requests, scikit-learn, lightgbm, shap, matplotlib, folium.
- Make the repo **public** before submitting, and test every link in an incognito window.

## 10. Write-up (README.md, about one page, using the official template)

```
# Alerta Açude
**Track:** Climate
**Team:** (names from Filipe)

## The problem
## What we built
## What we added   (our own idea: own user, own local data, own questions)
## How it works    (data: sources, sample counts, cleaning; model: what and why)
## Results         (baseline X vs model Y on held-out test campaigns; where it fails and why)
## What we'd do next
## Sources         (every dataset, paper, library, AI tool with links, including Claude Code and Claude)
```

Also include:
- the line "This project is a prototype. It does not replace laboratory testing of drinking water.";
- the exact train, validation and test date ranges.

## 11. Demo video (up to 2 minutes, unlisted on YouTube or shared from Drive)

| Part | Length | Content |
|---|---|---|
| Problem | ~15 s | Açudes, quarterly lab gaps, 20,000 cells/mL rule, the technician |
| Demo | ~60 s | Map: a real recent image goes in, ranked risk and reasons come out |
| How it works | ~30 s | Data, model, baseline vs model on future campaigns |
| Next steps | ~15 s | One limitation, what we'd do next |

A screen recording with Filipe's voice is enough.

## 12. Schedule (Brasília time)

| By | Done |
|---|---|
| Sat 12:00 | Repo set up, at least 2 COGERH PDFs parsed and the parser test passing |
| Sat 18:00 | Reservoir geometry, Sentinel-2 features for all samples, weather joined |
| Sat 23:00 | Baselines and the first model on validation |
| Sun 13:00 | Threshold chosen, test results, explainability, failure analysis, own questions |
| Sun 18:00 | Risk map demo working |
| **Sun 21:00** | **README done, video uploaded, FIRST SUBMISSION sent** |
| Mon 01:00 | Final resubmission at the latest (the deadline is 01:59) |

If a data source fails to load within about 30 minutes, switch to the fallback (the UFC data, or the centroid buffer) instead of fighting it.

## 13. How to work with Filipe

- Work in small, verifiable steps. After each step, print counts, shapes and sanity checks (samples per campaign, rows dropped and why, class balance).
- **Never fabricate data, results or citations.** If something is missing, stop and ask Filipe.
- Explain each modelling choice in one or two sentences, so Filipe can defend it to the judges.
- Commit after every working step with a clear message.
- If a result looks too good (for example, PR-AUC > 0.95), assume leakage and check before celebrating.
- Before the final submission, collect from Filipe: each team member's full name, email and school.

## 14. Decisions made during the hackathon (Sat 14 Nov)

Filipe asked to keep everything simple and explainable. These replace the plan above where they differ.

- **Ground truth:** all 28 COGERH IET PDF reports on the official list (Feb/2016 to Feb/2025, `hidro.ce.gov.br/documentos/152`; the old `portalhidrologico` address is dead). Parser test passes.
- **Database cross-check:** the portal's own database (`/acude/eutrofizacao/dadosanuais`) is a second copy of the same lab results. Rule: a sample is not used if the two sources disagree on its date or count. Exception: the database's thousands-separator slip (Feb/2020, Nov/2021 stored ÷1,000) counts as agreement. Counts agree 99.6%. The database's newer campaigns (to Aug/2026) are used only in the demo, as "last lab result".
- **Usable sample:** has a count, date within 75 days of its campaign month, not contradicted by the database (`usable` column in `samples.csv`).
- **Geometry:** reference point and basin from the portal campaign pages (fixed per reservoir). AOI = water within 1 km of the point, clipped to the OSM polygon (+100 m) when the match is trustworthy (≥ 0.1 km², ≤ 200 m), else the disc. 14 reservoirs no longer on the portal are left out (246 samples).
- **Sentinel-2:** one STAC search per sample (±5 days), closest image with ≥ 30 clean water pixels. Bands B03, B04, B05, B06, B08, B11 only (what the indices need), 20 m. Offset −1000 for baseline ≥ 04.00.
- **Weather:** NASA POWER daily (MERRA-2 grid, ~50 km) instead of Open-Meteo, because Open-Meteo's free tier counts a multi-year request as hundreds of calls.
- **Current volume for the demo:** portal page `/quantidade-nivel-diario` (embeds today's volume % for 144 reservoirs).
- **Target:** stays > 20,000 cells/mL (80% of usable samples are positive). Train on all basins; the demo map focuses on the Jaguaribe Valley.
