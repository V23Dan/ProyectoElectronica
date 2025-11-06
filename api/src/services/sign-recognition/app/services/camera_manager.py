import cv2
import numpy as np
import logging
from typing import Optional, List
import threading
import time

class CameraManager:
    def __init__(self):
        self.available_cameras = []
        self.current_camera = None
        self.camera_type = "unknown" 
        self.is_connected = False
        self.cap = None
        self.frame_buffer = None
        self.lock = threading.Lock()
        self.scan_thread = None
        self.running = False
        
        # Configuraciones para diferentes tipos de cámara
        self.camera_configs = {
            "laptop": {
                "width": 640,
                "height": 480,
                "fps": 30
            },
            "esp32": {
                "width": 640,
                "height": 480,
                "fps": 10
            },
        }
        
        logging.info("CameraManager inicializado")
    
    def scan_available_cameras(self) -> List[dict]:
        """Escanea y detecta cámaras disponibles"""
        cameras = []
        
        # Probar cámaras locales
        for i in range(2):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    camera_info = {
                        "index": i,
                        "type": "laptop",
                        "name": f"Cámara Laptop {i}",
                        "resolution": f"{int(cap.get(3))}x{int(cap.get(4))}",
                        "fps": cap.get(5)
                    }
                    cameras.append(camera_info)
                    logging.info(f" Cámara local detectada: {camera_info}")
                cap.release()
            time.sleep(0.1)
        
        # Probar cámaras IP/ESP32-CAM comunes
        esp32_urls = [
            "http://192.168.1.100:81/stream",  # ESP32-CAM común
        ]
        
        for url in esp32_urls:
            if self._test_ip_camera(url):
                camera_info = {
                    "url": url,
                    "type": "esp32",
                    "name": f"ESP32-CAM ({url})",
                    "resolution": "640x480",
                    "fps": 10
                }
                cameras.append(camera_info)
                logging.info(f" ESP32-CAM detectada: {url}")
        
        self.available_cameras = cameras
        return cameras
    
    def _test_ip_camera(self, url: str) -> bool:
        """Prueba si una cámara IP está disponible"""
        try:
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                # Intentar leer un frame
                ret, frame = cap.read()
                cap.release()
                return ret and frame is not None
        except Exception as e:
            logging.debug(f"Error probando cámara IP {url}: {e}")
        return False
    
    def connect_camera(self, camera_config: dict) -> bool:
        """Conecta a una cámara específica"""
        self.disconnect_camera()
        
        try:
            if camera_config["type"] == "laptop":
                self.cap = cv2.VideoCapture(camera_config["index"])
                self.camera_type = "laptop"
            else:  # esp32 o ip_camera
                self.cap = cv2.VideoCapture(camera_config["url"])
                self.camera_type = "esp32"
            
            if not self.cap.isOpened():
                logging.error(f"No se pudo abrir la cámara: {camera_config}")
                return False
            
            # Configurar parámetros según el tipo de cámara
            config = self.camera_configs[self.camera_type]
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config["width"])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config["height"])
            self.cap.set(cv2.CAP_PROP_FPS, config["fps"])
            
            # Verificar que funciona
            ret, frame = self.cap.read()
            if not ret:
                logging.error("La cámara no devuelve frames")
                self.cap.release()
                return False
            
            self.is_connected = True
            self.current_camera = camera_config
            
            # Iniciar hilo de captura continua
            self.running = True
            self.capture_thread = threading.Thread(target=self._capture_frames)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            
            logging.info(f" Conectado a: {camera_config['name']}")
            return True
            
        except Exception as e:
            logging.error(f"Error conectando a la cámara: {e}")
            self.disconnect_camera()
            return False
    
    def auto_connect(self) -> bool:
        """Conecta automáticamente a la mejor cámara disponible"""
        cameras = self.scan_available_cameras()
        
        if not cameras:
            logging.error(" No se encontraron cámaras disponibles")
            return False
        
        # Priorizar ESP32-CAM si está disponible
        esp32_cameras = [cam for cam in cameras if cam["type"] == "esp32"]
        if esp32_cameras:
            return self.connect_camera(esp32_cameras[0])
        
        # Si no hay ESP32, usar la primera cámara local
        laptop_cameras = [cam for cam in cameras if cam["type"] == "laptop"]
        if laptop_cameras:
            return self.connect_camera(laptop_cameras[0])
        
        return False
    
    def _capture_frames(self):
        """Hilo para captura continua de frames"""
        while self.running and self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    with self.lock:
                        self.frame_buffer = frame.copy()
                else:
                    # Reconectar si hay error
                    if self.running:
                        logging.warning("Frame vacío, intentando reconectar...")
                        time.sleep(1)
                        self.reconnect()
            except Exception as e:
                logging.error(f"Error en captura de frames: {e}")
                if self.running:
                    time.sleep(1)
                    self.reconnect()
    
    def reconnect(self):
        """Intenta reconectar a la cámara actual"""
        if self.current_camera:
            logging.info("Reconectando a la cámara...")
            self.connect_camera(self.current_camera)
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Obtiene el frame más reciente"""
        with self.lock:
            if self.frame_buffer is not None:
                return self.frame_buffer.copy()
        return None
    
    def disconnect_camera(self):
        """Desconecta la cámara actual"""
        self.running = False
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        with self.lock:
            self.frame_buffer = None
        
        self.is_connected = False
        self.current_camera = None
        logging.info("Cámara desconectada")
    
    def get_camera_info(self) -> dict:
        """Obtiene información de la cámara actual"""
        if not self.is_connected or not self.current_camera:
            return {"status": "disconnected"}
        
        info = self.current_camera.copy()
        info["status"] = "connected"
        info["frame_available"] = self.frame_buffer is not None
        
        if self.cap:
            info["actual_fps"] = self.cap.get(cv2.CAP_PROP_FPS)
            info["actual_width"] = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            info["actual_height"] = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        return info