# resemis-epm

ReSemis EPM includes:

- Deterministic financial engine (`main.py`)
- Modern collaborative web dashboard (`streamlit_app.py`)

## Setup

Run bootstrap (creates `.venv` and installs dependencies):

```powershell
.\setup.ps1
```

Optional flags:

```powershell
# install into current Python env (no venv)
.\setup.ps1 -NoVenv

# upgrade pip during setup
.\setup.ps1 -UpgradePip

# install dev tooling (Playwright screenshots)
.\setup.ps1 -DevTools
```

## Run Dashboard UI

```powershell
streamlit run streamlit_app.py
```

## Run CLI Engine

```powershell
python main.py run --scenario base
python main.py run --all
python main.py validate
```

## Workbook Flow

```powershell
python main.py build-assumptions-from-workbook --xlsx "c:\projects\resemis-model-audit\output\ReSemis_Financial_Model_V8_CGPT_Rsheet_audited_v15.xlsx" --output assumptions/base.yaml
python main.py reconcile-workbook --xlsx "c:\projects\resemis-model-audit\output\ReSemis_Financial_Model_V8_CGPT_Rsheet_audited_v15.xlsx"
```

## UI Validation Screenshots

```powershell
python scripts/capture_ui_screenshots.py
```

Outputs:

- `docs/design/ui-validation/screenshots/*`
- `docs/design/MOODBOARD.md`

## Free Hosting

Deployment guides are in `DEPLOYMENT.md`.
