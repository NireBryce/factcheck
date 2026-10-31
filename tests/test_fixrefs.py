"""fix-refs: a throwaway git repo, a move, and what the fixer does to every
kind of reference. Each case is one a real reorganisation hit in the repo
the fixer came from, including the two its first pass there missed
(`<...>` links and `$root/`-prefixed paths). Also: the CLI wiring."""
import pathlib
import subprocess
import tempfile
import unittest

from factcheck import cli
from factcheck.checks import fixrefs
from factcheck.config import Config


class Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.root), *a], check=True,
                              capture_output=True, text=True).stdout

    def write(self, path, text):
        f = self.root / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)

    def read(self, path):
        return (self.root / path).read_text()

    def commit_all(self):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")

    def move(self, old, new):
        (self.root / new).parent.mkdir(parents=True, exist_ok=True)
        self.git("mv", old, new)

    def fixer(self, *args, data=None):
        import io, contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = fixrefs.fix_refs(self.root, Config(self.root, data or {}),
                                  list(args))
        return rc, out.getvalue()

    def run_tool(self, *extra, data=None):
        mode = "dry-run" if "--dry-run" in extra else "apply"
        pairs = [e for e in extra if e != "--dry-run"]
        rc, out = self.fixer(mode, *pairs, data=data)
        self.assertEqual(rc, 0, out)
        return out


class Links(Repo):
    def test_links_follow_a_moved_target_and_a_moved_source(self):
        self.write("wiki/hosts.md", "# hosts\n")
        self.write("wiki/other.md", "see [hosts](hosts.md#top) and [x](../README.md)\n")
        self.write("README.md", "# r\n")
        self.commit_all()
        self.move("wiki/hosts.md", "wiki/fleet/hosts.md")
        self.move("wiki/other.md", "wiki/misc/other.md")
        self.run_tool()
        self.assertEqual(self.read("wiki/misc/other.md"),
                         "see [hosts](../fleet/hosts.md#top) and [x](../../README.md)\n")

    def test_angle_bracket_links_are_rewritten(self):
        self.write("wiki/a.md", "[d](<../flake/doc/x.md>)\n")
        self.write("flake/doc/x.md", "x\n")
        self.commit_all()
        self.move("wiki/a.md", "wiki/sub/a.md")
        self.run_tool()
        self.assertEqual(self.read("wiki/sub/a.md"), "[d](<../../flake/doc/x.md>)\n")

    def test_visible_text_that_was_the_target_follows_it(self):
        self.write("wiki/a.md", "[b.md](b.md) and [`b.md`](b.md)\n")
        self.write("wiki/b.md", "b\n")
        self.commit_all()
        self.move("wiki/b.md", "wiki/deep/b.md")
        self.run_tool()
        self.assertEqual(self.read("wiki/a.md"),
                         "[deep/b.md](deep/b.md) and [`deep/b.md`](deep/b.md)\n")

    def test_urls_missing_targets_and_plain_anchors_are_untouched(self):
        body = "[u](https://x.org/wiki/b.md) [m](nope.md) [a](#frag)\n"
        self.write("wiki/a.md", body)
        self.write("wiki/b.md", "b\n")
        self.commit_all()
        self.move("wiki/b.md", "wiki/deep/b.md")
        self.run_tool()
        self.assertEqual(self.read("wiki/a.md"), body)

    def test_reference_style_definitions(self):
        self.write("wiki/a.md", "[b]: b.md\n")
        self.write("wiki/b.md", "b\n")
        self.commit_all()
        self.move("wiki/b.md", "wiki/deep/b.md")
        self.run_tool()
        self.assertEqual(self.read("wiki/a.md"), "[b]: deep/b.md\n")


class BarePaths(Repo):
    def setUp(self):
        super().setUp()
        self.write("wiki/scripts/check.py", "x = 1\n")
        self.write("wiki/scripts/other.py", "y = 1\n")
        self.write("wiki/hosts.md", "h\n")
        self.write("run.sh", "")
        self.commit_all()
        self.move("wiki/scripts/check.py", "wiki/meta/scripts/check.py")
        self.move("wiki/scripts/other.py", "wiki/meta/scripts/other.py")
        self.move("wiki/hosts.md", "wiki/fleet/hosts.md")

    def test_prose_and_code_mentions(self):
        self.write("run.sh", 'python3 wiki/scripts/check.py\nsee wiki/hosts.md.\n')
        self.run_tool()
        self.assertEqual(self.read("run.sh"),
                         'python3 wiki/meta/scripts/check.py\nsee wiki/fleet/hosts.md.\n')

    def test_variable_prefixed_and_dotdot_prefixed_paths(self):
        self.write("run.sh", '[ -f "$root/wiki/scripts/check.py" ]\n'
                             'ln ${root}/wiki/hosts.md\n`../../wiki/hosts.md`\n')
        self.run_tool()
        self.assertEqual(self.read("run.sh"),
                         '[ -f "$root/wiki/meta/scripts/check.py" ]\n'
                         'ln ${root}/wiki/fleet/hosts.md\n`../../wiki/fleet/hosts.md`\n')

    def test_a_longer_path_that_merely_ends_the_same_is_left_alone(self):
        body = "docs/wiki/hosts.md and wiki/hosts.md.bak\n"
        self.write("run.sh", body)
        self.run_tool()
        self.assertEqual(self.read("run.sh"), body)

    def test_whole_directory_is_inferred(self):
        self.write("run.sh", "ls wiki/scripts/ && ls wiki/scripts\n")
        self.run_tool()
        self.assertEqual(self.read("run.sh"),
                         "ls wiki/meta/scripts/ && ls wiki/meta/scripts\n")

    def test_partial_directory_move_is_not_a_directory_move(self):
        self.write("a/x.txt", "x\n")
        self.write("a/y.txt", "y\n")
        self.write("note.md", "a/ and a/y.txt\n")
        self.commit_all()
        self.move("a/x.txt", "b/x.txt")      # a/y.txt stays
        self.run_tool()
        self.assertEqual(self.read("note.md"), "a/ and a/y.txt\n")


