"""Tests for markdown_graph_kit primitives."""

import tempfile
from datetime import date
from pathlib import Path

import pytest

import markdown_graph_kit as mgk


class TestTitleFilenameConversion:
    """Test title ↔ filename encoding with triple-lowbar namespaces."""

    def test_simple_title(self):
        assert mgk.title_to_filename("Home") == "Home"
        assert mgk.filename_to_title("Home") == "Home"

    def test_namespaced_title(self):
        assert mgk.title_to_filename("Company/Role/Application") == "Company___Role___Application"
        assert mgk.filename_to_title("Company___Role___Application") == "Company/Role/Application"

    def test_roundtrip(self):
        """Title → filename → title preserves the original."""
        titles = [
            "Home",
            "My Page",
            "Namespace/Child",
            "A/B/C/D/E",
        ]
        for title in titles:
            filename = mgk.title_to_filename(title)
            recovered = mgk.filename_to_title(filename)
            assert recovered == title


class TestDirectoryPaths:
    """Test directory path helpers."""

    def test_pages_dir(self):
        root = Path("/tmp/test_graph")
        assert mgk.pages_dir(root) == root / "pages"

    def test_journals_dir(self):
        root = Path("/tmp/test_graph")
        assert mgk.journals_dir(root) == root / "journals"

    def test_assets_dir(self):
        root = Path("/tmp/test_graph")
        assert mgk.assets_dir(root) == root / "assets"

    def test_recycle_dir(self):
        root = Path("/tmp/test_graph")
        assert mgk.recycle_dir(root) == root / ".recycle"

    def test_logseq_dir(self):
        root = Path("/tmp/test_graph")
        assert mgk.logseq_dir(root) == root / "logseq"

    def test_page_path(self):
        root = Path("/tmp/test_graph")
        page = mgk.page_path(root, "Company/Role/Application")
        assert page == root / "pages" / "Company___Role___Application.md"

    def test_journal_filename(self):
        d = date(2026, 7, 20)
        assert mgk.journal_filename(d) == "2026_07_20.md"


class TestConfigManagement:
    """Test config.edn creation and management."""

    def test_ensure_graph_config_creates_minimal_config(self):
        """Creating config.edn in a fresh graph."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_root = Path(tmpdir)
            mgk.ensure_graph_config(graph_root)

            cfg_file = mgk.logseq_dir(graph_root) / "config.edn"
            assert cfg_file.exists()

            content = cfg_file.read_text()
            assert ":file/name-format :triple-lowbar" in content
            assert ':journal/page-title-format "yyyy/MM/dd"' in content
            assert "{:meta/version 1" in content

    def test_ensure_graph_config_idempotent(self):
        """Calling ensure_graph_config twice produces the same result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_root = Path(tmpdir)
            mgk.ensure_graph_config(graph_root)
            content_1 = (mgk.logseq_dir(graph_root) / "config.edn").read_text()

            mgk.ensure_graph_config(graph_root)
            content_2 = (mgk.logseq_dir(graph_root) / "config.edn").read_text()

            assert content_1 == content_2

    def test_ensure_graph_config_preserves_user_settings(self):
        """Existing config is not overwritten, only missing keys added."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_root = Path(tmpdir)
            cfg_file = mgk.logseq_dir(graph_root) / "config.edn"

            # Write a custom config with one of the required settings
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            cfg_file.write_text("{:user/custom-setting true\n :file/name-format :triple-lowbar\n}\n")

            mgk.ensure_graph_config(graph_root)

            content = cfg_file.read_text()
            assert ":user/custom-setting true" in content
            assert ":file/name-format :triple-lowbar" in content
            assert ':journal/page-title-format "yyyy/MM/dd"' in content


class TestPropertyParsing:
    """Test page property extraction."""

    def test_parse_empty_page(self):
        """Parsing an empty file returns minimal properties."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.md"
            filepath.write_text("")
            props = mgk.parse_page_properties(filepath)
            assert props["name"] == "test"
            assert props["file"] == str(filepath)

    def test_parse_properties_block(self):
        """Extract properties from the front-matter of a page."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.md"
            filepath.write_text(
                "type:: #Page\n"
                "status:: #Active\n"
                "tags:: foo, bar\n"
                "\n"
                "- Some bullet content\n"
                "- More content\n"
            )
            props = mgk.parse_page_properties(filepath)
            assert props["type"] == "#Page"
            assert props["status"] == "#Active"
            assert props["tags"] == "foo, bar"
            assert props["name"] == "test"

    def test_parse_stops_at_bullets(self):
        """Property parsing stops at the first bullet point."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.md"
            filepath.write_text(
                "type:: #Page\n"
                "- First bullet (not a property)\n"
                "status:: #Ignored\n"  # This looks like a property but comes after a bullet
            )
            props = mgk.parse_page_properties(filepath)
            assert props["type"] == "#Page"
            assert "status" not in props

    def test_parse_unreadable_file(self):
        """Parsing a non-existent file returns minimal properties."""
        props = mgk.parse_page_properties(Path("/nonexistent/file.md"))
        assert props["name"] == "file"
        assert props["file"] == "/nonexistent/file.md"


