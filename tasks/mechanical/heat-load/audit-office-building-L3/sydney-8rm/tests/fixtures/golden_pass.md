# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 3,
      "field": "conduction_w",
      "given_value": 4320.0,
      "correct_value": 1600,
      "explanation": "Conduction uses volume (270.0 m\u00b3 \u00d7 16 W/m\u00b2 = 4320.0) instead of floor area (100 m\u00b2 \u00d7 16 W/m\u00b2 = 1600)"
    },
    {
      "room_no": 4,
      "field": "people_sensible_w",
      "given_value": 1300.0,
      "correct_value": 1500.0,
      "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain"
    },
    {
      "room_no": 6,
      "field": "ventilation_latent_w",
      "given_value": 0.0,
      "correct_value": 1584.63,
      "explanation": "Ventilation latent heat gain omitted (set to 0)"
    }
  ]
}
```
