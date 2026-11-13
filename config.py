"""Rangos óptimos de calidad de agua y pesos del ICA.

Los valores de pH y temperatura salen del informe (trucha arcoíris:
pH 6.5-8.0, temperatura 10-18 °C). La turbidez y el oxígeno siguen lo
indicado en el plan del Sprint 1: turbidez <= 25 NTU y oxígeno >= 6 mg/L.
"""

# Rango óptimo por parámetro. Fuera de estos límites el parámetro pierde
# puntaje de forma proporcional al ancho del rango.
OPTIMAL_RANGES = {
    "ph": {"min": 6.5, "max": 8.0},
    "temperature": {"min": 10.0, "max": 18.0},
    "turbidity": {"min": 0.0, "max": 25.0},
    "oxygen": {"min": 6.0, "max": 14.0},
}

# Peso de cada parámetro en el índice. Si un parámetro no viene en la
# lectura, su peso se reparte entre los que sí están.
ICA_WEIGHTS = {
    "ph": 0.3,
    "temperature": 0.3,
    "turbidity": 0.2,
    "oxygen": 0.2,
}
