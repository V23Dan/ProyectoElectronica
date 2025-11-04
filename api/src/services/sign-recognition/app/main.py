from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import cv2
import numpy as np
import base64
import json
import asyncio
import logging

#Servicios de la App importados
from app.utils.postgres_client import PostgresClient
from app.services.video_processor import VideoProcessor

#Configurar el logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Servicio de Reconocimiento de lenguaje de señas")

#Configuracion de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", 
                   "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#Inicializar componentes
db_client = PostgresClient()
video_processor = VideoProcessor()

@app.on_event("startup")
async def startup_event():
    logger.info("Iniciando el servicio de reconocimiento de lenguaje de señas...")
    
    # Iniciar cámara automáticamente
    camera_connected = video_processor.initialize_camera(auto_connect=True)
    if camera_connected:
        camera_info = video_processor.get_camera_status()
        logger.info(f"Cámara conectada: {camera_info.get('name', 'Desconocida')}")  
    else:
        logger.warning("No se pudo conectar a la cámara al iniciar la aplicación.")
        
    try:
        # Iniciar conexión con base de datos
        await db_client.postgres_connection() 
        logger.info("Conexión a la base de datos Postgres establecida.")
    except Exception as e:
        logger.error(f"Error al conectar con la base de datos Postgres: {e}")

#WebSocket para transmisión de video y datos
@app.websocket("/ws/video")
async def websocket_video(websocket: WebSocket):
    await websocket.accept()
    logger.info("Cliente conectado al WebSocket de video")
    
    try:
        # Iniciar sesión en la base de datos
        session_id = await db_client.create_session()
        await websocket.send_json({
            "type": "session_started",
            "session_id": session_id,
            "message": "Sesión iniciada correctamente"
        })
        
        # Bucle principal de procesamiento de video
        while True:
            try:
                # Procesar siguiente frame
                processed_frame, prediction, confidence = video_processor.process_next_frame()
                
                if processed_frame is not None:
                    # Codificar frame procesado a base64
                    _, buffer = cv2.imencode('.jpg', processed_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    jpeg_bytes = buffer.tobytes()
                    base64_frame = base64.b64encode(jpeg_bytes).decode('utf-8')
                    
                    # Preparar datos para enviar
                    response_data = {
                        "type": "video_frame",
                        "frame": f"data:image/jpeg;base64,{base64_frame}",
                        "prediction": prediction,
                        "confidence": float(confidence),
                        "camera_info": video_processor.get_camera_status(),
                        "timestamp": asyncio.get_event_loop().time()
                    }
                    
                    # Guardar traducción en BD si la confianza es alta
                    if confidence > 0.7 and prediction not in ["NO_HANDS_DETECTED", "SECUENCIA_INCOMPLETA", "ERROR_PREDICCION"]:
                        try:
                            await db_client.save_translation(
                                session_id=session_id,
                                text_output=prediction,
                                confidence=confidence
                            )
                            
                            # Enviar evento de traducción guardada
                            response_data["translation_saved"] = True
                            
                        except Exception as db_error:
                            logger.error(f"Error guardando traducción: {db_error}")
                            await db_client.log_system_event(
                                session_id=session_id,
                                event_type="TRANSLATION_SAVE_ERROR",
                                message=str(db_error),
                                severity="ERROR"
                            )
                    
                    # Enviar frame procesado y datos al cliente
                    await websocket.send_json(response_data)
                
                else:
                    # No hay frame disponible, esperar un poco
                    await asyncio.sleep(0.1)
                    
                    # Enviar estado de la cámara
                    camera_status = video_processor.get_camera_status()
                    await websocket.send_json({
                        "type": "camera_status",
                        "camera_status": camera_status,
                        "message": "Esperando frames de la cámara..."
                    })
                
                # Pequeña pausa para controlar FPS
                await asyncio.sleep(0.05)  # ~20 FPS
                
            except Exception as processing_error:
                logger.error(f"Error en procesamiento de frame: {processing_error}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Error procesando video: {str(processing_error)}"
                })
                await asyncio.sleep(1)  # Esperar antes de reintentar
                
    except WebSocketDisconnect:
        logger.info("Cliente desconectado del WebSocket de video")
        
        # Finalizar sesión en la base de datos
        try:
            await db_client.end_session(session_id)
            await db_client.log_system_event(
                session_id=session_id,
                event_type="SESSION_ENDED",
                message="Sesión finalizada por desconexión del cliente",
                severity="INFO"
            )
        except Exception as e:
            logger.error(f"Error finalizando sesión: {e}")
            
    except Exception as e:
        logger.error(f"Error en WebSocket de video: {e}")
        try:
            await websocket.send_json({
                "type": "error", 
                "message": f"Error interno del servidor: {str(e)}"
            })
        except:
            pass  # El cliente ya se desconectó

