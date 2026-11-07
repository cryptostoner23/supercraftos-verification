#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM_COMMIT="fc7a81a6de678aa707e05399ffafb8be0ad56921"
BUILD_ROOT="${TMPDIR:-/tmp}/supercraftos-isideload-build"
rm -rf "$BUILD_ROOT"
git clone --quiet https://github.com/nab138/isideload.git "$BUILD_ROOT"
git -C "$BUILD_ROOT" checkout --quiet "$UPSTREAM_COMMIT"
mkdir -p "$BUILD_ROOT/examples/minimal/src/bin"
cp "$ROOT/native/ios-signer/sign-for-devices.rs" "$BUILD_ROOT/examples/minimal/src/bin/sign-for-devices.rs"
python3 - "$BUILD_ROOT/examples/minimal/Cargo.toml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
text = text.replace('isideload = { path = "../../isideload" }',
                    'isideload = { path = "../../isideload", features = ["fs-storage"] }')
path.write_text(text)
PY
cargo build --release --manifest-path "$BUILD_ROOT/Cargo.toml" -p minimal --bin sign-for-devices
install -m 0755 "$BUILD_ROOT/target/release/sign-for-devices" "$ROOT/tools/sign-for-devices.new"
mv "$ROOT/tools/sign-for-devices.new" "$ROOT/tools/sign-for-devices"
echo "built tools/sign-for-devices from isideload $UPSTREAM_COMMIT"
