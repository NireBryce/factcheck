"""One definition of "inside a fenced code block".

The ancestor tool's scripts each carried their own fence handling -- with
three different ideas of what opens a fence and none of them matching
CommonMark on when a fence closes, and one pattern defined twice in the
same file with the later one silently winning. This module is the one
definition; checks that care about fences go through it.

The rules are CommonMark's, for a line-based reading (no container blocks):

- A fence opens on a line indented at most 3 spaces that starts with 3 or
  more backticks or tildes. A backtick fence's info string may not itself
  contain a backtick, so ```` ```foo``` bar ```` is inline code, not a
  fence.
- It closes on a line indented at most 3 spaces made of the SAME
  character, at least as many as the opener, and nothing else but
  whitespace. A shorter run, or the other character, is content -- which
  is how a 4-backtick block shows a 3-backtick one.
- An unclosed fence runs to the end of the text.
"""
import re

OPEN = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
CLOSE = re.compile(r'^ {0,3}(`{3,}|~{3,})[ \t]*$')

# What a line is, relative to the fences around it.
TEXT, OPENER, BODY, CLOSER = 'text', 'open', 'body', 'close'


def scan_lines(text):
    """Yields (lineno, line, kind) for each line of `text`, lineno from 1.
    `kind` is TEXT outside a fence, OPENER for the line that opens one,
    BODY inside it, CLOSER for the line that closes it."""
    fence = None  # (char, length) of the open fence
    for lineno, line in enumerate(text.splitlines(), 1):
        if fence is None:
            m = OPEN.match(line)
            if m and not (m.group(1)[0] == '`' and '`' in m.group(2)):
                fence = (m.group(1)[0], len(m.group(1)))
                yield lineno, line, OPENER
            else:
                yield lineno, line, TEXT
            continue
        m = CLOSE.match(line)
        if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1]:
            fence = None
            yield lineno, line, CLOSER
        else:
            yield lineno, line, BODY


def iter_lines(text):
    """Yields (lineno, line, in_fence); the fence's own opening and closing
    lines count as in the fence."""
    for lineno, line, kind in scan_lines(text):
        yield lineno, line, kind != TEXT


def blank_fences(text):
    """`text` with every fenced line -- delimiters included -- blanked to
    spaces, newlines kept: line numbers and character offsets still index
    the original."""
    out = []
    kinds = {n: kind for n, _, kind in scan_lines(text)}
    for n, line in enumerate(text.splitlines(keepends=True), 1):
        if kinds.get(n, TEXT) == TEXT:
            out.append(line)
        else:
            out.append(re.sub(r'[^\r\n]', ' ', line))
    return ''.join(out)
