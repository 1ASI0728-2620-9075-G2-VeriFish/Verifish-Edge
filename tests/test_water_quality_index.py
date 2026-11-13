import pytest

from water_quality import compute_ica, quality_of

LECTURA_OPTIMA = {"ph": 7.0, "temperature": 14.0, "turbidity": 5.0, "oxygen": 8.0}


def test_todo_dentro_del_rango_da_100():
    assert compute_ica(LECTURA_OPTIMA) == 100.0


def test_limites_del_rango_cuentan_como_optimos():
    assert quality_of(6.5, 6.5, 8.0) == 100.0
    assert quality_of(8.0, 6.5, 8.0) == 100.0


def test_ph_muy_alto_baja_el_ica():
    lectura = {**LECTURA_OPTIMA, "ph": 12.0}
    # pH fuera por 4.0 con ancho 1.5 -> q = 0; el resto pesa 0.7
    assert compute_ica(lectura) == 70.0


def test_fuera_del_rango_pierde_puntaje_proporcional():
    # 0.75 por encima del máximo, ancho 1.5 -> q = 50
    assert quality_of(8.75, 6.5, 8.0) == pytest.approx(50.0)


def test_puntaje_nunca_baja_de_cero():
    assert quality_of(100.0, 6.5, 8.0) == 0.0


def test_renormaliza_cuando_falta_un_parametro():
    # Sin oxígeno, los pesos restantes se reparten y el resultado sigue en 100
    lectura = {"ph": 7.0, "temperature": 14.0, "turbidity": 5.0}
    assert compute_ica(lectura) == 100.0


def test_valores_no_numericos_se_ignoran():
    lectura = {**LECTURA_OPTIMA, "oxygen": "sin dato", "turbidity": None}
    assert compute_ica(lectura) == 100.0


def test_sin_parametros_conocidos_devuelve_none():
    assert compute_ica({"deviceId": "YAKU-001"}) is None


def test_rango_invalido_lanza_error():
    with pytest.raises(ValueError):
        quality_of(5.0, 8.0, 8.0)
