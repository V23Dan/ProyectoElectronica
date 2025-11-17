# app/services/video_processor.py
"""
Video Processor Híbrido que procesa frames con HolisticProcessor
y clasifica señas usando el modelo híbrido (258 features).
"""

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
    Procesador de video que:
    1. Captura frames desde CameraManager
    2. Extrae landmarks holísticos (258 features) con HolisticProcessor
    3. Acumula secuencias de 30 frames
    4. Clasifica señas con HybridSignClassifier
    """
    
    def __init__(
        self, 
        camera_manager: CameraManager, 
        classifier: HybridSignClassifier,
        holistic_processor: HolisticProcessor,
        show_video: bool = False
    ):
        """
        Inicializa el procesador de video híbrido.
        
        Args:
            camera_manager: Gestor de cámara
            classifier: Clasificador híbrido
            holistic_processor: Procesador holístico
            show_video: Si True, muestra ventana con video procesado
        """
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
        self.stability_threshold = 5  # Frames sin detección antes de limpiar buffer
        
        # Configuración de umbral de confianza
        self.confidence_threshold = 0.4
        
        logger.info("HybridVideoProcessor inicializado")

    def initialize_camera(self, auto_connect: bool = True) -> bool:
        """
        Inicializa la cámara.
        
        Args:
            auto_connect: Si True, intenta conectar automáticamente
            
        Returns:
            bool: True si la cámara se inicializó correctamente
        """
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
        """
        Cambia entre cámaras (ESP32 o local).
        
        Args:
            camera_config: Configuración de cámara
            
        Returns:
            bool: True si el cambio fue exitoso
        """
        return self.camera_manager.switch_camera(camera_config)

    def get_camera_status(self) -> Dict[str, Any]:
        """Retorna el estado actual de la cámara"""
        return self.camera_manager.get_status()

    def get_available_cameras(self) -> Dict[str, Any]:
        """Lista cámaras disponibles"""
        return self.camera_manager.list_cameras()

    def close(self):
        """Cierra y libera todos los recursos"""
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
        Procesa el siguiente frame del video stream.
        
        Pipeline:
        1. Captura frame de cámara
        2. Extrae landmarks holísticos (258 features)
        3. Agrega al buffer de secuencia (30 frames)
        4. Cuando buffer está lleno, clasifica la seña
        5. Anota frame con predicción y métricas
        
        Returns:
            Optional[Tuple]: (frame_procesado, prediccion, confianza) o None si no hay frame
        """
        # 1. CAPTURAR FRAME
        frame = self.camera_manager.get_frame()
        if frame is None:
            return None

        self.performance.start_frame()

        # 2. PROCESAR CON HOLISTIC
        landmarks_vector, results = self.holistic_processor.process(frame)

        # 3. VERIFICAR DETECCIONES
        has_hands = self.holistic_processor.has_hands(results)
        
        if not has_hands:
            self.no_detection_counter += 1
            
            # Limpiar buffer si pasan muchos frames sin detección
            if self.no_detection_counter > self.stability_threshold:
                if len(self.sequence_buffer) > 0:
                    self.sequence_buffer.clear()
                    logger.debug("🗑️ Buffer limpiado por falta de detecciones")
                self.current_prediction = ("NO_HANDS_DETECTED", 0.0)
            
            # Dibujar landmarks disponibles (si hay pose pero no manos)
            annotated = self.holistic_processor.draw_landmarks(frame, results)
            processed = self._annotate_frame(
                annotated, 
                "Sin manos detectadas",
                show_buffer=True
            )
            
            self.performance.end_frame()
            return processed, "NO_HANDS_DETECTED", 0.0
        
        # Resetear contador de no-detección
        self.no_detection_counter = 0
        
        # 4. VALIDAR LANDMARKS
        if landmarks_vector is None or landmarks_vector.shape[0] != 258:
            logger.warning(
                f"Landmarks inválidos: "
                f"{landmarks_vector.shape if landmarks_vector is not None else 'None'}"
            )
            annotated = self.holistic_processor.draw_landmarks(frame, results)
            processed = self._annotate_frame(annotated, "Error en extracción")
            self.performance.end_frame()
            return processed, "ERROR_EXTRACTION", 0.0
        
        # 5. AGREGAR AL BUFFER
        self.sequence_buffer.append(landmarks_vector)
        
        # 6. DIBUJAR LANDMARKS
        annotated = self.holistic_processor.draw_landmarks(frame, results)
        
        # 7. VERIFICAR SI TENEMOS 30 FRAMES
        if len(self.sequence_buffer) < 30:
            frames_needed = 30 - len(self.sequence_buffer)
            processed = self._annotate_frame(
                annotated,
                f"Cargando secuencia... ({frames_needed} frames restantes)",
                show_buffer=True
            )
            self.performance.end_frame()
            return processed, "LOADING_SEQUENCE", 0.0
        
        # 8. CONSTRUIR SECUENCIA PARA CLASIFICACIÓN
        sequence_array = np.array(list(self.sequence_buffer), dtype=np.float32)
        sequence_array = sequence_array.reshape(1, 30, 258)
        
        # 9. CLASIFICAR
        start_inf = time.perf_counter()
        try:
            prediction, confidence = self.classifier.predict(sequence_array)
            
            # Filtrar predicciones con baja confianza
            if confidence < self.confidence_threshold:
                original_pred = prediction
                prediction = "BAJA_CONFIANZA"
                logger.debug(
                    f"Confianza baja: {original_pred} ({confidence:.2%}) < "
                    f"{self.confidence_threshold:.2%}"
                )
                
        except Exception as e:
            logger.error(f"Error en inferencia: {e}", exc_info=True)
            prediction, confidence = "ERROR_PREDICCION", 0.0
        
        self.last_inference_time = time.perf_counter() - start_inf

        # 10. ACTUALIZAR PREDICCIÓN ACTUAL
        self.current_prediction = (prediction, confidence)

        # 11. ANOTAR FRAME CON INFORMACIÓN
        processed_frame = self._annotate_frame(
            annotated, 
            prediction, 
            confidence,
            show_buffer=True,
            show_inference_time=True
        )

        self.performance.end_frame()
        
        # 12. MOSTRAR VENTANA SI ESTÁ HABILITADO
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
        """Reinicia el estado interno del clasificador"""
        self.sequence_buffer.clear()
        self.current_prediction = ("", 0.0)
        self.no_detection_counter = 0
        logger.info("Clasificador reiniciado (buffer limpiado)")

    def get_current_prediction(self) -> Tuple[str, float]:
        """
        Retorna la última predicción realizada.
        
        Returns:
            Tuple[str, float]: (prediccion, confianza)
        """
        return self.current_prediction

    def _annotate_frame(
        self, 
        frame: np.ndarray, 
        text: str, 
        confidence: Optional[float] = None,
        show_buffer: bool = False,
        show_inference_time: bool = False
    ) -> np.ndarray:
        """
        Dibuja información de anotación sobre el frame.
        
        Args:
            frame: Frame a anotar
            text: Texto principal (predicción)
            confidence: Confianza de la predicción (0-1)
            show_buffer: Mostrar estado del buffer
            show_inference_time: Mostrar tiempo de inferencia
            
        Returns:
            Frame anotado
        """
        annotated = frame.copy()
        h, w = annotated.shape[:2]
        
        # Calcular altura de barra superior
        bar_height = 70
        if show_inference_time:
            bar_height = 95
        
        # FONDO SEMI-TRANSPARENTE
        overlay = np.zeros_like(annotated, dtype=np.uint8)
        cv2.rectangle(overlay, (0, 0), (w, bar_height), (0, 0, 0), -1)
        alpha = 0.65
        cv2.addWeighted(overlay, alpha, annotated, 1 - alpha, 0, annotated)

        # TEXTO PRINCIPAL (PREDICCIÓN)
        display_text = text
        if confidence is not None and confidence > 0:
            display_text += f" ({confidence*100:.1f}%)"
            
            # Color según confianza
            if confidence > 0.7:
                color = (0, 255, 0)  # Verde - Alta confianza
            elif confidence > self.confidence_threshold:
                color = (0, 255, 255)  # Amarillo - Media confianza
            else:
                color = (0, 165, 255)  # Naranja - Baja confianza
        else:
            color = (255, 255, 255)  # Blanco - Sin confianza

        cv2.putText(
            annotated, display_text, (10, 35), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA
        )
        
        # INFO DEL BUFFER
        if show_buffer:
            buffer_info = f"Buffer: {len(self.sequence_buffer)}/30"
            buffer_color = (0, 255, 0) if len(self.sequence_buffer) == 30 else (200, 200, 200)
            cv2.putText(
                annotated, buffer_info, (10, 60), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, buffer_color, 1, cv2.LINE_AA
            )
        
        # TIEMPO DE INFERENCIA
        if show_inference_time and self.last_inference_time > 0:
            inf_time = f"Inference: {self.last_inference_time*1000:.1f}ms"
            cv2.putText(
                annotated, inf_time, (10, 85), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1, cv2.LINE_AA
            )
        
        # INDICADOR DE FORMATO (esquina inferior derecha)
        format_text = "Holistic (258)"
        text_size = cv2.getTextSize(format_text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
        cv2.putText(
            annotated, format_text, 
            (w - text_size[0] - 10, h - 10), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1, cv2.LINE_AA
        )
        
        return annotated

    def set_confidence_threshold(self, threshold: float):
        """
        Ajusta el umbral de confianza para filtrar predicciones.
        
        Args:
            threshold: Nuevo umbral (0.0-1.0)
        """
        if 0.0 <= threshold <= 1.0:
            self.confidence_threshold = threshold
            logger.info(f"Umbral de confianza ajustado a {threshold:.2%}")
        else:
            logger.warning(f"Umbral inválido: {threshold} (debe estar entre 0 y 1)")

    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del procesador.
        
        Returns:
            dict con estadísticas de rendimiento y estado
        """
        return {
            "buffer_size": len(self.sequence_buffer),
            "buffer_capacity": 30,
            "buffer_full": len(self.sequence_buffer) == 30,
            "current_prediction": self.current_prediction[0],
            "current_confidence": self.current_prediction[1],
            "last_inference_time_ms": self.last_inference_time * 1000,
            "fps": self.performance.get_fps(),
            "confidence_threshold": self.confidence_threshold,
            "no_detection_counter": self.no_detection_counter
        }