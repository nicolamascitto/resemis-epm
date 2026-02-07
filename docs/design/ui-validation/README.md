# UI Theme Validation

This folder contains screenshot evidence of the Streamlit dashboard in both light and dark themes.

## Capture Script

Run:

```bash
python scripts/capture_ui_screenshots.py
```

The script launches the app on port `8503`, captures each section in both themes, and stores images in:

- `docs/design/ui-validation/screenshots/*`

## Coverage

- Overview: `overview_light.png`, `overview_dark.png`
- Scenario Lab: `scenario_lab_light.png`, `scenario_lab_dark.png`
- Model Inputs: `model_inputs_light.png`, `model_inputs_dark.png`
- Risk Radar: `risk_radar_light.png`, `risk_radar_dark.png`
- Data Room: `data_room_light.png`, `data_room_dark.png`

## Verification Checklist

- KPI cards preserve hierarchy and contrast in both themes.
- Chart backgrounds, axes, legends, and series remain readable in both themes.
- Tables and filters are legible and maintain affordance boundaries.
- Context panel remains visually distinct from main grid in both themes.
