# ReSemis EPM Project

## Vision
Build a deterministic, auditable EPM engine with a production-ready web dashboard that teams can use collaboratively from any browser.

## Product Scope

### Existing Core
- Deterministic financial engine with workbook-derived assumptions.
- Scenario execution and reconciliation CLI.

### New Milestone Scope (UI + Collaboration)
- Build a modern EPM dashboard UI with executive, manager, and individual views.
- Add dark mode toggle and verify component transitions across themes.
- Deliver free-hosting deployment path for team access via shared URL.

## Goals
- Keep scenario logic pure and formula-invariant.
- Expose insights in a clear web UI with strong hierarchy.
- Support quick decision workflows with filters, drill-down tables, and contextual detail panel.
- Make deployment repeatable for free hosting targets.

## Constraints
- No hardcoded business constants inside engine formulas.
- Inputs come from YAML or workbook-derived YAML.
- Dark and light themes must both be fully usable and visually coherent.
- Deployment must target a free plan service.
