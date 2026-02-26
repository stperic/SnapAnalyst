"""
Initialize Chainlit Database Tables

Creates the necessary database tables for Chainlit's persistence layer:
- users (with password_hash for authentication)
- threads (chat sessions)
- steps (messages)
- elements (attachments)
- feedbacks (user feedback)

This script should be run once on initial setup or can be called on app startup.
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


CHAINLIT_TABLES_SQL = """
-- Chainlit users table with password_hash for custom authentication
CREATE TABLE IF NOT EXISTS users (
    "id" UUID PRIMARY KEY,
    "identifier" TEXT NOT NULL UNIQUE,
    "metadata" JSONB NOT NULL DEFAULT '{}',
    "createdAt" TEXT,
    "password_hash" TEXT,  -- Added for custom password authentication
    "filter_preferences" JSONB DEFAULT '{}'::jsonb  -- User filter preferences (state/fiscal year)
);

-- Chainlit threads table (chat sessions)
CREATE TABLE IF NOT EXISTS threads (
    "id" UUID PRIMARY KEY,
    "createdAt" TEXT,
    "name" TEXT,
    "userId" UUID,
    "userIdentifier" TEXT,
    "tags" TEXT[],
    "metadata" JSONB,
    FOREIGN KEY ("userId") REFERENCES users("id") ON DELETE CASCADE
);

-- Chainlit steps table (messages/actions within threads)
CREATE TABLE IF NOT EXISTS steps (
    "id" UUID PRIMARY KEY,
    "name" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "threadId" UUID NOT NULL,
    "parentId" UUID,
    "streaming" BOOLEAN NOT NULL DEFAULT FALSE,
    "waitForAnswer" BOOLEAN,
    "isError" BOOLEAN,
    "metadata" JSONB,
    "tags" TEXT[],
    "input" TEXT,
    "output" TEXT,
    "createdAt" TEXT,
    "command" TEXT,
    "start" TEXT,
    "end" TEXT,
    "generation" JSONB,
    "showInput" TEXT,
    "language" TEXT,
    "indent" INT,
    "defaultOpen" BOOLEAN,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

-- Chainlit elements table (attachments, files, etc.)
CREATE TABLE IF NOT EXISTS elements (
    "id" UUID PRIMARY KEY,
    "threadId" UUID,
    "type" TEXT,
    "url" TEXT,
    "chainlitKey" TEXT,
    "name" TEXT NOT NULL,
    "display" TEXT,
    "objectKey" TEXT,
    "size" TEXT,
    "page" INT,
    "language" TEXT,
    "forId" UUID,
    "mime" TEXT,
    "props" JSONB,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

-- Chainlit feedbacks table (user feedback on responses)
CREATE TABLE IF NOT EXISTS feedbacks (
    "id" UUID PRIMARY KEY,
    "forId" UUID NOT NULL,
    "threadId" UUID NOT NULL,
    "value" INT NOT NULL,
    "comment" TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_threads_userId ON threads("userId");
CREATE INDEX IF NOT EXISTS idx_threads_userIdentifier ON threads("userIdentifier");
CREATE INDEX IF NOT EXISTS idx_steps_threadId ON steps("threadId");
CREATE INDEX IF NOT EXISTS idx_elements_threadId ON elements("threadId");
CREATE INDEX IF NOT EXISTS idx_feedbacks_threadId ON feedbacks("threadId");
"""


async def init_chainlit_tables():
    """Initialize Chainlit database tables."""
    import asyncpg

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is required")

    # Convert to asyncpg format
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgres://")
    elif db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgres://")

    try:
        conn = await asyncpg.connect(db_url)
        await conn.execute(CHAINLIT_TABLES_SQL)

        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename IN ('users', 'threads', 'steps', 'elements', 'feedbacks')
            ORDER BY tablename
        """)

        await conn.close()

        table_names = ", ".join(t["tablename"] for t in tables)
        print(f"[chainlit-db] Tables ready: {table_names}")

        return True

    except Exception as e:
        print(f"[chainlit-db] ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def init_chainlit_tables_sync():
    """Synchronous wrapper for table initialization."""
    return asyncio.run(init_chainlit_tables())


if __name__ == "__main__":
    if not init_chainlit_tables_sync():
        print("[chainlit-db] ERROR: Database initialization failed")
        sys.exit(1)
