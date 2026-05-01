#!/usr/bin/env python3
"""
Gait Recognition System
-----------------------
Entry point. Run with: python main.py
"""
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def check_imports():
    """Check critical dependencies before launching GUI."""
    missing = []
    try:
        import cv2
    except ImportError:
        missing.append("opencv-python")
    try:
        import mediapipe
    except ImportError:
        missing.append("mediapipe")
    try:
        import numpy
    except ImportError:
        missing.append("numpy")
    try:
        import sklearn
    except ImportError:
        missing.append("scikit-learn")
    try:
        import scipy
    except ImportError:
        missing.append("scipy")
    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow")
    return missing


def main():
    missing = check_imports()
    if missing:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        pkg_list = "\n  • ".join(missing)
        messagebox.showerror(
            "Missing Dependencies",
            f"The following packages are not installed:\n\n  • {pkg_list}\n\n"
            f"Run setup.bat (Windows) or:\n"
            f"  pip install -r requirements.txt\n\n"
            f"Then restart the application."
        )
        sys.exit(1)

    import tkinter as tk
    from gui.app import GaitRecognitionApp

    root = tk.Tk()
    app = GaitRecognitionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
