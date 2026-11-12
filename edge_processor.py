import os
import sys
import time
import json
import threading
import requests
import redis
import paho.mqtt.client as mqtt
from flask import Flask, request, jsonify, Response
from dotenv import load_dotenv

from signing import sign
from false_positive_filter import (
    FalsePositiveFilter,
    format_discarded,
    reading_source,
)

# Cargar variables de entorno desde .env
load_dotenv()

# Configuración inicial del servidor Flask
app = Flask(__name__)

# ==========================================
# 1. CONFIGURACIÓN DEL ENTORNO
# ==========================================
# Mosquitto (Broker MQTT)
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "yaku/telemetria/pond/#") # '#' escucha cualquier estanque

# Redis (Base de Datos en Memoria / Cola de mensajes)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_QUEUE = os.getenv("REDIS_QUEUE", "telemetry_queue")

# API Destino (Backend / Ingest Endpoint)
API_URL = os.getenv("API_URL", "http://localhost:8080/api/v1/telemetry/manual-ingest")

# Firma HMAC de las lecturas (headers X-Farm-Id y X-Signature)
FARM_ID = os.getenv("FARM_ID", "").strip()
FARM_TOKEN = os.getenv("FARM_TOKEN", "").strip()

if not FARM_ID or not FARM_TOKEN:
    print("Faltan FARM_ID y/o FARM_TOKEN en el .env. Son obligatorios para firmar la telemetría.")
    sys.exit(1)

if not FARM_ID.isdigit():
    print("FARM_ID debe ser numérico (el backend lo recibe como Long en X-Farm-Id).")
    sys.exit(1)

# Inicializar conexión a Redis
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    redis_client.ping()
    print("Conectado a Redis")
except Exception as e:
    print(f"Error conectando a Redis: {e}")
    sys.exit(1)

# ==========================================
# 2. EL RECEPTOR (MQTT -> REDIS)
# ==========================================
# Filtro de falsos positivos: mediana de las últimas 3 lecturas por estanque
# y parámetro. Se aplica antes del ICA y antes de encolar en Redis.
telemetry_filter = FalsePositiveFilter()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Conectado a Mosquitto MQTT en {MQTT_BROKER}")
        client.subscribe(MQTT_TOPIC)
        client.subscribe("yaku/config/#")
        client.subscribe("yaku/command/devices/#")
    else:
        print(f"Fallo al conectar a MQTT. Código: {rc}")

def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8")
    print(f"\n [MQTT] Recibido en tópico '{msg.topic}': {payload}")
    
    if msg.topic.startswith("yaku/config/thresholds/"):
        species = msg.topic.split("/")[-1]
        redis_client.set(f"config:species:{species}", payload)
        print(f"[REDIS] Configuración de umbrales guardada para especie {species}")
        return
        
    if msg.topic.startswith("yaku/config/devices/"):
        device_id = msg.topic.split("/")[-1]
        redis_client.set(f"route:device:{device_id}", payload)
        print(f"[REDIS] Routing guardado para dispositivo {device_id} -> {payload}")
        return
        
    if msg.topic.startswith("yaku/command/devices/"):
        device_id = msg.topic.split("/")[-1]
        redis_client.setex(f"cmd:device:{device_id}", 30, payload)
        print(f"[REDIS] Comando remoto guardado para {device_id} -> {payload} (Expira en 30s)")
        return
    
    try:
        data = json.loads(payload)
        
        # El payload ahora se envía tal cual, porque contiene el 'deviceId' (ej: YAKU-001)
        # El backend se encargará de buscar en su base de datos a qué 'pondId' pertenece.
        
        # Filtrar picos antes de encolar: una lectura aislada fuera de rango
        # no debe llegar al ICA ni a la nube.
        source = reading_source(data, msg.topic)
        data, descartados = telemetry_filter.apply(data, source)
        for linea in format_discarded(source, descartados):
            print(linea)
        
        # Empujar a la cola izquierda de Redis (FIFO)
        redis_client.lpush(REDIS_QUEUE, json.dumps(data))
        print(f"[REDIS] Dato guardado en la cola local para dispositivo {data.get('deviceId', 'Desconocido')}")

    except json.JSONDecodeError:
        print("[ERROR] El payload no es un JSON válido")

