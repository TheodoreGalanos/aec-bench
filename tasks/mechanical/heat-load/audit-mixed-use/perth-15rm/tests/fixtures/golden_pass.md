# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 7,
      "field": "ventilation_latent_w",
      "given_value": 112941.18,
      "correct_value": 43505.4,
      "explanation": "Used raw outdoor enthalpy (78.4 kJ/kg) instead of \u0394h (30.200000000000003 kJ/kg) in latent formula"
    },
    {
      "room_no": 3,
      "field": "conduction_w",
      "given_value": 12150.0,
      "correct_value": 4500,
      "explanation": "Conduction uses volume (675.0 m\u00b3 \u00d7 18 W/m\u00b2 = 12150.0) instead of floor area (250 m\u00b2 \u00d7 18 W/m\u00b2 = 4500)"
    },
    {
      "room_no": 15,
      "field": "people_sensible_w",
      "given_value": 2275.0,
      "correct_value": 2625.0,
      "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain"
    },
    {
      "room_no": 8,
      "field": "num_people",
      "given_value": 8.0,
      "correct_value": 16.0,
      "explanation": "Wrong AS 1668.2 lookup: used Office Areas density (10.0 m\u00b2/person) instead of Kitchens (Commercial) (5.0 m\u00b2/person)"
    },
    {
      "room_no": 14,
      "field": "ventilation_latent_w",
      "given_value": 0.0,
      "correct_value": 1450.18,
      "explanation": "Ventilation latent heat gain omitted (set to 0)"
    }
  ]
}
```
