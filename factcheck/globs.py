"""Glob-to-regex translation for path-glob semantics.

One definition, deliberately: more than one consumer translating the same
glob shape differently is exactly the drift this tool exists to catch.
Semantics: `**/` is zero or more directories, `**` is anything, `*` and
`?` stay within one path segment, `{a,b}` is alternation; brackets are
taken literally."""
import re


def glob_regex(pattern):
    """A repo-relative path glob as a compiled regex (anchored at the end;
    callers match against `re`-full-ish relative paths)."""
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith('**/', i):
            out.append('(?:.*/)?')
            i += 3
            continue
        if pattern.startswith('**', i):
            out.append('.*')
            i += 2
            continue
        if c == '*':
            out.append('[^/]*')
        elif c == '?':
            out.append('[^/]')
        elif c == '{':
            end = pattern.find('}', i)
            if end < 0:
                out.append(re.escape(c))
            else:
                alts = pattern[i + 1:end].split(',')
                out.append('(?:' + '|'.join(re.escape(a) for a in alts) + ')')
                i = end + 1
                continue
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile(''.join(out) + r'\Z')
