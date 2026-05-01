"""
Extracts biomechanical gait features from sequences of pose landmarks.

Feature vector breakdown (74 dimensions total):
  - 4 joint angle signals × 8 stats     = 32
  - 3 distance/width signals × 8 stats  = 24
  - 2 gait cycle features               =  2
  - 2 signals × 6 FFT harmonics         = 12
  - 2 symmetry indices                  =  2
  - 2 normalized body proportion ratios =  2
"""
import numpy as np
from typing import List, Optional
from scipy.stats import skew, kurtosis

from src.pose_estimator import LandmarkIndex as LM

FEATURE_SIZE = 74


class GaitFeatureExtractor:
    MIN_FRAMES = 30

    @staticmethod
    def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        """Angle at b formed by a–b–c (in degrees), using 2D x,y only."""
        ba = a[:2] - b[:2]
        bc = c[:2] - b[:2]
        n = np.linalg.norm(ba) * np.linalg.norm(bc)
        if n < 1e-6:
            return 0.0
        cos = np.clip(np.dot(ba, bc) / n, -1.0, 1.0)
        return float(np.degrees(np.arccos(cos)))

    @staticmethod
    def _dist(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.linalg.norm(a[:2] - b[:2]))

    @staticmethod
    def _stats(sig: np.ndarray) -> List[float]:
        if len(sig) == 0:
            return [0.0] * 8
        return [
            float(np.mean(sig)),
            float(np.std(sig)),
            float(np.min(sig)),
            float(np.max(sig)),
            float(np.ptp(sig)),
            float(skew(sig)) if len(sig) > 2 else 0.0,
            float(kurtosis(sig)) if len(sig) > 3 else 0.0,
            float(np.median(sig)),
        ]

    @staticmethod
    def _clean(sig: np.ndarray) -> np.ndarray:
        """Replace NaN by linear interpolation; fallback to zeros."""
        s = np.array(sig, dtype=np.float64)
        nans = np.isnan(s)
        if np.all(nans):
            return np.zeros(len(s))
        idx = np.arange(len(s))
        s[nans] = np.interp(idx[nans], idx[~nans], s[~nans])
        return s

    def extract(self, landmark_sequence: List[np.ndarray]) -> Optional[np.ndarray]:
        """
        Build a 74-dimensional feature vector from a pose landmark sequence.

        Args:
            landmark_sequence: list of (33, 4) arrays [x, y, z, visibility]

        Returns:
            np.ndarray of shape (74,), or None if sequence is too short.
        """
        if len(landmark_sequence) < self.MIN_FRAMES:
            return None

        lms = np.array(landmark_sequence, dtype=np.float32)  # (T, 33, 4)
        T = len(lms)

        left_knee_a, right_knee_a = [], []
        left_hip_a, right_hip_a = [], []
        hip_w, ankle_w, shoulder_w = [], [], []
        hip_h = []

        for t in range(T):
            lm = lms[t]
            v = lm[:, 3]

            def vis(*idxs):
                return all(v[i] > 0.4 for i in idxs)

            # Left knee: hip-knee-ankle
            if vis(LM.LEFT_HIP, LM.LEFT_KNEE, LM.LEFT_ANKLE):
                left_knee_a.append(self._angle(lm[LM.LEFT_HIP], lm[LM.LEFT_KNEE], lm[LM.LEFT_ANKLE]))
            else:
                left_knee_a.append(np.nan)

            # Right knee
            if vis(LM.RIGHT_HIP, LM.RIGHT_KNEE, LM.RIGHT_ANKLE):
                right_knee_a.append(self._angle(lm[LM.RIGHT_HIP], lm[LM.RIGHT_KNEE], lm[LM.RIGHT_ANKLE]))
            else:
                right_knee_a.append(np.nan)

            # Left hip: shoulder-hip-knee
            if vis(LM.LEFT_SHOULDER, LM.LEFT_HIP, LM.LEFT_KNEE):
                left_hip_a.append(self._angle(lm[LM.LEFT_SHOULDER], lm[LM.LEFT_HIP], lm[LM.LEFT_KNEE]))
            else:
                left_hip_a.append(np.nan)

            # Right hip
            if vis(LM.RIGHT_SHOULDER, LM.RIGHT_HIP, LM.RIGHT_KNEE):
                right_hip_a.append(self._angle(lm[LM.RIGHT_SHOULDER], lm[LM.RIGHT_HIP], lm[LM.RIGHT_KNEE]))
            else:
                right_hip_a.append(np.nan)

            # Width features
            if vis(LM.LEFT_HIP, LM.RIGHT_HIP):
                hip_w.append(self._dist(lm[LM.LEFT_HIP], lm[LM.RIGHT_HIP]))
                hip_h.append((lm[LM.LEFT_HIP][1] + lm[LM.RIGHT_HIP][1]) / 2.0)
            else:
                hip_w.append(np.nan)
                hip_h.append(np.nan)

            if vis(LM.LEFT_ANKLE, LM.RIGHT_ANKLE):
                ankle_w.append(self._dist(lm[LM.LEFT_ANKLE], lm[LM.RIGHT_ANKLE]))
            else:
                ankle_w.append(np.nan)

            if vis(LM.LEFT_SHOULDER, LM.RIGHT_SHOULDER):
                shoulder_w.append(self._dist(lm[LM.LEFT_SHOULDER], lm[LM.RIGHT_SHOULDER]))
            else:
                shoulder_w.append(np.nan)

        # Clean all signals
        lka = self._clean(left_knee_a)
        rka = self._clean(right_knee_a)
        lha = self._clean(left_hip_a)
        rha = self._clean(right_hip_a)
        hw = self._clean(hip_w)
        aw = self._clean(ankle_w)
        sw = self._clean(shoulder_w)
        hh = self._clean(hip_h)

        features = []

        # === 1. Statistical features of joint angles (32) ===
        for sig in [lka, rka, lha, rha]:
            features.extend(self._stats(sig))

        # === 2. Statistical features of width signals (24) ===
        for sig in [hw, aw, sw]:
            features.extend(self._stats(sig))

        # === 3. Gait cycle features via hip height FFT (2) ===
        hh_centered = hh - np.mean(hh)
        fft_mag = np.abs(np.fft.rfft(hh_centered))
        fft_freq = np.fft.rfftfreq(len(hh_centered))
        if len(fft_mag) > 1:
            dom_idx = np.argmax(fft_mag[1:]) + 1
            dom_freq = float(fft_freq[dom_idx])
            freq_ratio = float(fft_mag[dom_idx] / (np.sum(fft_mag[1:]) + 1e-8))
        else:
            dom_freq, freq_ratio = 0.0, 0.0
        features.extend([dom_freq, freq_ratio])

        # === 4. FFT harmonics of knee angles (12) ===
        for sig in [lka, rka]:
            sig_c = sig - np.mean(sig)
            fm = np.abs(np.fft.rfft(sig_c))
            fm = fm / (np.sum(fm) + 1e-8)
            harmonics = fm[1:7]  # 6 harmonics
            harmonics = np.pad(harmonics, (0, max(0, 6 - len(harmonics))))
            features.extend(harmonics.tolist())

        # === 5. Symmetry indices (2) ===
        features.append(float(np.mean(np.abs(lka - rka))))
        features.append(float(np.mean(np.abs(lha - rha))))

        # === 6. Normalized body proportions (2) ===
        mean_sw = float(np.nanmean(sw)) + 1e-8
        features.append(float(np.nanmean(hw)) / mean_sw)
        features.append(float(np.nanmean(aw)) / mean_sw)

        result = np.array(features, dtype=np.float32)

        # Safety: ensure exactly FEATURE_SIZE dimensions
        if len(result) < FEATURE_SIZE:
            result = np.pad(result, (0, FEATURE_SIZE - len(result)))
        else:
            result = result[:FEATURE_SIZE]

        return result
