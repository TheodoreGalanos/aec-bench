# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 2,
      "field": "people_sensible_w",
      "given_value": 2275.0,
      "correct_value": 2625.0,
      "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain"
    },
    {
      "room_no": 6,
      "field": "ventilation_latent_w",
      "given_value": 0.0,
      "correct_value": 840.34,
      "explanation": "Ventilation latent heat gain omitted (set to 0)"
    },
    {
      "room_no": 11,
      "field": "ventilation_latent_w",
      "given_value": 95423.77,
      "correct_value": 12100.84,
      "explanation": "Used raw outdoor enthalpy (55.2 kJ/kg) instead of \u0394h (7.0 kJ/kg) in latent formula"
    },
    {
      "room_no": 5,
      "field": "conduction_w",
      "given_value": 6075.0,
      "correct_value": 2250,
      "explanation": "Conduction uses volume (405.0 m\u00b3 \u00d7 15 W/m\u00b2 = 6075.0) instead of floor area (150 m\u00b2 \u00d7 15 W/m\u00b2 = 2250)"
    },
    {
      "room_no": 3,
      "field": "ventilation_sensible_w",
      "given_value": 0.0,
      "correct_value": 5227.2,
      "explanation": "Ventilation sensible uses indoor-indoor delta T (0\u00b0C) instead of outdoor-indoor (12.0\u00b0C)"
    }
  ]
}
```
