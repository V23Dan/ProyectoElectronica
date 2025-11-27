"""
Script para convertir el modelo Keras a TensorFlow Lite
TFLite es mucho más rápido en CPU (~3-5x)
"""

from pathlib import Path
import tensorflow as tf
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def convert_model_to_tflite(
    keras_model_path: str, tflite_output_path: str, quantize: bool = True
):
    """
    Convierte modelo Keras a TFLite con optimizaciones.

    Args:
        keras_model_path: Ruta al modelo .keras
        tflite_output_path: Ruta de salida .tflite
        quantize: Si True, aplica cuantización INT8 (más rápido, menor precisión)
    """
    logger.info(f"📥 Cargando modelo: {keras_model_path}")
    model = tf.keras.models.load_model(keras_model_path)

    # Crear convertidor
    converter = tf.lite.TFLiteConverter.from_keras_model(model)

    # Optimizaciones
    converter.optimizations = [tf.lite.Optimize.DEFAULT]

    if quantize:
        logger.info("🔧 Aplicando cuantización INT8...")

        # Dataset representativo para cuantización
        def representative_dataset():
            for _ in range(100):
                # Generar datos dummy con la forma correcta
                yield [np.random.randn(1, 30, 258).astype(np.float32)]

        converter.representative_dataset = representative_dataset
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8, tf.lite.OpsSet.SELECT_TF_OPS]
        converter.inference_input_type = tf.float32
        converter.inference_output_type = tf.float32
    else:
        converter.target_spec.supported_ops = [
            tf.lite.OpsSet.TFLITE_BUILTINS,   # Usar ops FP32
            tf.lite.OpsSet.SELECT_TF_OPS      # Pero permitir ops de TF
        ]
    # Convertir
    logger.info("⚙️  Convirtiendo modelo...")
    tflite_model = converter.convert()

    # Guardar
    with open(tflite_output_path, "wb") as f:
        f.write(tflite_model)

    logger.info(f"✅ Modelo TFLite guardado: {tflite_output_path}")

    # Comparar tamaños
    import os

    original_size = os.path.getsize(keras_model_path) / (1024 * 1024)
    tflite_size = os.path.getsize(tflite_output_path) / (1024 * 1024)

    logger.info(f"📊 Tamaño original: {original_size:.2f} MB")
    logger.info(f"📊 Tamaño TFLite: {tflite_size:.2f} MB")
    logger.info(f"📊 Reducción: {(1 - tflite_size/original_size) * 100:.1f}%")


def benchmark_model(tflite_path: str, num_runs: int = 100):
    """Benchmark del modelo TFLite"""
    import time

    logger.info(f"\n🏃 Benchmarking modelo: {tflite_path}")

    # Cargar intérprete
    interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    # Datos de prueba
    test_input = np.random.randn(1, 30, 258).astype(np.float32)

    # Warmup
    for _ in range(10):
        interpreter.set_tensor(input_details[0]["index"], test_input)
        interpreter.invoke()

    # Benchmark
    times = []
    for _ in range(num_runs):
        start = time.perf_counter()
        interpreter.set_tensor(input_details[0]["index"], test_input)
        interpreter.invoke()
        times.append(time.perf_counter() - start)

    avg_time = np.mean(times) * 1000  # ms
    std_time = np.std(times) * 1000
    fps = 1000 / avg_time

    logger.info(f"⏱️  Tiempo promedio: {avg_time:.2f} ± {std_time:.2f} ms")
    logger.info(f"📊 FPS estimado: {fps:.1f}")
    logger.info(f"📊 Min: {min(times)*1000:.2f} ms | Max: {max(times)*1000:.2f} ms")


if __name__ == "__main__":
    # Rutas
    BASE_DIR = Path(__file__).resolve().parent
    KERAS_MODEL = BASE_DIR / "model" / "best_hybrid_model.keras"
    TFLITE_OUTPUT = BASE_DIR / "model" / "best_hybrid_model.tflite"
    TFLITE_QUANTIZED = BASE_DIR / "model" / "best_hybrid_model_int8.tflite"

    # Convertir sin cuantización
    logger.info("\n" + "=" * 70)
    logger.info("CONVERSIÓN SIN CUANTIZACIÓN (FP32)")
    logger.info("=" * 70)
    convert_model_to_tflite(KERAS_MODEL, TFLITE_OUTPUT, quantize=False)
    benchmark_model(TFLITE_OUTPUT)

    # Convertir con cuantización INT8
    logger.info("\n" + "=" * 70)
    logger.info("CONVERSIÓN CON CUANTIZACIÓN (INT8)")
    logger.info("=" * 70)
    convert_model_to_tflite(KERAS_MODEL, TFLITE_QUANTIZED, quantize=True)
    benchmark_model(TFLITE_QUANTIZED)

    logger.info("\n✅ Conversión completada")
    logger.info("📝 Usa el modelo INT8 para mejor rendimiento en CPU")
