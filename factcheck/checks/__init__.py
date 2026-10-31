"""The built-in checks. Each submodule registers itself on import via
`@check`; importing this package registers all of them."""
from . import (  # noqa: F401
    anchors, contents, counts, dates, docrefs, drift, fixrefs, generated,
    lessons, links, paths, recipes, restatement, rules, siblings, skillfiles,
    skills, summaries)