#Controles del sistema via WebSocket
@app.websocket("/ws/control")
async def websocket_control(websocket: WebSocket):
    await websocket.accept()
    logger.info("Cliente conectado al WebSocket de control")
    
    try:
        while True:
            # Recibir comandos del cliente
            data = await websocket.receive_text()
            command_data = json.loads(data)
            command = command_data.get("command")
            
            if command == "get_cameras":
                # Obtener lista de cámaras disponibles
                cameras = video_processor.get_available_cameras()
                await websocket.send_json({
                    "type": "cameras_list",
                    "cameras": cameras
                })
                
            elif command == "switch_camera":
                # Cambiar de cámara
                camera_config = command_data.get("camera_config")
                if camera_config:
                    success = video_processor.switch_camera(camera_config)
                    await websocket.send_json({
                        "type": "camera_switch_result",
                        "success": success,
                        "camera_name": camera_config.get("name", "Desconocida") if success else None,
                        "message": "Cámara cambiada exitosamente" if success else "Error al cambiar de cámara"
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Configuración de cámara no proporcionada"
                    })
                    
            elif command == "reset_classifier":
                # Reiniciar el clasificador
                video_processor.reset_classifier()
                await websocket.send_json({
                    "type": "classifier_reset",
                    "message": "Clasificador reiniciado correctamente"
                })
                
            elif command == "get_status":
                # Obtener estado completo del sistema
                camera_status = video_processor.get_camera_status()
                current_pred, current_conf = video_processor.get_current_prediction()
                
                await websocket.send_json({
                    "type": "system_status",
                    "camera_status": camera_status,
                    "current_prediction": current_pred,
                    "current_confidence": current_conf,
                    "classifier_sequence": video_processor.sign_classifier.get_sequence_length()
                })
                
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Comando no reconocido: {command}"
                })
                
    except WebSocketDisconnect:
        logger.info("Cliente desconectado del WebSocket de control")
    except Exception as e:
        logger.error(f"Error en WebSocket de control: {e}")

# Endpoints REST
@app.post("/session/start")
async def start_session():
    """Iniciar una nueva sesión"""
    try:
        session_id = await db_client.create_session()
        
        # Log del evento
        await db_client.log_system_event(
            session_id=session_id,
            event_type="SESSION_STARTED",
            message="Sesión iniciada mediante API REST",
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

@app.post("/session/end/{session_id}")
async def end_session(session_id: int):
    """Finalizar una sesión"""
    try:
        await db_client.end_session(session_id)
        
        # Log del evento
        await db_client.log_system_event(
            session_id=session_id,
            event_type="SESSION_ENDED",
            message="Sesión finalizada mediante API REST",
            severity="INFO"
        )
        
        return {
            "status": "ended", 
            "message": f"Sesión {session_id} finalizada correctamente"
        }
    except Exception as e:
        logger.error(f"Error finalizando sesión: {e}")
        raise HTTPException(status_code=500, detail="Error finalizando sesión")

@app.get("/cameras")
async def get_available_cameras():
    """Obtener lista de cámaras disponibles"""
    try:
        cameras = video_processor.get_available_cameras()
        return {
            "cameras": cameras,
            "count": len(cameras)
        }
    except Exception as e:
        logger.error(f"Error obteniendo cámaras: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo cámaras disponibles")

@app.post("/camera/switch")
async def switch_camera(camera_config: dict):
    """Cambiar a una cámara específica"""
    try:
        success = video_processor.switch_camera(camera_config)
        
        if success:
            return {
                "success": True,
                "message": f"Cambiado a cámara: {camera_config.get('name', 'Desconocida')}",
                "camera_info": video_processor.get_camera_status()
            }
        else:
            raise HTTPException(status_code=400, detail="No se pudo conectar a la cámara especificada")
            
    except Exception as e:
        logger.error(f"Error cambiando cámara: {e}")
        raise HTTPException(status_code=500, detail="Error cambiando de cámara")

@app.get("/camera/status")
async def get_camera_status():
    """Obtener estado actual de la cámara"""
    try:
        status = video_processor.get_camera_status()
        return status
    except Exception as e:
        logger.error(f"Error obteniendo estado de cámara: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estado de la cámara")

@app.post("/classifier/reset")
async def reset_classifier():
    """Reiniciar el clasificador de señas"""
    try:
        video_processor.reset_classifier()
        return {
            "success": True,
            "message": "Clasificador reiniciado correctamente"
        }
    except Exception as e:
        logger.error(f"Error reiniciando clasificador: {e}")
        raise HTTPException(status_code=500, detail="Error reiniciando clasificador")

@app.get("/translations/{session_id}")
async def get_session_translations(session_id: int):
    """Obtener traducciones de una sesión específica"""
    try:
        # Este método necesitarías implementarlo en PostgresClient
        translations = await db_client.get_session_translations(session_id)
        return {
            "session_id": session_id,
            "translations": translations,
            "count": len(translations)
        }
    except Exception as e:
        logger.error(f"Error obteniendo traducciones: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo traducciones")

@app.get("/health")
async def health_check():
    """Endpoint de salud del servicio"""
    camera_status = video_processor.get_camera_status()
    db_connected = video_processor.camera_manager.is_connected
    
    health_status = {
        "status": "healthy",
        "service": "Sign Language Recognition API",
        "timestamp": asyncio.get_event_loop().time(),
        "camera_connected": camera_status.get("status") == "connected",
        "database_connected": db_connected,
        "camera_info": camera_status
    }
    
    return health_status

#Prueba
@app.get("/", response_class=HTMLResponse)
async def root():
    """Página de inicio simple para pruebas"""
    return """
    <html>
        <head>
            <title>Servicio de Reconocimiento de Lenguaje de Señas</title>
        </head>
        <body>
            <h1>Servicio de Reconocimiento de Lenguaje de Señas</h1>
            <p>El servicio está funcionando correctamente.</p>
            <p>Endpoints disponibles:</p>
            <ul>
                <li><strong>WebSocket Video:</strong> /ws/video</li>
                <li><strong>WebSocket Control:</strong> /ws/control</li>
                <li><strong>Estado de salud:</strong> /health</li>
                <li><strong>Cámaras disponibles:</strong> /cameras</li>
                <li><strong>Estado de cámara:</strong> /camera/status</li>
            </ul>
            <p>Conecta tu frontend React a los WebSockets para comenzar.</p>
        </body>
    </html>
    """