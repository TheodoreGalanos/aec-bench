# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 4,
      "field": "ventilation_sensible_w",
      "given_value": 0.0,
      "correct_value": 4126.1,
      "explanation": "Ventilation sensible uses indoor-indoor delta T (0\u00b0C) instead of outdoor-indoor (12.399999999999999\u00b0C)"
    },
    {
      "room_no": 8,
      "field": "num_people",
      "given_value": 10.0,
      "correct_value": 20.0,
      "explanation": "Wrong AS 1668.2 lookup: used Office Areas density (10.0 m\u00b2/person) instead of Retail Shops (5.0 m\u00b2/person)"
    },
    {
      "room_no": 7,
      "field": "ventilation_latent_w",
      "given_value": 12662.67,
      "correct_value": 2247.3,
      "explanation": "Used raw outdoor enthalpy (58.6 kJ/kg) instead of \u0394h (10.399999999999999 kJ/kg) in latent formula"
    },
    {
      "room_no": 9,
      "field": "conduction_w",
      "given_value": 5600.0,
      "correct_value": 1600,
      "explanation": "Conduction uses volume (280.0 m\u00b3 \u00d7 20 W/m\u00b2 = 5600.0) instead of floor area (80 m\u00b2 \u00d7 20 W/m\u00b2 = 1600)"
    },
    {
      "room_no": 2,
      "field": "people_sensible_w",
      "given_value": 1625.0,
      "correct_value": 1875.0,
      "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain"
    }
  ]
}
```
