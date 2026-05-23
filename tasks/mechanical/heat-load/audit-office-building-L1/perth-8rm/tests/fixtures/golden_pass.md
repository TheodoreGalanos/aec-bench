# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 5,
      "field": "ventilation_latent_w",
      "given_value": 75294.12,
      "correct_value": 29003.6,
      "explanation": "Used raw outdoor enthalpy (78.4 kJ/kg) instead of \u0394h (30.200000000000003 kJ/kg) in latent formula"
    },
    {
      "room_no": 2,
      "field": "conduction_w",
      "given_value": 12150.0,
      "correct_value": 4500,
      "explanation": "Conduction uses volume (675.0 m\u00b3 \u00d7 18 W/m\u00b2 = 12150.0) instead of floor area (250 m\u00b2 \u00d7 18 W/m\u00b2 = 4500)"
    },
    {
      "room_no": 3,
      "field": "people_sensible_w",
      "given_value": 975.0,
      "correct_value": 1125.0,
      "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain"
    }
  ]
}
```
