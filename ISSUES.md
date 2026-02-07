# Issues

- Need tighter monthly timing calibration to fully eliminate ending-cash variance versus annual workbook links.
- EV variance remains because workbook valuation horizon/terminal mechanics are annual-linked while engine runs monthly discounting.
- Conservative/aggressive workbook-native assumptions are not provided in the source workbook; current overrides remain generic.
- `streamlit_app.py` still uses a few APIs that emit future deprecation warnings in Streamlit output (non-blocking today).
- GitLab remote URL/token are required to complete push to GitLab from this local repo.
- Free hosting deployment requires platform account credentials to execute final publish step.
