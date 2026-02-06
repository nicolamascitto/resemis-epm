# ReSemis EPM Project

## Vision
Build a deterministic, auditable EPM engine where the audited V8 workbook is the primary input basis and Python produces reproducible investor metrics.

## Goals
- Keep scenario logic pure and formula-invariant.
- Remove deferred assumptions-layer gaps (loader + validation + tests).
- Bridge workbook V8 inputs into executable assumptions.
- Provide reconciliation output between Python engine and workbook baseline.

## Constraints
- No hardcoded business constants inside engine formulas.
- Inputs come from YAML or workbook-derived YAML.
- Validation must be runnable from CLI.
