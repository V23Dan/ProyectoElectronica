import cv2
import numpy as np
import mediapipe as mp
import requests
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

class CameraManager:
    def __init__(self):
        self.capture = None
        self.is_esp32 = False
        self.esp32_url = None
        self.mp_hands = mp.solutions.hands
        self.hands_detector = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.last_frame = None

    # Inicialización
    def initialize(self, auto_connect: bool = True) -> bool:
        """Intenta conectar automáticamente una cámara (ESP32 o local)."""
        if auto_connect:
            # Intenta ESP32
            if self.connect_esp32("http://192.168.126.15:81/"):
                logger.info("Conectado a cámara ESP32-CAM.")
                return True
            # Si falla, intenta cámara local
            if self.connect_local(0):
                logger.info("Cámara local inicializada.")
                return True
        logger.warning("No se detectó ninguna cámara disponible.")
        return False

    def connect_esp32(self, url: str) -> bool:
        """Conecta a stream ESP32-CAM (HTTP MJPEG)."""
        self.close()
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            logger.warning(f"No se pudo abrir el stream MJPEG de la ESP32-CAM: {url}")
            return False
        self.capture = cap
        self.is_esp32 = True
        self.esp32_url = url
        logger.info(f"✅ ESP32-CAM conectada a stream {url}")
        return True


    def get_frame(self) -> Optional[np.ndarray]:
        """Obtiene un frame de la cámara (ESP32 o local)."""
        if self.capture is not None and self.capture.isOpened():
            ret, frame = self.capture.read()
            if ret:
                self.last_frame = frame
                return frame
            else:
                logger.warning("⚠️ No se pudo leer frame de la cámara.")
        return None


    def connect_local(self, cam_index: int = 0) -> bool:
        """Conecta cámara local mediante OpenCV."""
        self.close()
        cap = cv2.VideoCapture(cam_index)
        if not cap.isOpened():
            logger.warning("No se pudo abrir la cámara local.")
            return False
        self.capture = cap
        self.is_esp32 = False
        return True

    def switch_camera(self, config: Dict[str, Any]) -> bool:
        """Permite cambiar entre cámaras (según configuración enviada)."""
        camera_type = config.get("type", "local")
        if camera_type == "esp32":
            return self.connect_esp32(config.get("url", "http://192.168.126.15:81/"))
        elif camera_type == "local":
            return self.connect_local(config.get("index", 0))
        return False

    def detect_hands(self, frame: np.ndarray):
        """
        Detecta manos en un frame y retorna lista de landmarks normalizados.
        """
        if frame is None:
            return None
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.hands_detector.process(rgb)
        landmarks_list = []

        if result.multi_hand_landmarks:
            for hand_landmarks in result.multi_hand_landmarks:
                # Extrae coordenadas normalizadas
                landmarks = [(lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark]
                landmarks_list.append(landmarks)
                # Dibuja la mano
                self.mp_drawing.draw_landmarks(
                    frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS
                )
        return landmarks_list

    # Estado
    def list_cameras(self) -> Dict[str, Any]:
        """Lista cámaras locales disponibles (0–3)."""
        available = []
        for i in range(4):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return {"local": available, "esp32": self.esp32_url}

    def get_status(self) -> Dict[str, Any]:
        """Estado actual de conexión."""
        return {
            "connected": self.capture is not None or self.is_esp32,
            "type": "esp32" if self.is_esp32 else "local",
            "esp32_url": self.esp32_url,
        }

    def close(self):
        """Libera recursos de cámara."""
        if self.capture:
            self.capture.release()
        self.capture = None
        self.is_esp32 = False
        self.esp32_url = None
        logger.info("Cámara cerrada correctamente.")
