import os
import sys
import json
import time
import subprocess
import asyncio
import redis.asyncio as aioredis

# Add parent directory to path to import app settings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import settings

async def admin_terminal():
    print("=== VSM Admin Terminal ===")
    print("Connecting to Redis...")
    
    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        channel = f"{settings.redis_channel_prefix}.updates"
        print(f"Connected. Target channel: {channel}")
    except Exception as e:
        print(f"Error connecting to Redis: {e}")
        return

    while True:
        try:
            cmd_input = await asyncio.get_event_loop().run_in_executor(None, input, "admin> ")
            parts = cmd_input.split()
            if not parts: continue
            
            cmd_name = parts[0].lower()
            
            if cmd_name == "worth":
                if len(parts) >= 3:
                    symbol = parts[1].upper()
                    try:
                        price = float(parts[2])
                        # We send a special broadcast message that the main server will listen to
                        # Wait, we need the main server to actually handle this.
                        # Since I can't easily change the running engine object from here,
                        # I'll send a 'control' message that the backend listener will act upon.
                        payload = {
                            "type": "admin_control",
                            "payload": {
                                "action": "set_worth",
                                "symbol": symbol,
                                "price": price
                            }
                        }
                        await r.publish(channel, json.dumps({"room": "__broadcast__", "payload": payload}))
                        print(f"Sent request to set {symbol} to {price}")
                    except ValueError:
                        print("Invalid price format.")
                else:
                    print("Usage: worth <SYMBOL> <PRICE>")
            
            elif cmd_name == "sys":
                sys_cmd = " ".join(parts[1:])
                print(f"Executing: {sys_cmd}")
                try:
                    result = subprocess.run(sys_cmd, shell=True, capture_output=True, text=True, timeout=10)
                    if result.stdout: print(result.stdout)
                    if result.stderr: print(result.stderr)
                except Exception as e:
                    print(f"Execution error: {e}")
            
            elif cmd_name == "help":
                print("Available commands:")
                print("  worth <SYM> <PRICE> - Change stock price live")
                print("  sys <CMD>           - Run system command")
                print("  exit                - Close terminal")
            
            elif cmd_name in ["exit", "quit"]:
                break
            
            else:
                print(f"Unknown command: {cmd_name}")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Terminal error: {e}")

    await r.close()
    print("Terminal closed.")

if __name__ == "__main__":
    asyncio.run(admin_terminal())
