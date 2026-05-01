"""SVM-based gait recognition with confidence scoring."""
import numpy as np
import pickle
import os
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score
from typing import Optional, Tuple, List, Dict


UNKNOWN = "Unknown"


class GaitRecognizer:
    def __init__(self, model_dir: str = "models", confidence_threshold: float = 0.60):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        self.model_path = os.path.join(model_dir, "gait_model.pkl")

        self.pipeline: Optional[Pipeline] = None
        self.label_names: Dict[int, str] = {}
        self.is_trained: bool = False
        self.confidence_threshold: float = confidence_threshold
        self.cv_accuracy: float = 0.0
        self.n_classes: int = 0

        self._load_model()

    def _build_pipeline(self) -> Pipeline:
        clf = SVC(
            kernel="rbf",
            C=10.0,
            gamma="scale",
            probability=True,
            class_weight="balanced",
        )
        return Pipeline([("scaler", StandardScaler()), ("svc", clf)])

    def train(
        self,
        features: List[np.ndarray],
        labels: List[int],
        label_names: Dict[int, str],
    ) -> Tuple[bool, str]:
        """
        Train the recognizer. Returns (success, message).
        Requires at least 2 enrolled users.
        """
        if len(features) < 4:
            return False, "Need at least 4 gait samples total to train."

        X = np.array(features, dtype=np.float32)
        y = np.array(labels, dtype=np.int64)

        unique, counts = np.unique(y, return_counts=True)
        if len(unique) < 2:
            self.label_names = label_names
            return False, "Need at least 2 enrolled users to train the classifier."

        # Warn if any class has very few samples
        min_samples = int(np.min(counts))

        self.label_names = label_names
        self.n_classes = len(unique)
        self.pipeline = self._build_pipeline()
        self.pipeline.fit(X, y)
        self.is_trained = True

        # Cross-validation (only if enough samples)
        cv_folds = min(5, min_samples)
        if cv_folds >= 2:
            scores = cross_val_score(self._build_pipeline(), X, y, cv=cv_folds, scoring="accuracy")
            self.cv_accuracy = float(np.mean(scores))
        else:
            self.cv_accuracy = 0.0

        self._save_model()
        msg = (
            f"Trained on {len(features)} samples, {self.n_classes} users. "
            f"CV accuracy: {self.cv_accuracy*100:.1f}%" if cv_folds >= 2
            else f"Trained on {len(features)} samples, {self.n_classes} users."
        )
        return True, msg

    def predict(self, feature_vector: np.ndarray) -> Tuple[str, float]:
        """
        Predict identity from a feature vector.
        Returns (name, confidence). Name is UNKNOWN if below threshold.
        """
        if not self.is_trained or self.pipeline is None:
            return UNKNOWN, 0.0

        try:
            X = feature_vector.reshape(1, -1)
            proba = self.pipeline.predict_proba(X)[0]
            best_idx = int(np.argmax(proba))
            confidence = float(proba[best_idx])
            pred_label = int(self.pipeline.classes_[best_idx])

            if confidence >= self.confidence_threshold:
                name = self.label_names.get(pred_label, f"User {pred_label}")
                return name, confidence
            return UNKNOWN, confidence
        except Exception:
            return UNKNOWN, 0.0

    def get_all_probabilities(self, feature_vector: np.ndarray) -> Dict[str, float]:
        """Return confidence scores for all enrolled users."""
        if not self.is_trained or self.pipeline is None:
            return {}
        try:
            X = feature_vector.reshape(1, -1)
            proba = self.pipeline.predict_proba(X)[0]
            result = {}
            for idx, p in enumerate(proba):
                label = int(self.pipeline.classes_[idx])
                name = self.label_names.get(label, f"User {label}")
                result[name] = float(p)
            return dict(sorted(result.items(), key=lambda x: -x[1]))
        except Exception:
            return {}

    def set_threshold(self, threshold: float):
        self.confidence_threshold = max(0.1, min(0.99, threshold))
        self._save_model()

    def _save_model(self):
        data = {
            "pipeline": self.pipeline,
            "label_names": self.label_names,
            "confidence_threshold": self.confidence_threshold,
            "is_trained": self.is_trained,
            "cv_accuracy": self.cv_accuracy,
            "n_classes": self.n_classes,
        }
        with open(self.model_path, "wb") as f:
            pickle.dump(data, f)

    def _load_model(self):
        if not os.path.exists(self.model_path):
            return
        try:
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
            self.pipeline = data.get("pipeline")
            self.label_names = data.get("label_names", {})
            self.confidence_threshold = data.get("confidence_threshold", 0.60)
            self.is_trained = data.get("is_trained", False)
            self.cv_accuracy = data.get("cv_accuracy", 0.0)
            self.n_classes = data.get("n_classes", 0)
        except Exception:
            pass

    def reset(self):
        """Clear trained model."""
        self.pipeline = None
        self.label_names = {}
        self.is_trained = False
        self.cv_accuracy = 0.0
        self.n_classes = 0
        if os.path.exists(self.model_path):
            os.remove(self.model_path)
