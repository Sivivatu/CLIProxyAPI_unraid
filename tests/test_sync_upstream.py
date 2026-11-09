import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'scripts/sync-upstream.py'


class SyncTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('sync_upstream', MODULE)
        self.sync = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.sync)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.original = 'ARG UPSTREAM_IMAGE=eceasy/cli-proxy-api:v8.0.56@sha256:' + 'a' * 64 + '\nFROM ${UPSTREAM_IMAGE}\n'
        (self.root / 'Dockerfile').write_text(self.original)

    def release(self, tag='v8.0.61', **extra):
        return dict(tag_name=tag, draft=False, prerelease=False, **extra)

    def manifest(self, architectures=('amd64', 'arm64')):
        return json.dumps({'manifests': [{'platform': {'os': 'linux', 'architecture': a}} for a in architectures]}).encode()

    def test_updates_version_digest_and_metadata_together(self):
        image = self.sync.resolve_image(self.manifest())
        changed = self.sync.update_pin(self.root, self.release(), image)
        self.assertTrue(changed)
        self.assertIn('v8.0.61@' + image, (self.root / 'Dockerfile').read_text())
        metadata = json.loads((self.root / 'upstream-release.json').read_text())
        self.assertEqual(metadata['version'], 'v8.0.61')
        self.assertEqual(metadata['digest'], image)
        self.assertFalse(self.sync.update_pin(self.root, self.release(), image))

    def test_rejects_unstable_or_malformed_releases(self):
        for release in [self.release('v8.0.62-rc.1'), self.release('bad\ninjection'), {'tag_name': 'v8.0.61', 'draft': True}, {'tag_name': 'v8.0.61', 'prerelease': True}, {}]:
            with self.subTest(release=release), self.assertRaises(ValueError):
                self.sync.update_pin(self.root, release, 'sha256:' + 'b' * 64)
        self.assertEqual((self.root / 'Dockerfile').read_text(), self.original)

    def test_refuses_downgrade_and_retagged_version(self):
        for tag in ('v8.0.55', 'v8.0.56'):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.sync.update_pin(self.root, self.release(tag), 'sha256:' + 'b' * 64)
        self.assertEqual((self.root / 'Dockerfile').read_text(), self.original)

    def test_requires_both_native_platforms(self):
        for platforms in [('amd64',), ('arm64',), ()]:
            with self.subTest(platforms=platforms), self.assertRaises(ValueError):
                self.sync.resolve_image(self.manifest(platforms))

    def test_outputs_validated_values_and_noop_flag(self):
        output = self.root / 'output'
        self.sync.write_outputs(output, 'v8.0.61', 'sha256:' + 'b' * 64, False)
        self.assertIn('changed=false\n', output.read_text())
        self.assertIn('image=eceasy/cli-proxy-api:v8.0.61@sha256:', output.read_text())

    def test_cli_uses_release_and_registry_and_writes_outputs(self):
        output = self.root / 'output'
        with patch.object(self.sync, 'github_release', return_value=self.release()), patch.object(self.sync, 'registry_manifest', return_value=self.manifest()):
            self.sync.main(['--root', str(self.root), '--output', str(output)])
        self.assertIn('changed=true', output.read_text())

    def test_rejects_invalid_digest_and_missing_pin(self):
        with self.assertRaises(ValueError):
            self.sync.update_pin(self.root, self.release(), 'invalid')
        (self.root / 'Dockerfile').write_text('FROM scratch\n')
        with self.assertRaises(ValueError):
            self.sync.update_pin(self.root, self.release(), 'sha256:' + 'b' * 64)


if __name__ == '__main__':
    unittest.main()
