import os
import json
import time
import random
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Configuración hacia el broker Mosquitto
BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC = os.getenv("MQTT_TOPIC", "yaku/telemetria/pond/1")

client = mqtt.Client(client_id="ArduinoSimulador")

try:
    client.connect(BROKER, PORT)
    print("Fake Arduino conectado a MQTT. Enviando datos cada 3 segundos...")
    print("Presiona Ctrl+C para detenerlo.\n")
    
    while True:
        # Generar datos aleatorios simulando los sensores físicos de agua
        payload = {
            "temperature": round(random.uniform(20.0, 35.0), 2),
            "ph": round(random.uniform(6.5, 8.5), 2),
            "turbidity": round(random.uniform(0.5, 5.0), 2)
        }
        
        # Publicar el mensaje en el broker
        client.publish(TOPIC, json.dumps(payload))
        print(f"[SIMULADOR] Publicado en {TOPIC}: {payload}")
        
        time.sleep(3)

except ConnectionRefusedError:
    print("Error: No se pudo conectar a Mosquitto. ¿Está corriendo Docker?")
except KeyboardInterrupt:
    print("\nApagando el simulador...")
    client.disconnect()