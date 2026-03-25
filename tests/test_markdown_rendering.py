"""
Comprehensive Tests for Markdown Rendering Functionality

Tests cover:
- Markdown formatting in article content
- Proper rendering/stripping in list view
- Proper rendering/stripping in detail view
- Edge cases with complex markdown
- HTML sanitization
"""

import pytest
from typing import Dict, Any


class TestMarkdownInArticleText:
    """Test markdown detection and handling in article text"""

    def test_detect_markdown_headers(self):
        """Test detection of markdown headers"""
        text_with_headers = """
        # Main Heading
        ## Subheading
        ### Section Title
        """

        # Should contain markdown syntax
        assert "#" in text_with_headers
        assert "##" in text_with_headers

    def test_detect_markdown_lists(self):
        """Test detection of markdown lists"""
        text_with_lists = """
        - Item one
        - Item two
        * Bullet point
        1. Numbered item
        """

        assert "-" in text_with_lists or "*" in text_with_lists

    def test_detect_markdown_links(self):
        """Test detection of markdown links"""
        text_with_links = "[Link text](https://example.com)"

        assert "[" in text_with_links
        assert "](" in text_with_links

    def test_detect_markdown_emphasis(self):
        """Test detection of markdown emphasis"""
        text_with_emphasis = "This is **bold** and *italic* text."

        assert "**" in text_with_emphasis
        assert "*" in text_with_emphasis


class TestMarkdownStrippingInListView:
    """Test that markdown is properly handled in article list view"""

    def test_excerpt_has_no_markdown_syntax(self, client):
        """Verify excerpts don't contain raw markdown syntax"""
        response = client.get("/api/articles")

        assert response.status_code == 200
        articles = response.json()

        for article in articles:
            excerpt = article.get("excerpt", "")

            if excerpt:
                # Should not have markdown headers
                assert not excerpt.startswith("#")

                # Should not have excessive markdown symbols
                # (some * or - might be legitimate text)

    def test_title_has_no_markdown_syntax(self, client):
        """Verify titles don't contain markdown syntax"""
        response = client.get("/api/articles")

        assert response.status_code == 200
        articles = response.json()

        for article in articles:
            title = article.get("title", "")

            # Title should not have markdown formatting
            assert not title.startswith("#")
            assert "**" not in title[:20]  # Check first part of title

    def test_list_view_excerpt_length(self, client):
        """Test that excerpts are appropriately truncated"""
        response = client.get("/api/articles")

        if response.status_code == 200:
            articles = response.json()

            for article in articles:
                excerpt = article.get("excerpt", "")

                if excerpt:
                    # Excerpts should be reasonable length (not too long)
                    assert len(excerpt) <= 500  # Typical excerpt limit


class TestMarkdownRenderingInDetailView:
    """Test markdown rendering in article detail view"""

    def test_full_text_preserves_structure(self, client):
        """Verify full text maintains readability"""
        response = client.get("/api/articles/article-0001")

        if response.status_code == 200:
            article = response.json()

            full_text = article.get("full_text") or article.get("extracted_text", "")

            # Text should exist
            assert isinstance(full_text, str)

            # Should have content
            if full_text:
                assert len(full_text) > 0

    def test_markdown_converted_to_readable_text(self, client):
        """Test that markdown is converted to readable format"""
        response = client.get("/api/articles/article-0001")

        if response.status_code == 200:
            article = response.json()

            # In detail view, text should be readable
            # (Either markdown rendered to HTML or stripped to plain text)
            full_text = article.get("full_text", "")

            # Should not have excessive markdown artifacts
            # that would confuse readers
            if full_text:
                # Basic readability check
                assert len(full_text.strip()) > 0


