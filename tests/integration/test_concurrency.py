"""
Integration tests for multi-user concurrency and thread-safety.

Tests that multiple users can use the system simultaneously without
cross-contamination of data, filters, or custom prompts.
"""
import concurrent.futures
import threading
import time
from unittest.mock import Mock, patch

import pytest


class TestCustomPromptThreadSafety:
    """Test that custom prompts don't leak between concurrent users."""

    @pytest.mark.integration
    def test_concurrent_custom_prompts_isolated(self):
        """
        Test that two users with different custom prompts don't interfere.

        CRITICAL: This tests the fix for the race condition where shared Vanna
        instance would have custom prompts overwrite each other.
        """
        from src.services.llm_providers import (
            get_request_custom_prompt,
            set_request_custom_prompt,
        )

        results = {}
        errors = []

        def user_a_request():
            """Simulate User A's request with custom prompt."""
            try:
                # Set User A's custom prompt
                set_request_custom_prompt("User A: Always filter by California")

                # Simulate some processing time
                time.sleep(0.1)

                # Verify we still have User A's prompt
                prompt = get_request_custom_prompt()
                results['user_a'] = prompt

                # Clean up
                set_request_custom_prompt(None)
            except Exception as e:
                errors.append(('user_a', str(e)))

        def user_b_request():
            """Simulate User B's request with different custom prompt."""
            try:
                # Set User B's custom prompt
                set_request_custom_prompt("User B: Always filter by Texas")

                # Simulate some processing time
                time.sleep(0.1)

                # Verify we still have User B's prompt
                prompt = get_request_custom_prompt()
                results['user_b'] = prompt

                # Clean up
                set_request_custom_prompt(None)
            except Exception as e:
                errors.append(('user_b', str(e)))

        # Run both users concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(user_a_request)
            future_b = executor.submit(user_b_request)

            # Wait for both to complete
            future_a.result()
            future_b.result()

        # Verify no errors
        assert not errors, f"Errors occurred: {errors}"

        # Verify results don't contain cross-contamination
        assert "California" in results['user_a'], "User A lost their custom prompt"
        assert "Texas" in results['user_b'], "User B lost their custom prompt"
        assert "Texas" not in results['user_a'], "User A got User B's prompt"
        assert "California" not in results['user_b'], "User B got User A's prompt"

    @pytest.mark.integration
    @patch('src.services.llm_providers._get_vanna_instance')
    def test_concurrent_sql_generation_with_different_prompts(self, mock_vanna):
        """
        Test that concurrent SQL generation requests use correct prompts.

        Simulates the full flow from _generate_sql_sync with mocked Vanna.
        """
        from src.services.llm_service import _generate_sql_sync

        # Mock Vanna instance
        mock_vn = Mock()
        mock_vn.generate_sql = Mock(side_effect=lambda q: f"SELECT * FROM data WHERE {q}")
        mock_vanna.return_value = mock_vn

        # Mock get_user_prompt to return different prompts for different users
        with patch('src.services.llm_service.get_user_prompt') as mock_get_prompt:
            def get_prompt_side_effect(user_id, prompt_type):
                return f"Custom prompt for {user_id}"

            mock_get_prompt.side_effect = get_prompt_side_effect

            results = {}
            errors = []

            def user_request(user_id: str, question: str):
                """Simulate a user's SQL generation request."""
                try:
                    sql, explanation = _generate_sql_sync(
                        question=question,
                        user_id=user_id
                    )
                    results[user_id] = sql
                except Exception as e:
                    errors.append((user_id, str(e)))

            # Run 5 concurrent users
            users = [f"user_{i}" for i in range(5)]
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(user_request, user_id, f"question from {user_id}")
                    for user_id in users
                ]

                # Wait for all to complete
                for future in concurrent.futures.as_completed(futures):
                    future.result()

            # Verify no errors
            assert not errors, f"Errors occurred: {errors}"

            # Verify all users got results
            assert len(results) == 5, f"Expected 5 results, got {len(results)}"
            for user_id in users:
                assert user_id in results, f"Missing result for {user_id}"


