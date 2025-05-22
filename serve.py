from app import CoreApp
import toml

with open("/app/config.toml", "r") as f:
    config = toml.load(f)

CoreApp(config).startService()