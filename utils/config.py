import os
from typing import Any, Optional, List
from utils.jsonc import load_jsonc
from utils.logger import log

class Config:
    def __init__(self):
        self._data = {}
        self.load()

    def load(self):
        config_path = os.path.join(os.getcwd(), 'config.json')
        if os.path.exists(config_path):
            try:
                self._data = load_jsonc(config_path)
                log.info("Config loaded successfully from config.json.")
            except Exception as e:
                log.error("Failed to load config.json: %s", e)
                self._data = {}
        else:
            log.warning("config.json not found. Copy config.example.json to config.json or configure via environment variables.")
            self._data = {}

    @property
    def premium_guild_ids(self) -> List[int]:
        # Environment variable override (comma-separated IDs)
        env_val = os.getenv("PREMIUM_GUILD_IDS")
        if env_val:
            return [int(x.strip()) for x in env_val.split(",") if x.strip().isdigit()]

        ids = self._data.get("premium_guild_ids", [])
        if not ids and "guild_id" in self._data:
            ids = [self._data["guild_id"]]
        return [int(gid) for gid in ids]

    @property
    def master_guild_ids(self) -> List[int]:
        # Environment variable override (comma-separated IDs)
        env_val = os.getenv("MASTER_GUILD_IDS")
        if env_val:
            return [int(x.strip()) for x in env_val.split(",") if x.strip().isdigit()]

        ids = self._data.get("master_guild_ids", [])
        if not ids and "guild_id" in self._data:
            ids = [self._data["guild_id"]]
        return [int(gid) for gid in ids]

    @property
    def language(self) -> str:
        return os.getenv("BOT_LANGUAGE") or self._data.get("language", "en")

    @property
    def command_suffix(self) -> str:
        return self._data.get("command_suffix", "")

    @property
    def command_prefix(self) -> str:
        return os.getenv("COMMAND_PREFIX") or self._data.get("command_prefix", "!")

    @property
    def version(self) -> str:
        return self._data.get("globals", {}).get("version", "v2.2.0")

    @property
    def wizard_timeout(self) -> int:
        return self._data.get("globals", {}).get("wizard_timeout", 600)

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self._data.get(key, default)

# Global singleton config instance
config = Config()
