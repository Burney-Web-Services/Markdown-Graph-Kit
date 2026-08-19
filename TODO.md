# TODO

## Templates — full support for using and editing defined templates

Logseq templates are not first-class in the API yet. Nothing in `markdown_graph_kit`
knows a template exists, reads its properties, or applies one.

- **Discover templates** — a template is marked by a `template::` property on a
  *block*, not the page (page-level `^template::` greps miss it — see the
  `BWS-Templates.md` postmortem in Sèvo's `Story - Domain Brains and the
  C-VO Cortex.md`, 2026-08-09 log: a duplicate page got created because this
  exact distinction was missed). Need a function that finds template blocks
  across pages, not just page properties.
- **Read a template** — return its properties/body in a structured form a
  caller can fill in (name → default value, required vs. optional fields).
- **Apply a template** — instantiate a new page/block from a named template,
  substituting values, without hand-copying the block tree.
- **Edit a template** — update an existing template's fields in place, the
  way `set_page_property` does for a single property today, but template-aware
  (so editing the template doesn't silently orphan pages already created from it).

Motivation: every downstream graph that has this to point to now hand-rolls it or
does without — BWS tickets fill a hand-copied `BWS-Templates.md` block by eye,
and nothing catches drift when the template changes after pages already exist.
