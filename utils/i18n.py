from typing import Optional, Any
import json
import os
import re
import database

from utils.config import config
from utils.emojis import get_all_emojis
from utils.cache import guild_cache
from utils.text_utils import safe_format

# Cache emojis globally to avoid redundant function calls
GLOBAL_EMOJIS = get_all_emojis()

# Default fallback language from config
DEFAULT_LANG = config.language


# Load all available language files
ALL_MESSAGES = {} # {"hu": {...}, "en": {...}}
LOCALES_DIR = "locales"

if os.path.exists(LOCALES_DIR):
    for filename in os.listdir(LOCALES_DIR):
        if filename.endswith(".json"):
            # Extract lang_code (first part before any dot or underscore)
            # e.g., 'en.json' -> 'en', 'en.templates.json' -> 'en', 'hu_main.json' -> 'hu'
            lang_code = re.split(r'[\._]', filename)[0]
            
            try:
                with open(os.path.join(LOCALES_DIR, filename), "r", encoding="utf-8") as f:
                    new_messages = json.load(f)
                    if lang_code not in ALL_MESSAGES:
                        ALL_MESSAGES[lang_code] = {}
                    ALL_MESSAGES[lang_code].update(new_messages)
            except Exception as e:
                print(f"Error loading {filename}: {e}")

GUILD_CACHE: dict[str, Any] = {}  # In-memory backwards-compatible cache interface


def invalidate_guild_cache(guild_id: Optional[Any]) -> None:
    """Invalidates cached translation overrides and guild settings for a specific guild."""
    if not guild_id:
        return
    gid_str = str(guild_id)
    guild_cache.delete_sync(gid_str)
    GUILD_CACHE.pop(gid_str, None)


async def load_guild_translations(guild_id: Optional[Any], force_reload: bool = False) -> dict[str, Any]:
    """Fetch overrides and settings from DB and cache them with TTL caching."""
    if not guild_id:
        return {"overrides": {}, "settings": {}, "lang": DEFAULT_LANG}
    gid_str = str(guild_id)

    # 1. Check if already cached and valid
    if not force_reload:
        cached = guild_cache.get_sync(gid_str)
        if cached is not None:
            GUILD_CACHE[gid_str] = cached
            return cached

    # 2. Fetch fresh data from PostgreSQL
    overrides = await database.get_guild_translations(gid_str)
    settings = await database.get_all_guild_settings(gid_str)
    guild_lang = settings.get("language", DEFAULT_LANG)

    data = {
        "overrides": overrides,
        "settings": settings,
        "lang": guild_lang
    }
    guild_cache.set_sync(gid_str, data, ttl=300.0)
    GUILD_CACHE[gid_str] = data
    return data

def t(translation_key: Optional[str], guild_id: Optional[Any] = None, use_template_lang: bool = False, **kwargs) -> str:
    """
    Translates a key with multi-layer priority:
    1. Guild-specific override (DB)
    2. Guild-specific preferred language (JSON)
    3. Global default language (JSON)
    4. The key itself
    """
    if translation_key is None:
        return ""
    
    text = None
    pref_lang = DEFAULT_LANG
    gid_str = str(guild_id) if guild_id else None

    # 1. Check Guild Cache for overrides and preferred language
    if gid_str:
        cache = GUILD_CACHE.get(gid_str)
        if cache is None:
            cached = guild_cache.get_sync(gid_str)
            if cached is not None:
                GUILD_CACHE[gid_str] = cached
                cache = cached

        if cache:
            text = cache.get("overrides", {}).get(translation_key)
            pref_lang = cache.get("lang", DEFAULT_LANG)
            if use_template_lang and "settings" in cache:
                tpl_lang = cache["settings"].get("template_language", "default")
                if tpl_lang != "default":
                    pref_lang = tpl_lang

    # 2. If no override, try the preferred language file
    if text is None:
        lang_dict = ALL_MESSAGES.get(pref_lang, ALL_MESSAGES.get(DEFAULT_LANG, {}))
        text = lang_dict.get(translation_key)

    # 3. Fallback to default language if not found in preferred
    if text is None and pref_lang != DEFAULT_LANG:
        text = ALL_MESSAGES.get(DEFAULT_LANG, {}).get(translation_key)

    # 4. Final fallback to key
    if text is None:
        text = str(translation_key)
    
    # Merge global emojis with provided kwargs
    # Emojis are used for placeholders like {SUCCESS}, {ERROR}, etc.
    formatting_args = {**GLOBAL_EMOJIS, **kwargs}
    return safe_format(text, **formatting_args)


# Essential Templates for the Notification Wizard
CATEGORIES = {
    "Notifications": [
        "MSG_DEFAULT_PROMO",
        "MSG_PROMOTED_DEFAULT",
        "MSG_WAITLIST_HINT",
        "MSG_REM_DESC",
        "MSG_EVENT_CANCELLED",
        "MSG_EVENT_POSTPONED"
    ]
}
