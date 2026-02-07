<task type="auto">
  <name>Create visual research moodboard</name>
  <files>docs/design/MOODBOARD.md,docs/design/moodboard/screenshots/*,scripts/capture_reference_screenshots.py</files>
  <action>Capture high-signal visual references and synthesize a coherent direction for the EPM UI.</action>
  <verify>python scripts/capture_reference_screenshots.py</verify>
  <done>Moodboard markdown and screenshots are committed and traceable.</done>
</task>

<task type="auto">
  <name>Implement multi-view dashboard with dark mode</name>
  <files>streamlit_app.py,ui/dashboard_data.py,.streamlit/config.toml,requirements.txt</files>
  <action>Deliver executive, team, and individual views with KPI cards, chart grid, filters, pagination, contextual right panel, and tokenized theme switch.</action>
  <verify>python -m streamlit run streamlit_app.py --server.headless true --server.port 8501</verify>
  <done>Dashboard runs locally and all sections render in light and dark mode.</done>
</task>

<task type="auto">
  <name>Validate screenshots and deployment path</name>
  <files>scripts/capture_ui_screenshots.py,docs/design/ui-validation/*,README.md,DEPLOYMENT.md</files>
  <action>Capture light/dark UI screenshots per section and document free-host deployment workflow.</action>
  <verify>python scripts/capture_ui_screenshots.py</verify>
  <done>Theme transition evidence and deployment instructions are available for team handoff.</done>
</task>
