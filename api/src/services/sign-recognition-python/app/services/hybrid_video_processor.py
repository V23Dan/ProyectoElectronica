import time
import logging
import cv2
import numpy as np
from collections import deque
from typing import Tuple, Dict, Any, Optional

from app.services.camera_manager import CameraManager
from app.services.holistic_processor import HolisticProcessor
from app.models.hybrid_sign_classifier import HybridSignClassifier
from app.utils.performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class HybridVideoProcessor:
    """
    Procesador de video optimizado para mejor rendimiento.
    """
    
    def __init__(
        self, 
        camera_manager: CameraManager, 
        classifier: HybridSignClassifier,
        holistic_processor: HolisticProcessor,
        show_video: bool = False
    ):
        self.camera_manager = camera_manager
        self.classifier = classifier
        self.holistic_processor = holistic_processor
        self.show_video = show_video
        self.performance = PerformanceMonitor()
        
        # Estado de predicción
        self.current_prediction = ("", 0.0)
        self.last_inference_time = 0.0
        
        # Buffer de secuencias (30 frames)
        self.sequence_buffer = deque(maxlen=30)
        
        # Estado de inicialización
        self.initialized = False
        
        # Control de estabilidad
        self.no_detection_counter = 0
        self.stability_threshold = 3  # Reducido de 5 a 3
        
        # Configuración de umbral de confianza
        self.confidence_threshold = 0.3  # Reducido de 0.4 a 0.3
        
        # Optimización: inferencia cada N frames
        self.inference_interval = 3  # Solo clasificar cada 3 frames
        self.frame_count = 0
        
        # Cache del último frame procesado
        self.last_processed_frame = None
        
        logger.info("HybridVideoProcessor inicializado")
        logger.info(f"   - Umbral confianza: {self.confidence_threshold}")
        logger.info(f"   - Intervalo inferencia: cada {self.inference_interval} frames")

    def initialize_camera(self, auto_connect: bool = True) -> bool:
        if not auto_connect:
            logger.info("Inicialización manual de cámara deshabilitada")
            return False
        
        ok = self.camera_manager.initialize(auto_connect=True)
        self.initialized = ok
        
        if ok:
            logger.info("Cámara inicializada correctamente")
        else:
            logger.warning("No se pudo inicializar ninguna cámara")
        
        return ok

    def switch_camera(self, camera_config: Dict[str, Any]) -> bool:
        return self.camera_manager.switch_camera(camera_config)

    def get_camera_status(self) -> Dict[str, Any]:
        return self.camera_manager.get_status()

    def get_available_cameras(self) -> Dict[str, Any]:
        return self.camera_manager.list_cameras()

    def close(self):
        try:
            self.holistic_processor.close()
            self.camera_manager.close()
            if self.show_video:
                cv2.destroyAllWindows()
            logger.info("HybridVideoProcessor cerrado correctamente")
        except Exception as e:
            logger.error(f"Error cerrando HybridVideoProcessor: {e}")

    def process_next_frame(self) -> Optional[Tuple[np.ndarray, str, float]]:
        """
        Procesa el siguiente frame con optimizaciones de rendimiento.
        """
        # 1. CAPTURAR FRAME
        frame = self.camera_manager.get_frame()
        if frame is None:
            return None

        self.performance.start_frame()
        self.frame_count += 1

        # OPTIMIZACIÓN: Reducir resolución del frame para procesamiento más rápido
        # (mantenemos original para display)
        frame_display = frame.copy()
        
        # Reducir a 640x480 si es más grande
        h, w = frame.shape[:2]
        if w > 640 or h > 480:
            frame = cv2.resize(frame, (640, 480))

        # 2. PROCESAR CON HOLISTIC
        landmarks_vector, results = self.holistic_processor.process(frame)

        # 3. VERIFICAR DETECCIONES
        has_hands = self.holistic_processor.has_hands(results)
        
        if not has_hands:
            self.no_detection_counter += 1
            
            # Limpiar buffer más rápido
            if self.no_detection_counter > self.stability_threshold:
                if len(self.sequence_buffer) > 0:
                    self.sequence_buffer.clear()
                    logger.debug("Buffer limpiado")
                self.current_prediction = ("NO_HANDS_DETECTED", 0.0)
            
            # Reutilizar último frame procesado si existe
            if self.last_processed_frame is not None:
                processed = self.last_processed_frame
            else:
                annotated = self.holistic_processor.draw_landmarks(frame_display, results)
                processed = self._annotate_frame(
                    annotated, 
                    "Sin manos detectadas",
                    show_buffer=True
                )
                self.last_processed_frame = processed
            
            self.performance.end_frame()
            return processed, "NO_HANDS_DETECTED", 0.0
        
        # Resetear contador
        self.no_detection_counter = 0
        
        # 4. VALIDAR LANDMARKS
        if landmarks_vector is None or landmarks_vector.shape[0] != 258:
            logger.warning(
                f"Landmarks inválidos: "
                f"{landmarks_vector.shape if landmarks_vector is not None else 'None'}"
            )
            annotated = self.holistic_processor.draw_landmarks(frame_display, results)
            processed = self._annotate_frame(annotated, "Error en extracción")
            self.performance.end_frame()
            return processed, "ERROR_EXTRACTION", 0.0
        
        # 5. AGREGAR AL BUFFER
        self.sequence_buffer.append(landmarks_vector)
        
        # 6. DIBUJAR LANDMARKS
        annotated = self.holistic_processor.draw_landmarks(frame_display, results)
        
        # 7. VERIFICAR SI TENEMOS 30 FRAMES
        if len(self.sequence_buffer) < 30:
            frames_needed = 30 - len(self.sequence_buffer)
            processed = self._annotate_frame(
                annotated,
                f"Cargando... ({frames_needed} frames)",
                show_buffer=True
            )
            self.performance.end_frame()
            return processed, "LOADING_SEQUENCE", 0.0
        
        # 8. CLASIFICAR SOLO CADA N FRAMES (OPTIMIZACIÓN)
        prediction = self.current_prediction[0]
        confidence = self.current_prediction[1]
        
        if self.frame_count % self.inference_interval == 0:
            # Construir secuencia
            sequence_array = np.array(list(self.sequence_buffer), dtype=np.float32)
            sequence_array = sequence_array.reshape(1, 30, 258)
            
            # Clasificar
            start_inf = time.perf_counter()
            try:
                prediction, confidence = self.classifier.predict(sequence_array)
                
                # Mostrar siempre la predicción, incluso con baja confianza
                # (para debugging)
                if confidence < self.confidence_threshold:
                    # Mantener la predicción pero indicar baja confianza
                    logger.debug(
                        f"Baja confianza: {prediction} ({confidence:.2%})"
                    )
                    
            except Exception as e:
                logger.error(f"Error en inferencia: {e}", exc_info=True)
                prediction, confidence = "ERROR_PREDICCION", 0.0
            
            self.last_inference_time = time.perf_counter() - start_inf
            self.current_prediction = (prediction, confidence)
        
        # 9. ANOTAR FRAME
        processed_frame = self._annotate_frame(
            annotated, 
            prediction, 
            confidence,
            show_buffer=True,
            show_inference_time=(self.frame_count % self.inference_interval == 0)
        )
        
        # Cachear frame procesado
        self.last_processed_frame = processed_frame

        self.performance.end_frame()
        
        if self.show_video:
            cv2.imshow("Hybrid Sign Recognition", processed_frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                logger.info("Tecla 'q' presionada, cerrando...")
                self.close()
            elif key == ord('r'):
                logger.info("Tecla 'r' presionada, reiniciando buffer...")
                self.reset_classifier()

        return processed_frame, prediction, confidence

    def reset_classifier(self):
        """Reinicia el estado interno"""
        self.sequence_buffer.clear()
        self.current_prediction = ("", 0.0)
        self.no_detection_counter = 0
        self.frame_count = 0
        self.last_processed_frame = None
        logger.info("Clasificador reiniciado")

    def get_current_prediction(self) -> Tuple[str, float]:
        return self.current_prediction

    def _annotate_frame(
        self, 
        frame: np.ndarray, 
        text: str, 
        confidence: Optional[float] = None,
        show_buffer: bool = False,
        show_inference_time: bool = False
    ) -> np.ndarray:
        """Dibuja información de anotación (versión ligera)"""
        annotated = frame.copy()
        h, w = annotated.shape[:2]
        
        # Barra superior más pequeña
        bar_height = 50 if not show_inference_time else 70
        
        # Fondo semi-transparente
        overlay = np.zeros((bar_height, w, 3), dtype=np.uint8)
        cv2.addWeighted(overlay, 0.65, annotated[0:bar_height], 0.35, 0, annotated[0:bar_height])

        # Texto principal
        display_text = text
        if confidence is not None and confidence > 0:
            display_text += f" ({confidence*100:.0f}%)"
            
            if confidence > 0.7:
                color = (0, 255, 0)
            elif confidence > self.confidence_threshold:
                color = (0, 255, 255)
            else:
                color = (0, 165, 255)
        else:
            color = (255, 255, 255)

        cv2.putText(
            annotated, display_text, (10, 30), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA
        )
        
        # Buffer info
        if show_buffer:
            buffer_info = f"{len(self.sequence_buffer)}/30"
            buffer_color = (0, 255, 0) if len(self.sequence_buffer) == 30 else (200, 200, 200)
            cv2.putText(
                annotated, buffer_info, (w - 80, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, buffer_color, 1, cv2.LINE_AA
            )
        
        # Tiempo de inferencia
        if show_inference_time and self.last_inference_time > 0:
            inf_time = f"{self.last_inference_time*1000:.0f}ms"
            cv2.putText(
                annotated, inf_time, (10, 60), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1, cv2.LINE_AA
            )
        
        return annotated

    def set_confidence_threshold(self, threshold: float):
        """Ajusta el umbral de confianza"""
        if 0.0 <= threshold <= 1.0:
            self.confidence_threshold = threshold
            logger.info(f"Umbral ajustado a {threshold:.2%}")
        else:
            logger.warning(f"Umbral inválido: {threshold}")

    def set_inference_interval(self, interval: int):
        """Ajusta cada cuántos frames hacer inferencia"""
        if interval >= 1:
            self.inference_interval = interval
            logger.info(f"Intervalo de inferencia: cada {interval} frames")
        else:
            logger.warning(f"Intervalo inválido: {interval}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "buffer_size": len(self.sequence_buffer),
            "buffer_capacity": 30,
            "buffer_full": len(self.sequence_buffer) == 30,
            "current_prediction": self.current_prediction[0],
            "current_confidence": self.current_prediction[1],
            "last_inference_time_ms": self.last_inference_time * 1000,
            "fps": self.performance.get_fps(),
            "confidence_threshold": self.confidence_threshold,
            "inference_interval": self.inference_interval,
            "frame_count": self.frame_count
        }