"""Cálculo del Índice de Calidad del Agua (ICA) en el nodo Edge.

El índice va de 0 a 100. Cada parámetro recibe un puntaje según qué tan lejos
esté del rango óptimo de la especie y luego se combinan con pesos. Si falta un
sensor, los pesos se renormalizan para no castigar la lectura por un dato que
nunca llegó.
"""

from config import ICA_WEIGHTS, OPTIMAL_RANGES


def quality_of(value, minimum, maximum):
    """Puntaje de 0 a 100 de un parámetro respecto a su rango óptimo."""
    width = maximum - minimum
    if width <= 0:
        raise ValueError("El rango óptimo debe tener max > min")

    if minimum <= value <= maximum:
        return 100.0

    distance = minimum - value if value < minimum else value - maximum
    return max(0.0, 100.0 * (1.0 - distance / width))


def compute_ica(reading, ranges=None, weights=None):
    """Calcula el ICA de una lectura y devuelve un valor de 0 a 100.

    ``reading`` es el diccionario que llega del sensor. Solo se usan los
    parámetros presentes y numéricos; el resto se ignora. Devuelve ``None``
    si la lectura no trae ningún parámetro conocido.
    """
    ranges = ranges or OPTIMAL_RANGES
    weights = weights or ICA_WEIGHTS

    total_score = 0.0
    total_weight = 0.0

    for parameter, weight in weights.items():
        if weight <= 0 or parameter not in ranges:
            continue

        value = to_float(reading.get(parameter))
        if value is None:
            continue

        limits = ranges[parameter]
        score = quality_of(value, limits["min"], limits["max"])
        total_score += score * weight
        total_weight += weight

    if total_weight == 0:
        return None

    return round(total_score / total_weight, 2)


def to_float(value):
    """Convierte un valor a float y devuelve None si no es numérico."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
