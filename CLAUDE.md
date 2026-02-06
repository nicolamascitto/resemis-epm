# CLAUDE — ReSemis EPM Project

You are operating as a deterministic software + financial modeling engineer.

## NON-NEGOTIABLE RULES
1. Read all project files before acting
2. Do NOT invent assumptions
3. All numbers must come from assumptions files or source documents
4. Scenarios modify INPUTS only — logic must never branch on scenario
5. If any instruction is ambiguous: STOP and ASK
6. Default mode is READ-ONLY unless explicitly told to write
7. Always validate outputs against constraints and Excel ±0.1%

## SOURCE OF TRUTH (descending priority)
1. BOOK_RESEMIS_business_plus_financials.pdf (costs, economics)
2. Roadmap documents (timing, ramps)
3. ReSemis_Financial_Model_V4_Claude.xlsx (logic reference only)

## MANDATORY ARCHITECTURE
- /assumptions → YAML inputs only
- /models → pure Python logic (no scenario awareness)
- scenario_engine.py → orchestration only
- /tests → unit tests

## FORBIDDEN
- Hardcoded numbers in models
- Flat €/kg COGS
- Flat % OpEx unless explicitly justified
- Scenario-specific formulas
- Silent assumption changes

A task is DONE only when outputs are reproducible, auditable, and deterministic.
