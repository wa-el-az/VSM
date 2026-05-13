from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from app.config import settings


@dataclass
class AssetState:
    """Live state for a single simulated asset."""
    symbol: str
    price: float
    mu: float
    sigma: float
    base_price: float
    volume: float = 0.0
    tick: int = 0
    ohlc_open: float = 0.0
    ohlc_high: float = 0.0
    ohlc_low: float = float("inf")


@dataclass
class NewsEffect:
    """Active news event modifier on an asset."""
    event_id: str
    drift_modifier: float
    volatility_modifier: float
    remaining_ticks: int
    decay: str = "exponential"


class SimulationEngine:
    """GBM-based asset price simulator with news event overlays.

    Uses the exact log-normal solution (not Euler approximation):
        S_{t+dt} = S_t * exp((mu - sigma^2/2)*dt + sigma*sqrt(dt)*Z)
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = np.random.default_rng(seed or settings.simulation_seed)
        self._assets: dict[str, AssetState] = {}
        self._effects: dict[str, list[NewsEffect]] = {}
        self._dt: float = settings.simulation_tick_interval / 252 / 6.5 / 3600

    def register_asset(
        self,
        symbol: str,
        price: float,
        mu: float,
        sigma: float,
    ) -> None:
        self._assets[symbol] = AssetState(
            symbol=symbol,
            price=price,
            mu=mu,
            sigma=sigma,
            base_price=price,
            ohlc_open=price,
            ohlc_high=price,
            ohlc_low=price,
        )
        self._effects[symbol] = []

    def apply_news_effect(self, symbol: str, effect: NewsEffect) -> None:
        if symbol in self._effects:
            self._effects[symbol].append(effect)

    def tick(self) -> dict[str, dict]:
        """Advance all assets by one time step. Returns price updates."""
        results: dict[str, dict] = {}
        now = time.time()

        for symbol, state in self._assets.items():
            mu_eff = state.mu
            sigma_eff = state.sigma

            for effect in self._effects.get(symbol, []):
                if effect.decay == "exponential":
                    decay_factor = effect.remaining_ticks / max(effect.remaining_ticks, 1)
                else:
                    decay_factor = 1.0
                mu_eff += effect.drift_modifier * decay_factor
                sigma_eff *= 1.0 + (effect.volatility_modifier - 1.0) * decay_factor
                effect.remaining_ticks -= 1

            self._effects[symbol] = [
                e for e in self._effects.get(symbol, []) if e.remaining_ticks > 0
            ]

            z = self._rng.standard_normal()
            drift = (mu_eff - 0.5 * sigma_eff ** 2) * self._dt
            diffusion = sigma_eff * np.sqrt(self._dt) * z
            new_price = float(state.price * np.exp(drift + diffusion))
            new_price = max(new_price, 0.01)

            volume = float(abs(z) * 1000 * (state.base_price / 100))

            state.ohlc_high = max(state.ohlc_high, new_price)
            state.ohlc_low = min(state.ohlc_low, new_price)
            state.volume += volume
            state.price = new_price
            state.tick += 1

            results[symbol] = {
                "symbol": symbol,
                "price": round(new_price, 2),
                "timestamp": now,
                "volume": round(volume, 2),
                "tick": state.tick,
            }

        return results

    def get_ohlc_and_reset(self, symbol: str) -> dict | None:
        """Return current OHLC bar and reset accumulators."""
        state = self._assets.get(symbol)
        if not state:
            return None

        bar = {
            "open": round(state.ohlc_open, 2),
            "high": round(state.ohlc_high, 2),
            "low": round(state.ohlc_low, 2),
            "close": round(state.price, 2),
            "volume": round(state.volume, 2),
            "timestamp": time.time(),
        }

        state.ohlc_open = state.price
        state.ohlc_high = state.price
        state.ohlc_low = state.price
        state.volume = 0.0

        return bar

    def get_price(self, symbol: str) -> float | None:
        state = self._assets.get(symbol)
        return state.price if state else None

    def get_all_prices(self) -> dict[str, float]:
        return {s: round(a.price, 2) for s, a in self._assets.items()}


def simulate_gbm_series(
    s0: float,
    mu: float,
    sigma: float,
    dt: float,
    n_steps: int,
    seed: int | None = None,
) -> np.ndarray:
    """Generate a full GBM price series using exact log-normal solution."""
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n_steps)
    drift = (mu - 0.5 * sigma ** 2) * dt
    diffusion = sigma * np.sqrt(dt) * z
    log_returns = drift + diffusion
    log_prices = np.concatenate([[np.log(s0)], log_returns])
    return np.exp(np.cumsum(log_prices))


engine = SimulationEngine()
