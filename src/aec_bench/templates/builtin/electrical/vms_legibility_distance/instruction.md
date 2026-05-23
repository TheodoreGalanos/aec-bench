You are a senior ITS engineer checking variable message sign readability.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Character height | {{ character_height_in }} | in |
| Design speed | {{ design_speed_mph }} | mph |
{% if reading_rate_chars_s is defined %}
| Reading rate | {{ reading_rate_chars_s }} | chars/s |
{% endif %}

## Constraints

- Use `minimum_legibility_distance = character_height_in x 40 ft`.
- Convert design speed from mph to ft/s.
- Reading time available equals legibility distance divided by speed.
- Message length limit equals reading time times reading rate.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "minimum_legibility_distance_ft": <numeric_value>,
  "design_speed_ft_s": <numeric_value>,
  "reading_time_available_s": <numeric_value>,
  "message_length_limit_chars": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
