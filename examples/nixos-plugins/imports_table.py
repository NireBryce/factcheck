"""The membership checks: a category's "Imported by" prose and its Index-
table cell must name every host that actually imports the category, and a
host named there must actually import it (or be phrased as an exclusion).

The mechanism is generic membership prose checking; the bindings -- the
categories pages directory, the "Imported by" heading, the Index table
shape -- are this repo's conventions, so this is a plugin, configured
under `[imports]`.

The exclusion-cue heuristic is deliberately narrow, and the narrowness is
the point: prose legitimately names a host to say it does NOT import the
category, and the docs do that constantly and on purpose. Flagging every
such mention produced 25 findings that were every one of them correct
prose -- exactly the volume that trains a reader to skim past the one
real stale inclusion. Only a mention with no exclusion/indirect cue in
its own clause is flagged, and a clause is bounded by punctuation, blank
line, or table pipe -- a bare newline is NOT a boundary, because the docs
hard-wrap prose and a wrapped sentence once read as two clauses.
"""
import re

from factcheck.checks.counts import NUMWORD
from factcheck.findings import Finding
from factcheck.registry import check

import tree

SEE = ("an import list the tree stopped agreeing with: re-read the page "
       "against the host's actual includes")

EXCLUSION_CUE = re.compile(
    r"\b(?:not|never|neither|nor|without|exclude[sd]?|excluded|absent|"
    r"absence)\b", re.I)
INDIRECT_CUE = re.compile(r"\bvia\b", re.I)
_CLAUSE_SPLIT = re.compile(r'(?:[.;]\s+|\n\s*\n|\|)')
IMPORTED_BY_HEADING = re.compile(r'^##\s+Imported by\s*$', re.M)
NEXT_HEADING = re.compile(r'^##\s+', re.M)
INDEX_HEADING = re.compile(r'^##\s+Index\s*$', re.M)
# One Index table row: `| [name](link) | dir | class | imported-by |`. The
# name comes from the link TEXT, not its target -- a row may link the
# category's nested index page instead of its own page.
INDEX_ROW = re.compile(
    r'^\|\s*\[(?P<name>[\w-]+)\]\([^)]*\)\s*\|(?P<dir>[^|]*)\|'
    r'(?P<cls>[^|]*)\|(?P<imp>[^|]*)\|\s*$', re.M)


def _blanket_phrase(count, tail):
    """'all four hosts' / 'All three NixOS hosts' -- a page may claim
    blanket coverage instead of naming every host. N is the roster's own
    count, so a phrase that went stale when a host was added covers
    nothing and the unnamed hosts are reported."""
    spelled = [w for w, n in NUMWORD.items() if n == count] + [str(count)]
    return re.compile(rf'\ball\s+(?:{"|".join(spelled)})\s+{tail}\b', re.I)


def _clauses_mentioning(section, host):
    return [c for c in _CLAUSE_SPLIT.split(section) if host in c]


def imported_by_findings(where, category, hosts, section, shorts, nixos,
                         class_label='NixOS'):
    """Shared by the page-section and table-cell callers: same heuristic,
    same two shapes. Blanket coverage removes the hosts it actually
    covers; the rest must be named; a named non-importer is REVIEW unless
    its own clause carries an exclusion or indirect cue."""
    findings = []
    covered = set()
    if _blanket_phrase(len(nixos), class_label + r'\s+hosts').search(section):
        covered |= nixos
    if _blanket_phrase(len(shorts), r'hosts').search(section):
        covered |= set(shorts)
    for host in hosts - covered:
        if host not in section:
            findings.append(Finding(
                'MISSING', str(where),
                f"'{category}' is imported by '{host}' but the host isn't "
                f"named in Imported by", see=SEE))
    for host in shorts:
        if host not in hosts:
            for clause in _clauses_mentioning(section, host):
                if EXCLUSION_CUE.search(clause) or INDIRECT_CUE.search(clause):
                    continue
                findings.append(Finding(
                    'REVIEW', str(where),
                    f"'{host}' is named in Imported by but does not actually "
                    f"import '{category}' -- confirm this is phrased as an "
                    f"exclusion, not a stale inclusion", review=True))
                break
    return findings


def _settings(cfg):
    s = cfg.section('imports')
    return {
        'pages': s.get('pages-dir', 'wiki/config-structure/categories'),
        'class_label': s.get('class-label', 'NixOS'),
        'index': s.get('index-page',
                       'wiki/config-structure/categories/00-INDEX.md'),
    }


def _by_category(root, categories):
    imports = tree.host_imports(root, categories, tree.roster(root)[0])
    by_category = {}
    for host, names in imports.items():
        for n in names:
            by_category.setdefault(n, set()).add(host)
    return by_category


@check('imports', order=10)
def check_imports(root, cfg):
    st = _settings(cfg)
    categories = tree.find_categories(root)
    by_category = _by_category(root, categories)
    shorts, nixos = tree.roster(root)
    pages = root / st['pages']
    suffix = cfg.section('siblings').get('suffix', '-for-agents')
    findings = []
    for category, hosts in sorted(by_category.items()):
        page = pages / f'{category}.md'
        if not page.exists():
            continue  # no page to check this category against
        # The `-for-agents` sibling may carry its own "Imported by" -- both
        # copies are checked; only absence from both is a finding.
        sib = pages / f'{category}{suffix}.md'
        checked = False
        for candidate in (page, sib):
            if not candidate.exists():
                continue
            text = candidate.read_text()
            m = IMPORTED_BY_HEADING.search(text)
            if not m:
                continue
            checked = True
            rest = text[m.end():]
            end = NEXT_HEADING.search(rest)
            section = rest[:end.start()] if end else rest
            findings += imported_by_findings(
                candidate, category, hosts, section, shorts, nixos,
                st['class_label'])
        if not checked:
            findings.append(Finding(
                "NO 'Imported by' SECTION", str(page),
                f"(nor {sib.name})" if sib.exists() else "", see=SEE))
    return findings


@check('table', order=20)
def check_table(root, cfg):
    """The Imported by cells of the categories index page's tables -- the
    one hand-written column there; the rest is generated regions'."""
    st = _settings(cfg)
    categories = tree.find_categories(root)
    by_category = _by_category(root, categories)
    shorts, nixos = tree.roster(root)

    index_page = root / st['index']
    text = index_page.read_text()
    m = INDEX_HEADING.search(text)
    if not m:
        return [Finding("NO 'Index' SECTION", str(index_page), "")]
    rest = text[m.end():]
    end = NEXT_HEADING.search(rest)
    section = rest[:end.start()] if end else rest
    findings = []
    for row in INDEX_ROW.finditer(section):
        name = row.group('name')
        if name not in categories:
            continue  # the header or separator row
        findings += imported_by_findings(
            f"{index_page} row for '{name}'", name,
            by_category.get(name, set()), row.group('imp'), shorts, nixos,
            st['class_label'])
    return findings
