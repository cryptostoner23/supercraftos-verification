"""Build a reproducible App Playground archive and mirror its shared core for tests."""
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'ios_app_dist'
BUNDLE = DIST / 'YourApp.swiftpm'
CATALOG = ROOT / 'swift-verification/Sources/ControlCore/KeyboardCatalog.swift'
CORE = ('AppConfig.swift', 'AgentModels.swift', 'BackendClient.swift', 'CredentialStore.swift', 'CIBackendFixture.swift')


def main():
    BUNDLE.mkdir(parents=True, exist_ok=True)
    sources = sorted(DIST.glob('*.swift'))
    # Validate all inputs before replacing any generated copy.
    for source in [*sources, CATALOG, BUNDLE / 'App.swift', BUNDLE / 'Package.swift']:
        data = source.read_bytes(); data.decode('utf-8')
        if b'\r' in data or b'```' in data or not data.endswith(b'\n'):
            raise ValueError('Swift source must be raw UTF-8 with LF endings')
    names = ['App.swift', 'Package.swift', 'KeyboardCatalog.swift', *(source.name for source in sources)]
    for stale in BUNDLE.glob('*.swift'):
        if stale.name not in names:
            stale.unlink()
    for source in sources:
        shutil.copyfile(source, BUNDLE / source.name)
    core = ROOT / 'swift-verification/Sources/ControlCore'
    core.mkdir(parents=True, exist_ok=True)
    for name in CORE:
        shutil.copyfile(DIST / name, core / name)
    shutil.copyfile(CATALOG, BUNDLE / 'KeyboardCatalog.swift')
    archive = DIST / 'YourApp.swiftpm.zip'
    with tempfile.TemporaryDirectory(dir=DIST) as temporary:
        candidate = Path(temporary) / archive.name
        with zipfile.ZipFile(candidate, 'w', zipfile.ZIP_DEFLATED) as output:
            for name in sorted(names):
                info = zipfile.ZipInfo('YourApp.swiftpm/' + name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                output.writestr(info, (BUNDLE / name).read_bytes())
        with zipfile.ZipFile(candidate) as verification:
            if verification.testzip() is not None: raise RuntimeError('Archive verification failed')
            for name in names:
                if verification.read('YourApp.swiftpm/' + name) != (BUNDLE / name).read_bytes():
                    raise RuntimeError('Archive source mismatch')
        candidate.replace(archive)
    result = {'archive': str(archive), 'files': sorted(names), 'bytes': archive.stat().st_size,
              'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'raw_exports_match': True, 'utf8_lf': True,
              'catalog_sha256': hashlib.sha256(CATALOG.read_bytes()).hexdigest()}
    report = ROOT / 'data/audit/package-verification.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
