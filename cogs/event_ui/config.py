import json
import database
from utils.config import config
from utils.logger import log

# In-memory cache for custom icon sets loaded from database
CUSTOM_ICON_SETS = {}

def get_event_conf(name: str):
    """Retrieves merged configuration settings for a given event name or config_name."""
    try:
        events = config.get("events_config", [])
        defaults = config.get("globals", {}).get("event_defaults", {})
        
        for e in events:
            if e.get("config_name") == name or e.get("name") == name:
                merged = defaults.copy()
                merged.update(e)
                return merged
    except Exception as e:
        log.error(f"Error loading event config: {e}")
    return None

async def load_custom_sets():
    """Fetch custom emoji sets from database (Global and Guild-specific)."""
    global CUSTOM_ICON_SETS
    try:
        # 1. Global sets
        global_sets = await database.get_all_global_emoji_sets()
        for s in global_sets:
            data = s["data"]
            if isinstance(data, str):
                data = json.loads(data)
            CUSTOM_ICON_SETS[s["set_id"]] = data
        
        # 2. Guild-specific sets (overwrites global if IDs match)
        db_sets = await database.get_all_custom_emoji_sets()
        for s in db_sets:
            data = s["data"]
            if isinstance(data, str):
                data = json.loads(data)
            CUSTOM_ICON_SETS[s["set_id"]] = data
            
        log.info(f"Loaded {len(CUSTOM_ICON_SETS)} emoji sets from database.")
    except Exception as e:
        log.error(f"Failed to load custom emoji sets: {e}")

def get_active_set(key: str) -> dict:
    """Return the icon set config for a given key, checking templates first then DB cache."""
    from utils.templates import get_template_data
    tmpl_data = get_template_data(key)
    if tmpl_data:
        return tmpl_data
    
    if key in CUSTOM_ICON_SETS:
        return CUSTOM_ICON_SETS[key]
    
    return {"options": []}
