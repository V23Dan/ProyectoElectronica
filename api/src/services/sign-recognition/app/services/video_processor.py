import cv2
import numpy as np
import logging
import time
from typing import Tuple, List, Optional

from app.services.hand_detector import HandDetector
from app.models.sign_classifier import SignClassifier
from app.services.camera_manager import CameraManager
from app.models.hand_landmarks import HandLandmarks

class VideoProcessor:
    def __init__(self):
        self.camera_manager = CameraManager()
        self.hand_detector = HandDetector()
        self.sign_classifier = SignClassifier()
        
        self.current_prediction = ""
        self.current_confidence = 0.0
        self.processing_stats = {
            "fps": 0,
            "processing_time": 0,
            "frames_processed": 0
        }
        
        self.fps_counter = 0
        self.fps_time = time.time()
        
        logging.info("VideoProcessor inicializado")
    
    def initialize_camera(self, auto_connect: bool = True) -> bool:
        """Inicializa la cámara automáticamente"""
        if auto_connect:
            success = self.camera_manager.auto_connect()
            if success:
                logging.info(" Cámara inicializada automáticamente")
            else:
                logging.warning(" No se pudo inicializar la cámara automáticamente")
            return success
        return False
    
    def connect_to_camera(self, camera_config: dict) -> bool:
        """Conecta a una cámara específica"""
        return self.camera_manager.connect_camera(camera_config)
    
    def process_next_frame(self) -> Tuple[Optional[np.ndarray], str, float]:
        """
        Procesa el siguiente frame disponible
        """
        try:
            # Obtener frame de la cámara
            frame = self.camera_manager.get_frame()
            if frame is None:
                return None, "ESPERANDO_CAMARA", 0.0
            
            # Calcular FPS
            self._update_fps()
            
            # Procesar frame
            start_time = time.time()
            processed_frame, prediction, confidence = self._process_single_frame(frame)
            processing_time = time.time() - start_time
            
            # Actualizar estadísticas
            self.processing_stats["processing_time"] = processing_time
            self.processing_stats["frames_processed"] += 1
            
            return processed_frame, prediction, confidence
            
        except Exception as e:
            logging.error(f"Error en process_next_frame: {e}")
            return None, "ERROR_PROCESAMIENTO", 0.0
    
    def _process_single_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, str, float]:
        """Procesa un frame individual"""
        # Voltear frame si es cámara laptop (efecto espejo)
        if self.camera_manager.camera_type == "laptop":
            frame = cv2.flip(frame, 1)
        
        # Detectar manos
        processed_frame, hand_landmarks_list = self.hand_detector.process_frame(frame)
        
        prediction = "NO_HANDS_DETECTED"
        confidence = 0.0
        
        # Procesar primera mano detectada
        if hand_landmarks_list:
            hand_data = hand_landmarks_list[0]
            
            if hand_data.is_valid():
                # Obtener landmarks para modelo
                landmarks_array = self.hand_detector.get_landmarks_for_model(hand_data)
                
                # Predecir seña
                prediction, confidence = self.sign_classifier.predict(landmarks_array)
                
                # Actualizar estado actual
                self.current_prediction = prediction
                self.current_confidence = confidence
                
                # Añadir información al frame
                self._add_debug_info(processed_frame, hand_data, prediction, confidence)
            else:
                prediction = "LANDMARKS_INVALID"
        else:
            # Reiniciar secuencia si no hay manos
            self.sign_classifier.reset_sequence()
        
        return processed_frame, prediction, confidence
    
    def _add_debug_info(self, frame: np.ndarray, hand_data: HandLandmarks, 
                       prediction: str, confidence: float):
        """Añade información de debug al frame"""
        # Información de la cámara
        cam_info = self.camera_manager.get_camera_info()
        camera_text = f"Cam: {cam_info.get('name', 'Unknown')}"
        cv2.putText(frame, camera_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Predicción y confianza
        prediction_text = f"Seña: {prediction} ({confidence:.2f})"
        color = (0, 255, 0) if confidence > 0.7 else (0, 255, 255)
        cv2.putText(frame, prediction_text, (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # Información de la mano
        hand_info = f"Mano: {hand_data.handedness} ({hand_data.score:.2f})"
        cv2.putText(frame, hand_info, (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        # Secuencia LSTM
        seq_info = f"Secuencia: {self.sign_classifier.get_sequence_length()}/{self.sign_classifier.sequence_length}"
        cv2.putText(frame, seq_info, (10, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        # FPS y tiempo de procesamiento
        fps_text = f"FPS: {self.processing_stats['fps']:.1f}"
        cv2.putText(frame, fps_text, (10, 150), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    def _update_fps(self):
        """Actualiza el cálculo de FPS"""
        self.fps_counter += 1
        current_time = time.time()
        
        if current_time - self.fps_time >= 1.0:
            self.processing_stats["fps"] = self.fps_counter
            self.fps_counter = 0
            self.fps_time = current_time
    
    def get_available_cameras(self) -> List[dict]:
        """Obtiene lista de cámaras disponibles"""
        return self.camera_manager.scan_available_cameras()
    
    def get_camera_status(self) -> dict:
        """Obtiene estado de la cámara actual"""
        cam_info = self.camera_manager.get_camera_info()
        cam_info.update(self.processing_stats)
        return cam_info
    
    def switch_camera(self, camera_config: dict) -> bool:
        """Cambia a otra cámara"""
        success = self.camera_manager.connect_camera(camera_config)
        if success:
            self.sign_classifier.reset_sequence()
        return success
    
    def get_current_prediction(self) -> Tuple[str, float]:
        """Obtiene la última predicción"""
        return self.current_prediction, self.current_confidence
    
    def reset_classifier(self):
        """Reinicia el clasificador"""
        self.sign_classifier.reset_sequence()
        self.current_prediction = ""
        self.current_confidence = 0.0
    
    def close(self):
        """Liberar recursos"""
        self.camera_manager.disconnect_camera()
        self.hand_detector.close()