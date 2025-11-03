import numpy as np
import tensorflow as tf
import logging
from typing import Tuple, List, Dict
import os

from app.models.hand_landmarks import HandLandmarks

class SignClassifier:
    def __init__(self, model_path: str = None, sequence_length: int = 30):
        self.model = None
        self.model_path = model_path
        self.sequence_length = sequence_length
        self.landmarks_sequence: List[np.ndarray] = []
        
        # Vocabulario de señas colombianas (ejemplo - ajustar con tu dataset)
        self.sign_vocabulary = {
            0: "HOLA",
            1: "GRACIAS", 
            2: "POR FAVOR",
            3: "AYUDA",
            4: "AGUA",
            5: "COMIDA",
            6: "BAÑO",
            7: "FAMILIA",
            8: "AMIGO",
            9: "CASA"
        }
        
        self.load_model()
        logging.info("SignClassifier inicializado")
    
    def load_model(self):
        """Carga el modelo LSTM pre-entrenado"""
        try:
            if self.model_path and os.path.exists(self.model_path):
                self.model = tf.keras.models.load_model(self.model_path)
                logging.info(f"Modelo cargado desde: {self.model_path}")
            else:
                # Crear modelo temporal para pruebas
                self._create_temporary_model()
                logging.warning("Usando modelo temporal para pruebas")
                
        except Exception as e:
            logging.error(f"Error cargando modelo: {e}")
            self._create_temporary_model()
    
    def _create_temporary_model(self):
        """Crea un modelo LSTM temporal para pruebas"""
        try:
            # Modelo LSTM simple para pruebas
            self.model = tf.keras.Sequential([
                tf.keras.layers.LSTM(64, return_sequences=True, 
                                   input_shape=(self.sequence_length, 63)),
                tf.keras.layers.Dropout(0.2),
                tf.keras.layers.LSTM(32),
                tf.keras.layers.Dense(16, activation='relu'),
                tf.keras.layers.Dense(len(self.sign_vocabulary), activation='softmax')
            ])
            
            # Compilar con optimizador y pérdida
            self.model.compile(
                optimizer='adam',
                loss='categorical_crossentropy',
                metrics=['accuracy']
            )
            
        except Exception as e:
            logging.error(f"Error creando modelo temporal: {e}")
    
    def add_landmarks_to_sequence(self, landmarks: np.ndarray):
        """Añade landmarks a la secuencia para LSTM"""
        if landmarks.size == 0:
            return
        
        # Si la secuencia está llena, eliminar el más antiguo
        if len(self.landmarks_sequence) >= self.sequence_length:
            self.landmarks_sequence.pop(0)
        
        self.landmarks_sequence.append(landmarks)
    
    def predict(self, landmarks: np.ndarray) -> Tuple[str, float]:
        """
        Predice la seña basada en los landmarks
        
        Returns:
            Tuple: (predicted_sign, confidence)
        """
        try:
            # Añadir a la secuencia
            self.add_landmarks_to_sequence(landmarks)
            
            # Verificar si tenemos suficiente datos para predicción
            if len(self.landmarks_sequence) < self.sequence_length:
                return "SECUENCIA_INCOMPLETA", 0.0
            
            # Preparar datos para el modelo
            sequence_array = np.array(self.landmarks_sequence)
            sequence_array = sequence_array.reshape(1, self.sequence_length, -1)
            
            # Hacer predicción
            prediction = self.model.predict(sequence_array, verbose=0)
            confidence = np.max(prediction)
            predicted_class = np.argmax(prediction)
            
            # Obtener nombre de la seña
            sign_name = self.sign_vocabulary.get(predicted_class, "DESCONOCIDO")
            
            return sign_name, float(confidence)
            
        except Exception as e:
            logging.error(f"Error en predicción: {e}")
            return "ERROR_PREDICCION", 0.0
    
    def reset_sequence(self):
        """Reinicia la secuencia de landmarks"""
        self.landmarks_sequence = []
    
    def get_sequence_length(self) -> int:
        """Obtiene la longitud actual de la secuencia"""
        return len(self.landmarks_sequence)
    
    def get_vocabulary(self) -> Dict[int, str]:
        """Obtiene el vocabulario de señas"""
        return self.sign_vocabulary.copy()