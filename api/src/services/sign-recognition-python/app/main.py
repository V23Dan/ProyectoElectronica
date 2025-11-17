import base64
import json
import asyncio
import logging
import time
import cv2
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.services.camera_manager import CameraManager
from app.services.holistic_processor import HolisticProcessor
from app.services.hybrid_video_processor import HybridVideoProcessor
from app.utils.performance_monitor import PerformanceMonitor
from app.models.hybrid_sign_classifier import HybridSignClassifier
from app.utils.postgres_client import PostgresClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("HYBRID_ASL_APP")

app = FastAPI(
    title="Hybrid Sign Language Recognition API",
    description="API para reconocimiento de lenguaje de señas colombiano (LSC)",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:5173",
        "http://localhost:5174"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# COMPONENTES GLOBALES
# ============================================================================

# Camera Manager
camera_manager = CameraManager()

holistic_processor = HolisticProcessor(
    detection_conf=0.4,      
    tracking_conf=0.4,       
    model_complexity=1     
)

# Clasificador Híbrido
classifier = HybridSignClassifier(
    model_path="trained_models/model/best_hybrid_model.keras",
    vocab_path="trained_models/model/hybrid_vocabulary.json",
    scaler_path="trained_models/model/hybrid_scaler.save"
)

# Video Processor
video_processor = HybridVideoProcessor(
    camera_manager=camera_manager,
    classifier=classifier,
    holistic_processor=holistic_processor,
    show_video=False
)

# Performance Monitor
performance_monitor = PerformanceMonitor()

# Database Client
db_client = PostgresClient()

# Clientes conectados
connected_video_clients = set()
connected_control_clients = set()

# ============================================================================
# STARTUP & SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Inicialización al arrancar la aplicación"""
    logger.info("="*70)
    logger.info("INICIANDO HYBRID SIGN LANGUAGE RECOGNITION API")
    logger.info("="*70)
    
    # Inicializar cámara
    logger.info("Inicializando cámara...")
    try:
        camera_manager.initialize(auto_connect=True)
        if camera_manager.get_status()['connected']:
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
    
    logger.info("="*70)
    logger.info("API LISTA PARA RECIBIR CONEXIONES")
    logger.info("="*70)

@app.on_event("shutdown")
async def shutdown_event():
    """Limpieza al cerrar la aplicación"""
    logger.info("Cerrando aplicación...")
    video_processor.close()
    logger.info("Recursos liberados")

# ============================================================================
# WEBSOCKET: VIDEO STREAM
# ============================================================================

@app.websocket("/ws/video")
async def websocket_video(websocket: WebSocket):
    """
    WebSocket para streaming de video (OPTIMIZADO).
    """
    await websocket.accept()
    connected_video_clients.add(websocket)
    client_id = id(websocket)
    logger.info(f"Cliente {client_id} conectado al stream de video")

    # Enviar estado inicial
    await websocket.send_json({
        "type": "init",
        "camera_status": camera_manager.get_status(),
        "model_info": {
            "type": "hybrid",
            "features": 258,
            "classes": len(classifier.classes)
        }
    })

    # Control de tasa de envío
    frame_skip = 2  # Enviar cada 2 frames (15 FPS si captura a 30)
    frame_counter = 0

    try:
        while True:
            # Procesar frame
            result = video_processor.process_next_frame()
            
            if result is None:
                await asyncio.sleep(0.05)
                continue

            frame, prediction, confidence = result
            frame_counter += 1

            # OPTIMIZACIÓN: Enviar solo cada N frames
            if frame_counter % frame_skip != 0:
                continue

            # Codificar frame con menor calidad para reducir bandwidth
            try:
                _, buffer = cv2.imencode(
                    '.jpg', 
                    frame, 
                    [cv2.IMWRITE_JPEG_QUALITY, 60]  # Reducido de 75 a 60
                )
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                frame_uri = f"data:image/jpeg;base64,{frame_base64}"
            except Exception as e:
                logger.warning(f"Error codificando frame: {e}")
                frame_uri = None

            # Métricas
            fps = video_processor.performance.get_fps()
            system_usage = video_processor.performance.get_system_usage() or {}

            # Enviar datos (compacto)
            message = {
                "type": "video_frame",
                "frame": frame_uri,
                "prediction": prediction,
                "confidence": float(confidence),
                "performance": {
                    "fps": fps,
                    "cpu": system_usage.get("cpu_percent"),
                    "ram": system_usage.get("ram_percent"),
                    "inference_time_ms": video_processor.last_inference_time * 1000
                },
                "buffer_status": {
                    "current": len(video_processor.sequence_buffer),
                    "max": 30
                }
            }

            await websocket.send_text(json.dumps(message))
            await asyncio.sleep(0.05)  # ~20 FPS máximo

    except WebSocketDisconnect:
        connected_video_clients.discard(websocket)
        logger.info(f"Cliente {client_id} desconectado")
    except Exception as e:
        connected_video_clients.discard(websocket)
        logger.error(f"Error en WS video (cliente {client_id}): {e}")

# ============================================================================
# WEBSOCKET: CONTROL
# ============================================================================

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
                await websocket.send_json({
                    "type": "system_status",
                    "camera_status": camera_manager.get_status(),
                    "fps": performance_monitor.get_fps(),
                    "model_info": {
                        "type": "hybrid",
                        "features": 258,
                        "classes": len(classifier.classes)
                    },
                    "connected_clients": {
                        "video": len(connected_video_clients),
                        "control": len(connected_control_clients)
                    }
                })

            # RESET CLASSIFIER
            elif command == "reset_classifier":
                try:
                    video_processor.reset_classifier()
                    await websocket.send_json({
                        "type": "info",
                        "message": "Clasificador reiniciado correctamente"
                    })
                    logger.info("Clasificador reiniciado por comando")
                except Exception as e:
                    logger.error(f"Error reiniciando clasificador: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Error: {str(e)}"
                    })

            # SWITCH CAMERA
            elif command == "switch_camera":
                camera_config = data.get("camera", {})
                try:
                    success = camera_manager.switch_camera(camera_config)
                    await websocket.send_json({
                        "type": "camera_status",
                        "camera_status": camera_manager.get_status(),
                        "success": success
                    })
                    logger.info(f"Cambio de cámara: {camera_config}")
                except Exception as e:
                    logger.error(f"Error cambiando cámara: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Error: {str(e)}"
                    })

            # START SESSION
            elif command == "start_session":
                try:
                    session_id = await db_client.create_session()
                    await websocket.send_json({
                        "type": "session_started",
                        "session_id": session_id
                    })
                    logger.info(f"Sesión iniciada: {session_id}")
                except Exception as e:
                    logger.error(f"Error creando sesión: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Error creando sesión"
                    })

            # STOP SESSION
            elif command == "stop_session":
                session_id = data.get("session_id")
                try:
                    if session_id:
                        await db_client.end_session(session_id)
                        logger.info(f"Sesión finalizada: {session_id}")
                    await websocket.send_json({
                        "type": "session_ended",
                        "session_id": session_id
                    })
                except Exception as e:
                    logger.error(f"Error finalizando sesión: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Error finalizando sesión"
                    })

            # COMANDO DESCONOCIDO
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Comando desconocido: {command}"
                })

    except WebSocketDisconnect:
        connected_control_clients.discard(websocket)
        logger.info(f"Cliente {client_id} desconectado del control")
    except Exception as e:
        connected_control_clients.discard(websocket)
        logger.error(f"Error en WS control (cliente {client_id}): {e}")

