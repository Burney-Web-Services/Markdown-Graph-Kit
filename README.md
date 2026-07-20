# markdown-graph-kit

Zero-dependency primitives for Logseq-style markdown knowledge graphs.

**Status**: Alpha. Extracted from [markdown-graph-mcp](https://github.com/pburney/markdown-graph-mcp) and expanded to support graph bootstrapping.

## What's included

- **Title/filename encoding**: Convert between Logseq's `___` (triple-lowbar) namespace encoding and human-readable `/` paths
- **Directory management**: Helpers for pages/, journals/, assets/, and .trash/ directories
- **Config management**: Ensure `logseq/config.edn` declares the required settings for correct namespace handling
- **Page I/O**: Read/write page properties, soft-delete with trash recovery
- **Graph bootstrap**: Initialize a fresh, correctly-formed graph from scratch

## Installation

Clone the repo and install:

```bash
git clone https://github.com/pburney/markdown-graph-kit.git
cd markdown-graph-kit
pip install -e .
```

Or install from GitHub:

```bash
pip install git+https://github.com/pburney/markdown-graph-kit.git
```

## Usage

```python
from markdown_graph_kit import bootstrap_graph, page_path, set_page_property

# Create a new graph
graph_root = bootstrap_graph("path/to/my_graph")

# Write a page property
page = page_path(graph_root, "MyPage")
old_val, action = set_page_property(page, "type", "#MyType")
print(f"Property {action}: {old_val} → #MyType")
```

## API

See `src/markdown_graph_kit/__init__.py` for the full API and docstrings.

### Core functions

- `bootstrap_graph(graph_root)` — create directories and config for a new graph
- `title_to_filename(title)` / `filename_to_title(stem)` — encode/decode namespace paths
- `pages_dir(graph_root)` / `journals_dir(graph_root)` / `assets_dir(graph_root)` — directory paths
- `page_path(graph_root, title)` — canonical path for a page
- `parse_page_properties(filepath)` — extract front-matter from a page
- `set_page_property(page_path, key, value)` — add or update a property
- `backup_page_file(page_file, graph_root)` / `delete_page_file(page_file, graph_root)` — soft-delete with recovery
- `ensure_graph_config(graph_root)` — ensure config.edn has required settings

## Compatibility

- **Python**: ≥3.11
- **Dependencies**: None (pure stdlib)
- **Platforms**: Linux, macOS, Windows (anywhere Python 3.11+ runs)

## License

MIT

## See also

- [markdown-graph-mcp](https://github.com/pburney/markdown-graph-mcp) — MCP server for markdown graph access
