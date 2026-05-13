from __future__ import annotations

import json
import random
from pathlib import Path

from app.simulation import NewsEffect, engine


class NewsEngine:
    """JSON-driven fat-tail market shock generator."""

    def __init__(self, events_path: str = "data/news_events.json") -> None:
        self._events: list[dict] = []
        self._active_events: list[dict] = []
        path = Path(events_path)
        if path.exists():
            self._events = json.loads(path.read_text(encoding="utf-8"))

    def reload(self, events_path: str = "data/news_events.json") -> None:
        path = Path(events_path)
        if path.exists():
            self._events = json.loads(path.read_text(encoding="utf-8"))

    def roll_events(self) -> list[dict]:
        """Roll RNG for each event. Returns list of triggered events."""
        triggered: list[dict] = []

        for event in self._events:
            if random.random() < event.get("probability", 0):
                triggered.append(event)
                self._active_events.append(event)

                for sector_or_symbol in event.get("affected_sectors", []):
                    prices = engine.get_all_prices()
                    for symbol in prices:
                        effect = NewsEffect(
                            event_id=event["event_id"],
                            drift_modifier=event.get("drift_modifier", 0.0),
                            volatility_modifier=event.get("volatility_modifier", 1.0),
                            remaining_ticks=event.get("duration_ticks", 30),
                            decay=event.get("decay", "exponential"),
                        )
                        engine.apply_news_effect(symbol, effect)

        return triggered

    @property
    def active_events(self) -> list[dict]:
        return list(self._active_events)

    def clear_expired(self) -> None:
        self._active_events = [
            e for e in self._active_events
            if e.get("duration_ticks", 0) > 0
        ]


news_engine = NewsEngine()
