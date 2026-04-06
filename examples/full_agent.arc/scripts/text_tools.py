"""
Text processing utilities for full_agent.
"""


def to_upper(text: str) -> str:
    """Convert text to uppercase."""
    return text.upper()


def to_lower(text: str) -> str:
    """Convert text to lowercase."""
    return text.lower()


def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def reverse_text(text: str) -> str:
    """Reverse the text."""
    return text[::-1]


def get_word_count(text: str) -> dict:
    """Get detailed word count statistics."""
    words = text.split()
    return {
        "word_count": len(words),
        "char_count": len(text),
        "first_word": words[0] if words else "",
        "last_word": words[-1] if words else ""
    }