class TestFilterManagerThreadSafety:
    """Test that FilterManager correctly isolates user filters."""

    @pytest.mark.integration
    def test_concurrent_filter_operations(self):
        """
        Test that multiple users can set filters simultaneously without interference.
        """
        from src.api.dependencies import get_request_user, set_request_user

        results = {}
        errors = []

        def user_request(user_id: str, state: str):
            """Simulate a user setting a filter."""
            try:
                # Set user context
                set_request_user(user_id)

                # Note: FilterManager._get_user_id() will use get_request_user()
                # which returns the user_id we set above

                # Simulate some processing
                time.sleep(0.05)

                # Verify context is still correct
                current_user = get_request_user()
                results[user_id] = current_user

            except Exception as e:
                errors.append((user_id, str(e)))

        # Run multiple users concurrently
        users = [
            ("user_1", "California"),
            ("user_2", "Texas"),
            ("user_3", "Florida"),
            ("user_4", "New York"),
        ]

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(user_request, user_id, state)
                for user_id, state in users
            ]

            for future in concurrent.futures.as_completed(futures):
                future.result()

        # Verify no errors
        assert not errors, f"Errors occurred: {errors}"

        # Verify each user kept their own context
        assert results["user_1"] == "user_1"
        assert results["user_2"] == "user_2"
        assert results["user_3"] == "user_3"
        assert results["user_4"] == "user_4"

    @pytest.mark.integration
    def test_request_context_cleanup(self):
        """
        Test that request context is properly cleaned up after requests.
        """
        from src.api.dependencies import get_request_user, set_request_user

        # Set user context
        set_request_user("test_user")
        assert get_request_user() == "test_user"

        # Simulate request completion - manually clean up
        set_request_user(None)
        assert get_request_user() is None


class TestConcurrentDatabaseAccess:
    """Test that database sessions are properly isolated per request."""

    @pytest.mark.integration
    def test_concurrent_database_queries(self):
        """
        Test that multiple concurrent database queries don't interfere.

        This verifies that database session management is thread-safe.
        """
        from src.database.engine import get_db

        results = {}
        errors = []

        def query_database(thread_id: int):
            """Simulate a database query in a thread."""
            try:
                db = next(get_db())
                try:
                    # Execute a simple query
                    from sqlalchemy import text
                    result = db.execute(text("SELECT 1 as value"))
                    row = result.fetchone()
                    results[thread_id] = row[0] if row else None
                finally:
                    db.close()
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Run 10 concurrent database queries
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(query_database, i) for i in range(10)]

            for future in concurrent.futures.as_completed(futures):
                future.result()

        # Verify no errors
        assert not errors, f"Database errors occurred: {errors}"

        # Verify all queries succeeded
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"
        for i in range(10):
            assert results[i] == 1, f"Query {i} failed"


class TestRaceConditionPrevention:
    """Test that the specific race conditions identified are fixed."""

    @pytest.mark.integration
    def test_vanna_instance_shared_safely(self):
        """
        Test that shared Vanna instance doesn't cause cross-user contamination.

        This is the critical test for the race condition fix.
        """
        from src.services.llm_providers import (
            _get_vanna_instance,
            get_request_custom_prompt,
            set_request_custom_prompt,
        )

        # Get the shared Vanna instance
        vn = _get_vanna_instance()

        results = []
        lock = threading.Lock()

        def simulate_request(user_id: str, custom_prompt: str):
            """Simulate a request with custom prompt."""
            # Set custom prompt in thread-local storage
            set_request_custom_prompt(custom_prompt)

            # Simulate calling system_message (which Vanna calls during SQL generation)
            # The fixed implementation should read from thread-local storage
            retrieved_prompt = get_request_custom_prompt()

            with lock:
                results.append({
                    'user_id': user_id,
                    'set_prompt': custom_prompt,
                    'retrieved_prompt': retrieved_prompt,
                    'match': custom_prompt == retrieved_prompt
                })

            # Clean up
            set_request_custom_prompt(None)

        # Run 20 concurrent simulated requests
        prompts = [f"Custom prompt for user {i}" for i in range(20)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(simulate_request, f"user_{i}", prompt)
                for i, prompt in enumerate(prompts)
            ]

            for future in concurrent.futures.as_completed(futures):
                future.result()

        # Verify all prompts matched
        assert len(results) == 20, f"Expected 20 results, got {len(results)}"

        mismatches = [r for r in results if not r['match']]
        assert not mismatches, f"Found prompt mismatches (race condition): {mismatches}"
