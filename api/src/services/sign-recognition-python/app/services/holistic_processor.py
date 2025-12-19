import mediapipe as mp
import numpy as np
import cv2
import logging

logger = logging.getLogger(__name__)


class HolisticProcessor:
    def __init__(
        self,
        detection_conf: float = 0.5, 
        tracking_conf: float = 0.5, 
        model_complexity: int = 1,
    ):

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

            rgb_frame.flags.writeable = True

            landmarks_vector = self._extract_keypoints(results)

            return landmarks_vector, results

        except Exception as e:
            logger.error(f"Error procesando frame: {e}")
            return None, None

    def _extract_keypoints(self, results) -> np.ndarray:
        try:

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
                pose = np.zeros(132, dtype=np.float32)

            if results.left_hand_landmarks:
                left_hand = np.array(
                    [[lm.x, lm.y, lm.z] for lm in results.left_hand_landmarks.landmark]
                ).flatten()

                if left_hand.shape[0] != 63:
                    logger.warning(
                        f"Left hand shape incorrecta: {left_hand.shape[0]}, esperada 63"
                    )
                    left_hand = np.zeros(63, dtype=np.float32)
            else:
                left_hand = np.zeros(63, dtype=np.float32)

            if results.right_hand_landmarks:
                right_hand = np.array(
                    [[lm.x, lm.y, lm.z] for lm in results.right_hand_landmarks.landmark]
                ).flatten()

                if right_hand.shape[0] != 63:
                    logger.warning(
                        f"Right hand shape incorrecta: {right_hand.shape[0]}, esperada 63"
                    )
                    right_hand = np.zeros(63, dtype=np.float32)
            else:
                right_hand = np.zeros(63, dtype=np.float32)

            keypoints = np.concatenate([pose, left_hand, right_hand])

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
        if results is None:
            return frame

        annotated = frame.copy()

        try:
            if results.pose_landmarks:
                self.mp_drawing.draw_landmarks(
                    annotated,
                    results.pose_landmarks,
                    self.mp_holistic.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style(),
                )

            if results.left_hand_landmarks:
                self.mp_drawing.draw_landmarks(
                    annotated,
                    results.left_hand_landmarks,
                    self.mp_holistic.HAND_CONNECTIONS,
                    self.mp_drawing_styles.get_default_hand_landmarks_style(),
                    self.mp_drawing_styles.get_default_hand_connections_style(),
                )

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
        if results is None:
            return False

        return (
            results.left_hand_landmarks is not None
            or results.right_hand_landmarks is not None
        )

    def has_pose(self, results) -> bool:
        if results is None:
            return False

        return results.pose_landmarks is not None

    def get_detection_info(self, results) -> dict:
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

        if info["pose"]:
            info["total_landmarks"] += 33
        if info["left_hand"]:
            info["total_landmarks"] += 21
        if info["right_hand"]:
            info["total_landmarks"] += 21

        return info

    def close(self):
        try:
            if hasattr(self, "holistic"):
                self.holistic.close()
            logger.info("HolisticProcessor cerrado correctamente")
        except Exception as e:
            logger.error(f"Error cerrando HolisticProcessor: {e}")