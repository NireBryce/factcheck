"""restatement: prose stated twice across the docs.

"One pointer per fact": an instructions file carries the always-loaded
summary, skills the on-demand detail, deeper docs the full account, and
a fact stated twice in prose across them is a future stale claim -- the
next change fixes one copy and leaves the other. This check is the
mechanical half: shared word 8-grams between every pair of docs in the
docs scope, merged into contiguous spans, a pair reported once its spans
add up to `min-words`.

Every finding is REVIEW. Some overlap is by design (a one-line index
entry and the article it summarises, a quoted command whose one true home
is a table), and only a reader can say which copy should go. Excluded from
matching: fenced code (commands legitimately repeat), H1 lines (titles
repeat their index entries), and `## Contents` blocks (navigation).

A `<page>.md` / `<page><suffix>.md` sibling pair (the `siblings` check's
convention) restates its source densely on purpose, so it is held back
unless `siblings = true`; counting it would bury every real hit.

    [restatement]
    enable = true
    min-words = 12          # a pair under this isn't reported
    top = 15                # most-overlapping pairs first
    siblings = false        # rank the by-design sibling pairs in too
    exempt-pairs = [["^docs/lessons\\.md$", "^docs/lessons/"]]

`exempt-pairs` lists by-design pairs as [regex, regex] over repo paths;
a pair matching both, in either order, is not reported.

Ported from the check_restatement.py script of the repo factcheck was
extracted from.
"""
import collections
import re

from ..findings import Finding
from ..mdcore import fences
from ..registry import check

NGRAM = 8
HEADING = re.compile(r"^#+\s")
CONTENTS = re.compile(r"^##\s+Contents\s*$")
WORD = re.compile(r"[a-z0-9_]['a-z0-9_.-]*")
SEE = ("the same prose in two docs: keep the fact in one place and point "
       "to it from the other, unless the overlap is by design")


def words_of(text):
    """[(word, lineno)], with fenced lines, H1 lines and the Contents block
    dropped, so by-design repeats don't register."""
    tagged = []
    in_contents = False
    for lineno, line, in_fence in fences.iter_lines(text):
        if in_fence:
            continue
        if CONTENTS.match(line):
            in_contents = True
            continue
        if in_contents:
            if HEADING.match(line):
                in_contents = False
            else:
                continue
        if line.startswith("# "):
            continue
        for word in WORD.findall(line.lower()):
            tagged.append((word, lineno))
    return tagged


def spans_from_shared(shared):
    """Merges (pos_a, pos_b) shingle hits that advance together by one word
    into contiguous spans: [[start_a, start_b, shingles]]."""
    spans = []
    for pa, pb in sorted(shared):
        if spans and pa == spans[-1][0] + 1 and pb == spans[-1][1] + 1:
            spans[-1][2] += 1
        else:
            spans.append([pa, pb, 1])
    return spans


def is_sibling_pair(a, b, suffix):
    tail = f"{suffix}.md"
    for x, y in ((a, b), (b, a)):
        if x.endswith(tail) and x[:-len(tail)] + ".md" == y:
            return True
    return False


def overlaps(files, min_words):
    """[(words, (a, b), spans)] for every pair sharing min_words+, most
    first. `files` is {name: [(word, lineno)]}."""
    index = collections.defaultdict(lambda: collections.defaultdict(list))
    for name, tagged in files.items():
        words = [w for w, _ in tagged]
        for i in range(len(words) - NGRAM + 1):
            index[tuple(words[i:i + NGRAM])][name].append(i)
    pairs = collections.defaultdict(list)
    for positions in index.values():
        names = sorted(positions)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                for pa in positions[a]:
                    for pb in positions[b]:
                        pairs[(a, b)].append((pa, pb))
    out = []
    for pair, shared in pairs.items():
        spans = spans_from_shared(shared)
        total = sum(n + NGRAM - 1 for _, _, n in spans)
        if total >= min_words:
            out.append((total, pair, spans))
    out.sort(reverse=True)
    return out


@check('restatement', order=170)
def check_restatement(root, cfg):
    s = cfg.section('restatement')
    if not s.get('enable'):
        return []
    suffix = cfg.section('siblings').get('suffix', '-for-agents')
    exempt = [(re.compile(a), re.compile(b))
              for a, b in s.get('exempt-pairs', [])]
    files = {p.relative_to(root).as_posix(): words_of(p.read_text())
             for p in cfg.scope('docs')}

    def held_back(a, b):
        if not s.get('siblings') and is_sibling_pair(a, b, suffix):
            return True
        return any((x.search(a) and y.search(b)) or (x.search(b)
                   and y.search(a)) for x, y in exempt)

    hits = [h for h in overlaps(files, s.get('min-words', 12))
            if not held_back(*h[1])]
    findings = []
    for total, (a, b), spans in hits[:s.get('top', 15)]:
        pa, pb, n = max(spans, key=lambda sp: sp[2])
        length = n + NGRAM - 1
        words = [w for w, _ in files[a]]
        text = " ".join(words[pa:pa + length])
        findings.append(Finding(
            'RESTATEMENT', a,
            f"~{total} words shared with {b} in {len(spans)} span(s); "
            f"longest {length}w at {a}:{files[a][pa][1]} and "
            f"{b}:{files[b][pb][1]}: “{text[:100]}”",
            review=True, see=SEE))
    return findings
