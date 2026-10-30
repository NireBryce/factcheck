"""The built-in checks. Each submodule registers itself on import via
`@check`; importing this package registers all of them."""
from . import anchors, contents, dates, links  # noqa: F401
