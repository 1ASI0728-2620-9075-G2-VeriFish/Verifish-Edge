import os
import time
import random
import requests
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# El simulador habla con el Edge por HTTP, igual que el Arduino real
EDGE_URL = os.getenv("EDGE_URL", "http://localhost:5000/ingest")
DEVICE_ID = os.getenv("DEVICE_ID", "YAKU-001")
INTERVALO = 3

# Estado simulado del dispositivo
bombas = {1: False, 2: False}
max_temp = None
max_turb = None


def procesar_respuesta(texto):
    """Interpreta 'CFG:maxTemp,maxTurb[,CMD]' y aplica la configuración y el comando."""
    global max_temp, max_turb

    texto = texto.strip()
    if not texto.startswith("CFG:"):
        return

    partes = texto[4:].split(",")
    try:
        max_temp = float(partes[0])
        max_turb = float(partes[1])
    except (ValueError, IndexError):
        print(f"[SIMULADOR] Configuración inválida: {texto}")
        return
    print(f"[SIMULADOR] Umbrales recibidos: maxTemp={max_temp} maxTurb={max_turb}")

    if len(partes) > 2:
        ejecutar_comando(partes[2].strip())


def ejecutar_comando(comando):
    if comando in ("PUMP1_ON", "PUMP2_ON"):
        numero = int(comando[4])
        bombas[numero] = True
        print(f"[SIMULADOR] Bomba {numero} activada | estado: {bombas}")
    elif comando:
        print(f"[SIMULADOR] Comando desconocido: {comando}")


print(f"Fake Arduino {DEVICE_ID} enviando a {EDGE_URL} cada {INTERVALO} segundos...")
print("Presiona Ctrl+C para detenerlo.\n")

try:
    while True:
        # Generar datos aleatorios simulando los sensores físicos de agua
        payload = {
            "deviceId": DEVICE_ID,
            "temperature": round(random.uniform(20.0, 35.0), 2),
            "ph": round(random.uniform(6.5, 8.5), 2),
            "turbidity": round(random.uniform(0.5, 5.0), 2)
        }

        try:
            resp = requests.post(EDGE_URL, json=payload, timeout=5)
            print(f"[SIMULADOR] Enviado: {payload} -> {resp.status_code}")
            procesar_respuesta(resp.text)
        except requests.exceptions.RequestException as e:
            print(f"[SIMULADOR] No se pudo contactar al Edge ({e}). ¿Está corriendo edge_processor.py?")

        time.sleep(INTERVALO)

except KeyboardInterrupt:
    print("\nApagando el simulador...")
