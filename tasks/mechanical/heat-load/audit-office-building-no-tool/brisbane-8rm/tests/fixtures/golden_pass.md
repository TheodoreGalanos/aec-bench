# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 3,
      "field": "num_people",
      "given_value": 8.0,
      "correct_value": 40.0,
      "explanation": "Wrong AS 1668.2 lookup: used Office Areas density (10.0 m\u00b2/person) instead of Classrooms (2.0 m\u00b2/person)"
    },
    {
      "room_no": 2,
      "field": "ventilation_latent_w",
      "given_value": 13675.87,
      "correct_value": 4417.77,
      "explanation": "Used raw outdoor enthalpy (71.2 kJ/kg) instead of \u0394h (23.0 kJ/kg) in latent formula"
    },
    {
      "room_no": 4,
      "field": "ventilation_sensible_w",
      "given_value": 0.0,
      "correct_value": 3114.54,
      "explanation": "Ventilation sensible uses indoor-indoor delta T (0\u00b0C) instead of outdoor-indoor (14.299999999999997\u00b0C)"
    }
  ]
}
```
