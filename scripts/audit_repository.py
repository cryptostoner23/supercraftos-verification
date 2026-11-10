"""Inventory all repository files; statically check maintained source without secrets."""
import ast
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = {'.venv', '.cad-venv', '.git', 'node_modules', '__pycache__', '.build', 'target', 'browser'}
# Text formats where a committed credential would actually be executed or shipped.
SECRET_SCAN_EXTENSIONS = {'.py', '.swift', '.md', '.txt', '.yaml', '.yml', '.toml', '.html', '.plist'}

# 40+ opaque base64url-ish characters. Only flagged when they appear in a
# genuine credential-assignment context, so long URLs, path segments, filenames
# and semantic constants do not produce false positives.
OPAQUE_TOKEN_RE = re.compile(r'\b[A-Za-z0-9_\-]{40,}\b')
# A line is a credential context when an authentication/credential name is
# assigned (KEY/TOKEN/SECRET/PASSWORD/... = ... or ... : ...) or when env
# loading API calls are present.
CRED_CONTEXT_RE = re.compile(
    r'(\b[A-Za-z0-9_]{0,40}_?(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|BEARER)\b'
    r'|getenv|environ|\.env|secrets|token_urlsafe'
    r'|\b(?:key|token|secret|password|passwd|bearer|credential|apikey|api[_-]?key|authorization|jwt|oauth|webhook|signature)\b)'
    r'\s*[=:]',
    re.I,
)
# Known previously leaked credentials are banned outright. Assembled at runtime
# so this scanner does not itself match the pattern it guards.
LEAKED_GATEWAY_KEY_RE = re.compile('BCQM' + 'ChP')
# Hardcoded provider keys. The value must look like a real credential: not a
# <placeholder>, not ${interpolation}, not a Python concatenation, and at least
# 12 characters. This still catches actual committed keys while ignoring docs
# and security-test fixtures.
HARDCODED_PROVIDER_KEY_RE = re.compile(
    r'(BITRISE|REVYL|OPENROUTER|FIRECRAWL|COMPOSIO|HYPERBROWSER|STEEL|AIFLOWCHART|CONTEXT_DEV)'
    r'_?(API_)?KEY\s*=\s*["\'](?![<$])[^"\'\$]{12,}["\']',
    re.I,
)


def _is_credential_value(match: re.Match, line: str) -> bool:
    """True when an opaque token sits in value position rather than as a name.

    Real committed credentials are random opaque string values. A token is only
    treated as a candidate value when it is either quoted or occurs right after
    an assignment separator and right before a value terminator. Tokens that
    are clearly names or readable prose are then suppressed:
      - all-uppercase snake_case names (environment/constant names),
      - multi-word readable phrases joined by separators (e.g. a fake test
        password that reads as English),
      - identifiers used as mapping keys / framework-constant references
        (these are not terminated like a value and are filtered by the
        ``after`` check above).
    """
    token = match.group(0)
    start, end = match.start(), match.end()
    before = line[start - 1:start] if start > 0 else ""
    after = line[end:end + 1] if end < len(line) else ""
    before_ok = before in ("'", '"') or before in ("=", ":", "(", ",", " ", "\t")
    after_ok = after in ("'", '"', ",", ";", ")", "}") or after == ""
    if not (before_ok and after_ok):
        return False
    if re.fullmatch(r'[A-Z0-9_]+', token):
        return False
    words = re.split(r'[_\-]', token)
    if len(words) >= 2 and all(w.isalpha() and w == w.lower() for w in words):
        return False
    return True


def scan_for_secrets(path: Path, text: str):
    issues = []
    try:
        relative = str(path.relative_to(ROOT))
    except ValueError:
        relative = str(path)
    for line_no, line in enumerate(text.splitlines(), start=1):
        has_context = CRED_CONTEXT_RE.search(line) is not None
        for match in OPAQUE_TOKEN_RE.finditer(line):
            if has_context and _is_credential_value(match, line):
                issues.append({'path': relative, 'check': 'potential_secret_opaque_token',
                               'line': line_no})
        if LEAKED_GATEWAY_KEY_RE.search(line):
            issues.append({'path': relative, 'check': 'potential_secret_leaked_gateway_key',
                           'line': line_no})
        for match in HARDCODED_PROVIDER_KEY_RE.finditer(line):
            issues.append({'path': relative, 'check': 'potential_secret_hardcoded_provider_key',
                           'line': line_no})
    return issues


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
                if path.suffix in SECRET_SCAN_EXTENSIONS:
                    try:
                        issues.extend(scan_for_secrets(path, data.decode('utf-8')))
                    except UnicodeError:
                        pass
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
