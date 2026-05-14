import time
from typing import Optional
from ..game.parser import MatchData
from ..log_config import get_logger

log = get_logger(__name__)


class MatchRecord:
    def __init__(self):
        self.timestamp: float = time.time()
        self.result: Optional[str] = None
        self.data = MatchData()
        self.mode: str = "unknown"
        self.duration_sec: float = 0.0

    def to_dict(self) -> dict:
        d = self.data.to_dict()
        d.update({
            "timestamp": self.timestamp,
            "result": self.result,
            "mode": self.mode,
            "duration_sec": self.duration_sec,
        })
        return d


class SessionTracker:
    def __init__(self):
        self.session_start: float = time.time()
        self.current_match: Optional[MatchRecord] = None
        self.matches: list[MatchRecord] = []

    def start_match(self):
        self.current_match = MatchRecord()
        self.current_match.timestamp = time.time()
        log.info("New match started (#%d)", len(self.matches) + 1)

    def update_match(self, data: MatchData):
        if self.current_match:
            self.current_match.data = data

    def update_scoreboard(self, entries):
        if self.current_match:
            self.current_match.data.kills = sum(e.kills for e in entries if e.kills)
            self.current_match.data.deaths = sum(e.deaths for e in entries if e.deaths)
            self.current_match.data.assists = sum(e.assists for e in entries if e.assists)

    def end_match(self, result: Optional[str] = None):
        if self.current_match:
            self.current_match.result = result
            self.current_match.duration_sec = time.time() - self.current_match.timestamp
            self.matches.append(self.current_match)
            log.info("Match ended: result=%s, kills=%d, deaths=%d, duration=%.0fs",
                      result, self.current_match.data.kills,
                      self.current_match.data.deaths, self.current_match.duration_sec)
            self.current_match = None

    def get_session_summary(self) -> dict:
        if not self.matches:
            return {"matches_played": 0}
        wins = sum(1 for m in self.matches if m.result == "win")
        losses = sum(1 for m in self.matches if m.result == "loss")
        total_kills = sum(m.data.kills for m in self.matches)
        total_deaths = sum(m.data.deaths for m in self.matches)
        total_assists = sum(m.data.assists for m in self.matches)
        avg_combat = sum(m.data.combat_score for m in self.matches) / len(self.matches)
        avg_support = sum(m.data.support_score for m in self.matches) / len(self.matches)
        avg_objective = sum(m.data.objective_score for m in self.matches) / len(self.matches)
        duration_h = (time.time() - self.session_start) / 3600
        return {
            "matches_played": len(self.matches),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / len(self.matches) * 100, 1) if self.matches else 0,
            "total_kills": total_kills,
            "total_deaths": total_deaths,
            "total_assists": total_assists,
            "avg_kills": round(total_kills / len(self.matches), 1),
            "avg_deaths": round(total_deaths / len(self.matches), 1),
            "avg_assists": round(total_assists / len(self.matches), 1),
            "avg_combat_score": round(avg_combat, 0),
            "avg_support_score": round(avg_support, 0),
            "avg_objective_score": round(avg_objective, 0),
            "session_duration_h": round(duration_h, 2),
        }

    def get_recent_matches(self, count: int = 10) -> list[dict]:
        return [m.to_dict() for m in self.matches[-count:]]
