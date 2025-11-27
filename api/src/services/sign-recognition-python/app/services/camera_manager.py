import cv2
import numpy as np
import mediapipe as mp
import logging
import threading
import time
from typing import Dict, Optional, Any
import requests

logger = logging.getLogger(__name__)

class CameraManager:
    def __init__(self):
        self.capture = None
        self.is_esp32 = False
        self.esp32_url = None
        self.frame_thread = None
        self.latest_frame = None
        self.thread_running = False
        self.lock = threading.Lock()
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils

    def initialize(self, auto_connect: bool = True) -> bool:
        if auto_connect:
            esp_url = "http://192.168.217.15:81/"
            logger.info("Intentando conectar a cámaras automáticamente...")

            if self.connect_esp32(esp_url):
                logger.info("Cámara ESP32-CAM inicializada.")
                return True
            else:
                logger.info("No se detectó cámara ESP32-CAM en la red.")
            logger.info("Intentando cámara local...")
            if self.connect_local(0):
                logger.info("Cámara local inicializada.")
                return True
        logger.warning("No se detectó ninguna cámara disponible.")
        return False

    def _start_reading_thread(self):
        if self.frame_thread is not None:
            self.thread_running = False
            self.frame_thread.join()

        self.thread_running = True
        self.frame_thread = threading.Thread(target=self._update_frame, daemon=True)
        self.frame_thread.start()
        logger.info("Hilo de lectura de cámara iniciado.")

    def _update_frame(self):
        while self.thread_running and self.capture is not None:
            if self.capture.isOpened():
                grabbed = self.capture.grab()

                if grabbed:
                    ret, frame = self.capture.retrieve()
                    if ret:
                        with self.lock:
                            self.latest_frame = frame
                    else:
                        time.sleep(0.01)
                else:
                    time.sleep(0.1)
            else:
                time.sleep(0.1)

    def connect_esp32(self, url: str) -> bool:
        self.close()  
        cap = cv2.VideoCapture(url)

        if not cap.isOpened():
            logger.warning(f"No se pudo abrir el stream ESP32: {url}")
            return False

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 0)

        self.capture = cap
        self.is_esp32 = True
        self.esp32_url = url

        self._start_reading_thread()

        logger.info(f"ESP32-CAM conectada a stream {url}")
        return True

    def connect_local(self, cam_index: int = 0) -> bool:
        self.close()
        cap = cv2.VideoCapture(cam_index)
        if not cap.isOpened():
            logger.warning("No se pudo abrir la cámara local.")
            return False

        self.capture = cap
        self.is_esp32 = False

        self._start_reading_thread()

        return True

    def get_frame(self) -> Optional[np.ndarray]:
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
        return None

    def switch_camera(self, config: Dict[str, Any]) -> bool:
        camera_type = config.get("type", "local")
        if camera_type == "esp32":
            return self.connect_esp32(config.get("url", "http://192.168.217.15:81/"))
        elif camera_type == "local":
            return self.connect_local(config.get("index", 0))
        return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self.capture is not None and self.thread_running,
            "type": "esp32" if self.is_esp32 else "local",
            "esp32_url": self.esp32_url,
        }

    def list_cameras(self) -> Dict[str, Any]:
        available = []
        for i in range(3):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return {"local": available, "esp32": self.esp32_url}

    def close(self):
        """Detiene hilo y libera cámara."""
        self.thread_running = False

        if self.frame_thread is not None:
            self.frame_thread.join(timeout=1.0)
            self.frame_thread = None

        if self.capture:
            self.capture.release()

        self.capture = None
        self.is_esp32 = False
        self.esp32_url = None
        self.latest_frame = None
        logger.info("Cámara cerrada y hilo detenido.")
