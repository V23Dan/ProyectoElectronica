import tensorflow as tf
import numpy as np
import joblib
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class HybridSignClassifier:
    """
    Clasificador híbrido que espera 258 features:
    - Pose: 132 features (33 landmarks × 4: x, y, z, visibility)
    - Left Hand: 63 features (21 landmarks × 3: x, y, z)
    - Right Hand: 63 features (21 landmarks × 3: x, y, z)
    """
    
    def __init__(self, model_path: str, vocab_path: str, scaler_path: str):
        self.model_path = model_path
        self.vocab_path = vocab_path
        self.scaler_path = scaler_path
        self.num_features = 258
        
        logger.info("Cargando modelo...")
        
        try: 
            self.model = tf.keras.models.load_model(self.model_path, compile=False)
            logger.info(f"Modelo cargado correctamente")    
        except Exception as e:
            logger.error(f"Error al cargar modelo: {e}")
            raise
    
        logger.info("Cargando scaler...")
        try: 
            self.scaler = joblib.load(self.scaler_path)
            logger.info("Scaler cargado ")
        except Exception as e: 
            logger.error(f"Error al cargar el scaler: {e}")
            raise
        
        logger.info("Cargando vocabulario...")
        try:
            with open(self.vocab_path, "r", encoding="utf-8") as f:
                vocab_raw = json.load(f)
                
            #Convertir claves a enteros: 
            self.vocab = {int(k): v for k, v in vocab_raw.items()}
            self.classes = [self.vocab[i] for i in sorted(self.vocab.keys())]
            
            logger.info(f"Vocabulario: {len(self.classes)} clases")
            logger.info(f"Formato esperado: (1, 30, 258)")
        except Exception as e: 
            logger.error(f"Error cargando vocabulario {e}")
            raise
    
    def predict(self, sequence_array: np.ndarray):
        """
        Predice la seña a partir de una secuencia de 30 frames.
        
        Args:
            sequence_array: Array de shape (1, 30, 258) con:
                - Pose: 132 features
                - Left Hand: 63 features  
                - Right Hand: 63 features
        
        Returns:
            (label, confidence): Tupla con predicción y confianza
        """
        if sequence_array is None:
            logger.warning("Secuencia es None")
            return "ERROR", 0.0
        
        expected_shape = (1, 30, self.num_features)
        if sequence_array.shape != expected_shape:
            logger.warning(
                f"Shape incorrecta: {sequence_array.shape}, "
                f"esperada {expected_shape}"
            )
            return "ERROR_SHAPE", 0.0
        
        try: 
            #Escalar cada frame individual
            seq_scaled = []
            
            for frame in sequence_array[0]:
                frame_scaled = self.scaler.transform(frame.reshape(1, -1))[0]
                seq_scaled.append(frame_scaled)
            
            #Reconstruir la secuencia escalada
            seq_scaled = np.array(seq_scaled, dtype=np.float32)
            seq_scaled = np.expand_dims(seq_scaled, axis=0) 
            
            #Prediccion
            preds = self.model.predict(seq_scaled, verbose=0)
            
            class_id = int(np.argmax(preds[0]))
            confidence = int(np.max(preds[0]))
            
            #Validar class_id
            if class_id >= len(self.classes):
                logger.error(
                    f"class_id {class_id} fuera de rango "
                    f"(vocab: {len(self.classes)} clases)"
                )
                return "ERROR_CLASS_ID", 0.0
            
            label = self.classes[class_id]
            
            logger.debug(f"Predicción: {label} ({confidence:.2%})")
            
            return label, confidence
        except Exception as e: 
            logger.error(f"Error en la prediccion: {e}", exc_info=True)
            return "ERROR_PREDICCION", 0.0