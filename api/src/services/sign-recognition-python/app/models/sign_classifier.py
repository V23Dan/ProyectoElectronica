import tensorflow as tf
import numpy as np
import joblib
import json
from pathlib import Path


class SignClassifier:
    def __init__(self, model_path: str, vocab_path: str, scaler_path: str):
        self.model_path = Path(model_path)
        self.vocab_path = Path(vocab_path)
        self.scaler_path = Path(scaler_path)

        print("[INFO] Cargando modelo .keras...")
        self.model = tf.keras.models.load_model(self.model_path, compile=False)
        self.scaler = joblib.load(self.scaler_path)

        with open(self.vocab_path, "r", encoding="utf-8") as f:
            self.vocab = json.load(f)
        self.classes = list(self.vocab.values())

        # Precompilamos la predicción para acelerar tiempo de inferencia
        self.predict_fn = tf.function(self.model.__call__)

        print("[OK] Modelo cargado correctamente.")

    def preprocess(self, landmarks_vector: np.ndarray):
        # Escala los landmarks usando el scaler entrenado
        return self.scaler.transform([landmarks_vector])

    def predict(self, sequence_array: np.ndarray):
        if sequence_array is None or sequence_array.shape[-1] != 126:
            return None, 0.0

        # Escalar cada frame en la secuencia
        seq_scaled = np.array(
            [
                self.scaler.transform(frame.reshape(1, -1))[0]
                for frame in sequence_array[0]
            ]
        )

        seq_scaled = np.expand_dims(seq_scaled, axis=0)

        preds = self.predict_fn(tf.constant(seq_scaled, dtype=tf.float32))
        class_id = int(np.argmax(preds))
        confidence = float(np.max(preds))
        label = self.classes[class_id]
        return label, confidence
