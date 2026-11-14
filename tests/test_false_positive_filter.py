from false_positive_filter import FalsePositiveFilter, format_discarded, reading_source


def enviar(filtro, temperaturas, source="YAKU-001"):
    resultados = []
    for t in temperaturas:
        resultados.append(filtro.apply({"temperature": t}, source))
    return resultados


def test_pico_aislado_es_descartado():
    filtro = FalsePositiveFilter()
    resultados = enviar(filtro, [14.0, 14.2, 40.0])
    lectura, descartados = resultados[-1]

    assert lectura["temperature"] == 14.2
    assert "temperature" in descartados
    assert descartados["temperature"][0] == 40.0


def test_el_pico_deja_de_afectar_cuando_sale_de_la_ventana():
    filtro = FalsePositiveFilter()
    resultados = enviar(filtro, [14.0, 14.2, 40.0, 14.1, 14.3])
    assert resultados[-1][0]["temperature"] == 14.3


def test_desviacion_sostenida_es_conservada():
    filtro = FalsePositiveFilter()
    resultados = enviar(filtro, [14.0, 14.2, 30.0, 30.1, 30.2])
    lectura, descartados = resultados[-1]

    assert lectura["temperature"] == 30.1
    assert descartados == {}


def test_cada_fuente_tiene_su_propia_ventana():
    filtro = FalsePositiveFilter()
    enviar(filtro, [14.0, 14.0], source="YAKU-001")
    lectura, _ = filtro.apply({"temperature": 30.0}, "YAKU-002")
    assert lectura["temperature"] == 30.0


def test_campos_no_filtrados_pasan_intactos():
    filtro = FalsePositiveFilter()
    lectura, _ = filtro.apply({"deviceId": "YAKU-001", "temperature": 14.0}, "YAKU-001")
    assert lectura["deviceId"] == "YAKU-001"


def test_valor_no_numerico_no_rompe_el_filtro():
    filtro = FalsePositiveFilter()
    lectura, descartados = filtro.apply({"temperature": None}, "YAKU-001")
    assert lectura["temperature"] is None
    assert descartados == {}


def test_log_del_pico_descartado():
    filtro = FalsePositiveFilter()
    resultados = enviar(filtro, [14.0, 14.2, 40.0])
    lineas = format_discarded("YAKU-001", resultados[-1][1])
    assert len(lineas) == 1
    assert "Pico descartado" in lineas[0]
    assert "YAKU-001" in lineas[0]


def test_reading_source_prioriza_device_pond_y_topico():
    assert reading_source({"deviceId": "YAKU-001", "pondId": 3}, "yaku/telemetria/pond/9") == "YAKU-001"
    assert reading_source({"pondId": 3}, "yaku/telemetria/pond/9") == "pond/3"
    assert reading_source({}, "yaku/telemetria/pond/9") == "pond/9"
    assert reading_source({}, "otro/topico") == "desconocido"
