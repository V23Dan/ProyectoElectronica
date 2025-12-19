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
        self.performance = PerformanceMonitor()
        self.current_prediction = ("", 0.0)
        self.last_inference_time = 0.0

        self.sequence_buffer = deque(maxlen=30)
        self.initialized = False
        self.no_detection_counter = 0
        self.stability_threshold = 5
        self.confidence_threshold = 0.4

        self.target_resolution = (640, 480)
        self.current_frame_size = None

        logger.info("HybridVideoProcessor inicializado (OPTIMIZADO)")

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

        h, w = frame.shape[:2]
        if (w, h) != self.target_resolution:
            if self.current_frame_size != (w, h):
                logger.info(f"Ajustando resolución: {w}x{h} -> {self.target_resolution[0]}x{self.target_resolution[1]}")
                self.current_frame_size = (w, h)
            
            frame = cv2.resize(frame, self.target_resolution, interpolation=cv2.INTER_LINEAR)

        landmarks_vector, results = self.holistic_processor.process(frame)
        has_hands = self.holistic_processor.has_hands(results)

        if not has_hands:
            self.no_detection_counter += 1

            if self.no_detection_counter > self.stability_threshold:
                if len(self.sequence_buffer) > 0:
                    self.sequence_buffer.clear()
                    logger.debug("Buffer limpiado por falta de detecciones")
                self.current_prediction = ("NO_HANDS_DETECTED", 0.0)

            annotated = self._annotate_minimal(frame, "Sin manos", results)
            self.performance.end_frame()
            return annotated, "NO_HANDS_DETECTED", 0.0

        self.no_detection_counter = 0

        if landmarks_vector is None or landmarks_vector.shape[0] != 258:
            logger.warning(f"Landmarks inválidos: {landmarks_vector.shape if landmarks_vector is not None else 'None'}")
            annotated = self._annotate_minimal(frame, "Error extracción", results)
            self.performance.end_frame()
            return annotated, "ERROR_EXTRACTION", 0.0

        self.sequence_buffer.append(landmarks_vector)

        if len(self.sequence_buffer) < 30:
            frames_needed = 30 - len(self.sequence_buffer)
            annotated = self._annotate_minimal(
                frame, 
                f"Cargando... ({frames_needed})", 
                results
            )
            self.performance.end_frame()
            return annotated, "LOADING_SEQUENCE", 0.0

        sequence_array = np.array(list(self.sequence_buffer), dtype=np.float32)
        sequence_array = sequence_array.reshape(1, 30, 258)

        start_inf = time.perf_counter()
        try:
            prediction, confidence = self.classifier.predict(sequence_array)

            if confidence < self.confidence_threshold:
                original_pred = prediction
                prediction = "BAJA_CONFIANZA"
                logger.debug(f"Confianza baja: {original_pred} ({confidence:.2%})")

        except Exception as e:
            logger.error(f"Error en inferencia: {e}", exc_info=True)
            prediction, confidence = "ERROR_PREDICCION", 0.0

        self.last_inference_time = time.perf_counter() - start_inf
        self.current_prediction = (prediction, confidence)

        processed_frame = self._annotate_minimal(
            frame,
            prediction,
            results,
            confidence
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

    def _annotate_minimal(
        self,
        frame: np.ndarray,
        text: str,
        results,
        confidence: Optional[float] = None
    ) -> np.ndarray:

        annotated = frame  

        h, w = annotated.shape[:2]

        try:
            if results and results.left_hand_landmarks:
                self.holistic_processor.mp_drawing.draw_landmarks(
                    annotated,
                    results.left_hand_landmarks,
                    self.holistic_processor.mp_holistic.HAND_CONNECTIONS,
                    landmark_drawing_spec=None, 
                    connection_drawing_spec=None
                )

            if results and results.right_hand_landmarks:
                self.holistic_processor.mp_drawing.draw_landmarks(
                    annotated,
                    results.right_hand_landmarks,
                    self.holistic_processor.mp_holistic.HAND_CONNECTIONS,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=None
                )

        except Exception as e:
            logger.error(f"Error dibujando landmarks: {e}")

        cv2.rectangle(annotated, (0, 0), (w, 50), (0, 0, 0), -1)

        display_text = text
        if confidence is not None and confidence > 0:
            display_text += f" {int(confidence*100)}%"
            
            color = (0, 255, 0) if confidence > 0.7 else (0, 255, 255) if confidence > 0.4 else (0, 165, 255)
        else:
            color = (255, 255, 255)

        cv2.putText(
            annotated, display_text, (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA
        )

        buffer_text = f"{len(self.sequence_buffer)}/30"
        cv2.putText(
            annotated, buffer_text, (w - 80, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA
        )

        return annotated

    def _annotate_frame(
        self,
        frame: np.ndarray,
        text: str,
        confidence: Optional[float] = None,
        show_buffer: bool = False,
        show_inference_time: bool = False
    ) -> np.ndarray:

        return self._annotate_minimal(frame, text, None, confidence)

    def reset_classifier(self):
        self.sequence_buffer.clear()
        self.current_prediction = ("", 0.0)
        self.no_detection_counter = 0
        logger.info("Clasificador reiniciado (buffer limpiado)")

    def get_current_prediction(self) -> Tuple[str, float]:
        return self.current_prediction

    def set_confidence_threshold(self, threshold: float):
        if 0.0 <= threshold <= 1.0:
            self.confidence_threshold = threshold
            logger.info(f"Umbral de confianza ajustado a {threshold:.2%}")
        else:
            logger.warning(f"Umbral inválido: {threshold}")

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