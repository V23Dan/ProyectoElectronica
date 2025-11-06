import numpy as np
import tensorflow as tf
import logging
from typing import Tuple, List, Dict
import os
import json

from app.models.hand_landmarks import HandLandmarks

class SignClassifier:
    def __init__(self, model_path: str = None, sequence_length: int = 30):
        self.model = None
        if model_path is None:
            current_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.model_path = os.path.join(current_dir, "trained_models", "actionPalabrasV2.h5")
        else:
            self.model_path = model_path
        self.sequence_length = sequence_length
        self.landmarks_sequence: List[np.ndarray] = []
        self.expected_features = 258  
        self.input_features = 63 
        
        # Cargar vocabulario del modelo real si existe
        self.sign_vocabulary = self._load_vocabulary()
        
        self.load_model()
        logging.info("SignClassifier inicializado")
    
    def _load_vocabulary(self):
        vocab_path = self.model_path.replace('.h5', '_vocabulary.json')
        if os.path.exists(vocab_path):
            try:
                with open(vocab_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"No se pudo cargar vocabulario: {e}")
        
        return {
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
    
    def load_model(self):
        """Carga el modelo"""
        try:
            if self.model_path and os.path.exists(self.model_path):
                # Intentar cargar con diferentes opciones de compatibilidad
                try:
                    self.model = tf.keras.models.load_model(self.model_path)
                    logging.info(f"Modelo cargado desde: {self.model_path}")
                    
                    # Verificar la forma de entrada del modelo
                    if hasattr(self.model, 'input_shape') and self.model.input_shape:
                        self.expected_features = self.model.input_shape[-1]
                        logging.info(f"Modelo espera {self.expected_features} características")
                    
                except Exception as e1:
                    logging.warning(f"Primer intento falló: {e1}. Probando con compile=False...")
                    
                    # Segundo intento sin compilar
                    self.model = tf.keras.models.load_model(self.model_path, compile=False)
                    logging.info(f"Modelo cargado sin compilar: {self.model_path}")
                    
                    if hasattr(self.model, 'input_shape') and self.model.input_shape:
                        self.expected_features = self.model.input_shape[-1]
                        logging.info(f"Modelo espera {self.expected_features} características")
                        
            else:
                logging.warning(f"Archivo de modelo no encontrado: {self.model_path}")
                self._create_temporary_model()
                
        except Exception as e:
            logging.error(f"Error cargando modelo: {e}")
            self._create_temporary_model()
    
    def _create_temporary_model(self):
        """Crea un modelo temporal para pruebas"""
        try:
            logging.info("Creando modelo temporal...")
            self.expected_features = 63  # Para el modelo temporal
            
            self.model = tf.keras.Sequential([
                tf.keras.layers.LSTM(64, return_sequences=True, 
                                   input_shape=(self.sequence_length, self.expected_features)),
                tf.keras.layers.Dropout(0.2),
                tf.keras.layers.LSTM(32),
                tf.keras.layers.Dense(16, activation='relu'),
                tf.keras.layers.Dense(len(self.sign_vocabulary), activation='softmax')
            ])
            
            self.model.compile(
                optimizer='adam',
                loss='categorical_crossentropy',
                metrics=['accuracy']
            )
            
            logging.info("Modelo temporal creado")
            
        except Exception as e:
            logging.error(f"Error creando modelo temporal: {e}")
    
    def _adapt_features(self, landmarks: np.ndarray) -> np.ndarray:
        """Adapta las características a lo que espera el modelo"""
        if landmarks.size == 0:
            return np.zeros(self.expected_features)
        
        # Si el modelo espera más características de las que tenemos
        if self.expected_features > self.input_features:
            # Rellenar con ceros o repetir características
            adapted = np.zeros(self.expected_features)
            min_features = min(self.expected_features, len(landmarks))
            adapted[:min_features] = landmarks[:min_features]
            return adapted
        # Si el modelo espera menos características
        elif self.expected_features < self.input_features:
            return landmarks[:self.expected_features]
        else:
            return landmarks
    
    def add_landmarks_to_sequence(self, landmarks: np.ndarray):
        """Añade landmarks a la secuencia para LSTM"""
        if landmarks.size == 0:
            return
        
        # Adaptar características al modelo
        adapted_landmarks = self._adapt_features(landmarks)
        
        # Si la secuencia está llena, eliminar el más antiguo
        if len(self.landmarks_sequence) >= self.sequence_length:
            self.landmarks_sequence.pop(0)
        
        self.landmarks_sequence.append(adapted_landmarks)
    
    def predict(self, landmarks: np.ndarray) -> Tuple[str, float]:
        """
        Predice la seña basada en los landmarks
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
            
            # Verificar que la forma coincide con lo que espera el modelo
            if sequence_array.shape[-1] != self.expected_features:
                logging.warning(f"Forma incorrecta: esperaba {self.expected_features}, obtuvo {sequence_array.shape[-1]}")
                return "ERROR_FORMA", 0.0
            
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
    
    def get_model_info(self) -> Dict:
        """Obtiene información del modelo cargado"""
        if self.model and hasattr(self.model, 'input_shape'):
            return {
                "input_shape": self.model.input_shape,
                "expected_features": self.expected_features,
                "actual_features": self.input_features,
                "sequence_length": self.sequence_length,
                "vocabulary_size": len(self.sign_vocabulary)
            }
        return {"status": "model_not_loaded"}