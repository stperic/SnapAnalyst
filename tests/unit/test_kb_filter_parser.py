"""
Unit tests for Knowledge Base Filter Parser

Tests filter parsing from user questions for knowledge base searches.
"""

from src.utils.kb_filter_parser import (
    format_search_scope,
    parse_kb_filters,
    parse_memadd_command,
)


class TestParseKBFilters:
    """Test parse_kb_filters function"""

    def test_parse_simple_question(self):
        """Test parsing simple question without filters"""
        result = parse_kb_filters("What are SNAP rules?", "user123")

        assert result['question'] == "What are SNAP rules?"
        assert result['chromadb_path'] == 'kb'
        assert result['collections'] == ['kb']
        assert result['tags'] == []
        assert result['category'] is None
        assert result['user_scope'] == 'all'

    def test_parse_with_snap_qc_path(self):
        """Test parsing with snap_qc path prefix"""
        result = parse_kb_filters("snap_qc What tables have income?", "user123")

        assert result['question'] == "What tables have income?"
        assert result['chromadb_path'] == 'snap_qc'
        assert result['collections'] == ['ddl', 'documentation', 'sql']

    def test_parse_with_snap_qc_specific_collection(self):
        """Test parsing with snap_qc path and specific collection"""
        result = parse_kb_filters("snap_qc:ddl Show me the schema", "user123")

        assert result['question'] == "Show me the schema"
        assert result['chromadb_path'] == 'snap_qc'
        assert result['collections'] == ['ddl']

    def test_parse_with_kb_path(self):
        """Test parsing with explicit kb path"""
        result = parse_kb_filters("kb What is SNAP?", "user123")

        assert result['question'] == "What is SNAP?"
        assert result['chromadb_path'] == 'kb'
        assert result['collections'] == ['kb']

    def test_parse_with_all_path(self):
        """Test parsing with 'all' path to search everywhere"""
        result = parse_kb_filters("all Find anything about errors", "user123")

        assert result['question'] == "Find anything about errors"
        assert result['chromadb_path'] == 'all'
        assert result['collections'] == ['kb', 'ddl', 'documentation', 'sql']

    def test_parse_with_user_scope_me(self):
        """Test parsing with @me user scope"""
        result = parse_kb_filters("@me What did I note?", "user123")

        assert result['question'] == "What did I note?"
        assert result['user_scope'] == 'private'

    def test_parse_with_user_scope_private(self):
        """Test parsing with @private user scope"""
        result = parse_kb_filters("@private My notes on SNAP", "user123")

        assert result['question'] == "My notes on SNAP"
        assert result['user_scope'] == 'private'

    def test_parse_with_category(self):
        """Test parsing with category filter"""
        result = parse_kb_filters("category:glossary What is QC?", "user123")

        assert result['question'] == "What is QC?"
        assert result['category'] == 'glossary'

    def test_parse_with_single_hashtag(self):
        """Test parsing with single hashtag"""
        result = parse_kb_filters("Show #research notes", "user123")

        assert result['question'] == "Show notes"
        assert result['tags'] == ['research']

    def test_parse_with_multiple_hashtags(self):
        """Test parsing with multiple hashtags"""
        result = parse_kb_filters("Find #snap #policy #eligibility docs", "user123")

        assert result['question'] == "Find docs"
        assert result['tags'] == ['snap', 'policy', 'eligibility']

    def test_parse_with_all_filters(self):
        """Test parsing with all filter types combined"""
        result = parse_kb_filters("snap_qc @me category:rules #snap #qc Find errors", "user123")

        assert result['question'] == "Find errors"
        assert result['chromadb_path'] == 'snap_qc'
        assert result['user_scope'] == 'private'
        assert result['category'] == 'rules'
        assert result['tags'] == ['snap', 'qc']

    def test_parse_normalizes_tags_to_lowercase(self):
        """Test that tags are normalized to lowercase"""
        result = parse_kb_filters("#SNAP #PoLiCy #MiXeD", "user123")

        assert result['tags'] == ['snap', 'policy', 'mixed']

    def test_parse_normalizes_category_to_lowercase(self):
        """Test that category is normalized to lowercase"""
        result = parse_kb_filters("category:GLOSSARY test", "user123")

        assert result['category'] == 'glossary'

    def test_parse_cleans_whitespace(self):
        """Test that extra whitespace is cleaned"""
        result = parse_kb_filters("What   are    SNAP    rules?", "user123")

        assert result['question'] == "What are SNAP rules?"

    def test_parse_case_insensitive_paths(self):
        """Test that path matching is case-insensitive"""
        result = parse_kb_filters("SNAP_QC What is this?", "user123")

        assert result['chromadb_path'] == 'snap_qc'

    def test_parse_case_insensitive_user_scope(self):
        """Test that user scope matching is case-insensitive"""
        result = parse_kb_filters("@ME my notes", "user123")

        assert result['user_scope'] == 'private'

    def test_parse_state_ca_path(self):
        """Test parsing with state_ca path"""
        result = parse_kb_filters("state_ca Find state data", "user123")

        assert result['question'] == "Find state data"
        assert result['chromadb_path'] == 'state_ca'
        assert result['collections'] == ['ddl', 'documentation', 'sql']


