"""SQLite database for storing gait profiles, samples, and recognition log."""
import sqlite3
import numpy as np
import os
import csv
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
            cols = [row[1] for row in conn.execute("PRAGMA table_info(users)")]
            if "photo" not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN photo BLOB")
                conn.commit()

    # ── Users ─────────────────────────────────────────────────────────────────

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
            return conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone() is not None

    def set_user_photo(self, user_id: int, photo_bytes: bytes):
        with self._get_conn() as conn:
            conn.execute("UPDATE users SET photo = ? WHERE id = ?", (photo_bytes, user_id))
            conn.commit()

    def get_user_photo(self, user_id: int) -> Optional[bytes]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT photo FROM users WHERE id = ?", (user_id,)).fetchone()
            return row[0] if row and row[0] else None

    def get_user_id_by_name(self, name: str) -> Optional[int]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
            return row[0] if row else None

    # ── Samples ───────────────────────────────────────────────────────────────

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

    # ── Recognition log ───────────────────────────────────────────────────────

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

    def get_all_recognitions(self, limit: int = 1000, person: str = None) -> List[Tuple]:
        with self._get_conn() as conn:
            if person and person != "All":
                return conn.execute("""
                    SELECT predicted_name, confidence,
                           strftime('%Y-%m-%d  %H:%M:%S', created_at) as dt
                    FROM recognition_log
                    WHERE predicted_name = ?
                    ORDER BY created_at DESC LIMIT ?
                """, (person, limit)).fetchall()
            return conn.execute("""
                SELECT predicted_name, confidence,
                       strftime('%Y-%m-%d  %H:%M:%S', created_at) as dt
                FROM recognition_log
                ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()

    def get_unique_log_names(self) -> List[str]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT predicted_name FROM recognition_log ORDER BY predicted_name"
            ).fetchall()
        return [r[0] for r in rows]

    def get_log_stats(self) -> Dict:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM recognition_log").fetchone()[0]
            identified = conn.execute(
                "SELECT COUNT(*) FROM recognition_log WHERE predicted_name != 'Unknown'"
            ).fetchone()[0]
            most_row = conn.execute("""
                SELECT predicted_name FROM recognition_log
                WHERE predicted_name != 'Unknown'
                GROUP BY predicted_name ORDER BY COUNT(*) DESC LIMIT 1
            """).fetchone()
            avg_row = conn.execute(
                "SELECT AVG(confidence) FROM recognition_log WHERE predicted_name != 'Unknown'"
            ).fetchone()
        return {
            "total": total,
            "identified": identified,
            "rate": (identified / total * 100) if total > 0 else 0.0,
            "most_freq": most_row[0] if most_row else "—",
            "avg_conf": avg_row[0] if avg_row and avg_row[0] else 0.0,
        }

    def get_user_analytics(self, user_name: str) -> Dict:
        with self._get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM recognition_log WHERE predicted_name = ?", (user_name,)
            ).fetchone()[0]
            avg_conf = conn.execute(
                "SELECT AVG(confidence) FROM recognition_log WHERE predicted_name = ?", (user_name,)
            ).fetchone()[0]
            last_seen = conn.execute(
                "SELECT strftime('%Y-%m-%d %H:%M', MAX(created_at)) FROM recognition_log WHERE predicted_name = ?",
                (user_name,)
            ).fetchone()[0]
        return {
            "total_recognitions": total,
            "avg_confidence": avg_conf or 0.0,
            "last_seen": last_seen or "Never",
        }

    def clear_recognition_log(self):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM recognition_log")
            conn.commit()

    def export_log_csv(self, path: str):
        rows = self.get_all_recognitions(limit=100000)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["DateTime", "Person", "Confidence"])
            for name, conf, dt in rows:
                writer.writerow([dt, name, f"{conf * 100:.1f}%"])

    def get_stats(self) -> Dict:
        with self._get_conn() as conn:
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            sample_count = conn.execute("SELECT COUNT(*) FROM gait_samples").fetchone()[0]
            recog_count = conn.execute("SELECT COUNT(*) FROM recognition_log").fetchone()[0]
        return {"users": user_count, "samples": sample_count, "recognitions": recog_count}
