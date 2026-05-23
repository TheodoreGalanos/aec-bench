# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 4,
      "field": "num_people",
      "given_value": 8.0,
      "correct_value": 40.0,
      "explanation": "Wrong AS 1668.2 lookup: used Office Areas density (10.0 m\u00b2/person) instead of Classrooms (2.0 m\u00b2/person)"
    },
    {
      "room_no": 6,
      "field": "ventilation_latent_w",
      "given_value": 0.0,
      "correct_value": 6626.65,
      "explanation": "Ventilation latent heat gain omitted (set to 0)"
    },
    {
      "room_no": 7,
      "field": "conduction_w",
      "given_value": 1620.0,
      "correct_value": 600,
      "explanation": "Conduction uses volume (108.0 m\u00b3 \u00d7 15 W/m\u00b2 = 1620.0) instead of floor area (40 m\u00b2 \u00d7 15 W/m\u00b2 = 600)"
    },
    {
      "room_no": 2,
      "field": "ventilation_latent_w",
      "given_value": 17094.84,
      "correct_value": 5522.21,
      "explanation": "Used raw outdoor enthalpy (71.2 kJ/kg) instead of \u0394h (23.0 kJ/kg) in latent formula"
    },
    {
      "room_no": 5,
      "field": "ventilation_sensible_w",
      "given_value": 0.0,
      "correct_value": 6229.08,
      "explanation": "Ventilation sensible uses indoor-indoor delta T (0\u00b0C) instead of outdoor-indoor (14.299999999999997\u00b0C)"
    }
  ]
}
```
