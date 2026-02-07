<task type="auto">
  <name>Realign dashboard IA to investor/CFO workflows</name>
  <files>streamlit_app.py,ui/dashboard_data.py,docs/design/MOODBOARD.md</files>
  <action>Replace HR-oriented views with financial overview, scenario lab, model inputs, risk radar, and data room aligned to investor-grade decision flows.</action>
  <verify>python -m py_compile streamlit_app.py ui/dashboard_data.py</verify>
  <done>Navigation, charts, and context panels reflect ReSemis financial model use-cases.</done>
</task>

<task type="auto">
  <name>Implement assumptions workbench and stress modeling</name>
  <files>streamlit_app.py</files>
  <action>Add editable input forms for clients/markets, products/pricing/mix, BOM/input costs, OpEx/CapEx/funding, valuation; add stress sliders and sensitivity tornado.</action>
  <verify>python -m pytest -q</verify>
  <done>Users can modify core model assumptions and instantly see financial and valuation impact.</done>
</task>

<task type="auto">
  <name>Validate dark-mode coverage and updated navigation screenshots</name>
  <files>scripts/capture_ui_screenshots.py,docs/design/ui-validation/*,README.md,DEPLOYMENT.md</files>
  <action>Capture light/dark screenshots for new sections and ensure chart backgrounds/axes/labels are theme-correct.</action>
  <verify>python scripts/capture_ui_screenshots.py</verify>
  <done>All new sections have dark/light evidence and documentation is aligned.</done>
</task>
