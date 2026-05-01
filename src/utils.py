"""Shared utilities for the Gait Recognition system."""
import cv2
import numpy as np
from typing import Optional


def open_camera(index: int = 0) -> Optional[cv2.VideoCapture]:
    """Open camera, returning None if unavailable."""
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(index)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        return cap
    return None


def frame_to_photoimage(frame: np.ndarray, width: int = 640, height: int = 480):
    """Convert a BGR numpy frame to a Tkinter PhotoImage."""
    from PIL import Image, ImageTk
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb)
    img = img.resize((width, height), Image.LANCZOS)
    return ImageTk.PhotoImage(img)


def placeholder_frame(width: int = 640, height: int = 480, text: str = "No Camera") -> np.ndarray:
    """Create a dark placeholder frame with centered text."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (20, 20, 35)
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size = cv2.getTextSize(text, font, 1.0, 2)[0]
    x = (width - text_size[0]) // 2
    y = (height + text_size[1]) // 2
    cv2.putText(frame, text, (x, y), font, 1.0, (100, 100, 150), 2, cv2.LINE_AA)
    return frame


def draw_recording_indicator(frame: np.ndarray, frame_num: int) -> np.ndarray:
    """Draw a pulsing REC indicator on the top-right of the frame."""
    h, w = frame.shape[:2]
    if (frame_num // 15) % 2 == 0:
        cv2.circle(frame, (w - 30, 25), 10, (0, 0, 220), -1)
        cv2.putText(frame, "REC", (w - 75, 32), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 0, 220), 2, cv2.LINE_AA)
    return frame


def check_dependencies() -> dict:
    """Check which required packages are available."""
    status = {}
    try:
        import cv2
        status["opencv"] = cv2.__version__
    except ImportError:
        status["opencv"] = None
    try:
        import mediapipe as mp
        status["mediapipe"] = mp.__version__
    except ImportError:
        status["mediapipe"] = None
    try:
        import sklearn
        status["scikit-learn"] = sklearn.__version__
    except ImportError:
        status["scikit-learn"] = None
    try:
        import numpy as np
        status["numpy"] = np.__version__
    except ImportError:
        status["numpy"] = None
    try:
        import scipy
        status["scipy"] = scipy.__version__
    except ImportError:
        status["scipy"] = None
    try:
        from PIL import Image
        import PIL
        status["Pillow"] = PIL.__version__
    except ImportError:
        status["Pillow"] = None
    return status
