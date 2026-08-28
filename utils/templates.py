from typing import Optional, Any, Dict
import json
import database
from utils.config import config
from utils.logger import log
from utils.emoji_utils import parse_emoji_config

# Canonical Template IDs and their human-readable strings (6-column format)
# Format: Emoji | Label | List Label | Limit | Flags
ICON_SET_TEMPLATES = {
    "standard": {
        "id": "standard",
        "label_key": "TEMP_STANDARD", # "Alap (Igen / Nem)"
        "emoji": "",
        "text": "{TEMP_STD_YES} | I'm coming | Coming | 0 | SPEY\n{TEMP_STD_MAYBE} | Maybe | Not sure | 0 | SEY\n{TEMP_STD_NO} | Not coming | Not coming | 0 | SEY",
        "buttons_per_row": 5,
        "show_mgmt": True
    },
    "mmo": {
        "id": "mmo",
        "label_key": "TEMP_MMO", # "Raid (Tank / Heal / DPS)"
        "emoji": "",
        "text": "{TEMP_MMO_TANK} | Tank | Tanks | 0 | SPEY\n{TEMP_MMO_HEAL} | Heal | Healers | 0 | SPEY\n{TEMP_MMO_DPS} | DPS | DPSes | 0 | SPEY\n{TEMP_MMO_MAYBE} | Maybe | Not sure | 0 | SEY\n{TEMP_MMO_NO} | Not coming | Not coming | 0 | SEY",
        "buttons_per_row": 5,
        "show_mgmt": False
    },
    "survey": {
        "id": "survey",
        "label_key": "TEMP_SURVEY", # "Szavazás (👍 / 👎)"
        "emoji": "",
        "text": "{TEMP_SURVEY_LIKE} | Like | Liked it | 0 | SPEY\n{TEMP_SURVEY_DISLIKE} | Dislike | Disliked it | 0 | SPEY",
        "buttons_per_row": 5,
        "show_mgmt": False
    },
    "teams": {
        "id": "teams",
        "label_key": "SET_TEAMS", # "Csapatok (🅰️, 🅱️, 👀)"
        "emoji": "",
        "text": "{TEMP_TEAM_A} | Team A | Team A | 0 | SPBB\n{TEMP_TEAM_B} | Team B | Team B | 0 | SPBB\n{TEMP_TEAM_SPECTATE} | I'll spectate | Spectators | 0 | SPBB\n{TEMP_TEAM_MAYBE} | Maybe | Unsure | 0 | SBB\n{TEMP_TEAM_NO} | Not coming | Not coming | 0 | SBB",
        "buttons_per_row": 3,
        "show_mgmt": False
    }
}

# In-memory cache for custom icon sets loaded from database
CUSTOM_ICON_SETS: Dict[str, Any] = {}

def get_template_data(template_id: str) -> Optional[dict]:
    """Returns the parsed JSON-ready dict for a given template."""
    tmpl = ICON_SET_TEMPLATES.get(template_id)
    if not tmpl:
        return None
    
    opts, pos_count = parse_emoji_config(tmpl["text"])
    
    KEY_MAP = {
        "i_m_coming": {"label_key": "BTN_ACCEPT", "list_label_key": "RSVP_ACCEPTED"},
        "maybe": {"label_key": "BTN_TENTATIVE", "list_label_key": "RSVP_TENTATIVE"},
        "not_coming": {"label_key": "BTN_DECLINE", "list_label_key": "RSVP_DECLINED"},
        "tank": {"list_label_key": "RSVP_TANK"},
        "heal": {"list_label_key": "RSVP_HEAL"},
        "dps": {"list_label_key": "RSVP_DPS"},
        "team_a": {"list_label_key": "RSVP_TEAM_A"},
        "team_b": {"list_label_key": "RSVP_TEAM_B"},
        "i_ll_spectate": {"list_label_key": "RSVP_SPECTATOR"},
        "like": {"label_key": "BTN_LIKE", "list_label_key": "RSVP_LIKED"},
        "dislike": {"label_key": "BTN_DISLIKE", "list_label_key": "RSVP_DISLIKED"},
    }
    for o in opts:
        km = KEY_MAP.get(o["id"])
        if km:
            if "label_key" in km:
                o["label_key"] = km["label_key"]
            if "list_label_key" in km:
                o["list_label_key"] = km["list_label_key"]

    return {
        "options": opts,
        "positive_count": pos_count,
        "buttons_per_row": tmpl.get("buttons_per_row", 5),
        "show_mgmt": tmpl.get("show_mgmt", True)
    }

def get_event_conf(name: str) -> Optional[dict]:
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
        log.error("Error loading event config: %s", e)
    return None

async def load_custom_sets() -> None:
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
            
        log.info("Loaded %d emoji sets from database.", len(CUSTOM_ICON_SETS))
    except Exception as e:
        log.error("Failed to load custom emoji sets: %s", e)

def get_active_set(key: str) -> dict:
    """Return the icon set config for a given key, checking templates first then DB cache."""
    tmpl_data = get_template_data(key)
    if tmpl_data:
        return tmpl_data
    
    if key in CUSTOM_ICON_SETS:
        return CUSTOM_ICON_SETS[key]
    
    return {"options": []}
