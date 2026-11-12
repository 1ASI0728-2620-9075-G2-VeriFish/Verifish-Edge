"""Filtro de falsos positivos (T17) para la telemetría del nodo Edge.

Un sensor puede entregar un pico aislado (ruido eléctrico, una hoja tapando la
sonda, una lectura en falso). Para que ese pico no llegue al ICA ni a la cola
de Redis, cada parámetro pasa por una ventana de las últimas 3 lecturas y se
publica la mediana:

- pico aislado -> la mediana se queda con los valores normales (se descarta).
- desviación sostenida -> la mediana acompaña al sensor (se conserva).

La ventana se lleva por estanque/dispositivo y por parámetro, así que la
historia de un estanque no contamina a otro.
"""

import statistics
import threading
from collections import deque

# Lecturas que entran en la ventana por cada parámetro.
WINDOW_SIZE = 3

# Parámetros numéricos que se filtran. El resto del payload pasa intacto.
FILTERED_PARAMETERS = ("temperature", "ph", "turbidity", "oxygen")

# Desvío mínimo (valor crudo vs mediana) para reportar un pico descartado.
# Evita llenar el log con el ruido normal del sensor.
TOLERANCES = {
    "temperature": 1.0,
    "ph": 0.3,
    "turbidity": 2.0,
    "oxygen": 0.5,
}

UNITS = {
    "temperature": "°C",
    "ph": "pH",
    "turbidity": "NTU",
    "oxygen": "mg/L",
}


class FalsePositiveFilter:
    """Ventana móvil de lecturas por fuente (estanque/dispositivo) y parámetro."""

    def __init__(self, window_size=WINDOW_SIZE, parameters=FILTERED_PARAMETERS):
        if window_size < 1:
            raise ValueError("window_size debe ser >= 1")
        self.window_size = window_size
        self.parameters = tuple(parameters)
        self._windows = {}
        self._lock = threading.Lock()

    def apply(self, reading, source):
        """Filtra una lectura y devuelve (lectura_filtrada, picos_descartados).

        ``source`` identifica al estanque/dispositivo (ver ``reading_source``).
        ``picos_descartados`` es un dict {parámetro: (valor_crudo, mediana)}.
        """
        filtered = dict(reading)
        discarded = {}

        with self._lock:
            for parameter in self.parameters:
                if parameter not in reading:
                    continue

                try:
                    value = float(reading[parameter])
                except (TypeError, ValueError):
                    # Valor no numérico (None, texto): se deja tal como vino.
                    continue

                key = (source, parameter)
                window = self._windows.setdefault(
                    key, deque(maxlen=self.window_size)
                )
                # Se guarda el valor crudo: cuando el pico sale de la ventana,
                # el filtro vuelve solo a la lectura real del sensor.
                window.append(value)

                median = float(statistics.median(window))
                filtered[parameter] = round(median, 2)

                tolerance = TOLERANCES.get(parameter, 0.0)
                if abs(value - median) > tolerance:
                    discarded[parameter] = (value, median, len(window))

        return filtered, discarded


def reading_source(data, topic):
    """Identifica de qué estanque/dispositivo viene una lectura.

    Orden: ``deviceId`` -> ``pondId`` -> id del tópico
    ``yaku/telemetria/pond/<id>``.
    """
    device_id = data.get("deviceId")
    if device_id:
        return str(device_id)

    pond_id = data.get("pondId")
    if pond_id:
        return f"pond/{pond_id}"

    parts = topic.split("/") if topic else []
    if len(parts) >= 4 and parts[2] == "pond":
        return f"pond/{parts[3]}"

    return "desconocido"


def format_discarded(source, discarded):
    """Arma una línea de log por cada pico descartado."""
    lines = []
    for parameter, (value, median, samples) in discarded.items():
        unit = UNITS.get(parameter, "")
        lines.append(
            f"[FILTRO] Pico descartado | {source} | "
            f"{parameter}: {value:g} {unit} -> {median:g} {unit} "
            f"(mediana de {samples} lecturas)"
        )
    return lines
