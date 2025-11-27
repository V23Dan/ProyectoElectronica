import mediapipe as mp
import numpy as np
import cv2
import logging

logger = logging.getLogger(__name__)


class HolisticProcessor:
    """
    Procesador que captura landmarks holísticos (Pose + Hands) usando MediaPipe.

    Estructura de features (258 total):
    - Pose: 132 features (33 landmarks × 4: x, y, z, visibility)
    - Left Hand: 63 features (21 landmarks × 3: x, y, z)
    - Right Hand: 63 features (21 landmarks × 3: x, y, z)
    """

    def __init__(
        self,
        detection_conf: float = 0.5, 
        tracking_conf: float = 0.5, 
        model_complexity: int = 1,
    ):
        """
        Inicializa el procesador holistic.

        Args:
            detection_conf: Confianza mínima para detección inicial (0.0-1.0)
            tracking_conf: Confianza mínima para tracking continuo (0.0-1.0)
            model_complexity: Complejidad del modelo
                - 0: Lite (más rápido, menos preciso) ← RECOMENDADO para rendimiento
                - 1: Full (balanceado)
                - 2: Heavy (más lento, más preciso)
        """
        self.mp_holistic = mp.solutions.holistic
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        # Inicializar MediaPipe Holistic con configuración optimizada
        self.holistic = self.mp_holistic.Holistic(
            static_image_mode=False,
            model_complexity=model_complexity,
            smooth_landmarks=True,
            enable_segmentation=False,
            refine_face_landmarks=False,
            min_detection_confidence=detection_conf,
            min_tracking_confidence=tracking_conf,
        )

        logger.info(
            f"HolisticProcessor inicializado"
            f"(complexity={model_complexity}, "
            f"det_conf={detection_conf}, "
            f"track_conf={tracking_conf})"
        )

    def process(self, frame: np.ndarray):
        """
        Procesa un frame y extrae landmarks holísticos.

        Args:
            frame: Frame BGR de OpenCV (numpy array)

        Returns:
            tuple: (landmarks_vector, results)
                - landmarks_vector: np.array de 258 features o None si hay error
                - results: Objeto de resultados de MediaPipe (para visualización)
        """
        if frame is None:
            logger.warning("Frame es None")
            return None, None

        try:
            # Convertir BGR (OpenCV) -> RGB (MediaPipe)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Optimización: marcar imagen como no editable durante procesamiento
            rgb_frame.flags.writeable = False

            # Procesar con Holistic
            results = self.holistic.process(rgb_frame)

            # Restaurar flag de escritura
            rgb_frame.flags.writeable = True

            # Extraer landmarks en formato vectorial
            landmarks_vector = self._extract_keypoints(results)

            return landmarks_vector, results

        except Exception as e:
            logger.error(f"Error procesando frame: {e}")
            return None, None

    def _extract_keypoints(self, results) -> np.ndarray:
        """
        Extrae y formatea keypoints en un vector de 258 features.

        Estructura exacta del vector:
        [0:132]   - Pose landmarks (33 × 4)
        [132:195] - Left hand landmarks (21 × 3)
        [195:258] - Right hand landmarks (21 × 3)

        Args:
            results: Resultados de MediaPipe Holistic

        Returns:
            np.array de shape (258,) con dtype float32
        """
        try:
            # 1. POSE LANDMARKS (132 features = 33 landmarks × 4 valores)
            if results.pose_landmarks:
                pose = np.array(
                    [
                        [lm.x, lm.y, lm.z, lm.visibility]
                        for lm in results.pose_landmarks.landmark
                    ]
                ).flatten()

                # Validación
                if pose.shape[0] != 132:
                    logger.warning(
                        f"Pose shape incorrecta: {pose.shape[0]}, esperada 132"
                    )
                    pose = np.zeros(132, dtype=np.float32)
            else:
                # Sin pose detectada -> rellenar con zeros
                pose = np.zeros(132, dtype=np.float32)

            # 2. LEFT HAND LANDMARKS (63 features = 21 landmarks × 3 valores)
            if results.left_hand_landmarks:
                left_hand = np.array(
                    [[lm.x, lm.y, lm.z] for lm in results.left_hand_landmarks.landmark]
                ).flatten()

                # Validación
                if left_hand.shape[0] != 63:
                    logger.warning(
                        f"Left hand shape incorrecta: {left_hand.shape[0]}, esperada 63"
                    )
                    left_hand = np.zeros(63, dtype=np.float32)
            else:
                # Sin mano izquierda detectada
                left_hand = np.zeros(63, dtype=np.float32)

            # 3. RIGHT HAND LANDMARKS (63 features = 21 landmarks × 3 valores)
            if results.right_hand_landmarks:
                right_hand = np.array(
                    [[lm.x, lm.y, lm.z] for lm in results.right_hand_landmarks.landmark]
                ).flatten()

                # Validación
                if right_hand.shape[0] != 63:
                    logger.warning(
                        f"Right hand shape incorrecta: {right_hand.shape[0]}, esperada 63"
                    )
                    right_hand = np.zeros(63, dtype=np.float32)
            else:
                # Sin mano derecha detectada
                right_hand = np.zeros(63, dtype=np.float32)

            # 4. CONCATENAR TODO EN ORDEN
            keypoints = np.concatenate([pose, left_hand, right_hand])

            # Validación final
            if keypoints.shape[0] != 258:
                logger.error(
                    f"Shape final incorrecta: {keypoints.shape[0]}, esperada 258"
                )
                return np.zeros(258, dtype=np.float32)

            return keypoints.astype(np.float32)

        except Exception as e:
            logger.error(f"Error extrayendo keypoints: {e}")
            return np.zeros(258, dtype=np.float32)

    def draw_landmarks(self, frame: np.ndarray, results) -> np.ndarray:
        """
        Dibuja todos los landmarks detectados sobre el frame.

        Args:
            frame: Frame BGR de OpenCV
            results: Resultados de MediaPipe Holistic

        Returns:
            Frame con landmarks dibujados (copia del original)
        """
        if results is None:
            return frame

        # Trabajar sobre una copia para no modificar el original
        annotated = frame.copy()

        try:
            # 1. Dibujar POSE (esqueleto del cuerpo)
            if results.pose_landmarks:
                self.mp_drawing.draw_landmarks(
                    annotated,
                    results.pose_landmarks,
                    self.mp_holistic.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style(),
                )

            # 2. Dibujar MANO IZQUIERDA
            if results.left_hand_landmarks:
                self.mp_drawing.draw_landmarks(
                    annotated,
                    results.left_hand_landmarks,
                    self.mp_holistic.HAND_CONNECTIONS,
                    self.mp_drawing_styles.get_default_hand_landmarks_style(),
                    self.mp_drawing_styles.get_default_hand_connections_style(),
                )

            # 3. Dibujar MANO DERECHA
            if results.right_hand_landmarks:
                self.mp_drawing.draw_landmarks(
                    annotated,
                    results.right_hand_landmarks,
                    self.mp_holistic.HAND_CONNECTIONS,
                    self.mp_drawing_styles.get_default_hand_landmarks_style(),
                    self.mp_drawing_styles.get_default_hand_connections_style(),
                )

        except Exception as e:
            logger.error(f"Error dibujando landmarks: {e}")

        return annotated

    def has_hands(self, results) -> bool:
        """
        Verifica si hay al menos una mano detectada.

        Args:
            results: Resultados de MediaPipe Holistic

        Returns:
            bool: True si hay al menos una mano detectada
        """
        if results is None:
            return False

        return (
            results.left_hand_landmarks is not None
            or results.right_hand_landmarks is not None
        )

    def has_pose(self, results) -> bool:
        """
        Verifica si hay pose detectada.

        Args:
            results: Resultados de MediaPipe Holistic

        Returns:
            bool: True si hay pose detectada
        """
        if results is None:
            return False

        return results.pose_landmarks is not None

    def get_detection_info(self, results) -> dict:
        """
        Obtiene información detallada sobre las detecciones.

        Args:
            results: Resultados de MediaPipe Holistic

        Returns:
            dict con información de detecciones
        """
        if results is None:
            return {
                "pose": False,
                "left_hand": False,
                "right_hand": False,
                "total_landmarks": 0,
            }

        info = {
            "pose": results.pose_landmarks is not None,
            "left_hand": results.left_hand_landmarks is not None,
            "right_hand": results.right_hand_landmarks is not None,
            "total_landmarks": 0,
        }

        # Contar landmarks detectados
        if info["pose"]:
            info["total_landmarks"] += 33
        if info["left_hand"]:
            info["total_landmarks"] += 21
        if info["right_hand"]:
            info["total_landmarks"] += 21

        return info

    def close(self):
        """Libera recursos de MediaPipe"""
        try:
            if hasattr(self, "holistic"):
                self.holistic.close()
            logger.info("HolisticProcessor cerrado correctamente")
        except Exception as e:
            logger.error(f"Error cerrando HolisticProcessor: {e}")
