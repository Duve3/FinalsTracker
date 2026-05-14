import re
from typing import Optional
from ..log_config import get_logger

log = get_logger(__name__)


class MatchData:
    def __init__(self):
        self.kills: int = 0
        self.deaths: int = 0
        self.assists: int = 0
        self.combat_score: int = 0
        self.support_score: int = 0
        self.objective_score: int = 0
        self.revives: int = 0
        self.team_cash: int = 0
        self.round: int = 1
        self.round_timer_sec: int = 0
        self.team_rounds_won: int = 0
        self.team_rounds_lost: int = 0

    def to_dict(self) -> dict:
        return {
            "kills": self.kills,
            "deaths": self.deaths,
            "assists": self.assists,
            "combat_score": self.combat_score,
            "support_score": self.support_score,
            "objective_score": self.objective_score,
            "revives": self.revives,
            "team_cash": self.team_cash,
            "round": self.round,
            "round_timer_sec": self.round_timer_sec,
            "team_rounds_won": self.team_rounds_won,
            "team_rounds_lost": self.team_rounds_lost,
        }

    def from_dict(self, data: dict):
        for k, v in data.items():
            if hasattr(self, k):
                setattr(self, k, v)


class ScoreboardEntry:
    def __init__(self, name: str = "", kills: int = 0, deaths: int = 0,
                 assists: int = 0, combat_score: int = 0,
                 support_score: int = 0, objective_score: int = 0,
                 revives: int = 0):
        self.name = name
        self.kills = kills
        self.deaths = deaths
        self.assists = assists
        self.combat_score = combat_score
        self.support_score = support_score
        self.objective_score = objective_score
        self.revives = revives

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kills": self.kills,
            "deaths": self.deaths,
            "assists": self.assists,
            "combat_score": self.combat_score,
            "support_score": self.support_score,
            "objective_score": self.objective_score,
            "revives": self.revives,
        }


def parse_cash_text(text: str) -> Optional[int]:
    cleaned = re.sub(r'[^0-9]', '', text)
    if cleaned:
        try:
            val = int(cleaned)
            return val
        except ValueError:
            log.warning("Failed to parse cash from '%s' (cleaned: '%s')", text, cleaned)
            return None
    log.debug("parse_cash_text: no digits found in '%s'", text)
    return None


def parse_timer_text(text: str) -> Optional[int]:
    match = re.search(r'(\d+):(\d+)', text)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        total = minutes * 60 + seconds
        log.debug("parse_timer_text '%s' -> %ds", text, total)
        return total
    log.debug("parse_timer_text: no timer pattern in '%s'", text)
    return None


def parse_scoreboard_line(text: str) -> Optional[ScoreboardEntry]:
    parts = text.split()
    if len(parts) < 4:
        log.debug("parse_scoreboard_line: too few parts (%d): '%s'", len(parts), text)
        return None
    name_parts = []
    numbers = []
    for p in parts:
        if re.match(r'^\d+$', p):
            numbers.append(int(p))
        else:
            name_parts.append(p)
    if not numbers:
        log.debug("parse_scoreboard_line: no numbers found in '%s'", text)
        return None
    entry = ScoreboardEntry()
    entry.name = ' '.join(name_parts)
    if len(numbers) >= 1:
        entry.kills = numbers[0]
    if len(numbers) >= 2:
        entry.deaths = numbers[1]
    if len(numbers) >= 3:
        entry.assists = numbers[2]
    log.debug("parse_scoreboard_line -> name='%s' k=%d d=%d a=%d",
              entry.name, entry.kills, entry.deaths, entry.assists)
    return entry


def parse_summary_result(text: str) -> Optional[str]:
    lower = text.lower().strip()
    if "victory" in lower or "win" in lower or "1st" in lower:
        log.debug("parse_summary_result '%s' -> win", lower)
        return "win"
    if "defeat" in lower or "loss" in lower or "eliminated" in lower:
        log.debug("parse_summary_result '%s' -> loss", lower)
        return "loss"
    log.debug("parse_summary_result '%s' -> unknown", lower)
    return None
