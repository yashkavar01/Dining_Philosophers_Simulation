"""
Shared enums and dataclasses used across the simulation engine.

Keeping these in one place means the API layer, the philosopher threads,
and the event logger all agree on the same vocabulary of states and event
types -- there is exactly one definition of "what EATING means" anywhere
in this codebase.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PhilosopherState(Enum):
    THINKING = "THINKING"
    HUNGRY = "HUNGRY"
    WAITING = "WAITING"
    EATING = "EATING"
    STOPPED = "STOPPED"   # terminal state after a reset/stop, for a brief moment


class StrategyName(Enum):
    NAIVE = "naive"
    ORDERED = "ordered"
    WAITER = "waiter"


class EventType(Enum):
    STATE_CHANGE = "STATE_CHANGE"
    FORK_REQUEST = "FORK_REQUEST"
    FORK_ACQUIRED = "FORK_ACQUIRED"
    FORK_RELEASED = "FORK_RELEASED"
    BLOCKED = "BLOCKED"
    EATING_STARTED = "EATING_STARTED"
    EATING_DONE = "EATING_DONE"
    DEADLOCK_DETECTED = "DEADLOCK_DETECTED"
    DEADLOCK_CLEARED = "DEADLOCK_CLEARED"
    STRATEGY_CHANGED = "STRATEGY_CHANGED"
    SIMULATION_RESET = "SIMULATION_RESET"
    SIMULATION_STARTED = "SIMULATION_STARTED"
    SIMULATION_PAUSED = "SIMULATION_PAUSED"
    SIMULATION_RESUMED = "SIMULATION_RESUMED"


@dataclass
class Event:
    id: int
    timestamp: float                       # seconds since the current run started
    philosopher_id: Optional[int]
    event_type: str
    message: str
    data: dict = field(default_factory=dict)