class TestFormatSearchScope:
    """Test format_search_scope function"""

    def test_format_kb_scope(self):
        """Test formatting Knowledge Base scope"""
        filters = {
            'chromadb_path': 'kb',
            'collections': ['kb'],
            'tags': [],
            'category': None,
            'user_scope': 'all'
        }

        result = format_search_scope(filters)

        assert result == "Knowledge Base"

    def test_format_all_scope(self):
        """Test formatting All Sources scope"""
        filters = {
            'chromadb_path': 'all',
            'collections': ['kb', 'ddl', 'documentation', 'sql'],
            'tags': [],
            'category': None,
            'user_scope': 'all'
        }

        result = format_search_scope(filters)

        assert result == "All Sources"

    def test_format_dataset_scope(self):
        """Test formatting dataset scope"""
        filters = {
            'chromadb_path': 'snap_qc',
            'collections': ['ddl', 'documentation', 'sql'],
            'tags': [],
            'category': None,
            'user_scope': 'all'
        }

        result = format_search_scope(filters)

        assert result == "🔍 SNAP QC"

    def test_format_dataset_with_specific_collection(self):
        """Test formatting dataset with specific collection"""
        filters = {
            'chromadb_path': 'snap_qc',
            'collections': ['ddl'],
            'tags': [],
            'category': None,
            'user_scope': 'all'
        }

        result = format_search_scope(filters)

        assert result == "🔍 SNAP QC - Ddl"

    def test_format_with_tags(self):
        """Test formatting with tags"""
        filters = {
            'chromadb_path': 'kb',
            'collections': ['kb'],
            'tags': ['snap', 'policy'],
            'category': None,
            'user_scope': 'all'
        }

        result = format_search_scope(filters)

        assert "Knowledge Base" in result
        assert "Tags: #snap #policy" in result

    def test_format_with_category(self):
        """Test formatting with category"""
        filters = {
            'chromadb_path': 'kb',
            'collections': ['kb'],
            'tags': [],
            'category': 'glossary',
            'user_scope': 'all'
        }

        result = format_search_scope(filters)

        assert "Knowledge Base" in result
        assert "Category: glossary" in result

    def test_format_with_private_scope(self):
        """Test formatting with private user scope"""
        filters = {
            'chromadb_path': 'kb',
            'collections': ['kb'],
            'tags': [],
            'category': None,
            'user_scope': 'private'
        }

        result = format_search_scope(filters)

        assert "Knowledge Base" in result
        assert "🔒 Your Docs" in result

    def test_format_with_all_filters(self):
        """Test formatting with all filters combined"""
        filters = {
            'chromadb_path': 'snap_qc',
            'collections': ['ddl'],
            'tags': ['snap', 'qc'],
            'category': 'rules',
            'user_scope': 'private'
        }

        result = format_search_scope(filters)

        assert "🔍 SNAP QC - Ddl" in result
        assert "Tags: #snap #qc" in result
        assert "Category: rules" in result
        assert "🔒 Your Docs" in result

    def test_format_state_ca_scope(self):
        """Test formatting state_ca scope"""
        filters = {
            'chromadb_path': 'state_ca',
            'collections': ['ddl', 'documentation'],
            'tags': [],
            'category': None,
            'user_scope': 'all'
        }

        result = format_search_scope(filters)

        assert "🔍 STATE CA" in result


