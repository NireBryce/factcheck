"""GitHub's own heading-anchor algorithm."""


def github_slug(raw, seen):
    """The slug a GitHub render of heading `raw` gets, reverse-engineered
    against real rendered output rather than assumed: lowercase, drop every
    character that isn't a letter/digit/space/hyphen/underscore -- backticks,
    colons, periods, em-dashes, quotes, slashes, asterisks all just
    disappear, nothing put in their place, so a removed character sitting
    between two spaces leaves a double hyphen once spaces become hyphens,
    and one with no surrounding space glues its two neighbors together with
    none (`` `VMs/_lib/libvirt-vm.nix` `` slugs to `vms_liblibvirt-vmnix`,
    confirmed against a live page, not the `vmslib-libvirt-vmnix` a first
    guess produced) -- then turn each remaining space into a hyphen.

    `seen` is a dict this function mutates so repeated headings on one page
    get GitHub's own `-1`/`-2` suffix instead of colliding; pass a fresh
    `{}` per page, not per heading, and feed it every heading in document
    order (including ones you don't otherwise care about) so the counters
    land where GitHub's would.

    Known gap: operates on the heading's raw source characters, not a
    markdown-aware plain-text extraction -- a heading containing an actual
    `[text](url)` link would slug wrong, since the URL's characters aren't
    stripped as a unit. Backticks, `**bold**`, and `*italic*` are fine,
    since stripping their marker characters one at a time happens to
    produce the same result GitHub's real markdown-aware slugger gives."""
    s = raw.lower()
    s = ''.join(c for c in s if c.isalnum() or c in ' -_')
    s = s.replace(' ', '-')
    n = seen.get(s, 0)
    seen[s] = n + 1
    return s if n == 0 else f'{s}-{n}'
