"""SQLite database for storing gait profiles and samples."""
import sqlite3
import numpy as np
import os
from typing import List, Tuple, Optional, Dict


class GaitDatabase:
    def __init__(self, db_path: str = "data/gait.db"):
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gait_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    features BLOB NOT NULL,
                    feature_size INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recognition_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    predicted_name TEXT,
                    confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def add_user(self, name: str) -> int:
        with self._get_conn() as conn:
            cursor = conn.execute("INSERT INTO users (name) VALUES (?)", (name,))
            conn.commit()
            return cursor.lastrowid

    def get_or_create_user(self, name: str) -> int:
        with self._get_conn() as conn:
            row = conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
            if row:
                return row[0]
            cursor = conn.execute("INSERT INTO users (name) VALUES (?)", (name,))
            conn.commit()
            return cursor.lastrowid

    def user_exists(self, name: str) -> bool:
        with self._get_conn() as conn:
            row = conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
            return row is not None

    def add_sample(self, user_id: int, features: np.ndarray) -> int:
        feats = features.astype(np.float32)
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO gait_samples (user_id, features, feature_size) VALUES (?, ?, ?)",
                (user_id, feats.tobytes(), len(feats))
            )
            conn.commit()
            return cursor.lastrowid

    def get_all_samples(self) -> Tuple[List[np.ndarray], List[int], Dict[int, str]]:
        features, labels, label_names = [], [], {}
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT gs.features, gs.feature_size, gs.user_id, u.name
                FROM gait_samples gs
                JOIN users u ON gs.user_id = u.id
                ORDER BY gs.user_id
            """).fetchall()
            for feat_bytes, feat_size, user_id, name in rows:
                feat = np.frombuffer(feat_bytes, dtype=np.float32).copy()
                if len(feat) == feat_size:
                    features.append(feat)
                    labels.append(user_id)
                    label_names[user_id] = name
        return features, labels, label_names

    def get_all_users(self) -> List[Tuple[int, str, int, str]]:
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT u.id, u.name, COUNT(gs.id) as sample_count,
                       strftime('%Y-%m-%d %H:%M', u.created_at) as created
                FROM users u
                LEFT JOIN gait_samples gs ON u.id = gs.user_id
                GROUP BY u.id
                ORDER BY u.name
            """).fetchall()
        return rows

    def delete_user(self, user_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()

    def delete_user_samples(self, user_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM gait_samples WHERE user_id = ?", (user_id,))
            conn.commit()

    def get_user_sample_count(self, user_id: int) -> int:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM gait_samples WHERE user_id = ?", (user_id,)
            ).fetchone()
        return row[0] if row else 0

    def log_recognition(self, name: str, confidence: float):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO recognition_log (predicted_name, confidence) VALUES (?, ?)",
                (name, confidence)
            )
            conn.commit()

    def get_recent_recognitions(self, limit: int = 20) -> List[Tuple]:
        with self._get_conn() as conn:
            return conn.execute("""
                SELECT predicted_name, confidence,
                       strftime('%H:%M:%S', created_at) as time
                FROM recognition_log
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

    def get_stats(self) -> Dict:
        with self._get_conn() as conn:
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            sample_count = conn.execute("SELECT COUNT(*) FROM gait_samples").fetchone()[0]
            recog_count = conn.execute("SELECT COUNT(*) FROM recognition_log").fetchone()[0]
        return {
            "users": user_count,
            "samples": sample_count,
            "recognitions": recog_count,
        }
