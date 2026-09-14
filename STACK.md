# Yaku Edge — Stack Técnico y Guía de Ejecución

## 1. Información General del Proyecto
- **Tipo de Proyecto**: Nodo de Borde IoT (Edge Gateway) para recolección, encolado offline y sincronización de telemetría acuícola hacia la nube.
- **Lenguaje**: Python 3.10+.
- **Framework Core**: Flask (para puente HTTP/ingesta directa y visualización de cola).

---

## 2. Dependencias y Decisiones Arquitectónicas Clave

| Componente | Librería / Tecnología | Versión | Propósito / Decisión |
|---|---|---|---|
| **API Web & Endpoints** | `Flask` | >= 3.0.0 | Provee endpoints `/ingest` (puente HTTP a MQTT) y `/queue` (inspección del estado de la cola en tiempo real). |
| **Cliente MQTT** | `paho-mqtt` | 1.6.1 | Suscripción a tópicos de telemetría (`yaku/telemetria/pond/#`), thresholds y comandos de actuadores. |
| **Buffer / Cola Resiliente** | `redis` (Redis Python Client) | 5.0.1 | Almacena telemetría en memoria (`telemetry_queue`) ante caídas de conexión a Internet (soporte offline-first / Store and Forward). |
| **Sincronizador Cloud** | `requests` | 2.31.0 | Worker en hilo secundario (daemon) que extrae datos de Redis (RPOP) y los despacha al backend REST con reintentos automáticos si falla la red. |
| **Variables de Entorno** | `python-dotenv` | >= 1.0.0 | Carga automática de configuraciones desde el archivo `.env`. |
| **Infraestructura Local** | Docker Compose (`compose.yaml`) | - | Levanta broker Mosquitto (puerto 1883) y Redis (puerto 6379) localmente. |

---

## 3. Servicios Externos e Infraestructura

1. **Eclipse Mosquitto MQTT Broker**: Broker MQTT local para comunicación con microcontroladores (Arduino, ESP32, Raspberry Pi).
2. **Redis In-Memory Data Store**: Cola FIFO local para tolerancia a fallos de conectividad.
3. **Yaku Backend API**: Endpoint de ingesta (`/api/v1/telemetry/manual-ingest`) donde se sincronizan los paquetes de datos normalizados.

---

## 4. Cómo Levantar el Proyecto Localmente

### Prerrequisitos
- Python 3.10 o superior instalado (`python --version`).
- Docker y Docker Compose instalados y en ejecución.

### Pasos de Configuración y Ejecución
1. **Crear entorno virtual e instalar dependencias:**
   ```bash
   python -m venv venv
   # En Windows:
   .\venv\Scripts\activate
   # En Linux / macOS:
   source venv/bin/activate

   pip install -r requirements.txt
   ```

2. **Configurar variables de entorno:**
   ```bash
   cp .env.example .env
   # Modificar si se desea apuntar a un broker o API externa
   ```

3. **Levantar Mosquitto y Redis con Docker Compose:**
   ```bash
   docker compose up -d
   ```

4. **Ejecutar el procesador Edge:**
   ```bash
   python edge_processor.py
   ```

5. **(Opcional) Ejecutar simulador de sensores Arduino:**
   ```bash
   python arduino.py
   ```
