"""Markdown-backed Logseq graph primitives: zero-dependency utilities for creating,
reading, and managing Logseq-style knowledge graphs stored as markdown files."""

import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path

__version__ = "0.1.0"

# --- Title and filename encoding -----

def title_to_filename(title: str) -> str:
    """Convert a page title to its Logseq triple-lowbar filename stem.

    Logseq encodes `/` namespaces as `___` in filenames to match the
    `:file/name-format :triple-lowbar` config setting.
    """
    return title.replace("/", "___")


def filename_to_title(stem: str) -> str:
    """Convert a triple-lowbar filename stem to a page title."""
    return stem.replace("___", "/")


# --- Directory paths -----

def pages_dir(graph_root: Path) -> Path:
    """Return the pages directory for a graph."""
    return Path(graph_root) / "pages"


def journals_dir(graph_root: Path) -> Path:
    """Return the journals directory for a graph."""
    return Path(graph_root) / "journals"


def assets_dir(graph_root: Path) -> Path:
    """Return the assets directory for a graph."""
    return Path(graph_root) / "assets"


def recycle_dir(graph_root: Path) -> Path:
    """Return the trash directory for a graph (soft-delete recovery)."""
    return Path(graph_root) / ".recycle"


def logseq_dir(graph_root: Path) -> Path:
    """Return the logseq config directory for a graph."""
    return Path(graph_root) / "logseq"


def page_path(graph_root: Path, title: str) -> Path:
    """Return the canonical filesystem path for a page (may or may not exist)."""
    return pages_dir(graph_root) / (title_to_filename(title) + ".md")


def journal_filename(d: date) -> str:
    """Return the journal filename for a given date: YYYY_MM_DD.md"""
    return d.strftime("%Y_%m_%d") + ".md"


# --- Config management -----

DEFAULT_CONFIG_SETTINGS = (
    ("file/name-format", ":file/name-format :triple-lowbar"),
    ("journal/page-title-format", ':journal/page-title-format "yyyy/MM/dd"'),
)
"""Default Logseq config.edn settings required for correctness.

- file/name-format :triple-lowbar: REQUIRED. Makes Logseq decode `___` as the `/`
  namespace separator to match title_to_filename(). Without it, namespaced pages
  show as literal `A___B___C` and any [[A/B/C]] link spawns an empty duplicate.
- journal/page-title-format "yyyy/MM/dd": PREFERRED. Dates become namespaced pages
  (Year/Month/Day), giving an automatic time index.
"""


def ensure_graph_config(graph_root: Path) -> None:
    """Ensure the graph's logseq/config.edn declares the required defaults.

    Only adds a setting when its key is absent, so explicit user choices are
    never overwritten. Idempotent; safe to call before any write operations.
    """
    cfg = logseq_dir(graph_root) / "config.edn"
    if cfg.exists() and cfg.stat().st_size > 0:
        text = cfg.read_text(encoding="utf-8")
        additions = [line for key, line in DEFAULT_CONFIG_SETTINGS if key not in text]
        if not additions:
            return
        brace = text.find("{")
        if brace == -1:
            return  # not a recognizable EDN map; don't touch it
        insert = "\n" + "".join(f" {a}\n" for a in additions)
        cfg.write_text(text[:brace + 1] + insert + text[brace + 1:], encoding="utf-8")
    else:
        cfg.parent.mkdir(parents=True, exist_ok=True)
        body = "".join(f" {line}\n" for _key, line in DEFAULT_CONFIG_SETTINGS)
        cfg.write_text("{:meta/version 1\n" + body + "}\n", encoding="utf-8")


# --- Page property parsing -----

_PROPERTY_PATTERN = re.compile(r"^([a-zA-Z0-9_-]+)::\s*(.*)")


def _props_from_lines(stem: str, file_str: str, lines) -> dict:
    """Extract page-level properties from already-read lines.

    Shared by parse_page_properties (disk read). Properties are key:: value
    pairs appearing before the first bullet point.
    """
    props = {"name": stem, "file": file_str}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            break
        m = _PROPERTY_PATTERN.match(stripped)
        if m:
            props[m.group(1).lower()] = m.group(2).strip()
    return props


