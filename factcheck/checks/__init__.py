"""The built-in checks. Each submodule registers itself on import via
`@check`; importing this package registers all of them."""
from . import (  # noqa: F401
    anchors, contents, counts, dates, docrefs, generated, links, recipes,
    lessons, rules, siblings, skillfiles, skills, summaries)
