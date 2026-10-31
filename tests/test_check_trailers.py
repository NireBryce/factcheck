"""scripts/check_trailers.py and .githooks/commit-msg, against throwaway
repos and message files: the canonical trailer passes, the model-and-email
shape is caught (and rewritten by the hook), other agents pass through."""

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    'check_trailers', ROOT / 'scripts' / 'check_trailers.py')
check_trailers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_trailers)

GOOD = 'Co-Authored-By: Claude'
BAD = 'Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>'
LOWER = 'Co-authored-by: Claude <claude@anthropic.com>'
OTHER = 'Co-Authored-By: ZCode'


def git_env():
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('GIT_')}
    env.update(GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@example.invalid',
               GIT_COMMITTER_NAME='t',
               GIT_COMMITTER_EMAIL='t@example.invalid',
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
    return env


class BadTrailersTest(unittest.TestCase):
    def test_canonical_passes(self):
        self.assertEqual(check_trailers.bad_trailers(f'feat: x\n\n{GOOD}\n'), [])

    def test_model_and_email_caught(self):
        self.assertEqual(check_trailers.bad_trailers(f'x\n\n{BAD}\n'), [BAD])

    def test_any_key_case_caught(self):
        self.assertEqual(check_trailers.bad_trailers(f'x\n\n{LOWER}\n'),
                         [LOWER])

    def test_other_agent_passes(self):
        self.assertEqual(check_trailers.bad_trailers(f'x\n\n{OTHER}\n'), [])


class RangeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        self.env = git_env()
        self.git('init', '-q')
        self.commit(f'chore: base\n\n{GOOD}')

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(['git', '-C', self.repo, *args], env=self.env,
                              check=True, capture_output=True, text=True)

    def commit(self, msg):
        self.git('commit', '-q', '--allow-empty', '--no-verify', '-m', msg)

    def run_check(self):
        return subprocess.run(
            ['python3', str(ROOT / 'scripts' / 'check_trailers.py'),
             'HEAD~1..HEAD'], cwd=self.repo, env=self.env,
            capture_output=True, text=True)

    def test_clean_range_exits_zero(self):
        self.commit(f'feat: ok\n\n{GOOD}')
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('1 commit(s)', r.stdout)

    def test_bad_commit_in_range_exits_one(self):
        self.commit(f'feat: bad\n\n{BAD}')
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn('feat: bad', r.stderr)

    def test_bad_range_exits_two(self):
        r = subprocess.run(
            ['python3', str(ROOT / 'scripts' / 'check_trailers.py'),
             'nope..HEAD'], cwd=self.repo, env=self.env,
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


class CommitMsgHookTest(unittest.TestCase):
    def rewrite(self, body):
        with tempfile.NamedTemporaryFile('w+', suffix='.msg',
                                         delete=False) as f:
            f.write(body)
        try:
            subprocess.run([str(ROOT / '.githooks' / 'commit-msg'), f.name],
                           check=True, capture_output=True)
            return Path(f.name).read_text()
        finally:
            os.unlink(f.name)

    def test_rewrites_model_and_email(self):
        self.assertEqual(self.rewrite(f'feat: x\n\n{BAD}\n'),
                         f'feat: x\n\n{GOOD}\n')

    def test_rewrites_lowercase_key(self):
        self.assertEqual(self.rewrite(f'feat: x\n\n{LOWER}\n'),
                         f'feat: x\n\n{GOOD}\n')

    def test_rewrites_a_wrong_line_beside_a_canonical_one(self):
        self.assertEqual(self.rewrite(f'feat: x\n\n{GOOD}\n{BAD}\n'),
                         f'feat: x\n\n{GOOD}\n{GOOD}\n')

    def test_leaves_canonical_and_other_agents(self):
        body = f'feat: x\n\n{GOOD}\n{OTHER}\n'
        self.assertEqual(self.rewrite(body), body)


class WiringTest(unittest.TestCase):
    """Every hook the settings name exists and is executable, and every
    hook script on disk is named in the settings."""

    def test_settings_and_hooks_agree(self):
        import json
        settings = json.loads((ROOT / '.agents' / 'settings.json').read_text())
        named = set()
        for groups in settings.get('hooks', {}).values():
            for group in groups:
                for h in group['hooks']:
                    cmd = h['command'].replace('"', '')
                    named.add(cmd.replace('$CLAUDE_PROJECT_DIR/', ''))
        on_disk = {f'.agents/hooks/{p.name}'
                   for p in (ROOT / '.agents' / 'hooks').iterdir()}
        self.assertEqual(named, on_disk)
        for rel in named | {'.githooks/commit-msg', '.githooks/pre-push',
                            'scripts/check', 'scripts/check_trailers.py'}:
            self.assertTrue(os.access(ROOT / rel, os.X_OK), rel)

    def test_claude_dir_is_real_with_symlinks_into_agents(self):
        claude = ROOT / '.claude'
        self.assertTrue(claude.is_dir() and not claude.is_symlink())
        for name in ('skills', 'settings.json'):
            self.assertEqual(os.readlink(claude / name), f'../.agents/{name}')
        self.assertEqual(os.readlink(ROOT / 'CLAUDE.md'), 'AGENTS.md')


if __name__ == '__main__':
    unittest.main()
