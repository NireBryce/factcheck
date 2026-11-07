"""The built-in checks. Each submodule registers itself on import via
`@check`; importing this package registers all of them."""
from . import (  # noqa: F401
    anchors, commands, conflicts, contents, counts, dates, docrefs, drift,
    fixrefs, generated, history, issue_refs, lessons, links, paths, pins,
    recipes, restatement, rules, siblings, skillfiles, skills, summaries,
    symbol_refs)
