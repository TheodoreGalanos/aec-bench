# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 2,
      "field": "conduction_w",
      "given_value": 8400.0,
      "correct_value": 2400,
      "explanation": "Conduction uses volume (420.0 m\u00b3 \u00d7 20 W/m\u00b2 = 8400.0) instead of floor area (120 m\u00b2 \u00d7 20 W/m\u00b2 = 2400)"
    },
    {
      "room_no": 5,
      "field": "people_sensible_w",
      "given_value": 650.0,
      "correct_value": 750.0,
      "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain"
    },
    {
      "room_no": 7,
      "field": "ventilation_sensible_w",
      "given_value": 0.0,
      "correct_value": 1270.5,
      "explanation": "Ventilation sensible uses indoor-indoor delta T (0\u00b0C) instead of outdoor-indoor (7.0\u00b0C)"
    },
    {
      "room_no": 4,
      "field": "num_people",
      "given_value": 6.0,
      "correct_value": 12.0,
      "explanation": "Wrong AS 1668.2 lookup: used Office Areas density (10.0 m\u00b2/person) instead of Retail Shops (5.0 m\u00b2/person)"
    },
    {
      "room_no": 8,
      "field": "ventilation_latent_w",
      "given_value": 0.0,
      "correct_value": 156.06,
      "explanation": "Ventilation latent heat gain omitted (set to 0)"
    }
  ]
}
```
