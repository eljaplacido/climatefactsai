"""
Test suite for claims_status database migration

Tests verify that the claims_status field is properly added to the articles table
and that status transitions work correctly.
"""

import pytest
from datetime import datetime
from uuid import uuid4
from sqlalchemy import text


class TestClaimsStatusMigration:
    """Test claims_status database migration"""

    def test_claims_status_column_exists(self, postgres_client):
        """Verify that claims_status column was added to articles table"""
        query = """
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'articles'
            AND column_name = 'claims_status'
        """

        result = postgres_client.execute_query(query)

        assert len(result) == 1, "claims_status column should exist"
        assert result[0]['data_type'] == 'character varying', "Should be VARCHAR type"
        assert 'pending' in result[0]['column_default'], "Default should be 'pending'"

    def test_claims_error_message_column_exists(self, postgres_client):
        """Verify that claims_error_message column was added"""
        query = """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'articles'
            AND column_name = 'claims_error_message'
        """

        result = postgres_client.execute_query(query)

        assert len(result) == 1, "claims_error_message column should exist"
        assert result[0]['data_type'] == 'text', "Should be TEXT type"

    def test_claims_processed_at_column_exists(self, postgres_client):
        """Verify that claims_processed_at column was added"""
        query = """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'articles'
            AND column_name = 'claims_processed_at'
        """

        result = postgres_client.execute_query(query)

        assert len(result) == 1, "claims_processed_at column should exist"
        assert 'timestamp' in result[0]['data_type'], "Should be TIMESTAMP type"

    def test_claims_status_index_exists(self, postgres_client):
        """Verify that index on claims_status was created"""
        query = """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'articles'
            AND indexname = 'idx_articles_claims_status'
        """

        result = postgres_client.execute_query(query)

        assert len(result) == 1, "Index on claims_status should exist"

    def test_article_has_claims_available_function_exists(self, postgres_client):
        """Verify that helper function was created"""
        query = """
            SELECT proname, pronargs
            FROM pg_proc
            WHERE proname = 'article_has_claims_available'
        """

        result = postgres_client.execute_query(query)

        assert len(result) == 1, "article_has_claims_available function should exist"
        assert result[0]['pronargs'] == 2, "Function should accept 2 arguments"

    def test_claims_status_valid_values(self, postgres_client):
        """Test that only valid status values are accepted"""
        article_id = str(uuid4())

        # Test valid statuses
        valid_statuses = ['pending', 'processing', 'completed', 'failed']

        for status in valid_statuses:
            insert_query = text("""
                INSERT INTO articles (
                    article_id, url, title, extracted_text,
                    source_name, claims_status
                )
                VALUES (
                    :article_id, :url, :title, :text,
                    :source, :status
                )
            """)

            postgres_client.execute_update(
                str(insert_query),
                {
                    'article_id': str(uuid4()),
                    'url': f'https://example.com/test-{status}',
                    'title': f'Test Article {status}',
                    'text': 'Test content',
                    'source': 'Test Source',
                    'status': status
                }
            )

        # Verify all statuses were inserted
        count_query = """
            SELECT COUNT(*)
            FROM articles
            WHERE claims_status IN ('pending', 'processing', 'completed', 'failed')
        """

        result = postgres_client.execute_query(count_query)
        assert result[0]['count'] >= 4, "All valid statuses should be inserted"

    def test_claims_available_function_logic(self, postgres_client):
        """Test the article_has_claims_available function logic"""

        # Test completed with claims
        query = "SELECT article_has_claims_available('completed', 5)"
        result = postgres_client.execute_query(query)
        assert result[0]['article_has_claims_available'] == True

        # Test completed without claims
        query = "SELECT article_has_claims_available('completed', 0)"
        result = postgres_client.execute_query(query)
        assert result[0]['article_has_claims_available'] == False

        # Test processing with claims
        query = "SELECT article_has_claims_available('processing', 5)"
        result = postgres_client.execute_query(query)
        assert result[0]['article_has_claims_available'] == False

        # Test pending
        query = "SELECT article_has_claims_available('pending', 0)"
        result = postgres_client.execute_query(query)
        assert result[0]['article_has_claims_available'] == False

    def test_status_transitions(self, postgres_client):
        """Test status transitions from pending -> processing -> completed"""
        article_id = str(uuid4())

        # Insert article with pending status
        insert_query = text("""
            INSERT INTO articles (
                article_id, url, title, extracted_text,
                source_name, claims_status
            )
            VALUES (
                :article_id, :url, :title, :text,
                :source, 'pending'
            )
        """)

        postgres_client.execute_update(
            str(insert_query),
            {
                'article_id': article_id,
                'url': 'https://example.com/test-transition',
                'title': 'Test Transition Article',
                'text': 'Test content',
                'source': 'Test Source'
            }
        )

        # Update to processing
        update_query = text("""
            UPDATE articles
            SET claims_status = 'processing'
            WHERE article_id = :article_id
        """)

        postgres_client.execute_update(str(update_query), {'article_id': article_id})

        # Verify processing status
        select_query = "SELECT claims_status FROM articles WHERE article_id = :article_id"
        result = postgres_client.execute_query(select_query, {'article_id': article_id})
        assert result[0]['claims_status'] == 'processing'

        # Update to completed with timestamp
        complete_query = text("""
            UPDATE articles
            SET claims_status = 'completed',
                claims_count = 3,
                verified_claims_count = 2,
                claims_processed_at = NOW()
            WHERE article_id = :article_id
        """)

        postgres_client.execute_update(str(complete_query), {'article_id': article_id})

        # Verify completed status
        final_query = """
            SELECT claims_status, claims_count, claims_processed_at
            FROM articles
            WHERE article_id = :article_id
        """
        result = postgres_client.execute_query(final_query, {'article_id': article_id})

        assert result[0]['claims_status'] == 'completed'
        assert result[0]['claims_count'] == 3
        assert result[0]['claims_processed_at'] is not None


@pytest.fixture
def postgres_client():
    """Fixture to provide PostgreSQL client for tests.

    Requires a live PostgreSQL instance. Tests are skipped when
    the database is not available.
    """
    import os
    if os.getenv("POSTGRES_AVAILABLE", "false").lower() != "true":
        pytest.skip("Requires live PostgreSQL database (set POSTGRES_AVAILABLE=true)")
    from shared.database import get_postgres
    return get_postgres()