# Configurar el cliente MQTT
mqtt_client = mqtt.Client(client_id="YakuEdgeProcessor")
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# ==========================================
# 3. EL SINCRONIZADOR (REDIS -> NUBE)
# ==========================================
def sync_to_cloud():
    print("Iniciando el motor de sincronización hacia la API...")
    backoff_delay = 1
    max_backoff = 60

    while True:
        dato_crudo = None
        try:
            # Extraer el dato más antiguo de la cola derecha (RPOP)
            dato_crudo = redis_client.rpop(REDIS_QUEUE)

            if dato_crudo:
                data = json.loads(dato_crudo)

                # Map spanish keys from Arduino to english keys for the Java API
                api_data = {
                    "deviceId": data.get("deviceId"),
                    "temperature": float(data.get("temperature", 0)),
                    "turbidity": float(data.get("turbidity", 0)),
                    "ica": float(data.get("ica", 0)) if "ica" in data else None
                }
                print(f"[API] Enviando dato a la nube: {api_data}")

                # Firmar exactamente los mismos bytes que se envían:
                # el backend valida HMAC-SHA256(body crudo, FARM_TOKEN).
                body = json.dumps(api_data, separators=(",", ":"))
                signature = sign(body, FARM_TOKEN)
                headers = {
                    "Content-Type": "application/json",
                    "X-Farm-Id": FARM_ID,
                    "X-Signature": signature,
                }
                print(f"[HMAC] X-Farm-Id={FARM_ID} X-Signature={signature}")

                # Disparar hacia la API (con un límite de 5 segundos de espera)
                response = requests.post(
                    API_URL,
                    data=body.encode("utf-8"),
                    headers=headers,
                    timeout=5,
                )

                if response.status_code in (200, 201):
                    print("[API] Subida exitosa.")
                    backoff_delay = 1
                else:
                    print(
                        f"[API] Rechazó el dato (HTTP {response.status_code}). "
                        f"Devolviendo a la cola y reintentando en {backoff_delay}s..."
                    )
                    # Si la API falla, devolvemos a la cola derecha para reintentar con backoff
                    redis_client.rpush(REDIS_QUEUE, dato_crudo)
                    time.sleep(backoff_delay)
                    backoff_delay = min(backoff_delay * 2, max_backoff)
            else:
                # Si la cola está vacía, dormimos 1 segundo para no saturar el CPU de la laptop
                backoff_delay = 1
                time.sleep(1)

        except requests.exceptions.RequestException as e:
            print(f"🔌 [RED] Sin internet o API caída: {e}")
            if dato_crudo:
                print(
                    f"[REDIS] Rescatando el dato y devolviéndolo a la cola. "
                    f"Reintentando en {backoff_delay}s..."
                )
                redis_client.rpush(REDIS_QUEUE, dato_crudo)
            # Si se cae el internet, aplicamos backoff exponencial antes de reintentar
            time.sleep(backoff_delay)
            backoff_delay = min(backoff_delay * 2, max_backoff)
        except Exception as e:
            print(f"[SISTEMA] Error inesperado: {e}")
            if dato_crudo:
                redis_client.rpush(REDIS_QUEUE, dato_crudo)
            time.sleep(backoff_delay)
            backoff_delay = min(backoff_delay * 2, max_backoff)

# ==========================================
# 3.5. EL PUENTE HTTP (FLASK -> MQTT)
# ==========================================
@app.route('/ingest', methods=['POST'])
def ingest_http():
    try:
        data = request.json
        print(f"\n[HTTP] Recibido desde Arduino: {data}")
        # Publicamos internamente en Mosquitto simulando ser un dispositivo físico
        mqtt_client.publish("yaku/telemetria/pond/1", json.dumps(data))
        
        # Resolver configuración para el dispositivo
        device_id = data.get("deviceId") if isinstance(data, dict) else None
        if device_id:
            species = redis_client.get(f"route:device:{device_id}")
            if species:
                config_raw = redis_client.get(f"config:species:{species}")
                if config_raw:
                    try:
                        config = json.loads(config_raw)
                        max_temp = config.get("maxTemp", 0.0)
                        max_turb = config.get("maxTurb", 0.0)
                        response_str = f"CFG:{max_temp},{max_turb}"
                        
                        cmd = redis_client.get(f"cmd:device:{device_id}")
                        if cmd:
                            response_str += f",{cmd}"
                            redis_client.delete(f"cmd:device:{device_id}")
                            
                        response_str += "\n"
                        return Response(response_str, status=200, mimetype='text/plain')
                    except Exception as e:
                        print(f"[ERROR] Parseando config JSON desde Redis: {e}")
        
        return jsonify({"status": "ok", "message": "Puenteado a MQTT"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/queue', methods=['GET'])
def get_queue():
    try:
        # Obtenemos todos los elementos de la lista en Redis sin borrarlos (LRANGE)
        # 0 al -1 significa desde el primer elemento al último
        items_raw = redis_client.lrange(REDIS_QUEUE, 0, -1)
        items = []
        for item in items_raw:
            try:
                items.append(json.loads(item))
            except Exception:
                items.append(item)
                
        return jsonify({
            "status": "ok", 
            "count": len(items),
            "queue": items
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
# 4. ARRANQUE DEL SISTEMA
# ==========================================
if __name__ == "__main__":
    # Arrancar MQTT en un hilo secundario
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    
    # Arrancar el sincronizador de nube en otro hilo (daemon para que muera al cerrar)
    sync_thread = threading.Thread(target=sync_to_cloud, daemon=True)
    sync_thread.start()
    
    # Arrancar el servidor web (Flask) en el hilo principal
    print("\n[FLASK] Iniciando Servidor Puente HTTP en puerto 5000...")
    try:
        # debug=False y use_reloader=False son necesarios para no crear múltiples clientes MQTT
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("\n Apagando el Nodo Edge...")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        print("Apagado seguro completado.")