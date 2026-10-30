"""Heading iteration that knows about fenced code blocks."""
import re

from . import fences

HEADING = re.compile(r'^(#{1,6})\s+(.+?)\s*$')


def iter_headings(text):
    """Yields (level, raw_heading_text) for every real heading line -- `#`
    through `######` -- in document order, skipping anything inside a fenced
    code block. Without the fence tracking, a shell comment like `# or,
    one-off:` inside a ```sh block would be misread as a level-1 heading."""
    for _, line, in_fence in fences.iter_lines(text):
        if in_fence:
            continue
        m = HEADING.match(line)
        if m:
            yield len(m.group(1)), m.group(2)


def first_section(text):
    """The page's first `## ` heading other than `## Contents`, or None."""
    for line in text.splitlines():
        if line.startswith('## ') and line[3:].strip() != 'Contents':
            return line[3:].strip()
    return None
