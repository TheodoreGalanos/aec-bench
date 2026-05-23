# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 7,
      "field": "ventilation_latent_w",
      "given_value": 92549.02,
      "correct_value": 38543.42,
      "explanation": "Used raw outdoor enthalpy (82.6 kJ/kg) instead of \u0394h (34.39999999999999 kJ/kg) in latent formula"
    },
    {
      "room_no": 9,
      "field": "num_people",
      "given_value": 9.0,
      "correct_value": 18.0,
      "explanation": "Wrong AS 1668.2 lookup: used Office Areas density (10.0 m\u00b2/person) instead of Retail Shops (5.0 m\u00b2/person)"
    },
    {
      "room_no": 4,
      "field": "ventilation_latent_w",
      "given_value": 0.0,
      "correct_value": 9291.72,
      "explanation": "Ventilation latent heat gain omitted (set to 0)"
    },
    {
      "room_no": 2,
      "field": "conduction_w",
      "given_value": 8748.0,
      "correct_value": 3240,
      "explanation": "Conduction uses volume (486.00000000000006 m\u00b3 \u00d7 18 W/m\u00b2 = 8748.0) instead of floor area (180 m\u00b2 \u00d7 18 W/m\u00b2 = 3240)"
    },
    {
      "room_no": 13,
      "field": "people_sensible_w",
      "given_value": 227.5,
      "correct_value": 262.5,
      "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain"
    }
  ]
}
```
