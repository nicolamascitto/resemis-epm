<task type="auto">
  <name>Close deferred assumptions layer</name>
  <files>models/assumptions.py,models/scenario.py,tests/test_assumptions.py</files>
  <action>Implement schema-aware assumptions loader and validator, wire into scenario engine, add tests.</action>
  <verify>python -m pytest -q</verify>
  <done>Assumptions validation runs at runtime and tests pass.</done>
</task>

<task type="auto">
  <name>Adopt workbook V8 as input basis</name>
  <files>models/workbook_bridge.py,main.py,assumptions/base.yaml</files>
  <action>Build workbook parsing/baseline logic and CLI to generate assumptions from the attached workbook.</action>
  <verify>python main.py build-assumptions-from-workbook --xlsx &lt;path&gt; --output assumptions/base.yaml</verify>
  <done>Engine can run with workbook-derived assumptions.</done>
</task>

<task type="auto">
  <name>Add workbook reconciliation command</name>
  <files>models/workbook_bridge.py,main.py</files>
  <action>Add CLI command to compare annual engine metrics vs workbook-computed baseline and print variances.</action>
  <verify>python main.py reconcile-workbook --xlsx &lt;path&gt;</verify>
  <done>Variance JSON is emitted for revenue/cogs/opex/ebitda/cash/EV.</done>
</task>
