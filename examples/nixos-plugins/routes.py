"""routes: every routed URL mentioned in the docs resolves to a real path
prefix in the reverse proxy's config.

Narrow on purpose: it catches a route renamed or removed out from under a
doc that still names the old prefix -- not which of handle/handle_path a
doc claims, that nuance shows up in enough different phrasings that
matching it reliably would cost more false positives than it's worth.
Mentions match two shapes: the full FQDN form, or a backticked
`.../name/` shorthand -- deliberately NOT a bare `/name/`, which would
also hit ordinary filesystem paths like `/root/`.

Config (`[routes]`):

    [routes]
    sources = ["flake/modules/homelab-config/homelab/reverse-proxy/caddy/caddy.nix",
               "wiki/config-structure/categories/reverse-proxy-history.md"]
    base-domain = "ts-cube.moose-micro.ts.net"
    kept-path = 'path\\s+/([\\w-]+)\\s+/\\1/\\*'      # prefix kept on the app
    stripped-path = 'handle_path\\s+/([\\w-]+)/\\*'   # prefix stripped

The second source is where this fleet's retired routes are documented:
the docs legitimately name routes that are gone, and the mention check
would otherwise flag every one of them. It has never distinguished live
from retired -- it catches a doc naming a prefix that exists nowhere at
all, which is the whole claim.
"""
import re

from factcheck.findings import Finding
from factcheck.registry import check

DEFAULT_KEPT = r'path\s+/([\w-]+)\s+/\1/\*'
DEFAULT_STRIPPED = r'handle_path\s+/([\w-]+)/\*'


def routes(root, s):
    """path-prefix name -> True if the proxy strips it before reaching the
    app -- read straight out of the configured sources rather than
    assumed."""
    out = {}
    for rel in s.get('sources', []):
        p = root / rel
        if not p.exists():
            continue
        text = p.read_text()
        out.update({name: False
                    for name in re.findall(s.get('kept-path', DEFAULT_KEPT),
                                           text)})
        out.update({name: True
                    for name in re.findall(
                        s.get('stripped-path', DEFAULT_STRIPPED), text)})
    return out


@check('routes', order=70)
def check_routes(root, cfg):
    s = cfg.section('routes')
    known = routes(root, s)
    domain = s.get('base-domain', '')
    domain_rx = (re.escape(domain) + r'/([\w-]+)/') if domain else r'(?!x)x'
    mention = re.compile(domain_rx + r'|`\.\.\./([\w-]+)/`')
    primary = (s.get('sources') or ['the proxy config'])[0]
    findings = []
    for path in cfg.scope('docs'):
        for m in mention.finditer(path.read_text()):
            name = m.group(1) or m.group(2)
            if name not in known:
                findings.append(Finding(
                    'UNKNOWN ROUTE', str(path),
                    f"'/{name}/' is mentioned but {primary.rpartition('/')[2]}"
                    f" has no matching route"))
    return findings
