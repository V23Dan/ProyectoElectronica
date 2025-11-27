import base64
import json
import asyncio
import httpx
import logging
import time
import threading
import cv2
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from app.services.camera_manager import CameraManager
from app.services.holistic_processor import HolisticProcessor
from app.services.hybrid_video_processor import HybridVideoProcessor
from app.utils.performance_monitor import PerformanceMonitor
from app.models.hybrid_sign_classifier import HybridSignClassifier
from app.utils.postgres_client import PostgresClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("HYBRID_ASL_APP")

# Configuracion API nodejs
API_URL = "http://192.168.56.1:3000"

# Cliente http para comunicacion con Nodejs
http_client = httpx.AsyncClient(timeout=5.0)

app = FastAPI(
    title="Hybrid Sign Language Recognition API",
    description="API para reconocimiento de lenguaje de señas colombiano (LSC)",
    version="2.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Integracion con nodeks
async def notify_translation_to_nodejs(
    session_id: int, text_output: str, confidence: float
):
    """
    Notifica una traducción al backend Node.js para:
    1. Guardar en PostgreSQL
    2. Mostrar en el ESP32 LCD
    3. Notificar al frontend vía Socket.IO
    """
    try:
        response = await http_client.post(
            f"{API_URL}/api/translations",
            json={
                "sessionId": session_id,
                "textOutput": text_output,
                "confidence": confidence,
            },
        )

        if response.status_code == 200:
            logger.info(f"Traducción enviada a Node.js: {text_output}")
            return response.json()
        else:
            logger.warning(f"Error enviando traducción: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Error comunicando con Node.js: {e}")
        return None


async def get_calibration_from_nodejs():
    """
    Obtiene la calibración actual desde el backend Node.js
    """
    try:
        response = await http_client.get(f"{API_URL}/api/calibration")

        if response.status_code == 200:
            data = response.json()
            calibration = data.get("calibration")
            logger.info(f"Calibración obtenida: {calibration}")
            return calibration
        else:
            logger.warning("No se pudo obtener calibración")
            return None

    except Exception as e:
        logger.error(f"Error obteniendo calibración: {e}")
        return None


async def notify_system_event_to_nodejs(
    session_id: int, event_type: str, message: str, severity: str = "INFO"
):
    """
    Registra un evento del sistema en Node.js
    (esto podrías hacerlo también directamente con db_client)
    """
    try:
        response = await http_client.post(
            f"{API_URL}/api/system/log",
            json={
                "sessionId": session_id,
                "eventType": event_type,
                "message": message,
                "severity": severity,
            },
        )

        if response.status_code == 200:
            logger.debug(f"Evento registrado: {event_type}")

    except Exception as e:
        logger.error(f"Error registrando evento: {e}")

class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        # CAMBIO: Ahora guardamos el string listo para enviar, no el frame raw
        self.latest_message = None
        self.is_running = False
        self.current_session_id = None

    def update(self, message_dict):
        with self.lock:
            self.latest_message = message_dict

    def get_latest(self):
        with self.lock:
            # Devolvemos una copia del diccionario si existe
            return self.latest_message.copy() if self.latest_message else None

    def set_running(self, running: bool):
        with self.lock:
            self.is_running = running

    def is_active(self):
        with self.lock:
            return self.is_running


shared_state = SharedState()
camera_manager = CameraManager()

holistic_processor = HolisticProcessor(
    detection_conf=0.4, tracking_conf=0.4, model_complexity=1
)

# Clasificador Híbrido
classifier = HybridSignClassifier(
    model_path="trained_models/model/best_hybrid_model.keras",
    vocab_path="trained_models/model/hybrid_vocabulary.json",
    scaler_path="trained_models/model/hybrid_scaler.save",
)

# Video Processor
video_processor = HybridVideoProcessor(
    camera_manager=camera_manager,
    classifier=classifier,
    holistic_processor=holistic_processor,
    show_video=False,
)

# Performance Monitor
performance_monitor = PerformanceMonitor()

# Database Client
db_client = PostgresClient()

# Clientes conectados
connected_video_clients = set()
connected_control_clients = set()

def video_processing_loop():
    logger.info("Thread de procesamiento de video iniciado")

    fps_counter = 0
    fps_start = time.time()

    last_prediction = None
    last_prediction_time = 0
    prediction_cooldown = 2.0  # segundos entre traducciones iguales

    while shared_state.is_active():
        try:
            # 1. Procesamiento IA (Heavy)
            result = video_processor.process_next_frame()

            if result is not None:
                frame, prediction, confidence = result

                # Calcular FPS real del procesamiento
                fps_counter += 1
                if time.time() - fps_start >= 1.0:
                    processing_fps = fps_counter
                    fps_counter = 0
                    fps_start = time.time()
                else:
                    processing_fps = video_processor.performance.get_fps()

                try:
                    # Calidad 60 es suficiente para preview y mucho más rápido
                    _, buffer = cv2.imencode(
                        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60]
                    )
                    frame_base64 = base64.b64encode(buffer).decode("utf-8")
                    frame_uri = f"data:image/jpeg;base64,{frame_base64}"
                except Exception as e:
                    logger.error(f"Error codificando frame: {e}")
                    frame_uri = None

                # 3. Preparar el mensaje final JSON
                if frame_uri:
                    stats = {
                        "type": "video_frame",
                        "frame": frame_uri,
                        "prediction": prediction,
                        "confidence": float(confidence),
                        "performance": {
                            "fps": processing_fps,
                            "inference_time_ms": video_processor.last_inference_time
                            * 1000,
                        },
                        "buffer_status": {
                            "current": len(video_processor.sequence_buffer),
                            "max": 30,
                        },
                        "camera_info": camera_manager.get_status(),
                    }
                    # Actualizar estado compartido con el mensaje listo
                    shared_state.update(stats)

                current_time = time.time()

                # Solo enviar si:
                # 1. La confianza es suficiente
                # 2. No es la misma predicción reciente (evitar spam)
                # 3. Hay una sesión activa
                if (
                    confidence > 0.7
                    and prediction != "NADA"
                    and (
                        prediction != last_prediction
                        or current_time - last_prediction_time > prediction_cooldown
                    )
                ):
                    # Obtener sesión actual (deberías tener esto en alguna variable global)
                    current_session_id = getattr(
                        shared_state, "current_session_id", None
                    )

                    if current_session_id:
                        # Enviar a Node.js de forma asíncrona
                        asyncio.create_task(
                            notify_translation_to_nodejs(
                                session_id=current_session_id,
                                text_output=prediction,
                                confidence=confidence,
                            )
                        )

                        last_prediction = prediction
                        last_prediction_time = current_time

                        logger.info(
                            f"Traducción enviada: {prediction} ({confidence:.2f})"
                        )
            else:
                time.sleep(0.01)

        except Exception as e:
            logger.error(f"Error en loop de procesamiento: {e}", exc_info=True)
            time.sleep(0.1)
    logger.info("Thread de procesamiento de video detenido")


