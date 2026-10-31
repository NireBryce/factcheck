"""Markdown link-target parsing.

A link inside code is not a link: GitHub renders ``[t](x.md)`` in a code
span, and every line of a fenced block, as literal text. So link
matching runs on `prose(text)`, which blanks both while keeping every
offset and line number, never on the raw text.
"""
import re

from . import fences

# `[text](target)` -- the target only; `text` isn't checked against anything.
MD_LINK = re.compile(r'\[[^\]]*\]\(([^)]+)\)')

# A code span, CommonMark's way: a run of N backticks, then content, then a
# run of exactly N backticks (a longer or shorter run inside is content).
# The content may wrap a line but not cross a blank line, which ends the
# paragraph. A backslash-escaped backtick opens nothing.
CODE_SPAN = re.compile(
    r'(?<![`\\])(?P<run>`+)(?!`)(?P<body>(?:(?!\n[ \t]*\n).)+?)'
    r'(?<!`)(?P=run)(?!`)', re.S)


def _blank(m):
    return re.sub(r'[^\n]', ' ', m.group(0))


def prose(text):
    """`text` with fenced blocks and inline code spans blanked to spaces,
    newlines kept, so offsets and line numbers still index the original."""
    return CODE_SPAN.sub(_blank, fences.blank_fences(text))


def link_targets(text):
    """Match objects for every markdown link outside code; group(1) is the
    target."""
    return MD_LINK.finditer(prose(text))
