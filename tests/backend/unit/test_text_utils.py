"""
Tests for text processing utilities.
"""

import pytest
from app.utils.text import (
    strip_markdown,
    truncate_text,
    clean_whitespace,
    extract_excerpt
)


class TestStripMarkdown:
    """Tests for strip_markdown function."""

    def test_strip_bold(self):
        """Should remove bold formatting."""
        assert strip_markdown("**bold text**") == "bold text"
        assert strip_markdown("__bold text__") == "bold text"

    def test_strip_italic(self):
        """Should remove italic formatting."""
        assert strip_markdown("*italic text*") == "italic text"
        assert strip_markdown("_italic text_") == "italic text"

    def test_strip_headers(self):
        """Should remove header markers."""
        assert strip_markdown("# Heading 1") == "Heading 1"
        assert strip_markdown("## Heading 2") == "Heading 2"
        assert strip_markdown("### Heading 3") == "Heading 3"

    def test_strip_links(self):
        """Should remove link syntax but keep text."""
        assert strip_markdown("[Link text](http://example.com)") == "Link text"

    def test_strip_images(self):
        """Should remove image syntax but keep alt text."""
        assert strip_markdown("![Alt text](image.jpg)") == "Alt text"

    def test_strip_code(self):
        """Should remove code formatting."""
        assert strip_markdown("`inline code`") == "inline code"
        assert strip_markdown("```python\ncode block\n```") == ""

    def test_strip_lists(self):
        """Should remove list markers."""
        assert strip_markdown("- List item") == "List item"
        assert strip_markdown("* List item") == "List item"
        assert strip_markdown("1. List item") == "List item"

    def test_strip_blockquotes(self):
        """Should remove blockquote markers."""
        assert strip_markdown("> Quote text") == "Quote text"

    def test_complex_markdown(self):
        """Should handle complex markdown with multiple formats."""
        text = """
# Main Heading

This is **bold** and *italic* text.

- Item 1
- Item 2

[Link](http://example.com)
"""
        result = strip_markdown(text)
        assert "**" not in result
        assert "*" not in result
        assert "#" not in result
        assert "[" not in result
        assert "]" not in result
        assert "bold" in result
        assert "italic" in result

    def test_preserve_content(self):
        """Should preserve actual content."""
        text = "The Nordic countries have made **substantial progress** in reducing emissions."
        result = strip_markdown(text)
        assert "Nordic countries" in result
        assert "substantial progress" in result
        assert "reducing emissions" in result
        assert "**" not in result

    def test_empty_string(self):
        """Should handle empty string."""
        assert strip_markdown("") == ""
        assert strip_markdown(None) == ""

    def test_no_markdown(self):
        """Should pass through text without markdown."""
        text = "Plain text without any markdown."
        assert strip_markdown(text) == text


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_truncate_long_text(self):
        """Should truncate text longer than max_length."""
        text = "This is a very long text that needs to be truncated."
        result = truncate_text(text, 20)
        assert len(result) == 20
        assert result.endswith("...")

    def test_dont_truncate_short_text(self):
        """Should not truncate text shorter than max_length."""
        text = "Short text"
        result = truncate_text(text, 20)
        assert result == text

    def test_custom_suffix(self):
        """Should use custom suffix."""
        text = "Long text that needs truncation"
        result = truncate_text(text, 15, suffix=" [more]")
        assert result.endswith(" [more]")


class TestCleanWhitespace:
    """Tests for clean_whitespace function."""

    def test_remove_multiple_spaces(self):
        """Should convert multiple spaces to single space."""
        text = "Text  with   multiple    spaces"
        result = clean_whitespace(text)
        assert "  " not in result
        assert result == "Text with multiple spaces"

    def test_normalize_line_breaks(self):
        """Should normalize line breaks."""
        text = "Line 1\n\n\nLine 2"
        result = clean_whitespace(text)
        assert result == "Line 1\n\nLine 2"

    def test_strip_leading_trailing(self):
        """Should remove leading/trailing whitespace."""
        text = "  Text with spaces  \n"
        result = clean_whitespace(text)
        assert not result.startswith(" ")
        assert not result.endswith(" ")


class TestExtractExcerpt:
    """Tests for extract_excerpt function."""

    def test_extract_short_text(self):
        """Should return entire text if shorter than max_length."""
        text = "Short article text."
        result = extract_excerpt(text, max_length=100)
        assert result == text

    def test_extract_first_paragraph(self):
        """Should extract first paragraph when prefer_first_paragraph=True."""
        text = "First paragraph text.\n\nSecond paragraph text."
        result = extract_excerpt(text, max_length=100, prefer_first_paragraph=True)
        assert "First paragraph" in result
        assert "Second paragraph" not in result

    def test_truncate_long_paragraph(self):
        """Should truncate if first paragraph too long."""
        text = "This is a very long first paragraph that exceeds the maximum length limit."
        result = extract_excerpt(text, max_length=30)
        assert len(result) <= 30
        assert result.endswith("...")

    def test_strip_markdown_in_excerpt(self):
        """Should strip markdown from excerpt."""
        text = "**Bold text** in the excerpt."
        result = extract_excerpt(text, max_length=100)
        assert "**" not in result
        assert "Bold text" in result
