You are a senior security systems engineer sizing CCTV storage.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Camera count | {{ camera_count }} | count |
| Average bitrate | {{ average_bitrate_mbps }} | Mbps per camera |
| Recording hours per day | {{ recording_hours_per_day }} | h/day |
{% if retention_days is defined %}
| Retention period | {{ retention_days }} | days |
{% endif %}
| Storage overhead | {{ storage_overhead_pct }} | % |

## Constraints

- Convert Mbps to GB using `bitrate x hours x 3600 / 8 / 1000`.
- Total usable storage equals daily storage per camera times camera count times retention days.
- Raw storage equals usable storage times the overhead factor.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "daily_storage_per_camera_gb": <numeric_value>,
  "usable_storage_required_tb": <numeric_value>,
  "raw_storage_with_overhead_tb": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
