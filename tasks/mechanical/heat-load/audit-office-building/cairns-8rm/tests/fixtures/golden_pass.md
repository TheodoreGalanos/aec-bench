# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 2,
      "field": "num_people",
      "given_value": 6.0,
      "correct_value": 4.0,
      "explanation": "Wrong AS 1668.2 lookup: used Hotel Bedrooms density (10.0 m\u00b2/person) instead of Hotel Suites (15.0 m\u00b2/person)"
    },
    {
      "room_no": 3,
      "field": "conduction_w",
      "given_value": 4500.0,
      "correct_value": 1500,
      "explanation": "Conduction uses volume (300.0 m\u00b3 \u00d7 15 W/m\u00b2 = 4500.0) instead of floor area (100 m\u00b2 \u00d7 15 W/m\u00b2 = 1500)"
    },
    {
      "room_no": 1,
      "field": "ventilation_latent_w",
      "given_value": 0.0,
      "correct_value": 1992.8,
      "explanation": "Ventilation latent heat gain omitted (set to 0)"
    }
  ]
}
```