# ============================================================================
# REST ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Hybrid Sign Language Recognition",
        "version": "2.0.0",
        "connected_clients": {
            "video": len(connected_video_clients),
            "control": len(connected_control_clients)
        },
        "camera": camera_manager.get_status(),
        "model": {
            "type": "hybrid",
            "features": 258,
            "classes": len(classifier.classes)
        }
    }

@app.get("/api/vocabulary")
async def get_vocabulary():
    """Retorna el vocabulario completo del modelo"""
    return {
        "vocabulary": classifier.classes,
        "total_classes": len(classifier.classes)
    }

@app.post("/api/sessions/start")
async def start_session():
    """Inicia una nueva sesión de registro"""
    try:
        session_id = await db_client.create_session()
        await db_client.log_system_event(
            session_id=session_id,
            event_type="SESSION_STARTED",
            message="Sesión iniciada vía REST API",
            severity="INFO"
        )
        return {
            "session_id": session_id,
            "status": "started",
            "message": "Sesión iniciada correctamente"
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
            severity="INFO"
        )
        return {
            "status": "ended",
            "message": f"Sesión {session_id} finalizada correctamente"
        }
    except Exception as e:
        logger.error(f"Error finalizando sesión: {e}")
        raise HTTPException(status_code=500, detail="Error finalizando sesión")