"""factcheck's own README checks table, as a generated region.

The rows are the registry: every registered check in run order, then the
fixers. A check that registers without a row gets one with empty
hand-written cells, which the `generated` check reports until someone
describes it; a check that is removed loses its row. The two prose
columns, what it checks and what config binds it, are hand-written and
kept per row.

Loaded through factcheck.toml's `[plugins]`, so it applies to this repo
only: a consumer's run never sees it. Regenerate with
`factcheck fix-generated README.md`.
"""
from factcheck import fixers, genregions, registry

KEY = 'check'
HAND = ['claims it checks', 'bindings (config)']


def rows(root):
    for name, _ in registry.registered():
        yield name, {KEY: f'`{name}`'}
    for name in sorted(fixers.FIXERS):
        yield name, {KEY: f'`{name}`'}


genregions.register(genregions.Region(
    name='checks-table', page='README.md',
    source='the check and fixer registries',
    headers=[KEY, *HAND], key=KEY, hand=HAND, rows_fn=rows))
