# Portal Hidrológico do Ceará (COGERH / Funceme)

Fetched 2026-11-14 (Brasília) with `src/fetch_hidro.py`. The site has no robots.txt; requests went one at a time with a 1.5 s pause.

| Path | Source | Content |
|---|---|---|
| eutrofizacao.html | https://www.hidro.ce.gov.br/acude/eutrofizacao | Eutrophication page (latest campaign, Aug/2026) |
| reservoir_list.csv | dropdown of the page above | 134 reservoirs: portal id, name, lat, lon |
| campanhas/YYYY_MM.json | https://www.hidro.ce.gov.br/acude/eutrofizacao?campanha=MMM/YYYY | Records embedded in each campaign page (75 campaigns, Feb/2008 to Aug/2026): name, sampling point code, lat/lon, hydrographic region, lab values |
| dadosanuais/{id}.json | https://www.hidro.ce.gov.br/acude/eutrofizacao/dadosanuais?id={id} | Full lab history per reservoir (the JSON the page loads) |

Known problems found by cross-checking against the PDF reports (see notebook 01/02):
- Feb/2020 cyanobacteria counts are stored divided by 1,000 (46.132 instead of 46,132).
- Isolated values have the same problem in other campaigns (e.g. Acarape do Meio, May/2023: 134.503).
- Id 172 returns no history (`null`).
