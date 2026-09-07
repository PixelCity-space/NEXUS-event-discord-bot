import os
import tempfile

from utils.jsonc import load_jsonc


def test_load_jsonc_with_comments():
    """Test JSON loading with // line comments."""
    content = """{
        // Global configuration
        "bot_name": "Nexus",
        "debug": true // Inline comment
    }"""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".jsonc") as f:
        f.write(content)
        temp_path = f.name

    try:
        data = load_jsonc(temp_path)
        assert data["bot_name"] == "Nexus"
        assert data["debug"] is True
    finally:
        os.remove(temp_path)

def test_load_jsonc_with_urls():
    """Test that URLs containing // are not truncated as comments."""
    content = """{
        "api_url": "https://example.com/api/v1", // Comment after URL
        "doc_url": "http://discord.gg/test"
    }"""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".jsonc") as f:
        f.write(content)
        temp_path = f.name

    try:
        data = load_jsonc(temp_path)
        assert data["api_url"] == "https://example.com/api/v1"
        assert data["doc_url"] == "http://discord.gg/test"
    finally:
        os.remove(temp_path)

def test_load_jsonc_trailing_commas():
    """Test removing trailing commas before closing braces/brackets."""
    content = """{
        "items": [
            "alpha",
            "beta",
        ],
        "enabled": true,
    }"""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".jsonc") as f:
        f.write(content)
        temp_path = f.name

    try:
        data = load_jsonc(temp_path)
        assert data["items"] == ["alpha", "beta"]
        assert data["enabled"] is True
    finally:
        os.remove(temp_path)
