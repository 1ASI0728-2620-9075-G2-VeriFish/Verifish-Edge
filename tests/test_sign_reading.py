import json
import shutil
import subprocess

import pytest

from signing import sign

TOKEN = "farm-token-de-prueba"
BODY = json.dumps(
    {"deviceId": "YAKU-001", "temperature": 14.5, "turbidity": 4.0, "ph": 7.2, "ica": 92.0},
    separators=(",", ":"),
)


def test_vector_conocido_rfc4231():
    # Caso 2 de RFC 4231 para HMAC-SHA256
    esperado = "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843"
    assert sign("what do ya want for nothing?", "Jefe") == esperado


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl no está instalado")
def test_firma_coincide_con_openssl():
    salida = subprocess.run(
        ["openssl", "dgst", "-sha256", "-hmac", TOKEN],
        input=BODY.encode("utf-8"),
        capture_output=True,
        check=True,
    ).stdout.decode()
    # openssl imprime "SHA2-256(stdin)= <hex>" o "(stdin)= <hex>"
    esperado = salida.strip().split("= ")[-1]
    assert sign(BODY, TOKEN) == esperado


def test_firma_es_hex_minusculas_de_64_caracteres():
    firma = sign(BODY, TOKEN)
    assert len(firma) == 64
    assert firma == firma.lower()
    int(firma, 16)


def test_cambiar_el_body_cambia_la_firma():
    assert sign(BODY, TOKEN) != sign(BODY.replace("14.5", "30.0"), TOKEN)


def test_cambiar_el_token_cambia_la_firma():
    assert sign(BODY, TOKEN) != sign(BODY, "otro-token")


def test_json_compacto_es_el_que_se_firma():
    # El Edge firma json.dumps(..., separators=(',', ':')); con espacios la firma sería otra
    con_espacios = json.dumps(json.loads(BODY))
    assert " " in con_espacios
    assert sign(con_espacios, TOKEN) != sign(BODY, TOKEN)
