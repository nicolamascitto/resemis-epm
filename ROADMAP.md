# Roadmap

## Phase 1: Foundation Closure
- Implement assumptions loader/validator module.
- Add assumptions tests and integrate into scenario runtime.

## Phase 2: Workbook Bridge
- Parse workbook V8 assumptions and derive model inputs.
- Generate `assumptions/base.yaml` from workbook.

## Phase 3: Reconciliation
- Compute workbook baseline outputs from sheet formulas.
- Compare engine annual outputs against workbook baseline.

## Phase 4: Hardening
- Fix test defects and keep full suite green.
- Update state/progress and ship.
