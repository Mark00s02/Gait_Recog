"""MediaPipe-based pose estimation using the Tasks API (mediapipe >= 0.10)."""
import cv2
import numpy as np
import os
import urllib.request
from typing import Optional, Tuple

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODEL_PATH = os.path.join(_ROOT, "models", "pose_landmarker.task")
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)

# Skeleton connections for manual drawing
_CONNECTIONS = [
    (11, 12),                          # shoulders
    (11, 13), (13, 15),                # left arm
    (12, 14), (14, 16),                # right arm
    (11, 23), (12, 24),                # torso sides
    (23, 24),                          # hips
    (23, 25), (25, 27), (27, 29), (27, 31),  # left leg
    (24, 26), (26, 28), (28, 30), (28, 32),  # right leg
    (29, 31), (30, 32),                # feet
]

# Body landmark colors (BGR)
_COLORS = {
    "bone":  (0, 200, 80),
    "joint": (0, 120, 255),
    "face":  (180, 180, 180),
}


class LandmarkIndex:
    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    LEFT_EAR = 7
    RIGHT_EAR = 8
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


def _ensure_model() -> str:
    """Download the pose landmarker model if not already present."""
    os.makedirs(os.path.dirname(_MODEL_PATH), exist_ok=True)
    if not os.path.exists(_MODEL_PATH) or os.path.getsize(_MODEL_PATH) < 1024:
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
    return _MODEL_PATH


class PoseEstimator:
    """
    Estimates 33-point body pose landmarks using MediaPipe Tasks API.
    Works with mediapipe >= 0.10 (Python 3.14 compatible).
    """

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ):
        model_path = _ensure_model()

        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = mp_vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_segmentation_masks=False,
        )
        self._landmarker = mp_vision.PoseLandmarker.create_from_options(options)
        self._timestamp_ms: int = 0

    def process_frame(
        self, frame: np.ndarray
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Process a BGR frame.

        Returns:
            annotated_frame: frame with skeleton drawn
            landmarks: (33, 4) array [x_px, y_px, z_px, visibility], or None
        """
        h, w = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        self._timestamp_ms += 33  # ~30 fps
        result = self._landmarker.detect_for_video(mp_image, self._timestamp_ms)

        annotated = frame.copy()
        landmarks = None

        if result.pose_landmarks and len(result.pose_landmarks) > 0:
            raw = result.pose_landmarks[0]  # first (and only) detected pose

            landmarks = np.array(
                [
                    [
                        lm.x * w,
                        lm.y * h,
                        lm.z * w,
                        float(getattr(lm, "visibility", 1.0)),
                    ]
                    for lm in raw
                ],
                dtype=np.float32,
            )
            annotated = self._draw_skeleton(annotated, landmarks)

        return annotated, landmarks

    def _draw_skeleton(self, frame: np.ndarray, lms: np.ndarray) -> np.ndarray:
        # Connections
        for a, b in _CONNECTIONS:
            if lms[a, 3] > 0.4 and lms[b, 3] > 0.4:
                cv2.line(
                    frame,
                    (int(lms[a, 0]), int(lms[a, 1])),
                    (int(lms[b, 0]), int(lms[b, 1])),
                    _COLORS["bone"], 2, cv2.LINE_AA,
                )
        # Joints
        for i, lm in enumerate(lms):
            if lm[3] > 0.4:
                color = _COLORS["face"] if i <= 10 else _COLORS["joint"]
                cv2.circle(
                    frame, (int(lm[0]), int(lm[1])),
                    4, color, -1, cv2.LINE_AA,
                )
        return frame

    def draw_confidence_overlay(
        self, frame: np.ndarray, name: str, confidence: float
    ) -> np.ndarray:
        """Draw recognition result banner on frame."""
        h, w = frame.shape[:2]
        color = (0, 220, 80) if confidence >= 0.65 else (0, 165, 255)

        cv2.rectangle(frame, (0, 0), (w, 60), (20, 20, 40), -1)
        cv2.putText(frame, name, (15, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, color, 2, cv2.LINE_AA)
        bar_w = int((w - 160) * confidence)
        cv2.rectangle(frame, (130, 18), (130 + bar_w, 44), color, -1)
        cv2.rectangle(frame, (130, 18), (w - 30, 44), (100, 100, 100), 1)
        cv2.putText(frame, f"{confidence*100:.0f}%", (w - 70, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 220, 220), 1, cv2.LINE_AA)
        return frame

    def close(self):
        try:
            self._landmarker.close()
        except Exception:
            pass

    def __del__(self):
        self.close()
