import numpy as np
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Landmark:
    x: float
    y: float
    z: float
    visibility: Optional[float] = None

class HandLandmarks:
    def __init__(self):
        self.landmarks: List[Landmark] = []
        self.world_landmarks: List[Landmark] = []
        self.handedness: str = "" 
        self.score: float = 0.0
    
    def add_landmark(self, x: float, y: float, z: float, visibility: float = None):
        """Añade un landmark a la lista"""
        landmark = Landmark(x, y, z, visibility)
        self.landmarks.append(landmark)
    
    def add_world_landmark(self, x: float, y: float, z: float):
        """Añade un landmark en coordenadas mundiales"""
        landmark = Landmark(x, y, z)
        self.world_landmarks.append(landmark)
    
    def get_landmarks_array(self) -> np.ndarray:
        """Convierte los landmarks a array numpy para el modelo"""
        if not self.landmarks:
            return np.array([])
        
        landmarks_array = []
        for landmark in self.landmarks:
            landmarks_array.extend([landmark.x, landmark.y, landmark.z])
        
        return np.array(landmarks_array)
    
    def get_normalized_landmarks(self) -> np.ndarray:
        """Normaliza los landmarks respecto a un punto de referencia (wrist)"""
        if len(self.landmarks) < 1:
            return np.array([])
        
        # Usar la muñeca (landmark 0) como referencia
        wrist = self.landmarks[0]
        normalized = []
        
        for landmark in self.landmarks:
            # Normalizar respecto a la muñeca
            norm_x = landmark.x - wrist.x
            norm_y = landmark.y - wrist.y
            norm_z = landmark.z - wrist.z
            normalized.extend([norm_x, norm_y, norm_z])
        
        return np.array(normalized)
    
    def is_valid(self) -> bool:
        """Verifica si hay landmarks válidos"""
        return len(self.landmarks) == 21  # MediaPipe detecta 21 landmarks por mano
    
    def __len__(self):
        return len(self.landmarks)