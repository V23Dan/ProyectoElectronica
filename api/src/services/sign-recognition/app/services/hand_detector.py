import cv2
import mediapipe as mp
import numpy as np
from typing import List, Tuple, Optional
import logging

from app.models.hand_landmarks import HandLandmarks

class HandDetector:
    def __init__(self, 
                 static_image_mode: bool = False,
                 max_num_hands: int = 2,
                 min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5):
        
        self.static_image_mode = static_image_mode
        self.max_num_hands = max_num_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        
        # Inicializar MediaPipe Hands
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.hands = self.mp_hands.Hands(
            static_image_mode=static_image_mode,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        
        # Configurar estilo de dibujo
        self.drawing_styles = mp.solutions.drawing_styles
        
        logging.info("HandDetector inicializado correctamente")
    
    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, List[HandLandmarks]]:
        """
        Procesa un frame y detecta manos
        """
        hand_landmarks_list = []
        
        try:
            # Convertir BGR a RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False
            
            # Procesar con MediaPipe
            results = self.hands.process(rgb_frame)
            
            # Convertir de vuelta a BGR para dibujar
            rgb_frame.flags.writeable = True
            annotated_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
            
            if results.multi_hand_landmarks and results.multi_handedness:
                for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                    # Crear objeto HandLandmarks personalizado
                    hand_data = HandLandmarks()
                    hand_data.handedness = handedness.classification[0].label
                    hand_data.score = handedness.classification[0].score
                    
                    # Extraer landmarks
                    for landmark in hand_landmarks.landmark:
                        hand_data.add_landmark(landmark.x, landmark.y, landmark.z)
                    
                    # Extraer world landmarks si están disponibles
                    if results.multi_hand_world_landmarks:
                        for world_landmark in results.multi_hand_world_landmarks:
                            for landmark in world_landmark.landmark:
                                hand_data.add_world_landmark(landmark.x, landmark.y, landmark.z)
                    
                    hand_landmarks_list.append(hand_data)
                    
                    # Dibujar landmarks en el frame
                    self.mp_draw.draw_landmarks(
                        annotated_frame,
                        hand_landmarks,
                        self.mp_hands.HAND_CONNECTIONS,
                        self.drawing_styles.get_default_hand_landmarks_style(),
                        self.drawing_styles.get_default_hand_connections_style()
                    )
                    
                    # Añadir etiqueta de mano (izquierda/derecha)
                    h, w, _ = annotated_frame.shape
                    x_min = int(min([lm.x for lm in hand_landmarks.landmark]) * w)
                    y_min = int(min([lm.y for lm in hand_landmarks.landmark]) * h)
                    
                    cv2.putText(annotated_frame, 
                               f"{hand_data.handedness} ({hand_data.score:.2f})",
                               (x_min, y_min - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            return annotated_frame, hand_landmarks_list
            
        except Exception as e:
            logging.error(f"Error procesando frame: {e}")
            return frame, []
    
    def get_landmarks_for_model(self, hand_landmarks: HandLandmarks) -> np.ndarray:
        """Prepara los landmarks para el modelo de clasificación"""
        if not hand_landmarks.is_valid():
            return np.array([])
        
        # Usar landmarks normalizados para mejor consistencia
        return hand_landmarks.get_normalized_landmarks()
    
    def close(self):
        """Liberar recursos"""
        if self.hands:
            self.hands.close()