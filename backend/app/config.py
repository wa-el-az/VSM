from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "VirtualStockMarket"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    hmac_secret_key: str = "CHANGE_ME"
    jwt_secret_key: str = "CHANGE_ME"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440

    database_url: str = "sqlite:///./data/market.db"

    redis_url: str = "redis://localhost:6379/0"
    redis_channel_prefix: str = "market"

    simulation_tick_interval: float = 1.0
    simulation_seed: int = 42

    initial_player_balance: float = 10_000.0

    tax_buy_rate: float = 0.005
    tax_sell_rate: float = 0.005
    tax_limit_rate: float = 0.003
    tax_transfer_rate: float = 0.02
    tax_withdrawal_rate: float = 0.01
    scr_target: float = 0.95
    scr_floor: float = 0.90
    scr_adjustment_step: float = 0.001

    task_tier1_reward_min: int = 50
    task_tier1_reward_max: int = 100
    task_tier1_cooldown: int = 30
    task_tier2_reward_min: int = 200
    task_tier2_reward_max: int = 500
    task_tier2_cooldown: int = 60
    task_tier3_reward_min: int = 1000
    task_tier3_reward_max: int = 2500
    task_tier3_cooldown: int = 300
    task_expiration_seconds: int = 120

    model_config = {
        "env_file": [
            "config/.env",
            "../config/.env",
            ".env"
        ],
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }


settings = Settings()