class TestSetPageProperty:
    """Test adding and updating page properties."""

    def test_add_property_to_empty_page(self):
        """Adding a property to an empty file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.md"
            old_val, action = mgk.set_page_property(filepath, "type", "#Page")
            assert old_val is None
            assert action == "added"
            assert filepath.exists()
            content = filepath.read_text()
            assert "type:: #Page" in content

    def test_add_property_before_bullets(self):
        """New properties are inserted before existing bullet content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.md"
            filepath.write_text("- Existing bullet\n")
            old_val, action = mgk.set_page_property(filepath, "type", "#Page")
            assert old_val is None
            assert action == "added"
            content = filepath.read_text()
            lines = content.splitlines()
            # Property should come before the bullet
            assert lines[0] == "type:: #Page"
            assert "Existing bullet" in lines[1]

    def test_update_existing_property(self):
        """Updating an existing property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.md"
            filepath.write_text("type:: #OldType\n- Content\n")
            old_val, action = mgk.set_page_property(filepath, "type", "#NewType")
            assert old_val == "#OldType"
            assert action == "updated"
            content = filepath.read_text()
            assert "type:: #NewType" in content
            assert "type:: #OldType" not in content

    def test_property_case_insensitive(self):
        """Property keys are case-insensitive for matching."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.md"
            filepath.write_text("TYPE:: #OldType\n")
            old_val, action = mgk.set_page_property(filepath, "type", "#NewType")
            assert old_val == "#OldType"
            assert action == "updated"
            # The key name should be lowercased
            content = filepath.read_text()
            assert "type:: #NewType" in content


class TestBootstrapGraph:
    """Test graph initialization."""

    def test_bootstrap_creates_directories(self):
        """Bootstrapping a graph creates all required directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_root = Path(tmpdir)
            mgk.bootstrap_graph(graph_root)

            assert (graph_root / "pages").is_dir()
            assert (graph_root / "journals").is_dir()
            assert (graph_root / "assets").is_dir()
            assert (graph_root / "logseq").is_dir()

    def test_bootstrap_creates_config(self):
        """Bootstrapping creates a valid config.edn."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_root = Path(tmpdir)
            mgk.bootstrap_graph(graph_root)

            cfg_file = graph_root / "logseq" / "config.edn"
            assert cfg_file.exists()
            content = cfg_file.read_text()
            assert ":file/name-format :triple-lowbar" in content
            assert ':journal/page-title-format "yyyy/MM/dd"' in content

    def test_bootstrap_idempotent(self):
        """Bootstrapping twice is safe and idempotent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_root = Path(tmpdir)
            mgk.bootstrap_graph(graph_root)
            cfg_before = (graph_root / "logseq" / "config.edn").read_text()

            mgk.bootstrap_graph(graph_root)
            cfg_after = (graph_root / "logseq" / "config.edn").read_text()

            assert cfg_before == cfg_after

    def test_bootstrap_resolves_path(self):
        """Bootstrap returns a resolved Path object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = mgk.bootstrap_graph(tmpdir)
            assert isinstance(result, Path)
            assert result.is_absolute()
            assert result.is_dir()


class TestSoftDelete:
    """Test page backup and soft-delete."""

    def test_backup_page_file(self):
        """Backing up a page creates a copy in .recycle/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_root = Path(tmpdir)
            mgk.bootstrap_graph(graph_root)

            # Create a page
            page = mgk.page_path(graph_root, "Test")
            page.write_text("Original content")

            # Backup it
            backup_path = mgk.backup_page_file(page, graph_root)

            # Original still exists
            assert page.exists()
            assert page.read_text() == "Original content"

            # Backup exists in .recycle/
            assert backup_path.exists()
            assert backup_path.read_text() == "Original content"
            assert backup_path.parent == mgk.recycle_dir(graph_root)

    def test_delete_page_file_soft_delete(self):
        """Soft-deleting moves the file to .recycle/ instead of hard-deleting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_root = Path(tmpdir)
            mgk.bootstrap_graph(graph_root)

            # Create and delete a page
            page = mgk.page_path(graph_root, "Test")
            page.write_text("Content to delete")
            trash_path = mgk.delete_page_file(page, graph_root)

            # Original is gone from pages/
            assert not page.exists()

            # But it's recoverable from .recycle/
            assert trash_path.exists()
            assert trash_path.read_text() == "Content to delete"
            assert trash_path.parent == mgk.recycle_dir(graph_root)