def parse_page_properties(filepath: Path) -> dict:
    """Return dict of page-level properties from a Logseq .md file.

    Reads the file up to the first bullet point and extracts any key:: value
    pairs found. Returns at least {"name": stem, "file": str(filepath)}.
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError):
        return {"name": filepath.stem, "file": str(filepath)}
    return _props_from_lines(filepath.stem, str(filepath), lines)


def _normalize_prop(value: str) -> str:
    """Strip [[...]] wrappers and leading # for comparison; lowercase."""
    value = value.strip()
    value = re.sub(r"^\[\[(.+)\]\]$", r"\1", value)
    value = re.sub(r"^#", "", value)
    return value.lower()


# --- Page I/O -----

def _backup_timestamp() -> str:
    """Return a timestamp suitable for backup/trash filenames."""
    return datetime.now().strftime("%Y%m%dT%H%M%S")


def backup_page_file(page_file: Path, graph_root: Path) -> Path:
    """Copy page_file's current content into .recycle/<timestamp>-<filename>.

    The original file is left in place. Returns the backup path.
    .recycle/ is a dotdir, so it's already excluded from every read/search tool's
    rglob (they all skip any path component starting with '.').
    """
    trash = recycle_dir(graph_root)
    trash.mkdir(parents=True, exist_ok=True)
    backup_path = trash / f"{_backup_timestamp()}-{page_file.name}"
    backup_path.write_bytes(page_file.read_bytes())
    return backup_path


def delete_page_file(page_file: Path, graph_root: Path) -> Path:
    """Soft-delete: move page_file into .recycle/<timestamp>-<filename>.

    Never a hard delete — the file is fully recoverable from .recycle/.
    Returns the trash path.
    """
    trash = recycle_dir(graph_root)
    trash.mkdir(parents=True, exist_ok=True)
    trash_path = trash / f"{_backup_timestamp()}-{page_file.name}"
    page_file.rename(trash_path)
    return trash_path


def set_page_property(page_path: Path, key: str, value: str) -> tuple:
    """Set or update a property on a page.

    Returns (old_value_or_None, 'added' | 'updated').
    Writes atomically via a temp file. Creates the page if it doesn't exist.
    """
    key_lower = key.lower().strip()
    prop_pattern = re.compile(rf"^{re.escape(key_lower)}\s*::", re.IGNORECASE)

    if page_path.exists():
        lines = page_path.read_text(encoding="utf-8").splitlines(keepends=True)
    else:
        lines = []

    new_line = f"{key_lower}:: {value}\n"
    old_value = None
    action = None

    # Try to find and replace existing property
    for i, line in enumerate(lines):
        if prop_pattern.match(line):
            m = re.match(r"^[^:]+::\s*(.*)", line.rstrip())
            old_value = m.group(1) if m else ""
            lines[i] = new_line
            action = "updated"
            break

    if action is None:
        # Insert before first bullet, or append
        insert_at = len(lines)
        for i, line in enumerate(lines):
            if line.lstrip().startswith(("- ", "* ")):
                insert_at = i
                break
        lines.insert(insert_at, new_line)
        action = "added"

    # Atomic write
    dir_ = page_path.parent
    dir_.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(lines)
        os.replace(tmp, page_path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    return old_value, action


# --- Graph bootstrap -----

def bootstrap_graph(graph_root: str | Path) -> Path:
    """Create and initialize a new Logseq graph at graph_root.

    Creates the directory structure (pages/, journals/, assets/, logseq/)
    and writes a minimal but correct config.edn. Idempotent; safe to call
    on an existing graph.

    Args:
        graph_root: Path to the graph root directory.

    Returns:
        Path object for the graph root (resolved).
    """
    graph_root = Path(graph_root).resolve()

    # Create directory structure
    pages_dir(graph_root).mkdir(parents=True, exist_ok=True)
    journals_dir(graph_root).mkdir(parents=True, exist_ok=True)
    assets_dir(graph_root).mkdir(parents=True, exist_ok=True)

    # Ensure config.edn with required settings
    ensure_graph_config(graph_root)

    return graph_root


__all__ = [
    "title_to_filename",
    "filename_to_title",
    "pages_dir",
    "journals_dir",
    "assets_dir",
    "recycle_dir",
    "logseq_dir",
    "page_path",
    "journal_filename",
    "DEFAULT_CONFIG_SETTINGS",
    "ensure_graph_config",
    "parse_page_properties",
    "backup_page_file",
    "delete_page_file",
    "set_page_property",
    "bootstrap_graph",
]