class DryRunAndReview(Repo):
    def test_dry_run_writes_nothing_and_lists_files(self):
        self.write("wiki/a.md", "[b](b.md)\n")
        self.write("wiki/b.md", "b\n")
        self.commit_all()
        self.move("wiki/b.md", "wiki/deep/b.md")
        out = self.run_tool("--dry-run")
        self.assertEqual(self.read("wiki/a.md"), "[b](b.md)\n")
        self.assertIn("would rewrite 1 file", out)
        self.assertIn("wiki/a.md", out)

    def test_review_flags_built_paths_and_depth_in_moved_scripts(self):
        self.write("wiki/categories/x.md", "x\n")
        self.write("wiki/scripts/tool.py",
                   "import pathlib\nROOT = pathlib.Path(__file__).resolve().parents[2]\n"
                   "pages = ROOT / 'wiki' / 'categories'\n")
        self.commit_all()
        self.move("wiki/categories/x.md", "wiki/cs/categories/x.md")
        self.move("wiki/scripts/tool.py", "wiki/meta/scripts/tool.py")
        out = self.run_tool()
        self.assertIn("parents[2]", out)
        self.assertIn("builds a moved path from 'categories'", out)

    def test_no_renames_is_an_error_not_a_silent_success(self):
        self.write("a.md", "a\n")
        self.commit_all()
        self.assertEqual(self.fixer("apply")[0], 2)

    def test_explicit_map_covers_a_move_git_did_not_detect(self):
        self.write("a.md", "a\n")
        self.write("n.md", "[a](a.md)\n")
        self.commit_all()
        self.move("a.md", "sub/a.md")
        self.run_tool("a.md=sub/a.md")
        self.assertEqual(self.read("n.md"), "[a](sub/a.md)\n")

    def test_unknown_mode_and_bad_pair_are_usage_errors(self):
        self.write("a.md", "a\n")
        self.commit_all()
        self.assertEqual(self.fixer("go")[0], 2)
        self.assertEqual(self.fixer("apply", "a.md")[0], 2)

    def test_excluded_files_are_not_rewritten(self):
        self.write("wiki/b.md", "b\n")
        self.write("vendor/a.md", "[b](../wiki/b.md)\n")
        self.commit_all()
        self.move("wiki/b.md", "wiki/deep/b.md")
        self.run_tool(data={"fix-refs": {"exclude": ["vendor/*"]}})
        self.assertEqual(self.read("vendor/a.md"), "[b](../wiki/b.md)\n")


class GitEdges(Repo):
    def test_non_ascii_paths_are_rewritten(self):
        self.write("my docs/é.md", "e\n")
        self.write("README.md", "[e](my%20docs/é.md) and `my docs/é.md`\n")
        self.commit_all()
        self.move("my docs/é.md", "my docs/ü.md")
        out = self.run_tool()
        self.assertIn("rewrote 1 file", out)
        self.assertIn("`my docs/ü.md`", self.read("README.md"))

    def test_no_commits_yet_is_an_error_not_a_traceback(self):
        self.write("a.md", "a\n")
        self.git("add", "-A")
        rc, out = self.fixer("apply", "a.md=b.md")
        self.assertEqual(rc, 2)
        self.assertIn("needs at least one commit", out)

    def test_not_a_repo_is_an_error(self):
        import tempfile as tf
        with tf.TemporaryDirectory() as d:
            rc = fixrefs.fix_refs(pathlib.Path(d),
                                  Config(pathlib.Path(d), {}), ["apply"])
            self.assertEqual(rc, 2)


class Cli(Repo):
    def test_exit_status_and_usage_reach_the_cli(self):
        import io
        self.write("a.md", "a\n")
        self.commit_all()
        out = io.StringIO()
        self.assertEqual(cli.main(["--root", str(self.root), "fix-refs"],
                                  out=out), 2)
        self.assertIn("apply|dry-run", out.getvalue())
        self.assertEqual(cli.main(["--root", str(self.root), "fix-refs",
                                   "apply"], out=io.StringIO()), 2)

    def test_apply_from_inside_the_repo_without_root(self):
        import contextlib, io, os
        self.write("wiki/b.md", "b\n")
        self.write("wiki/sub/a.md", "[b](../b.md)\n")
        self.commit_all()
        self.move("wiki/b.md", "wiki/deep/b.md")
        cwd = os.getcwd()
        os.chdir(self.root / "wiki" / "sub")   # a subdirectory, on purpose
        self.addCleanup(os.chdir, cwd)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = cli.main(["fix-refs", "apply"], out=io.StringIO())
        self.assertEqual(rc, 0)
        self.assertEqual(self.read("wiki/sub/a.md"), "[b](../deep/b.md)\n")


if __name__ == "__main__":
    unittest.main()
