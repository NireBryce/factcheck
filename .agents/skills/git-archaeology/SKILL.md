---
name: git-archaeology
description: Finds the commit that added, changed or removed something when the file has since been renamed or moved.
when_to_use: Asked when something was removed, git log on a file's current path comes back empty, or about to conclude no commit ever touched something.
---

# Finding a change in git history despite renames

## Applies to

You need the commit behind a date or claim you're recording, or "when
was this check, key or comment removed?", and `git log` scoped to the
file's current path came back empty. Also before concluding that no
commit ever touched something: an empty result usually indicts the
pathspec, not the history.

## The issue

`git log -- <path>`, and the pickaxe `-S`/`-G` with a pathspec, match only
commits where *that exact path* changed. A file that was moved or renamed
doesn't match its old path. factcheck itself was extracted from a checker
that lived under another repo's paths, so much of its history isn't in
this repo at all: look in nixos-configs for anything older than the
extraction.

## Steps

1. **Pick a needle that existed verbatim** where you expect the change,
   such as the removed line's own words. A distinctive phrase beats a
   common word.
2. **Search across renames, not paths:**

   ```sh
   git log --all --format='%h %cs %s' -S '<needle>' -- '*<filename>'
   ```

   In a bare wildcard pathspec `*` crosses directory separators, so
   `'*links.py'` matches every path the file has lived at. A distinctive
   needle can drop the pathspec entirely.
3. **Read `%cs`; don't pre-scope with `--since`/`--until`.** Filtering
   results by date is safe; scoping the search with a wrong pathspec is
   what produces the empty result. `%cs` is the committer date, when the
   commit landed.
4. **Verify the hit.** A pickaxe hit means the needle's count changed,
   not that this is *the* commit: a move also changes it. Read it with
   `git show <hash> -- '*<filename>'`.
5. **Record the hash and the date together**, so the claim stays
   checkable after the next rename.

## See also

`fact-hygiene` (where those hashes get recorded). Adapted from
nixos-configs' `git-archaeology` skill.
