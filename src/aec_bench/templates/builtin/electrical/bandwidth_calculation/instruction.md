You are a senior ITS communications engineer sizing network bandwidth.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Cameras | {{ camera_count }} | count |
| Camera data rate | {{ camera_data_rate_mbps }} | Mbps each |
| Controllers | {{ controller_count }} | count |
| Controller data rate | {{ controller_data_rate_mbps }} | Mbps each |
| Sensors | {{ sensor_count }} | count |
| Sensor data rate | {{ sensor_data_rate_mbps }} | Mbps each |
| Network overhead | {{ network_overhead_pct }} | % |
{% if future_capacity_buffer_pct is defined %}
| Future capacity buffer | {{ future_capacity_buffer_pct }} | % |
{% endif %}

## Constraints

- Sum device count times data rate for base bandwidth.
- Apply network overhead to get peak demand.
- Apply future capacity buffer to peak demand.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "base_bandwidth_mbps": <numeric_value>,
  "peak_demand_mbps": <numeric_value>,
  "required_bandwidth_mbps": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
