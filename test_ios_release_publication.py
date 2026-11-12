"""Release packaging must preserve installed signing state and reject incomplete CI output."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from scripts import build_release_assets as release
from scripts import publish_ios_release as publication
from test_verify_ios_artifacts import build_app, build_keyboard


def fixture_download(out, build):
    for name, make, platform in [
        ('SuperCraftOS-iOS-Simulator.app.zip', build_app, 'iPhoneSimulator'),
        ('SuperCraftOS-iOS-Device-unsigned.app.zip', build_app, 'iPhoneOS'),
        ('SuperCraftOSKeyboard.appex.zip', build_keyboard, None),
    ]:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle = make(base, supported_platform=platform) if platform else make(base)
            with zipfile.ZipFile(out / name, 'w') as archive:
                for path in bundle.rglob('*'):
                    if path.is_file(): archive.write(path, path.relative_to(base))


class IOSReleasePublicationTests(unittest.TestCase):
    def test_missing_artifacts_preserves_existing_release_and_signed_ipa(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'ios'; (out / 'signed').mkdir(parents=True)
            (out / 'signed/personal.ipa').write_bytes(b'existing signed app')
            (out / 'manifest.json').write_bytes(b'existing manifest')
            info = {'status': 'success', 'commit': 'a'*40, 'build_slug': 'fixture'}
            with patch.object(release.subprocess, 'check_output', return_value=json.dumps(info).encode()), \
                 patch.object(release, 'download'), patch('sys.argv', ['release', '--out', str(out)]):
                with self.assertRaisesRegex(ValueError, 'Missing release artifacts'):
                    release.main()
            self.assertEqual((out/'manifest.json').read_bytes(), b'existing manifest')
            self.assertEqual((out/'signed/personal.ipa').read_bytes(), b'existing signed app')

    def test_complete_release_records_source_and_hashes_without_deleting_signed_files(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'ios'; (out / 'signed').mkdir(parents=True)
            (out / 'signed/personal.ipa').write_bytes(b'keep signed app')
            info = {'status': 'success', 'commit': 'b'*40, 'build_slug': 'fixture'}
            with patch.object(release.subprocess, 'check_output', return_value=json.dumps(info).encode()), \
                 patch.object(release, 'download', side_effect=fixture_download), \
                 patch('sys.argv', ['release', '--out', str(out)]):
                self.assertEqual(release.main(), 0)
            result=json.loads((out/'manifest.json').read_text())
            self.assertEqual(result['build']['commit'], 'b'*40)
            self.assertTrue(result['verified'])
            self.assertTrue(result['signing'].startswith('unsigned;'))
            for name,digest in result['sha256'].items():
                self.assertEqual(hashlib.sha256((out/name).read_bytes()).hexdigest(),digest)
            self.assertEqual((out/'signed/personal.ipa').read_bytes(),b'keep signed app')

class PublicationTests(unittest.TestCase):
    def test_bad_hash_never_replaces_public_download(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'source'; dest=root/'public'
            source.mkdir();dest.mkdir()
            (source/'app.ipa').write_bytes(b'corrupted upload')
            (dest/'app.ipa').write_bytes(b'previous release')
            (source/'manifest.json').write_text(json.dumps({'verified':True,
                'build':{'commit':'a'*40},'sha256':{'app.ipa':'0'*64}}))
            with self.assertRaisesRegex(ValueError,'does not match'):
                publication.publish(source,dest)
            self.assertEqual((dest/'app.ipa').read_bytes(),b'previous release')

if __name__ == '__main__': unittest.main()
