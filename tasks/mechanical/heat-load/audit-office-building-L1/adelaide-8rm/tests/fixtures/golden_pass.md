# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 3,
      "field": "num_people",
      "given_value": 5.0,
      "correct_value": 3.33,
      "explanation": "Wrong AS 1668.2 lookup: used Hotel Bedrooms density (10.0 m\u00b2/person) instead of Hotel Suites (15.0 m\u00b2/person)"
    },
    {
      "room_no": 5,
      "field": "ventilation_latent_w",
      "given_value": 0.0,
      "correct_value": 11684.67,
      "explanation": "Ventilation latent heat gain omitted (set to 0)"
    },
    {
      "room_no": 1,
      "field": "conduction_w",
      "given_value": 972.0,
      "correct_value": 360,
      "explanation": "Conduction uses volume (81.0 m\u00b3 \u00d7 12 W/m\u00b2 = 972.0) instead of floor area (30 m\u00b2 \u00d7 12 W/m\u00b2 = 360)"
    }
  ]
}
```