# Variable global para el thread
processing_thread: Optional[threading.Thread] = None

@app.on_event("startup")
async def startup_event():
    """Inicialización al arrancar la aplicación"""
    global processing_thread

    logger.info("=" * 70)
    logger.info("INICIANDO HYBRID SIGN LANGUAGE RECOGNITION API")
    logger.info("=" * 70)

    calibration = await get_calibration_from_nodejs()
    if calibration:
        # Aplicar calibración al clasificador o procesador
        logger.info(f"Calibración aplicada: {calibration}")

    # Inicializar cámara
    logger.info("Inicializando cámara...")
    try:
        camera_manager.initialize(auto_connect=True)
        if camera_manager.get_status()["connected"]:
            logger.info("Cámara inicializada correctamente")
        else:
            logger.warning("No se pudo iniciar ninguna cámara")
    except Exception as e:
        logger.error(f"Error inicializando cámara: {e}")

    # Conectar a PostgreSQL
    logger.info("Conectando a PostgreSQL...")
    try:
        await db_client.postgres_connection()
        logger.info("Conectado a PostgreSQL")
    except Exception as e:
        logger.error(f"Error conectando a PostgreSQL: {e}")

    # Iniciar thread de procesamiento de video
    logger.info("Iniciando thread de procesamiento de video...")
    shared_state.set_running(True)
    processing_thread = threading.Thread(
        target=video_processing_loop, daemon=True, name="VideoProcessingThread"
    )
    processing_thread.start()
    logger.info("Thread de procesamiento iniciado")

    logger.info("=" * 70)
    logger.info("API LISTA PARA RECIBIR CONEXIONES")
    logger.info("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """Limpieza al cerrar la aplicación"""
    logger.info("Cerrando aplicación...")
    # Detener thread de procesamiento de video
    await http_client.aclose()
    shared_state.set_running(False)
    if processing_thread:
        processing_thread.join(timeout=5)
        logger.info("Thread de procesamiento de video detenido")
    video_processor.close()
    logger.info("Recursos liberados")

@app.websocket("/ws/video")
async def websocket_video(websocket: WebSocket):
    await websocket.accept()
    connected_video_clients.add(websocket)
    client_id = id(websocket)
    logger.info(f"Cliente {client_id} conectado al stream de video")

    try:
        while True:
            # El hilo principal solo lee y envía. Cero procesamiento.
            message = shared_state.get_latest()

            if message is not None:
                await websocket.send_text(json.dumps(message))

            # Importante: ceder el control para mantener el heartbeat del socket
            await asyncio.sleep(0.033)  # ~30 FPS cap de envío

    except WebSocketDisconnect:
        connected_video_clients.discard(websocket)
        logger.info(f"Cliente {client_id} desconectado del stream")
    except Exception as e:
        connected_video_clients.discard(websocket)
        logger.error(f"Error en WS video: {e}")

@app.websocket("/ws/control")
async def websocket_control(websocket: WebSocket):
    """
    WebSocket para comandos de control.

    Comandos soportados:
    - get_status: Estado del sistema
    - reset_classifier: Reiniciar clasificador
    - switch_camera: Cambiar cámara
    - start_session: Iniciar sesión de registro
    - stop_session: Detener sesión
    """
    await websocket.accept()
    connected_control_clients.add(websocket)
    client_id = id(websocket)
    logger.info(f"Cliente {client_id} conectado al canal de control")

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            command = data.get("command")

            # GET STATUS
            if command == "get_status":
                await websocket.send_json(
                    {
                        "type": "system_status",
                        "camera_status": camera_manager.get_status(),
                        "fps": performance_monitor.get_fps(),
                        "model_info": {
                            "type": "hybrid",
                            "features": 258,
                            "classes": len(classifier.classes),
                        },
                        "connected_clients": {
                            "video": len(connected_video_clients),
                            "control": len(connected_control_clients),
                        },
                    }
                )

            # RESET CLASSIFIER
            elif command == "reset_classifier":
                try:
                    video_processor.reset_classifier()
                    await websocket.send_json(
                        {
                            "type": "info",
                            "message": "Clasificador reiniciado correctamente",
                        }
                    )
                    logger.info("Clasificador reiniciado por comando")
                except Exception as e:
                    logger.error(f"Error reiniciando clasificador: {e}")
                    await websocket.send_json(
                        {"type": "error", "message": f"Error: {str(e)}"}
                    )

            # SWITCH CAMERA
            elif command == "switch_camera":
                camera_config = data.get("camera", {})
                try:
                    success = camera_manager.switch_camera(camera_config)
                    await websocket.send_json(
                        {
                            "type": "camera_status",
                            "camera_status": camera_manager.get_status(),
                            "success": success,
                        }
                    )
                    logger.info(f"Cambio de cámara: {camera_config}")
                except Exception as e:
                    logger.error(f"Error cambiando cámara: {e}")
                    await websocket.send_json(
                        {"type": "error", "message": f"Error: {str(e)}"}
                    )

            # START SESSION
            elif command == "start_session":
                try:
                    session_id = await db_client.create_session()
                    shared_state.current_session_id = session_id
                    await websocket.send_json(
                        {"type": "session_started", "session_id": session_id}
                    )
                    logger.info(f"Sesión iniciada: {session_id}")
                except Exception as e:
                    logger.error(f"Error creando sesión: {e}")
                    await websocket.send_json(
                        {"type": "error", "message": "Error creando sesión"}
                    )

            # STOP SESSION
            elif command == "stop_session":
                session_id = data.get("session_id")
                try:
                    if session_id:
                        await db_client.end_session(session_id)
                        logger.info(f"Sesión finalizada: {session_id}")
                    shared_state.current_session_id = None
                    await websocket.send_json(
                        {"type": "session_ended", "session_id": session_id}
                    )
                except Exception as e:
                    logger.error(f"Error finalizando sesión: {e}")
                    await websocket.send_json(
                        {"type": "error", "message": "Error finalizando sesión"}
                    )

            # COMANDO DESCONOCIDO
            else:
                await websocket.send_json(
                    {"type": "error", "message": f"Comando desconocido: {command}"}
                )

    except WebSocketDisconnect:
        connected_control_clients.discard(websocket)
        logger.info(f"Cliente {client_id} desconectado del control")
    except Exception as e:
        connected_control_clients.discard(websocket)
        logger.error(f"Error en WS control (cliente {client_id}): {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Hybrid Sign Language Recognition",
        "version": "2.0.0",
        "connected_clients": {
            "video": len(connected_video_clients),
            "control": len(connected_control_clients),
        },
        "camera": camera_manager.get_status(),
        "model": {
            "type": "hybrid",
            "features": 258,
            "classes": len(classifier.classes),
        },
    }


@app.get("/api/vocabulary")
async def get_vocabulary():
    """Retorna el vocabulario completo del modelo"""
    return {"vocabulary": classifier.classes, "total_classes": len(classifier.classes)}


@app.post("/api/sessions/start")
async def start_session():
    """Inicia una nueva sesión de registro"""
    try:
        session_id = await db_client.create_session()
        await db_client.log_system_event(
            session_id=session_id,
            event_type="SESSION_STARTED",
            message="Sesión iniciada vía REST API",
            severity="INFO",
        )
        return {
            "session_id": session_id,
            "status": "started",
            "message": "Sesión iniciada correctamente",
        }
    except Exception as e:
        logger.error(f"Error iniciando sesión: {e}")
        raise HTTPException(status_code=500, detail="Error iniciando sesión")


@app.post("/api/sessions/end/{session_id}")
async def end_session(session_id: int):
    """Finaliza una sesión existente"""
    try:
        await db_client.end_session(session_id)
        await db_client.log_system_event(
            session_id=session_id,
            event_type="SESSION_ENDED",
            message="Sesión finalizada vía REST API",
            severity="INFO",
        )
        return {
            "status": "ended",
            "message": f"Sesión {session_id} finalizada correctamente",
        }
    except Exception as e:
        logger.error(f"Error finalizando sesión: {e}")
        raise HTTPException(status_code=500, detail="Error finalizando sesión")
