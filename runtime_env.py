"""Load local credentials without logging values or overwriting process settings."""
import os
import fcntl
import re
import tempfile
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
PROVIDER_CREDENTIAL_NAMES = frozenset({
    'HYPERBROWSER_API_KEY', 'STEEL_API_KEY', 'FIRECRAWL_API_KEY',
    'PEERPUSH_API_KEY', 'DEVHUNT_API_KEY', 'COMPOSIO_API_KEY',
    'AIRTABLE_API_KEY', 'HYRVE_API_KEY', 'SKYFIRE_API_KEY', 'OPENCODE_GO_API_KEY', 'OPENROUTER_API_KEY',
})


def _credential_valid(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9._~+/=-]{12,4096}', value) is not None


def _provider_values(path):
    if not path.exists():
        return {}
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError('Provider credential file must be private and not a symlink')
    with path.open() as handle:
        text = handle.read(65537)
    if len(text) > 65536:
        raise ValueError('Provider credential file exceeds size limit')
    values = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([A-Z0-9_]+)=(?:'([^']*)'|\"([^\"]*)\"|([^\s#]*))", line)
        if match:
            name, *candidates = match.groups()
            value = next((item for item in candidates if item is not None), '')
            if name in PROVIDER_CREDENTIAL_NAMES and _credential_valid(value):
                values[name] = value
    return values


def load_provider_credentials(path=None, *, environ=None):
    """Load only known credential names; explicit server settings take precedence."""
    target = os.environ if environ is None else environ
    values = _provider_values(Path(path) if path is not None else ROOT / 'data/provider-credentials.env')
    restored = 0
    for name, value in values.items():
        if not target.get(name):
            target[name] = value
            restored += 1
    return restored


def persist_provider_credential(name, value, path=None):
    """Atomically merge private credentials in writable data, never in source/root."""
    if name not in PROVIDER_CREDENTIAL_NAMES or not _credential_valid(value):
        raise ValueError('Unsupported provider credential')
    path = Path(path) if path is not None else ROOT / 'data/provider-credentials.env'
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_fd = os.open(path.with_suffix('.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'a') as lock:
        os.fchmod(lock.fileno(), 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        values = _provider_values(path)
        values[name] = value
        descriptor, temporary = tempfile.mkstemp(prefix='.provider-credentials-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'w') as handle:
                for key, credential in sorted(values.items()):
                    handle.write(f"{key}='{credential}'\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def load_environment():
    # Explicit locations win over the home-directory fallback.
    for path in (Path('/.env'), ROOT / '.env', Path('/root/.env')):
        try:
            load_dotenv(path, override=False)
        except OSError:
            # A non-root deployment cannot traverse another user's home.
            continue
    aliases = {
        'GMAIL_ADDRESS': ('Gmail_USERNAME', 'GMAIL_USERNAME'),
        'GMAIL_LOGIN_PASSWORD': ('GMAIL_PASSWORD',),
        'STEEL_API_KEY': ('STEELDEV_API',),
        'BROWSERLESS_TOKEN': ('BROWSERLESS_API_KEY',),
    }
    for canonical, candidates in aliases.items():
        if not os.getenv(canonical):
            for candidate in candidates:
                if os.getenv(candidate):
                    os.environ[canonical] = os.environ[candidate]
                    break
    try:
        load_provider_credentials()
    except (OSError, ValueError):
        pass
    # A Gmail account password is not assumed to be an IMAP app password.
    # Restore AES-GCM-stored provider credentials into the live process env so the
    # app is fully equipped on restart without re-entering keys. Only fills variables
    # that are not already set (process env and .env always win); never writes or
    # logs secrets. Lazy import avoids a module cycle.
    try:
        from notion_db_setup import restore_environment_secrets
        restore_environment_secrets()
    except Exception:
        pass
    # Explicitly reconnected credentials supersede the rejected deployment key.
    # This file is private, allowlisted and written only after authentication.
    try:
        recovered = _provider_values(ROOT / 'data/reconnected-providers.env')
        for name, value in recovered.items():
            if name in PROVIDER_CREDENTIAL_NAMES:
                os.environ[name] = value
    except (OSError, ValueError):
        pass
