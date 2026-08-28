from typing import Optional, Any, Union, Tuple
import re
import discord
from utils.emojis import get_all_emojis
from .text_utils import slugify

def parse_emoji_config(text_value: str) -> Tuple[list[dict[str, Any]], int]:
    """Parses a text block into a list of option dicts.
    Format: Emoji | Label | List | Limit | Flags
    Returns (new_opts, positive_count)
    """
    new_opts = []
    positive_count = 0
    lines = text_value.strip().split("\n")
    color_map = {"G": "success", "R": "danger", "B": "primary", "Y": "secondary"}
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2: 
            raise ValueError(f"Line {i}: Too few columns (need at least Emoji | Label)")
        
        emoji = parts[0]
        btn_label = parts[1]
        list_label = parts[2] if len(parts) > 2 and parts[2] else btn_label
        oid = slugify(btn_label)
        
        limit = 0
        if len(parts) > 3:
            try:
                limit = int(parts[3])
            except (ValueError, TypeError):
                limit = 0
            
        flags = parts[4].upper() if len(parts) > 4 else "SPB"
        show_in_list = "S" in flags
        is_positive = "P" in flags
        if is_positive:
            positive_count += 1
        
        style = "emoji" if "E" in flags else ("label" if "T" in flags else "both")
        btn_color = "secondary"
        for code, name in color_map.items():
            if code in flags:
                btn_color = name
                break
            
        new_opts.append({
            "id": oid, "emoji": emoji, "label": btn_label, "list_label": list_label,
            "max_slots": limit, "button_style": style, "button_color": btn_color,
            "show_in_list": show_in_list, "positive": is_positive
        })
        
    return new_opts, positive_count

def resolve_placeholders(text: Optional[str]) -> str:
    """Replaces all {PLACEHOLDERS} in a string with their centralized registry values."""
    if text is None:
        return ""
    text_str = str(text)
    if not text_str or "{" not in text_str:
        return text_str
    
    try:
        registry = get_all_emojis()
        
        def replace(match: re.Match) -> str:
            key = match.group(1).upper()
            return registry.get(key, match.group(0))
        
        return re.sub(r"\{([a-zA-Z0-9\_]+)\}", replace, text_str)
    except Exception:
        return text_str

def split_emoji(label: Optional[str]) -> Tuple[Optional[Union[discord.PartialEmoji, str]], str]:
    """Splits a leading custom or unicode emoji from a string label."""
    if label is None:
        return None, ""
    label_str = str(label)
    
    emoji_obj = None
    m = re.match(r'^(<a?:[a-zA-Z0-9_]+:[0-9]+>)\s*', label_str)
    if m:
        raw = m.group(1)
        clean_label = label_str[m.end():]
        try:
            emoji_obj = discord.PartialEmoji.from_str(raw)
        except Exception:
            pass
        return emoji_obj, clean_label

    um = re.match(r'^([\U00002600-\U0001FFFF]+)\s*', label_str)
    if um:
        emoji_obj = um.group(1)
        clean_label = label_str[um.end():]
        return emoji_obj, clean_label

    return None, label_str

def make_select_option(label: str, **kwargs) -> discord.SelectOption:
    """Create a discord.SelectOption, auto-extracting any leading custom emoji
    from *label* into the separate ``emoji`` kwarg so Discord renders it
    properly (SelectOption.label is plain-text only).
    """
    emoji_obj = kwargs.pop("emoji", None)
    m = re.match(r'^(<a?:[a-zA-Z0-9_]+:[0-9]+>)\s*', label)
    if m and not emoji_obj:
        raw = m.group(1)
        label = label[m.end():]
        try:
            emoji_obj = discord.PartialEmoji.from_str(raw)
        except Exception:
            pass

    if not emoji_obj and not m:
        um = re.match(r'^([\U00002600-\U0001FFFF]+)\s*', label)
        if um:
            emoji_obj = um.group(1)
            label = label[um.end():]

    return discord.SelectOption(label=label[:100], emoji=emoji_obj, **kwargs)

def make_button(label: Optional[str], **kwargs) -> discord.ui.Button:
    """Create a discord.ui.Button, auto-extracting any leading custom or standard 
    emoji from *label* into the separate ``emoji`` kwarg so Discord renders it
    properly (Button.label is plain-text only).
    """
    label_str = str(label) if label is not None else ""
    emoji_obj, clean_label = split_emoji(label_str)
    
    # If explicitly provided an emoji, let it override the extracted one
    final_emoji = kwargs.pop("emoji", emoji_obj)
    return discord.ui.Button(label=clean_label[:80], emoji=final_emoji, **kwargs)

def to_emoji(emoji_str: Optional[str]) -> Optional[Union[discord.PartialEmoji, str]]:
    """Converts a string to a discord.PartialEmoji if it matches custom emoji format, 
    resolves {PLACEHOLDERS} from the registry, otherwise returns original."""
    if not emoji_str:
        return None
    s = str(emoji_str).strip()

    # Dynamic Placeholder Resolution
    if s.startswith("{") and s.endswith("}"):
        try:
            registry = get_all_emojis()
            key = s[1:-1].upper()
            if key in registry:
                s = registry[key]
        except Exception:
            pass

    # Check for Discord custom emoji format: <:name:id> or <a:name:id>
    if re.match(r'^<(a?):[a-zA-Z0-9\_]+:[0-9]+>$', s):
        try:
            return discord.PartialEmoji.from_str(s)
        except Exception:
            return s
    return s
