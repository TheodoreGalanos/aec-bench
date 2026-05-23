# Golden Pass Output

```json
{
  "errors_found": [
    {
      "room_no": 2,
      "field": "ventilation_latent_w",
      "given_value": 13882.35,
      "correct_value": 5781.51,
      "explanation": "Used raw outdoor enthalpy (82.6 kJ/kg) instead of \u0394h (34.39999999999999 kJ/kg) in latent formula"
    },
    {
      "room_no": 5,
      "field": "num_people",
      "given_value": 8.0,
      "correct_value": 16.0,
      "explanation": "Wrong AS 1668.2 lookup: used Office Areas density (10.0 m\u00b2/person) instead of Retail Shops (5.0 m\u00b2/person)"
    },
    {
      "room_no": 3,
      "field": "ventilation_latent_w",
      "given_value": 0.0,
      "correct_value": 7226.89,
      "explanation": "Ventilation latent heat gain omitted (set to 0)"
    }
  ]
}
```
