# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 5,
      "field": "num_people",
      "given_value": 16.67,
      "correct_value": 25.0,
      "explanation": "Wrong AS 1668.2 lookup: used Meeting Rooms density (3.0 m\u00b2/person) instead of Conference Rooms (2.0 m\u00b2/person)"
    },
    {
      "room_no": 8,
      "field": "ventilation_latent_w",
      "given_value": 0.0,
      "correct_value": 3380.55,
      "explanation": "Ventilation latent heat gain omitted (set to 0)"
    },
    {
      "room_no": 4,
      "field": "conduction_w",
      "given_value": 5832.0,
      "correct_value": 2160,
      "explanation": "Conduction uses volume (324.0 m\u00b3 \u00d7 18 W/m\u00b2 = 5832.0) instead of floor area (120 m\u00b2 \u00d7 18 W/m\u00b2 = 2160)"
    },
    {
      "room_no": 10,
      "field": "ventilation_latent_w",
      "given_value": 7109.24,
      "correct_value": 1901.56,
      "explanation": "Used raw outdoor enthalpy (65.8 kJ/kg) instead of \u0394h (17.599999999999994 kJ/kg) in latent formula"
    },
    {
      "room_no": 6,
      "field": "people_sensible_w",
      "given_value": 1137.5,
      "correct_value": 1312.5,
      "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain"
    }
  ]
}
```
