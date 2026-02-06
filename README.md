# resemis-epm

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
```

## Run

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
