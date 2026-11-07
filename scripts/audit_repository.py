"""Inventory all repository files; statically check maintained source without secrets."""
import ast
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = {'.venv', '.cad-venv', '.git', 'node_modules', '__pycache__', '.build', 'target', 'browser'}


def main():
    inventory = []
    issues = []
    source_count = 0
    for directory, directories, filenames in os.walk(ROOT, followlinks=False):
        for filename in filenames:
            path = Path(directory) / filename
            relative = path.relative_to(ROOT)
            try:
                size = path.lstat().st_size
            except OSError:
                issues.append({'path': str(relative), 'check': 'stat_failed'})
                continue
            generated = any(part in GENERATED for part in relative.parts) or relative.parts[0] in {'data', 'agent-brain'}
            record = {'path': str(relative), 'bytes': size, 'scope': 'dependency_or_artifact' if generated else 'maintained'}
            if not generated and path.suffix in {'.py', '.swift', '.rs', '.html', '.yaml', '.toml', '.md', '.txt', '.lock'} and not path.is_symlink():
                data = path.read_bytes()
                record['sha256'] = hashlib.sha256(data).hexdigest()
                source_count += 1
                if path.suffix in {'.py', '.swift'}:
                    try:
                        text = data.decode('utf-8')
                        if path.suffix == '.py': ast.parse(text)
                        elif b'\r' in data or '```' in text: issues.append({'path': str(relative), 'check': 'swift_raw_format'})
                    except (UnicodeError, SyntaxError): issues.append({'path': str(relative), 'check': 'syntax_or_encoding'})
            inventory.append(record)
    report = {'total_files_inventoried': len(inventory), 'maintained_files_hashed': source_count,
              'issues': issues, 'scope': 'All files inventoried by metadata; maintained text hashed and Python parsed. Dependencies, binary artifacts and external agent-brain are not semantically audited.',
              'files': inventory}
    target = ROOT / 'data/audit/inventory.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2))
    target.chmod(0o600)
    print(json.dumps({key: value for key, value in report.items() if key != 'files'}))
    return bool(issues)


if __name__ == '__main__':
    raise SystemExit(main())