class TestParseMemaddCommand:
    """Test parse_memadd_command function"""

    def test_parse_simple_category_and_tags(self):
        """Test parsing simple category with tags"""
        category, tags, is_private = parse_memadd_command("policy #snap #eligibility", "eric@example.com")

        assert category == "policy"
        assert tags == ["snap", "eligibility"]
        assert is_private is False

    def test_parse_only_tags(self):
        """Test parsing with only tags (no category)"""
        category, tags, is_private = parse_memadd_command("#snap", "eric@example.com")

        assert category == "general"
        assert tags == ["snap"]
        assert is_private is False

    def test_parse_private_scope(self):
        """Test parsing with @me for private scope"""
        category, tags, is_private = parse_memadd_command("@me notes #research", "eric@example.com")

        assert category == "user:eric@example.com"
        assert tags == ["research"]
        assert is_private is True

    def test_parse_private_keyword(self):
        """Test parsing with @private keyword"""
        category, tags, is_private = parse_memadd_command("@private ideas #brainstorm", "eric@example.com")

        assert category == "user:eric@example.com"
        assert tags == ["brainstorm"]
        assert is_private is True

    def test_parse_normalizes_tags_to_lowercase(self):
        """Test that tags are normalized to lowercase"""
        category, tags, is_private = parse_memadd_command("rules #SNAP #PoLiCy", "eric@example.com")

        assert tags == ["snap", "policy"]

    def test_parse_normalizes_category_to_lowercase(self):
        """Test that category is normalized to lowercase"""
        category, tags, is_private = parse_memadd_command("GLOSSARY #snap", "eric@example.com")

        assert category == "glossary"

    def test_parse_empty_string(self):
        """Test parsing empty string"""
        category, tags, is_private = parse_memadd_command("", "eric@example.com")

        assert category == "general"
        assert tags == []
        assert is_private is False

    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only string"""
        category, tags, is_private = parse_memadd_command("   ", "eric@example.com")

        assert category == "general"
        assert tags == []
        assert is_private is False

    def test_parse_only_category(self):
        """Test parsing with only category (no tags)"""
        category, tags, is_private = parse_memadd_command("glossary", "eric@example.com")

        assert category == "glossary"
        assert tags == []
        assert is_private is False

    def test_parse_multiple_tags(self):
        """Test parsing with multiple tags"""
        category, tags, is_private = parse_memadd_command("docs #tag1 #tag2 #tag3", "eric@example.com")

        assert category == "docs"
        assert len(tags) == 3
        assert tags == ["tag1", "tag2", "tag3"]

    def test_parse_private_with_no_category(self):
        """Test @me with no explicit category"""
        category, tags, is_private = parse_memadd_command("@me #notes", "eric@example.com")

        assert category == "user:eric@example.com"
        assert tags == ["notes"]
        assert is_private is True

    def test_parse_case_insensitive_private(self):
        """Test that @me and @private are case-insensitive"""
        category1, _, is_private1 = parse_memadd_command("@ME notes", "user@test.com")
        category2, _, is_private2 = parse_memadd_command("@PRIVATE notes", "user@test.com")

        assert is_private1 is True
        assert is_private2 is True
        assert category1 == "user:user@test.com"
        assert category2 == "user:user@test.com"
