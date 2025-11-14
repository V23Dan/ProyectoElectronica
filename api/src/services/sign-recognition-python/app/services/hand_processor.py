import mediapipe as mp
import numpy as np
import cv2

class HandProcessor:
    def __init__(self, max_hands=2, detection_conf=0.6, tracking_conf=0.6):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=detection_conf,
            min_tracking_confidence=tracking_conf
        )
        self.mp_draw = mp.solutions.drawing_utils

    def process(self, frame):
        # Convierte de BGR (OpenCV) a RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)

        landmarks_vector = None
        if results.multi_hand_landmarks:
            all_landmarks = []
            for hand_landmarks in results.multi_hand_landmarks:
                coords = [(lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark]
                all_landmarks.append(np.array(coords).flatten())

            # Si hay dos manos, concatenamos los vectores
            if len(all_landmarks) == 2:
                landmarks_vector = np.concatenate(all_landmarks)
            else:
                # Si solo hay una mano, rellenamos con ceros para mantener dimensión constante
                single_hand = all_landmarks[0]
                zeros = np.zeros_like(single_hand)
                landmarks_vector = np.concatenate([single_hand, zeros])

        return landmarks_vector, results

    def draw_hands(self, frame, results):
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(
                    frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
        return frame
