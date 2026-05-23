# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 1,
      "field": "conduction_w",
      "given_value": 6300.0,
      "correct_value": 1800,
      "explanation": "Conduction uses volume (315.0 m\u00b3 \u00d7 20 W/m\u00b2 = 6300.0) instead of floor area (90 m\u00b2 \u00d7 20 W/m\u00b2 = 1800)"
    },
    {
      "room_no": 3,
      "field": "people_sensible_w",
      "given_value": 390.0,
      "correct_value": 450.0,
      "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain"
    },
    {
      "room_no": 5,
      "field": "ventilation_sensible_w",
      "given_value": 0.0,
      "correct_value": 677.6,
      "explanation": "Ventilation sensible uses indoor-indoor delta T (0\u00b0C) instead of outdoor-indoor (7.0\u00b0C)"
    }
  ]
}
```
