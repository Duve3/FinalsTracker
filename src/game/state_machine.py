import asyncio
import time
from enum import Enum
from typing import Optional, Callable, Any
from ..log_config import get_logger

log = get_logger(__name__)


class GameState(Enum):
    UNKNOWN = "unknown"
    MENU = "menu"
    LOADING = "loading"
    INGAME = "ingame"
    SCOREBOARD = "scoreboard"
    SUMMARY = "summary"


TRANSITIONS = {
    GameState.UNKNOWN:     {GameState.MENU, GameState.LOADING, GameState.INGAME},
    GameState.MENU:        {GameState.LOADING, GameState.INGAME},
    GameState.LOADING:     {GameState.INGAME},
    GameState.INGAME:      {GameState.SCOREBOARD, GameState.SUMMARY, GameState.MENU},
    GameState.SCOREBOARD:  {GameState.INGAME, GameState.SUMMARY},
    GameState.SUMMARY:     {GameState.MENU},
}


class StateMachine:
    def __init__(self):
        self.state: GameState = GameState.UNKNOWN
        self.previous_state: Optional[GameState] = None
        self.state_start_time: float = time.time()
        self._listeners: list[Callable[..., Any]] = []
        self.last_scoreboard_toggle: float = 0
        self.scoreboard_debounce: float = 0.3

    def on_transition(self, callback: Callable[..., Any]):
        self._listeners.append(callback)

    def transition_to(self, new_state: GameState):
        if new_state == self.state:
            return
        if new_state not in TRANSITIONS.get(self.state, set()):
            log.warning("Blocked invalid transition: %s -> %s", self.state.value, new_state.value)
            return
        old = self.state
        self.previous_state = old
        self.state = new_state
        self.state_start_time = time.time()
        log.info("State transition: %s -> %s", old.value, new_state.value)
        for cb in self._listeners:
            result = cb(old, new_state)
            if asyncio.iscoroutine(result):
                asyncio.ensure_future(result)

    def handle_scoreboard_detected(self, visible: bool):
        now = time.time()
        if now - self.last_scoreboard_toggle < self.scoreboard_debounce:
            return
        if visible and self.state == GameState.INGAME:
            log.debug("Scoreboard opened (Tab held)")
            self.last_scoreboard_toggle = now
            self.transition_to(GameState.SCOREBOARD)
        elif not visible and self.state == GameState.SCOREBOARD:
            log.debug("Scoreboard closed (Tab released)")
            self.last_scoreboard_toggle = now
            self.transition_to(GameState.INGAME)

    def time_in_state(self) -> float:
        return time.time() - self.state_start_time

    def is_playing(self) -> bool:
        return self.state in (GameState.INGAME, GameState.SCOREBOARD)

    def reset(self):
        old = self.state
        self.state = GameState.UNKNOWN
        self.previous_state = None
        self.state_start_time = time.time()
        if old != GameState.UNKNOWN:
            log.info("State machine reset: %s -> unknown", old.value)

    def __repr__(self) -> str:
        return f"StateMachine(state={self.state.value}, elapsed={self.time_in_state():.1f}s)"
