import tensorflow as tf
import numpy as np
import os
from typing import Tuple

class SignPredictor:
    def __init__(self, model_path: str):
        self.model = None
        self,model_path = model_path
        self.load_model()
        self.class_names = self.load_class_names()
        
    def load_model(self):
        #Cargar el modelo LSTM preentrenado
        if os.path.exists(self.model_path):
            self.model = tf.keras.models.load_model(self.model_path)
        else:
            self.model = self._create_temp_model()
    def _create_temp_model(self):
        """Modelo temporal para pruebas"""
        model = tf.keras.Sequential([
            tf.keras.layers.LSTM(64, return_sequences=True, input_shape=(30, 63)),
            tf.keras.layers.LSTM(32),
            tf.keras.layers.Dense(16, activation='relu'),
            tf.keras.layers.Dense(5, activation='softmax')  # 5 clases de ejemplo
        ])
        return model
    
    def load_class_names(self):
        #Cargar nombres de clases (señas)
        # Mapeo temporal - reemplazar con tu vocabulario real
        return {
            0: "HOLA",
            1: "GRACIAS", 
            2: "AYUDA",
            3: "AGUA",
            4: "COMIDA"
        }
        
    def predict(self, landmarks: np.array) -> Tuple[str, float]:
        """
        Predecir la seña basada en los landmarks proporcionados.
        
        Args:
            landmarks (np.array): Array de forma (30, 63) que contiene los landmarks.
        
        Returns:
            Tuple[str, float]: Nombre de la seña predicha y su probabilidad.
        """
        if self.model is None:
            raise ValueError("El modelo no ha sido cargado correctamente.")
        
        sequence = np.array([landmarks] * 30)
        
        prediction = self.model.predict(sequence[np.newaxis, ...])
        confidence = np.max(prediction)
        class_id = np.argmax(prediction)
        
        return self.class_names.get(class_id, "Desconocido"), float(confidence)