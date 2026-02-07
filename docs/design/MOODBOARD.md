# ReSemis EPM UI Moodboard

This moodboard is now aligned to an investor/CEO/CFO use case, not HR workflows.

## Visual Direction

- Investor cockpit style: strict hierarchy, clean surfaces, controlled accent color, low visual noise.
- Decision-first narrative: headline KPIs first, then scenario spread, then risk and assumption drivers.
- Auditability over decoration: every chart answers one financial question and maps to model assumptions.

## Key Reference Families

### Dashboard shell and hierarchy

1. Datadog dashboard layout patterns: `docs/design/moodboard/screenshots/datadog_dashboards_product.png`
2. Power BI dashboard composition patterns: `docs/design/moodboard/screenshots/powerbi_design_tips.png`
3. Tableau dashboard clarity rules: `docs/design/moodboard/screenshots/tableau_dashboard_best_practices.png`

### Filters, controls, and drilldowns

1. Metabase filter system: `docs/design/moodboard/screenshots/metabase_filters.png`
2. Looker dashboard exploration model: `docs/design/moodboard/screenshots/looker_dashboards_docs.png`

### FP&A and scenario-planning references

1. Anaplan FP&A software positioning and use-case framing.
2. Planful scenario-planning workflow concepts.
3. Cube FP&A dashboard examples.
4. CFI sensitivity-analysis/tornado pattern references.
5. Local benchmark app: `C:/projects/resemis-model-audit/dashboard/app.py`

## Pattern Synthesis Adopted

- Top strip KPIs for Revenue, EBITDA Margin, Ending Cash, and Enterprise Value.
- Dedicated Scenario Lab with deterministic scenario comparison plus stress sliders.
- Explicit sensitivity view (single-metric tornado) for downside/upside communication.
- Model Inputs workbench with editable client/market, product/pricing/mix, BOM/input costs, OpEx/CapEx/funding, and valuation blocks.
- Risk Radar fed by model outputs (liquidity, concentration, working-capital pressure, valuation fragility).
- Consistent light/dark mode tokens, including explicit chart canvas/grid/font colors to prevent unreadable dark-mode charts.

## Source URLs

- https://www.datadoghq.com/product/platform/dashboards/
- https://learn.microsoft.com/en-us/power-bi/create-reports/service-dashboards-design-tips
- https://www.tableau.com/blog/best-practices-for-building-effective-dashboards
- https://www.metabase.com/docs/latest/dashboards/filters
- https://cloud.google.com/looker/docs/viewing-dashboards
- https://www.anaplan.com/solutions/financial-planning-analysis-software/
- https://planful.com/platform/scenario-planning/
- https://www.cubesoftware.com/blog/fpa-dashboards
- https://corporatefinanceinstitute.com/resources/valuation/sensitivity-analysis/
