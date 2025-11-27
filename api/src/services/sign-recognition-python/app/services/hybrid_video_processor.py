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

        self.current_prediction = ("", 0.0)
        self.last_inference_time = 0.0
        
        self.sequence_buffer = deque(maxlen=30)

        self.initialized = False
        
        self.no_detection_counter = 0
        self.stability_threshold = 5 

        self.confidence_threshold = 0.4
        
        logger.info("HybridVideoProcessor inicializado")

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

        frame = self.camera_manager.get_frame()
        if frame is None:
            return None

        self.performance.start_frame()
        frame = cv2.resize(frame, (640, 480))


        landmarks_vector, results = self.holistic_processor.process(frame)

        has_hands = self.holistic_processor.has_hands(results)
        
        if not has_hands:
            self.no_detection_counter += 1

            if self.no_detection_counter > self.stability_threshold:
                if len(self.sequence_buffer) > 0:
                    self.sequence_buffer.clear()
                    logger.debug("Buffer limpiado por falta de detecciones")
                self.current_prediction = ("NO_HANDS_DETECTED", 0.0)

            annotated = self.holistic_processor.draw_landmarks(frame, results)
            processed = self._annotate_frame(
                annotated, 
                "Sin manos detectadas",
                show_buffer=True
            )
            
            self.performance.end_frame()
            return processed, "NO_HANDS_DETECTED", 0.0
        
        self.no_detection_counter = 0
        if landmarks_vector is None or landmarks_vector.shape[0] != 258:
            logger.warning(
                f"Landmarks inválidos: "
                f"{landmarks_vector.shape if landmarks_vector is not None else 'None'}"
            )
            annotated = self.holistic_processor.draw_landmarks(frame, results)
            processed = self._annotate_frame(annotated, "Error en extracción")
            self.performance.end_frame()
            return processed, "ERROR_EXTRACTION", 0.0

        self.sequence_buffer.append(landmarks_vector)

        annotated = self.holistic_processor.draw_landmarks(frame, results)

        if len(self.sequence_buffer) < 30:
            frames_needed = 30 - len(self.sequence_buffer)
            processed = self._annotate_frame(
                annotated,
                f"Cargando secuencia... ({frames_needed} frames restantes)",
                show_buffer=True
            )
            self.performance.end_frame()
            return processed, "LOADING_SEQUENCE", 0.0

        sequence_array = np.array(list(self.sequence_buffer), dtype=np.float32)
        sequence_array = sequence_array.reshape(1, 30, 258)

        start_inf = time.perf_counter()
        try:
            prediction, confidence = self.classifier.predict(sequence_array)

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

        self.current_prediction = (prediction, confidence)

        processed_frame = self._annotate_frame(
            annotated, 
            prediction, 
            confidence,
            show_buffer=True,
            show_inference_time=True
        )

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
        self.sequence_buffer.clear()
        self.current_prediction = ("", 0.0)
        self.no_detection_counter = 0
        logger.info("Clasificador reiniciado (buffer limpiado)")

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
        annotated = frame.copy()
        h, w = annotated.shape[:2]
        

        bar_height = 70
        if show_inference_time:
            bar_height = 95

        overlay = np.zeros_like(annotated, dtype=np.uint8)
        cv2.rectangle(overlay, (0, 0), (w, bar_height), (0, 0, 0), -1)
        alpha = 0.65
        cv2.addWeighted(overlay, alpha, annotated, 1 - alpha, 0, annotated)

        display_text = text
        if confidence is not None and confidence > 0:
            display_text += f" ({confidence*100:.1f}%)"
            if confidence > 0.7:
                color = (0, 255, 0) 
            elif confidence > self.confidence_threshold:
                color = (0, 255, 255) 
            else:
                color = (0, 165, 255) 
        else:
            color = (255, 255, 255)  

        cv2.putText(
            annotated, display_text, (10, 35), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA
        )

        if show_buffer:
            buffer_info = f"Buffer: {len(self.sequence_buffer)}/30"
            buffer_color = (0, 255, 0) if len(self.sequence_buffer) == 30 else (200, 200, 200)
            cv2.putText(
                annotated, buffer_info, (10, 60), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, buffer_color, 1, cv2.LINE_AA
            )

        if show_inference_time and self.last_inference_time > 0:
            inf_time = f"Inference: {self.last_inference_time*1000:.1f}ms"
            cv2.putText(
                annotated, inf_time, (10, 85), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1, cv2.LINE_AA
            )

        format_text = "Holistic (258)"
        text_size = cv2.getTextSize(format_text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
        cv2.putText(
            annotated, format_text, 
            (w - text_size[0] - 10, h - 10), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1, cv2.LINE_AA
        )
        
        return annotated

    def set_confidence_threshold(self, threshold: float):
        if 0.0 <= threshold <= 1.0:
            self.confidence_threshold = threshold
            logger.info(f"Umbral de confianza ajustado a {threshold:.2%}")
        else:
            logger.warning(f"Umbral inválido: {threshold} (debe estar entre 0 y 1)")

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
            "no_detection_counter": self.no_detection_counter
        }