# Architecture
- `models/*`: deterministic engines by domain.
- `models/scenario.py`: orchestration and scenario comparison.
- `models/assumptions.py`: assumptions load/merge/validation.
- `models/workbook_bridge.py`: workbook V8 integration/reconciliation.
- `main.py`: CLI entry point.
- `ui/dashboard_data.py`: adapter layer from scenario outputs to dashboard entities.
- `streamlit_app.py`: web dashboard UI with multi-view navigation and dark mode.
- `scripts/capture_ui_screenshots.py`: visual regression evidence for light/dark themes.
