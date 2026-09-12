# Synthetic inspection report

Write a findings section and a summary from the public source `inspection`.
All data in this task is synthetic. Use `report_template.toml`, `sources.toml`,
and `checks.toml` to inspect the section fields, dependencies, and public rules.

State only the recorded count in both sections. Cite the source ID `inspection`
in both sections. Keep each section below 160 characters. Do not add a date,
cost, or other number that the source does not provide.

Write a JSON object with `findings` and `summary` keys. Each value has a `text`
string. Save the object to `/workspace/output.json`.

The public rubric weights evidence twice as much as concise presentation.
Required fields and pattern checks support drafting. The independent verifier
checks the submitted artifact and computes the task reward.
