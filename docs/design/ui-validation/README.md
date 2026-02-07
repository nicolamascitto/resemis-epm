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
- Teams: `teams_light.png`, `teams_dark.png`
- Individuals: `individuals_light.png`, `individuals_dark.png`
- Goals: `goals_light.png`, `goals_dark.png`
- Reviews: `reviews_light.png`, `reviews_dark.png`
- Settings: `settings_light.png`, `settings_dark.png`

## Verification Checklist

- KPI cards preserve hierarchy and contrast in both themes.
- Chart backgrounds, axes, legends, and series remain readable in both themes.
- Tables and filters are legible and maintain affordance boundaries.
- Context panel remains visually distinct from main grid in both themes.
