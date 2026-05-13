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
        # Simulation dt scaled for 1-second real-time ticks
        # We simulate 1 hour of market time per real-time second to make moves visible
        self._dt: float = settings.simulation_tick_interval / (252 * 24)

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

        # Count active "small players" (users with low balance)
        # For simplicity in this demo, we check the database for active user count
        # and balance distribution if we wanted to be precise, but here we 
        # simulate the "small player" effect based on an external economy factor.
        # We'll use a fixed threshold or logic for this simulation.
        
        for symbol, state in self._assets.items():
            mu_eff = state.mu
            sigma_eff = state.sigma

            # Exclusive "WAEL" stock behavior: Always goes up, high mu, low sigma
            if symbol == "WAEL":
                mu_eff = max(mu_eff, 0.5) # Very aggressive growth
                sigma_eff = 0.05 # Very stable

            for effect in self._effects.get(symbol, []):
                if effect.decay == "exponential":
                    decay_factor = effect.remaining_ticks / max(effect.remaining_ticks, 1)
                else:
                    decay_factor = 1.0
                mu_eff += effect.drift_modifier * decay_factor
                sigma_eff *= 1.0 + (effect.volatility_modifier - 1.0) * decay_factor
                effect.remaining_ticks -= 1

            # Mean reversion to base price (the 'not too random' part)
            # Gently pulls the price back toward the base if it drifts too far
            reversion_strength = 0.05 
            mu_eff += reversion_strength * (state.base_price - state.price) / state.base_price

            self._effects[symbol] = [
                e for e in self._effects.get(symbol, []) if e.remaining_ticks > 0
            ]

            # Clip noise to avoid extreme outlier spikes
            z = np.clip(self._rng.standard_normal(), -3.0, 3.0)
            
            # For WAEL, we force z to be mostly positive or just ensure mu dominates
            if symbol == "WAEL" and z < -1.0:
                z = abs(z) * 0.1 # Dampen downward spikes for WAEL

            drift = (mu_eff - 0.5 * sigma_eff ** 2) * self._dt
            diffusion = sigma_eff * np.sqrt(self._dt) * z
            new_price = float(state.price * np.exp(drift + diffusion))
            
            # Small player effect: If the price is low and players are "small",
            # it tends to stay at 0.01 - 0.05 unless high volume kicks in.
            # Here we implement the floor logic requested.
            if symbol != "WAEL":
                # Simulated "small player" downward pressure
                if new_price < 1.0:
                    new_price = max(new_price, 0.01)
                    if self._rng.random() < 0.1: # 10% chance to drop to floor if already low
                        new_price = self._rng.choice([0.01, 0.05])
            else:
                new_price = max(new_price, 1000.0) # WAEL floor is high

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
