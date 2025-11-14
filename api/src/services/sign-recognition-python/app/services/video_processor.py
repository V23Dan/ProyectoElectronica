import time
import logging
import cv2
import numpy as np
from collections import deque
from typing import Tuple, Dict, Any, Optional

from app.services.camera_manager import CameraManager
from app.models.sign_classifier import SignClassifier
from app.utils.performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, camera_manager: CameraManager, classifier: SignClassifier, show_video: bool = False):
        self.camera_manager = camera_manager
        self.classifier = classifier
        self.show_video = show_video
        self.performance = PerformanceMonitor()
        self.current_prediction = ("", 0.0)
        self.last_inference_time = 0.0
        self.sequence_buffer = deque(maxlen=30)  # Buffer para secuencias de frames
        self.initialized = False

    # ---- Cámara ----
    def initialize_camera(self, auto_connect: bool = True) -> bool:
        """Intenta conectar una cámara (ESP32 o local)."""
        if not auto_connect:
            logger.info("Inicialización manual de cámara deshabilitada.")
            return False
        ok = self.camera_manager.initialize(auto_connect=True)
        self.initialized = ok
        if ok:
            logger.info("Cámara inicializada correctamente.")
        else:
            logger.warning("No se pudo inicializar ninguna cámara.")
        return ok

    def switch_camera(self, camera_config: Dict[str, Any]) -> bool:
        """Cambia entre cámaras (ESP32 o local)."""
        return self.camera_manager.switch_camera(camera_config)

    def get_camera_status(self) -> Dict[str, Any]:
        """Retorna estado actual de cámara."""
        return self.camera_manager.get_status()

    def get_available_cameras(self) -> Dict[str, Any]:
        """Lista cámaras disponibles (solo locales si aplica)."""
        return self.camera_manager.list_cameras()

    def close(self):
        """Cierra cámara y limpia recursos."""
        self.camera_manager.close()

    # ---- Procesamiento ----
    def process_next_frame(self) -> Optional[Tuple[np.ndarray, str, float]]:
        """
        Captura un frame, obtiene landmarks y realiza inferencia.
        Retorna: (frame procesado, predicción, confianza)
        """
        frame = self.camera_manager.get_frame()
        if frame is None:
            return None

        self.performance.start_frame()

        # Detección de manos y landmarks
        landmarks_vector = self.camera_manager.detect_hands(frame)

        if landmarks_vector is None or len(landmarks_vector) == 0:
            self.current_prediction = ("NO_HANDS_DETECTED", 0.0)
            processed = self._annotate_frame(frame, "Sin manos detectadas")
            self.performance.end_frame()
            return processed, "NO_HANDS_DETECTED", 0.0
        
        flattened = []
        
        if len(landmarks_vector) == 1:
            #Solo una mano
            hand = np.array(landmarks_vector[0])
            wrist = hand[0]
            hand_norm = hand - wrist
            hand_norm[0] = [0.0, 0.0, 0.0]
            flattened.extend(hand_norm.flatten())
            flattened.extend([0.0] * 63) #Rellenar para la segunda mano
        elif len(landmarks_vector) == 2:
            lh = np.array(landmarks_vector[0])
            rh = np.array(landmarks_vector[1])
            lh_wrist = lh[0]
            rh_wrist = rh[0]
            lh_norm = lh - lh_wrist
            rh_norm = rh - rh_wrist
            lh_norm[0] = [0.0, 0.0, 0.0]
            rh_norm[0] = [0.0, 0.0, 0.0]
            flattened.extend(lh_norm.flatten())
            flattened.extend(rh_norm.flatten())
        else:
            # Sin manos detectadas
            flattened = [0.0] * 126
            
        x_input = np.array(flattened[:126])
        
        #Guardar en buffer de secuencia
        self.sequence_buffer.append(x_input)
        if len(self.sequence_buffer) < 30:
            processed = self._annotate_frame(frame, "Cargando secuencia...")
            self.performance.end_frame()
            return processed, "LOADING_SEQUENCE", 0.0
        
        sequence_array = np.array(self.sequence_buffer).reshape(1, 30, 126)
        
        # Clasificación de seña con modelo TensorFlow
        start_inf = time.perf_counter()
        try:
            prediction, confidence = self.classifier.predict(sequence_array)
        except Exception as e:
            logger.error(f"Error en inferencia: {e}")
            prediction, confidence = "ERROR_PREDICCION", 0.0
        self.last_inference_time = time.perf_counter() - start_inf

        # Actualiza predicción actual
        self.current_prediction = (prediction, confidence)

        # Dibujar información en frame
        processed_frame = self._annotate_frame(frame, prediction, confidence)

        self.performance.end_frame()
        if self.show_video:
            cv2.imshow("Sign Language Recognition", processed_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.close()

        return processed_frame, prediction, confidence

    def reset_classifier(self):
        """Reinicia el estado interno del clasificador (por compatibilidad futura)."""
        self.current_prediction = ("", 0.0)
        logger.info("Clasificador reiniciado correctamente.")

    def get_current_prediction(self) -> Tuple[str, float]:
        """Retorna la última predicción y confianza."""
        return self.current_prediction

    # ---- Utilidades internas ----
    def _annotate_frame(self, frame: np.ndarray, text: str, confidence: Optional[float] = None) -> np.ndarray:
        """Dibuja texto informativo sobre el frame."""
        annotated = frame.copy()
        overlay = np.zeros_like(annotated, dtype=np.uint8)
        cv2.rectangle(overlay, (0, 0), (annotated.shape[1], 40), (0, 0, 0), -1)
        alpha = 0.6
        cv2.addWeighted(overlay, alpha, annotated, 1 - alpha, 0, annotated)

        display_text = f"{text}"
        if confidence is not None and confidence > 0:
            display_text += f" ({confidence*100:.1f}%)"

        cv2.putText(annotated, display_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        return annotated
