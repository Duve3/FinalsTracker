import sqlite3
import json
import os
from typing import Optional
from ..log_config import get_logger

log = get_logger(__name__)


class MatchDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                result TEXT,
                mode TEXT DEFAULT 'unknown',
                duration_sec REAL DEFAULT 0,
                kills INTEGER DEFAULT 0,
                deaths INTEGER DEFAULT 0,
                assists INTEGER DEFAULT 0,
                combat_score INTEGER DEFAULT 0,
                support_score INTEGER DEFAULT 0,
                objective_score INTEGER DEFAULT 0,
                revives INTEGER DEFAULT 0,
                team_cash INTEGER DEFAULT 0,
                rounds_won INTEGER DEFAULT 0,
                rounds_lost INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    def insert_match(self, match_data: dict) -> int:
        self.conn.execute("""
            INSERT INTO matches (timestamp, result, mode, duration_sec,
                kills, deaths, assists, combat_score, support_score,
                objective_score, revives, team_cash, rounds_won, rounds_lost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            match_data.get("timestamp", 0),
            match_data.get("result"),
            match_data.get("mode", "unknown"),
            match_data.get("duration_sec", 0),
            match_data.get("kills", 0),
            match_data.get("deaths", 0),
            match_data.get("assists", 0),
            match_data.get("combat_score", 0),
            match_data.get("support_score", 0),
            match_data.get("objective_score", 0),
            match_data.get("revives", 0),
            match_data.get("team_cash", 0),
            match_data.get("team_rounds_won", 0),
            match_data.get("team_rounds_lost", 0),
        ))
        self.conn.commit()
        row_id = self.conn.lastrowid
        log.debug("Inserted match record id=%d (result=%s, k=%d/d=%d)",
                   row_id, match_data.get("result"),
                   match_data.get("kills", 0), match_data.get("deaths", 0))
        return row_id

    def get_recent_matches(self, limit: int = 20) -> list[dict]:
        cursor = self.conn.execute("""
            SELECT * FROM matches ORDER BY id DESC LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def get_stats(self) -> dict:
        cursor = self.conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN result='loss' THEN 1 ELSE 0 END) as losses,
                   AVG(kills) as avg_kills,
                   AVG(deaths) as avg_deaths,
                   AVG(combat_score) as avg_combat,
                   AVG(support_score) as avg_support,
                   AVG(objective_score) as avg_objective
            FROM matches
        """)
        row = cursor.fetchone()
        if row:
            return {
                "total_matches": row[0] or 0,
                "wins": row[1] or 0,
                "losses": row[2] or 0,
                "avg_kills": round(row[3] or 0, 1),
                "avg_deaths": round(row[4] or 0, 1),
                "avg_combat_score": round(row[5] or 0, 0),
                "avg_support_score": round(row[6] or 0, 0),
                "avg_objective_score": round(row[7] or 0, 0),
            }
        return {}

    def close(self):
        log.info("Closing database connection: %s", self.db_path)
        self.conn.close()
