# app/main.py
import base64
import json
import asyncio
import logging
import time
import cv2
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.services.camera_manager import CameraManager
from app.services.video_processor import VideoProcessor
from app.utils.performance_monitor import PerformanceMonitor
from app.models.sign_classifier import SignClassifier
from app.utils.postgres_client import PostgresClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ASL_APP")

app = FastAPI(title="ASL Video Stream API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Componentes globales ----
camera_manager = CameraManager()
classifier = SignClassifier(
    model_path="trained_models/model_2/best_colombian_model.keras",
    vocab_path="trained_models/model_2/sign_language_vocabulary.json",
    scaler_path="trained_models/model_2/scaler.save"
)
performance_monitor = PerformanceMonitor()
db_client = PostgresClient()
video_processor = VideoProcessor(camera_manager, classifier)

connected_video_clients = set()
connected_control_clients = set()

# ---- Startup: inicializar cámara y BD ----
@app.on_event("startup")
async def startup_event():
    logger.info("Iniciando cámara automáticamente...")
    try:
        camera_manager.initialize(auto_connect=True)
        if camera_manager.get_status():
            logger.info("Cámara iniciada con éxito.")
        else:
            logger.warning("No se pudo iniciar ninguna cámara.")
    except Exception as e:
        logger.error(f"Error inicializando cámara: {e}")

    # Conexión a Postgres
    try:
        await db_client.postgres_connection()
        logger.info("Conectado a la base de datos PostgreSQL.")
    except Exception as e:
        logger.error(f"No se pudo conectar a la base de datos PostgreSQL: {e}")

# ---- WebSocket: video stream ----
@app.websocket("/ws/video")
async def websocket_video(websocket: WebSocket):
    await websocket.accept()
    connected_video_clients.add(websocket)
    logger.info("Cliente conectado al WS de video.")

    # Enviar estado inicial de cámara
    await websocket.send_json({
        "type": "camera_status",
        "camera_status": camera_manager.get_status()
    })

    try:
        while True:
            # Procesar el siguiente frame (incluye inferencia)
            result = video_processor.process_next_frame()
            if result is None:
                await asyncio.sleep(0.05)
                continue

            frame, prediction, confidence = result

            # Codificar frame procesado en base64
            try:
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                frame_uri = f"data:image/jpeg;base64,{frame_base64}"
            except Exception as e:
                logger.warning(f"Error codificando frame a JPEG: {e}")
                frame_uri = None

            # Obtener métricas de rendimiento
            fps = video_processor.performance.get_fps()
            system_usage = video_processor.performance.get_system_usage() or {}

            # Enviar frame + predicción + métricas
            message = {
                "type": "video_frame",
                "frame": frame_uri,
                "prediction": prediction,
                "confidence": float(confidence),
                "camera_info": camera_manager.get_status(),
                "fps": fps,
                "cpu": system_usage.get("cpu_percent"),
                "ram": system_usage.get("ram_percent"),
            }

            await websocket.send_text(json.dumps(message))
            await asyncio.sleep(0.03) 

    except WebSocketDisconnect:
        connected_video_clients.discard(websocket)
        logger.info("Cliente desconectado del WS de video.")
    except Exception as e:
        connected_video_clients.discard(websocket)
        logger.error(f"Error en WS de video: {e}")

# ---- WebSocket: control ----
@app.websocket("/ws/control")
async def websocket_control(websocket: WebSocket):
    await websocket.accept()
    connected_control_clients.add(websocket)
    logger.info("Cliente conectado al WS de control.")

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            command = data.get("command")

            if command == "get_status":
                await websocket.send_json({
                    "type": "system_status",
                    "camera_status": camera_manager.get_status(),
                    "fps": performance_monitor.get_fps()
                })

            elif command == "reset_classifier":
                # reset del clasificador a través del video_processor
                try:
                    video_processor.reset_classifier()
                    await websocket.send_json({"type": "info", "message": "Clasificador reiniciado."})
                except Exception as e:
                    logger.error(f"Error reiniciando clasificador: {e}")
                    await websocket.send_json({"type": "error", "message": "Error reiniciando clasificador."})

            elif command == "switch_camera":
                camera_config = data.get("camera", {})
                success = camera_manager.switch_camera(camera_config)
                await websocket.send_json({
                    "type": "camera_status",
                    "camera_status": camera_manager.get_status(),
                    "success": success
                })

            elif command == "start_session":
                try:
                    session_id = await db_client.create_session()
                    await websocket.send_json({"type": "session_started", "session_id": session_id})
                except Exception as e:
                    logger.error(f"Error creando sesión: {e}")
                    await websocket.send_json({"type": "error", "message": "Error creando sesión"})

            elif command == "stop_session":
                # Para tu implementación: espera session_id en payload o maneja cierre global
                await websocket.send_json({"type": "session_ended"})
            else:
                await websocket.send_json({"type": "error", "message": f"Comando desconocido: {command}"})

    except WebSocketDisconnect:
        connected_control_clients.discard(websocket)
        logger.info("Cliente desconectado del WS de control.")
    except Exception as e:
        connected_control_clients.discard(websocket)
        logger.error(f"Error en WS de control: {e}")

# ---- Endpoints REST adicionales ----
@app.post("/sessions/start")
async def start_session():
    try:
        session_id = await db_client.create_session()
        await db_client.log_system_event(
            session_id=session_id,
            event_type="SESSION_STARTED",
            message="Sesión iniciada mediante API REST",
            severity="INFO"
        )
        return {"session_id": session_id, "status": "started", "message": "Sesión iniciada correctamente"}
    except Exception as e:
        logger.error(f"Error iniciando sesión: {e}")
        raise HTTPException(status_code=500, detail="Error iniciando sesión")

@app.post("/session/end/{session_id}")
async def end_session(session_id: int):
    try:
        await db_client.end_session(session_id)
        await db_client.log_system_event(
            session_id=session_id,
            event_type="SESSION_ENDED",
            message="Sesión finalizada mediante API REST",
            severity="INFO"
        )
        return {"status": "ended", "message": f"Sesión {session_id} finalizada correctamente"}
    except Exception as e:
        logger.error(f"Error finalizando sesión: {e}")
        raise HTTPException(status_code=500, detail="Error finalizando sesión")

# ---- Health check ----
@app.get("/health")
async def health_check():
    return {"status": "ok", "connected_clients": len(connected_video_clients)}