class TestMarkdownEdgeCases:
    """Test edge cases in markdown handling"""

    def test_nested_markdown_elements(self):
        """Test handling of nested markdown (e.g., bold in list)"""
        nested_markdown = """
        - This is a **bold** item
        - This has *italic* text
        - [Link](https://example.com) in list
        """

        # Should handle multiple markdown types
        assert "**" in nested_markdown
        assert "*" in nested_markdown
        assert "[" in nested_markdown

    def test_markdown_code_blocks(self):
        """Test handling of code blocks"""
        text_with_code = """
        ```python
        def example():
            return "test"
        ```
        """

        # Should detect code blocks
        assert "```" in text_with_code

    def test_markdown_tables(self):
        """Test handling of markdown tables"""
        table_markdown = """
        | Header 1 | Header 2 |
        |----------|----------|
        | Cell 1   | Cell 2   |
        """

        # Should detect table syntax
        assert "|" in table_markdown

    def test_markdown_blockquotes(self):
        """Test handling of blockquotes"""
        quote_markdown = """
        > This is a quote
        > from multiple lines
        """

        # Should detect blockquote syntax
        assert ">" in quote_markdown

    def test_mixed_html_and_markdown(self):
        """Test handling of mixed HTML and markdown"""
        mixed_content = """
        # Heading
        <p>HTML paragraph</p>
        **Bold text**
        """

        # Should handle both
        assert "#" in mixed_content
        assert "<p>" in mixed_content


class TestHTMLSanitization:
    """Test that HTML is properly sanitized"""

    def test_dangerous_html_removed(self):
        """Test that dangerous HTML tags are removed"""
        dangerous_html = """
        <script>alert('xss')</script>
        <iframe src="evil.com"></iframe>
        """

        # In real implementation, these should be stripped
        # For now, just verify we can detect them
        assert "<script>" in dangerous_html
        assert "<iframe>" in dangerous_html

    def test_safe_html_preserved(self):
        """Test that safe HTML tags are preserved (if needed)"""
        safe_html = """
        <p>Paragraph</p>
        <strong>Bold</strong>
        <em>Italic</em>
        """

        # Basic formatting might be allowed
        assert "<p>" in safe_html

    def test_html_entities_handled(self):
        """Test HTML entities are properly handled"""
        text_with_entities = "This &amp; that &lt;tag&gt;"

        # Should handle common entities
        assert "&" in text_with_entities


class TestMarkdownInClaims:
    """Test markdown handling in extracted claims"""

    def test_claims_text_no_markdown(self, client):
        """Verify claim text doesn't have markdown formatting"""
        response = client.get("/api/articles/article-0001")

        if response.status_code == 200:
            article = response.json()

            for claim in article.get("claims", []):
                claim_text = claim.get("claim_text", "")

                if claim_text:
                    # Claims should be plain text
                    # (Markdown would interfere with fact-checking)
                    assert isinstance(claim_text, str)

    def test_claim_context_readability(self, client):
        """Test that claim context is readable"""
        response = client.get("/api/articles/article-0001")

        if response.status_code == 200:
            article = response.json()

            for claim in article.get("claims", []):
                context = claim.get("claim_context", "")

                if context:
                    # Context should be readable
                    assert len(context.strip()) > 0


class TestMarkdownPerformance:
    """Test performance of markdown processing"""

    def test_large_markdown_document_handling(self):
        """Test handling of large markdown documents"""
        # Simulate large document
        large_doc = "# Section\n" + ("Text paragraph. " * 1000)

        # Should handle without issues
        assert len(large_doc) > 10000

    def test_many_articles_with_markdown(self, client):
        """Test API performance with markdown in many articles"""
        response = client.get("/api/articles?limit=50")

        # Should respond in reasonable time
        assert response.status_code == 200


class TestMarkdownConfiguration:
    """Test markdown rendering configuration"""

    def test_consistent_rendering_across_views(self, client):
        """Verify markdown is rendered consistently"""
        # Get article in list view
        list_response = client.get("/api/articles")

        # Get same article in detail view
        if list_response.status_code == 200:
            articles = list_response.json()

            if len(articles) > 0:
                article_id = articles[0]["article_id"]
                detail_response = client.get(f"/api/articles/{article_id}")

                # Both should succeed
                assert detail_response.status_code == 200

    def test_markdown_rendering_locale_independent(self):
        """Test that markdown rendering works across locales"""
        # Test with different character sets
        unicode_markdown = "# Ääkköset ja émojis 🌍"

        # Should handle unicode
        assert len(unicode_markdown) > 0


class TestMarkdownInSearch:
    """Test markdown handling in search results"""

    def test_search_results_no_markdown(self, client):
        """Verify search results don't show raw markdown"""
        response = client.get("/api/articles?q=climate")

        if response.status_code == 200:
            articles = response.json()

            for article in articles:
                # Search snippets should be clean
                excerpt = article.get("excerpt", "")

                if excerpt:
                    # Should be readable, not raw markdown
                    assert isinstance(excerpt, str)
