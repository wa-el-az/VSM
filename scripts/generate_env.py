import secrets
import os

def generate_key():
    return secrets.token_hex(32)

env_template = """# Application
APP_NAME=VirtualStockMarket
APP_ENV=production
APP_DEBUG=false
APP_HOST=127.0.0.1
APP_PORT=8000

# Security
HMAC_SECRET_KEY={hmac_key}
JWT_SECRET_KEY={jwt_key}
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440

# Database
DATABASE_URL=sqlite:////var/www/stock.wael.work.gd/data/market.db

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_CHANNEL_PREFIX=market

# Simulation
SIMULATION_TICK_INTERVAL=1.0
SIMULATION_SEED=42

# Economics
INITIAL_PLAYER_BALANCE=10000.0
TAX_BUY_RATE=0.005
TAX_SELL_RATE=0.005
TAX_LIMIT_RATE=0.003
TAX_TRANSFER_RATE=0.02
TAX_WITHDRAWAL_RATE=0.01
SCR_TARGET=0.95
SCR_FLOOR=0.90
SCR_ADJUSTMENT_STEP=0.001

# Proof-of-Work Faucets
TASK_TIER1_REWARD_MIN=50
TASK_TIER1_REWARD_MAX=100
TASK_TIER1_COOLDOWN=30
TASK_TIER2_REWARD_MIN=200
TASK_TIER2_REWARD_MAX=500
TASK_TIER2_COOLDOWN=60
TASK_TIER3_REWARD_MIN=1000
TASK_TIER3_REWARD_MAX=2500
TASK_TIER3_COOLDOWN=300
TASK_EXPIRATION_SECONDS=120
"""

def main():
    config_dir = "config"
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    env_path = os.path.join(config_dir, ".env.production")
    
    if os.path.exists(env_path):
        print(f"{env_path} already exists. Skipping generation to avoid overwriting secrets.")
        return

    content = env_template.format(
        hmac_key=generate_key(),
        jwt_key=generate_key()
    )
    
    with open(env_path, "w") as f:
        f.write(content)
    
    print(f"Generated {env_path} with fresh security keys.")

if __name__ == "__main__":
    main()
