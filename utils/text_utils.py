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
