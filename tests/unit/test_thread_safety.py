"""
Unit tests for thread-safety of request context management.

These tests verify that the thread-local storage approach prevents
cross-user contamination without requiring heavy dependencies.
"""
import concurrent.futures
import threading
import time

import pytest


class TestThreadLocalStorage:
    """Test thread-local storage for user context."""

    def test_thread_local_isolation(self):
        """
        Test that thread-local storage properly isolates values per thread.

        This is the core mechanism that fixes the custom prompt race condition.
        """
        _thread_local = threading.local()
        results = {}
        errors = []

        def worker(worker_id: int, value: str):
            """Simulate work in a thread with thread-local storage."""
            try:
                # Set thread-local value
                _thread_local.value = value

                # Simulate some work
                time.sleep(0.05)

                # Read back the value - should be unchanged
                retrieved = getattr(_thread_local, 'value', None)
                results[worker_id] = retrieved

            except Exception as e:
                errors.append((worker_id, str(e)))

        # Run 10 concurrent workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(worker, i, f"value_{i}")
                for i in range(10)
            ]

            for future in concurrent.futures.as_completed(futures):
                future.result()

        # Verify no errors
        assert not errors, f"Errors occurred: {errors}"

        # Verify each worker got its own value
        for i in range(10):
            assert results[i] == f"value_{i}", \
                f"Worker {i} got wrong value: {results[i]}"

    def test_context_var_isolation(self):
        """
        Test that ContextVar properly isolates values per asyncio task/thread.

        This is what we use for FilterManager user context.
        """
        from contextvars import ContextVar

        context_var: ContextVar[str | None] = ContextVar('test_var', default=None)
        results = {}
        errors = []

        def worker(worker_id: int, value: str):
            """Simulate work with ContextVar."""
            try:
                # Set context value
                context_var.set(value)

                # Simulate some work
                time.sleep(0.05)

                # Read back the value - should be unchanged
                retrieved = context_var.get()
                results[worker_id] = retrieved

            except Exception as e:
                errors.append((worker_id, str(e)))

        # Run 10 concurrent workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(worker, i, f"user_{i}")
                for i in range(10)
            ]

            for future in concurrent.futures.as_completed(futures):
                future.result()

        # Verify no errors
        assert not errors, f"Errors occurred: {errors}"

        # Verify each worker got its own value
        for i in range(10):
            assert results[i] == f"user_{i}", \
                f"Worker {i} got wrong value: {results[i]}"


class TestRequestDependencies:
    """Test the request context dependencies."""

    def test_set_and_get_request_user(self):
        """Test setting and getting request user context."""
        from src.api.dependencies import get_request_user, set_request_user

        # Initially should be None
        assert get_request_user() is None

        # Set a user
        set_request_user("test_user_123")
        assert get_request_user() == "test_user_123"

        # Change user
        set_request_user("different_user")
        assert get_request_user() == "different_user"

        # Clear
        set_request_user(None)
        assert get_request_user() is None

    def test_concurrent_request_users(self):
        """Test that concurrent requests maintain separate user contexts."""
        from src.api.dependencies import get_request_user, set_request_user

        results = {}
        errors = []

        def simulate_request(user_id: str):
            """Simulate a request with user context."""
            try:
                # Set user for this request
                set_request_user(user_id)

                # Simulate request processing
                time.sleep(0.05)

                # Verify user is still correct
                current_user = get_request_user()
                results[user_id] = current_user

                # Clean up
                set_request_user(None)

            except Exception as e:
                errors.append((user_id, str(e)))

        # Run 10 concurrent simulated requests
        users = [f"user_{i}" for i in range(10)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(simulate_request, user) for user in users]

            for future in concurrent.futures.as_completed(futures):
                future.result()

        # Verify no errors
        assert not errors, f"Errors occurred: {errors}"

        # Verify each request maintained its own user context
        for user_id in users:
            assert results[user_id] == user_id, \
                f"User {user_id} got wrong context: {results[user_id]}"


class TestSharedInstanceSafety:
    """Test that shared instances are safe with thread-local storage."""

    def test_shared_object_with_thread_local_state(self):
        """
        Demonstrate that a shared object can safely use thread-local storage.

        This simulates the Vanna instance pattern we fixed.
        """
        class SharedService:
            """Simulates a shared service like Vanna."""

            def __init__(self):
                self._thread_local = threading.local()

            def set_user_context(self, context: str):
                """Set context in thread-local storage (SAFE)."""
                self._thread_local.context = context

            def get_user_context(self) -> str | None:
                """Get context from thread-local storage."""
                return getattr(self._thread_local, 'context', None)

            def process_with_context(self, data: str) -> str:
                """Process data with current context."""
                context = self.get_user_context()
                if context:
                    return f"{context}: {data}"
                return data

        # Create ONE shared instance (like our global Vanna instance)
        shared_service = SharedService()

        results = {}
        errors = []

        def worker(worker_id: int, context: str):
            """Simulate using the shared service."""
            try:
                # Set context for this thread
                shared_service.set_user_context(context)

                # Simulate work
                time.sleep(0.05)

                # Process with context - should use this thread's context only
                result = shared_service.process_with_context(f"data_{worker_id}")
                results[worker_id] = result

            except Exception as e:
                errors.append((worker_id, str(e)))

        # Run 10 concurrent workers using the SAME shared service
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(worker, i, f"context_{i}")
                for i in range(10)
            ]

            for future in concurrent.futures.as_completed(futures):
                future.result()

        # Verify no errors
        assert not errors, f"Errors occurred: {errors}"

        # Verify each worker used its own context
        for i in range(10):
            expected = f"context_{i}: data_{i}"
            assert results[i] == expected, \
                f"Worker {i} got wrong result: {results[i]} (expected {expected})"

    def test_broken_shared_instance_pattern(self):
        """
        Demonstrate the BROKEN pattern (instance attribute) for comparison.

        This shows what happens WITHOUT thread-local storage.
        """
        class BrokenSharedService:
            """Simulates the BROKEN pattern with instance attributes."""

            def __init__(self):
                self.context = None  # BROKEN: shared across threads

            def set_user_context(self, context: str):
                """Set context as instance attribute (UNSAFE)."""
                self.context = context

            def process_with_context(self, data: str) -> str:
                """Process data with current context."""
                if self.context:
                    return f"{self.context}: {data}"
                return data

        # Create ONE shared instance
        broken_service = BrokenSharedService()

        results = {}
        errors = []

        def worker(worker_id: int, context: str):
            """Simulate using the broken service."""
            try:
                # Set context (will overwrite others!)
                broken_service.set_user_context(context)

                # Simulate work - context might change during this!
                time.sleep(0.05)

                # Process with context - might use WRONG context!
                result = broken_service.process_with_context(f"data_{worker_id}")
                results[worker_id] = result

            except Exception as e:
                errors.append((worker_id, str(e)))

        # Run 10 concurrent workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(worker, i, f"context_{i}")
                for i in range(10)
            ]

            for future in concurrent.futures.as_completed(futures):
                future.result()

        # Verify no errors occurred
        assert not errors, f"Errors occurred: {errors}"

        # Count how many workers got the WRONG context (cross-contamination)
        contaminated = 0
        for i in range(10):
            expected = f"context_{i}: data_{i}"
            if results[i] != expected:
                contaminated += 1

        # In the broken pattern, we EXPECT cross-contamination
        # (This test documents the problem we fixed)
        assert contaminated > 0, \
            "Expected cross-contamination with broken pattern, but none occurred"

        print(f"\nBroken pattern resulted in {contaminated}/10 contaminated results")
        print("This demonstrates the race condition we fixed with thread-local storage")
