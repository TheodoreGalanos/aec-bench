# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 4,
      "field": "num_people",
      "given_value": 5.5,
      "correct_value": 3.67,
      "explanation": "Wrong AS 1668.2 lookup: used Hotel Bedrooms density (10.0 m\u00b2/person) instead of Hotel Suites (15.0 m\u00b2/person)"
    },
    {
      "room_no": 5,
      "field": "ventilation_latent_w",
      "given_value": 104233.69,
      "correct_value": 42513.01,
      "explanation": "Used raw outdoor enthalpy (81.4 kJ/kg) instead of \u0394h (33.2 kJ/kg) in latent formula"
    },
    {
      "room_no": 2,
      "field": "ventilation_latent_w",
      "given_value": 0.0,
      "correct_value": 1494.6,
      "explanation": "Ventilation latent heat gain omitted (set to 0)"
    },
    {
      "room_no": 7,
      "field": "conduction_w",
      "given_value": 5600.0,
      "correct_value": 1600,
      "explanation": "Conduction uses volume (280.0 m\u00b3 \u00d7 20 W/m\u00b2 = 5600.0) instead of floor area (80 m\u00b2 \u00d7 20 W/m\u00b2 = 1600)"
    },
    {
      "room_no": 10,
      "field": "people_sensible_w",
      "given_value": 1300.0,
      "correct_value": 1500.0,
      "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain"
    }
  ]
}
```
