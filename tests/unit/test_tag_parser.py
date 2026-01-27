"""
Unit tests for Tag Parser

Tests tag parsing, validation, and formatting utilities.
"""

from src.utils.tag_parser import (
    format_tags_display,
    parse_memadd_command,
    validate_category,
    validate_file_extension,
    validate_file_size,
    validate_tags,
)


class TestParseMemaddCommand:
    """Test parse_memadd_command function"""

    def test_parse_with_category_and_tags(self):
        """Test parsing command with category and tags"""
        category, tags = parse_memadd_command("business-rules #SNAP #eligibility")

        assert category == "business-rules"
        assert tags == ["snap", "eligibility"]

    def test_parse_with_only_tags(self):
        """Test parsing command with only hashtags (no category)"""
        category, tags = parse_memadd_command("#SNAP #policy")

        assert category == "general"
        assert tags == ["snap", "policy"]

    def test_parse_with_only_category(self):
        """Test parsing command with only category (no tags)"""
        category, tags = parse_memadd_command("glossary")

        assert category == "glossary"
        assert tags == []

    def test_parse_empty_string(self):
        """Test parsing empty command"""
        category, tags = parse_memadd_command("")

        assert category == "general"
        assert tags == []

    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only command"""
        category, tags = parse_memadd_command("   ")

        assert category == "general"
        assert tags == []

    def test_parse_normalizes_tags_to_lowercase(self):
        """Test that tags are normalized to lowercase"""
        category, tags = parse_memadd_command("rules #SNAP #UPPERCASE #MiXeD")

        assert tags == ["snap", "uppercase", "mixed"]

    def test_parse_with_multiple_tags(self):
        """Test parsing with many tags"""
        category, tags = parse_memadd_command("docs #tag1 #tag2 #tag3 #tag4")

        assert category == "docs"
        assert len(tags) == 4
        assert "tag1" in tags
        assert "tag4" in tags

    def test_parse_with_hyphens_in_tags(self):
        """Test parsing tags with hyphens"""
        category, tags = parse_memadd_command("#snap-benefits #error-codes")

        assert tags == ["snap-benefits", "error-codes"]

    def test_parse_with_underscores_in_tags(self):
        """Test parsing tags with underscores"""
        category, tags = parse_memadd_command("#snap_qc #error_handling")

        assert tags == ["snap_qc", "error_handling"]


class TestValidateCategory:
    """Test validate_category function"""

    def test_validate_valid_category(self):
        """Test validation of valid category"""
        result = validate_category("business-rules")

        assert result == "business-rules"

    def test_validate_empty_category(self):
        """Test validation of empty category returns 'general'"""
        result = validate_category("")

        assert result == "general"

    def test_validate_removes_invalid_characters(self):
        """Test that invalid characters are removed"""
        result = validate_category("test@category#with!invalid")

        assert result == "testcategorywithinvalid"

    def test_validate_converts_to_lowercase(self):
        """Test that category is converted to lowercase"""
        result = validate_category("MixedCase")

        assert result == "mixedcase"

    def test_validate_removes_spaces(self):
        """Test that spaces are removed"""
        result = validate_category("has spaces here")

        assert result == "hasspaceshere"

    def test_validate_truncates_long_category(self):
        """Test that category is truncated to 50 chars"""
        long_category = "a" * 100
        result = validate_category(long_category)

        assert len(result) == 50

    def test_validate_returns_general_if_all_invalid(self):
        """Test returns 'general' if all characters are invalid"""
        result = validate_category("@#$%^&*()")

        assert result == "general"

    def test_validate_allows_hyphens(self):
        """Test that hyphens are allowed"""
        result = validate_category("my-category")

        assert result == "my-category"

    def test_validate_allows_underscores(self):
        """Test that underscores are allowed"""
        result = validate_category("my_category")

        assert result == "my_category"

    def test_validate_allows_numbers(self):
        """Test that numbers are allowed"""
        result = validate_category("category123")

        assert result == "category123"


class TestValidateTags:
    """Test validate_tags function"""

    def test_validate_empty_tags(self):
        """Test validation of empty tag list"""
        result = validate_tags([])

        assert result == []

    def test_validate_single_tag(self):
        """Test validation of single tag"""
        result = validate_tags(["snap"])

        assert result == ["snap"]

    def test_validate_removes_duplicates(self):
        """Test that duplicate tags are removed"""
        result = validate_tags(["snap", "SNAP", "snap"])

        assert result == ["snap"]

    def test_validate_normalizes_to_lowercase(self):
        """Test that tags are normalized to lowercase"""
        result = validate_tags(["SNAP", "Policy", "MiXeD"])

        assert result == ["snap", "policy", "mixed"]

    def test_validate_removes_invalid_characters(self):
        """Test that invalid characters are removed"""
        result = validate_tags(["tag@1", "tag#2", "tag!3"])

        assert result == ["tag1", "tag2", "tag3"]

    def test_validate_truncates_long_tags(self):
        """Test that tags longer than 30 chars are truncated"""
        long_tag = "a" * 50
        result = validate_tags([long_tag])

        assert len(result[0]) == 30

    def test_validate_skips_empty_tags(self):
        """Test that empty tags are skipped"""
        result = validate_tags(["valid", "", "   ", "another"])

        assert result == ["valid", "another"]

    def test_validate_skips_tags_with_only_invalid_chars(self):
        """Test that tags with only invalid characters are skipped"""
        result = validate_tags(["valid", "@#$%", "another"])

        assert result == ["valid", "another"]

    def test_validate_many_tags_logs_warning(self):
        """Test that having > 10 tags triggers warning (still validates)"""
        many_tags = [f"tag{i}" for i in range(15)]
        result = validate_tags(many_tags)

        # Should still return all 15 tags, just logs warning
        assert len(result) == 15

    def test_validate_preserves_order(self):
        """Test that tag order is preserved"""
        result = validate_tags(["zebra", "alpha", "beta"])

        assert result == ["zebra", "alpha", "beta"]

    def test_validate_allows_hyphens_and_underscores(self):
        """Test that hyphens and underscores are allowed"""
        result = validate_tags(["snap-qc", "error_codes"])

        assert result == ["snap-qc", "error_codes"]


class TestValidateFileExtension:
    """Test validate_file_extension function"""

    def test_validate_allowed_extension_md(self):
        """Test that .md files are allowed by default"""
        result = validate_file_extension("document.md")

        assert result is True

    def test_validate_allowed_extension_txt(self):
        """Test that .txt files are allowed by default"""
        result = validate_file_extension("notes.txt")

        assert result is True

    def test_validate_disallowed_extension(self):
        """Test that non-allowed extensions are rejected"""
        result = validate_file_extension("script.py")

        assert result is False

    def test_validate_case_insensitive(self):
        """Test that extension check is case-insensitive"""
        result = validate_file_extension("document.MD")

        assert result is True

    def test_validate_custom_allowed_list(self):
        """Test validation with custom allowed extensions"""
        result = validate_file_extension("data.csv", allowed=['.csv', '.json'])

        assert result is True

    def test_validate_custom_allowed_list_rejects_others(self):
        """Test that custom list rejects non-allowed extensions"""
        result = validate_file_extension("document.md", allowed=['.csv', '.json'])

        assert result is False

    def test_validate_no_extension(self):
        """Test file with no extension"""
        result = validate_file_extension("README")

        assert result is False

    def test_validate_with_path(self):
        """Test validation with full file path"""
        result = validate_file_extension("/path/to/file.txt")

        assert result is True


class TestValidateFileSize:
    """Test validate_file_size function"""

    def test_validate_small_file(self):
        """Test that small files are valid"""
        result = validate_file_size(1024)  # 1 KB

        assert result is True

    def test_validate_exact_limit(self):
        """Test file exactly at limit (10 MB)"""
        max_bytes = 10 * 1024 * 1024
        result = validate_file_size(max_bytes)

        assert result is True

    def test_validate_over_limit(self):
        """Test file over limit is rejected"""
        max_bytes = 10 * 1024 * 1024
        result = validate_file_size(max_bytes + 1)

        assert result is False

    def test_validate_custom_max_size(self):
        """Test validation with custom max size"""
        result = validate_file_size(3 * 1024 * 1024, max_mb=5)  # 3 MB with 5 MB limit

        assert result is True

    def test_validate_custom_max_size_exceeded(self):
        """Test custom max size is enforced"""
        result = validate_file_size(6 * 1024 * 1024, max_mb=5)  # 6 MB with 5 MB limit

        assert result is False

    def test_validate_zero_size(self):
        """Test zero-sized file is valid"""
        result = validate_file_size(0)

        assert result is True

    def test_validate_large_file_default_limit(self):
        """Test large file exceeding default 10 MB limit"""
        result = validate_file_size(20 * 1024 * 1024)  # 20 MB

        assert result is False


class TestFormatTagsDisplay:
    """Test format_tags_display function"""

    def test_format_empty_tags(self):
        """Test formatting empty tag list"""
        result = format_tags_display([])

        assert result == ""

    def test_format_single_tag(self):
        """Test formatting single tag"""
        result = format_tags_display(["snap"])

        assert result == "#snap"

    def test_format_multiple_tags(self):
        """Test formatting multiple tags"""
        result = format_tags_display(["snap", "policy", "eligibility"])

        assert result == "#snap #policy #eligibility"

    def test_format_preserves_order(self):
        """Test that tag order is preserved in output"""
        result = format_tags_display(["zebra", "alpha", "beta"])

        assert result == "#zebra #alpha #beta"

    def test_format_with_hyphens(self):
        """Test formatting tags with hyphens"""
        result = format_tags_display(["snap-qc", "error-codes"])

        assert result == "#snap-qc #error-codes"

    def test_format_with_underscores(self):
        """Test formatting tags with underscores"""
        result = format_tags_display(["snap_benefits", "qc_data"])

        assert result == "#snap_benefits #qc_data"
