"""factcheck: checks the claims a project's documentation makes against the
repository it documents.

Docs drift silently: nothing about a rename, a deleted file, or a changed
config reads the prose that describes it. factcheck extracts structured,
checkable facts from markdown (link targets, recipe mentions, page
conventions, set-claims like "enrolls host X") and compares them against
reality (the filesystem, a justfile, plugin-provided sources).

Layout:

- `registry`   the `@check` registry; registration is the subcommand table
- `findings`   the Finding model: tags, soft REVIEW findings, see-advice
- `config`     factcheck.toml: file scopes, per-check bindings, plugins
- `mdcore`     markdown mechanics: fences, headings, GitHub slugs
- `checks`     the built-in checks
- `plugins`    loading out-of-tree check modules, which register via `@check`

Runs on the standard library alone (3.11+), from a checkout, with no
install -- the same property that lets it live in hooks and CI.
"""
__version__ = '0.1.0'
