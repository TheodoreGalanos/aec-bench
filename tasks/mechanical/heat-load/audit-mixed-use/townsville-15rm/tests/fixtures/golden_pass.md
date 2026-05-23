# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 7,
      "field": "num_people",
      "given_value": 9.0,
      "correct_value": 45.0,
      "explanation": "Wrong AS 1668.2 lookup: used Office Areas density (10.0 m\u00b2/person) instead of Classrooms (2.0 m\u00b2/person)"
    },
    {
      "room_no": 4,
      "field": "ventilation_latent_w",
      "given_value": 23709.48,
      "correct_value": 9243.7,
      "explanation": "Used raw outdoor enthalpy (79.0 kJ/kg) instead of \u0394h (30.799999999999997 kJ/kg) in latent formula"
    },
    {
      "room_no": 8,
      "field": "ventilation_latent_w",
      "given_value": 0.0,
      "correct_value": 5915.97,
      "explanation": "Ventilation latent heat gain omitted (set to 0)"
    },
    {
      "room_no": 15,
      "field": "conduction_w",
      "given_value": 4900.0,
      "correct_value": 1400,
      "explanation": "Conduction uses volume (245.0 m\u00b3 \u00d7 20 W/m\u00b2 = 4900.0) instead of floor area (70 m\u00b2 \u00d7 20 W/m\u00b2 = 1400)"
    },
    {
      "room_no": 2,
      "field": "people_sensible_w",
      "given_value": 1040.0,
      "correct_value": 1200.0,
      "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain"
    }
  ]
}
```
