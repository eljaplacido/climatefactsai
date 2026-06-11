"""
Text processing utilities for ClimateNews platform.

Provides text cleaning, markdown stripping, and formatting functions.
"""

import re
from typing import Optional


def strip_markdown(text: Optional[str]) -> str:
    """
    Strip markdown formatting from text, leaving clean readable text.

    Removes:
    - Headers (# ## ###)
    - Bold (**text** or __text__)
    - Italic (*text* or _text_)
    - Code blocks (```code```)
    - Inline code (`code`)
    - Links ([text](url))
    - Images (![alt](url))
    - Horizontal rules (---, ***)
    - Blockquotes (> text)
    - Lists (- item, * item, 1. item)

    Args:
        text: Text that may contain markdown formatting

    Returns:
        Clean text without markdown syntax

    Examples:
        >>> strip_markdown("**Bold** and *italic*")
        'Bold and italic'

        >>> strip_markdown("## Heading\\nNormal text")
        'Heading\\nNormal text'

        >>> strip_markdown("[Link](http://example.com)")
        'Link'
    """
    if not text:
        return ""

    # Remove code blocks (```code```)
    text = re.sub(r'```[\s\S]*?```', '', text)

    # Remove inline code (`code`)
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # Remove images (![alt](url))
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)

    # Remove links, keep text ([text](url))
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Remove headers (# ## ###)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Remove bold (**text** or __text__)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)

    # Remove italic (*text* or _text_)
    # More careful regex to avoid matching mid-word underscores
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'\b_([^_]+)_\b', r'\1', text)

    # Remove horizontal rules
    text = re.sub(r'^(-{3,}|\*{3,}|_{3,})$', '', text, flags=re.MULTILINE)

    # Remove blockquotes (> text)
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

    # Remove unordered list markers (- item, * item)
    text = re.sub(r'^[\*\-]\s+', '', text, flags=re.MULTILINE)

    # Remove ordered list markers (1. item)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)

    # Clean up multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Clean up multiple spaces
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length, adding suffix if truncated.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: String to append if truncated (default "...")

    Returns:
        Truncated text

    Examples:
        >>> truncate_text("This is a long text", 10)
        'This is...'

        >>> truncate_text("Short", 10)
        'Short'
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def clean_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.

    - Removes leading/trailing whitespace
    - Converts multiple spaces to single space
    - Normalizes line breaks

    Args:
        text: Text to clean

    Returns:
        Cleaned text
    """
    # Replace tabs with spaces
    text = text.replace('\t', ' ')

    # Replace multiple spaces with single space
    text = re.sub(r' {2,}', ' ', text)

    # Normalize line breaks (handle Windows/Unix)
    text = text.replace('\r\n', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]

    return '\n'.join(lines).strip()


def extract_excerpt(text: str, max_length: int = 300, prefer_first_paragraph: bool = True) -> str:
    """
    Extract excerpt from article text.

    Args:
        text: Full article text
        max_length: Maximum excerpt length
        prefer_first_paragraph: If True, try to extract first paragraph

    Returns:
        Excerpt text
    """
    if not text:
        return ""

    # Clean text first
    text = clean_whitespace(strip_markdown(text))

    # When the caller asks for the first paragraph, isolate it BEFORE the
    # length check (2026-06-11 audit). The old code returned the whole text
    # whenever it fit under max_length, so a short multi-paragraph article
    # leaked its second paragraph into the "first paragraph" excerpt.
    if prefer_first_paragraph:
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if paragraphs:
            first = paragraphs[0]
            return first if len(first) <= max_length else truncate_text(first, max_length)

    if len(text) <= max_length:
        return text

    # Truncate to max length
    return truncate_text(text, max_length)
