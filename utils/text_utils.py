import re
import unicodedata
from typing import Any

def slugify(text: Any, separator: str = "_") -> str:
    """
    Converts text to a safe lowercase ASCII slug, removing accents and non-alphanumeric characters,
    joining words with the specified separator ('_' by default, or '-').
    """
    if text is None:
        return ""

    # 1. Normalize to NFKD to separate accents from base characters
    text_str = unicodedata.normalize('NFKD', str(text))

    # 2. Encode to ASCII and ignore characters that can't be converted (accents)
    text_str = text_str.encode('ascii', 'ignore').decode('ascii')

    # 3. Lowercase and strip whitespace
    text_str = text_str.lower().strip()

    # 4. Replace non-alphanumeric character sequences with the separator
    text_str = re.sub(r'[^a-z0-9]+', separator, text_str)

    # 5. Remove leading and trailing separators
    return text_str.strip(separator)


def safe_format(template_str: Any, **kwargs: Any) -> str:
    """
    Safely substitutes placeholders in a template string (e.g. {title}, {user_id}) with provided kwargs.
    - Prevents KeyError when unknown or missing keys are present (keeps unknown placeholders intact).
    - Prevents ValueError on unescaped single braces or malformed syntax.
    - Prevents Python object introspection attacks (e.g. {title.__class__} is not matched or evaluated).
    """
    if template_str is None:
        return ""
    if not isinstance(template_str, str):
        template_str = str(template_str)

    if not template_str or not kwargs:
        return template_str

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        if key in kwargs:
            val = kwargs[key]
            return str(val) if val is not None else ""
        return match.group(0)

    # Matches only alphanumeric identifier keys: {identifier_name}
    return re.sub(r"\{([a-zA-Z0-9_]+)\}", _replace, template_str)
