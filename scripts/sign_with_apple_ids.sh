#!/usr/bin/env bash
# Sign the SuperCraftOS iOS build with several Apple IDs, one after the other.
#
#   scripts/sign_with_apple_ids.sh [options]
#
# Each Apple ID gets its own password, its own two factor code and its own
# signed bundle, so a rate limited account only costs that one account: the
# run continues with the next one and the summary at the end says which
# bundles exist.
#
# The password is typed here, with the echo off, and is handed to the signer
# through the SUPERCRAFTOS_APPLE_PASSWORD environment variable for that one
# run only. It is never written to a file, never passed on a command line,
# never echoed and never in the shell history. The two factor code is typed
# here too and goes straight into the signer's standard input, so it is not
# stored anywhere either.
#
# Options:
#   --app <path.ipa>       the unsigned app to sign
#                          (default: the newest release/ios/SuperCraftOS-iOS-Device-WithKeyboard-unsigned.ipa)
#   --out-dir <dir>        where the signed bundles are written, --out is the
#                          same option
#                          (default: release/ios/signed)
#   --udid <udid[:name]>   a device to sign for, repeatable. When given, these
#                          are the only devices that are signed for.
#   --apple-id <email>     an Apple ID to sign with, repeatable, and a comma
#                          separated list is accepted too. When given, these
#                          are the only accounts that are used.
#   --devices <path>       the device list to read the UDIDs from
#                          (default: data/ios-devices.json)
#   --signer <path>        the sign-for-devices binary
#                          (default: tools/sign-for-devices)
#   --shared-password      type the password once and use it for every account
#   --list-devices         print the devices that would be signed for and stop
#   --dry-run              print the plan and stop, without asking for anything
#   --help                 print this text
#
# The defaults can also be set with SUPERCRAFTOS_APP, SUPERCRAFTOS_OUT,
# SUPERCRAFTOS_DEVICES and SUPERCRAFTOS_SIGNER.
#
# The device list is read defensively. A JSON object with a "devices" list, a
# bare JSON list, and a mapping of UDID to record are all accepted, and each
# record may name the device with "name", "deviceName" or "device".
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The four accounts, in the order they are used. They can be replaced with
# --apple-id, so this list is the only place they are written down.
DEFAULT_APPLE_IDS=(
  "harjeev_kohli@hotmail.com"
  "cryptostoner94@icloud.com"
  "cryptostoner@iloud.com"
  "ngboy69@hotmail.com"
)

APP=""
OUT_DIR=""
SIGNER=""
DEVICES_FILE=""
APPLE_IDS=()
UDIDS=()
LIST_DEVICES=0
DRY_RUN=0
SHARED_PASSWORD=0
SHARED_PASSWORD_VALUE=""

RESULTS_ID=()
RESULTS_STATE=()
RESULTS_PATH=()
RESULTS_DETAIL=()

CERT_COUNT=0
PENDING_CERTS=0
RELAY_HANDLED=0

usage() {
  # The comment block at the top of the file is the usage text.
  awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "$0"
}

say() {
  printf '\n\033[1;35m==> %s\033[0m\n' "$*"
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 2
}

human_size() {
  local bytes="${1:-0}"
  if [ "$bytes" -ge 1048576 ]; then
    printf '%d.%d MB' $((bytes / 1048576)) $(((bytes % 1048576) * 10 / 1048576))
  elif [ "$bytes" -ge 1024 ]; then
    printf '%d.%d kB' $((bytes / 1024)) $(((bytes % 1024) * 10 / 1024))
  else
    printf '%d B' "$bytes"
  fi
}

# The name of the file a bundle is written under. The at sign becomes _at_,
# everything that is not a letter, a digit, a dot, a dash or an underscore
# becomes an underscore.
sanitize() {
  local value="${1,,}"
  value="${value//@/_at_}"
  value="${value//[^a-z0-9._-]/_}"
  printf '%s' "$value"
}

# Read a secret without echoing it. The prompt goes to the terminal, never
# into the captured output, and the value comes back on stdout.
prompt_secret() {
  local prompt="$1" value=""
  if [ -r /dev/tty ]; then
    printf '%s' "$prompt" > /dev/tty
    IFS= read -r -s value < /dev/tty || value=""
    printf '\n' > /dev/tty
  else
    printf '%s' "$prompt" >&2
    IFS= read -r -s value || value=""
    printf '\n' >&2
  fi
  printf '%s' "$value"
}

# Read a plain answer, the team number or the certificate numbers. Not a
# secret, so it is echoed.
prompt_line() {
  local prompt="$1" value=""
  if [ -r /dev/tty ]; then
    printf '%s' "$prompt" > /dev/tty
    IFS= read -r value < /dev/tty || value=""
  else
    printf '%s' "$prompt" >&2
    IFS= read -r value || value=""
  fi
  printf '%s' "$value"
}

# Read the device list. The file is written by another service, so it is read
# defensively: a broken file is a warning, not a crash.
read_devices_json() {
  python3 - "$1" <<'PY'
import json
import re
import sys

path = sys.argv[1]

# Every UDID shape Apple has used: the 40 character one, the 2018 one and the
# usual 8-4-4-4-12 one. The loose check is the last resort.
STRICT = re.compile(
    r"^(?:[0-9A-Fa-f]{40}|[0-9A-Fa-f]{8}-[0-9A-Fa-f]{16}|[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12})$"
)
LOOSE = re.compile(r"^[0-9A-Fa-f][0-9A-Fa-f-]{7,63}$")

UDID_KEYS = ("udid", "deviceudid", "uniqueidentifier", "uniqueid", "device_id", "id")
NAME_KEYS = ("name", "devicename", "displayname", "label", "title")
DEVICE_KEYS = ("device", "model", "product", "devicetype")


def warn(message):
    print("warning: %s" % message, file=sys.stderr)


def field(record, keys):
    lowered = {str(key).lower(): value for key, value in record.items()}
    for key in keys:
        value = lowered.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def entries(data):
    """The device records as (udid hint, record) pairs.

    The hint is the key of a mapping, where the key is the UDID itself.
    """
    if isinstance(data, list):
        return [("", item) for item in data if isinstance(item, (dict, str))]
    if isinstance(data, dict):
        for key in ("devices", "device_list", "devicelist", "results", "items", "records"):
            value = data.get(key)
            if isinstance(value, list):
                return [("", item) for item in value if isinstance(item, (dict, str))]
            if isinstance(value, dict):
                return [(k, v) for k, v in value.items() if isinstance(v, dict)]
        # A mapping of UDID to record.
        if data and all(isinstance(item, dict) for item in data.values()):
            return list(data.items())
    return []


def main():
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read()
    except OSError as error:
        warn("could not read %s: %s" % (path, error))
        return 0
    try:
        data = json.loads(raw)
    except ValueError as error:
        warn("could not parse %s: %s" % (path, error))
        return 0

    seen = set()
    for hint, record in entries(data):
        if isinstance(record, str):
            udid, name = record.strip(), ""
        else:
            udid = field(record, UDID_KEYS) or hint
            name = field(record, NAME_KEYS) or field(record, DEVICE_KEYS)
        udid = udid.strip()
        if not udid:
            continue
        if not (STRICT.match(udid) or LOOSE.match(udid)):
            warn("ignoring %r, it does not look like a UDID" % udid)
            continue
        key = udid.lower()
        if key in seen:
            continue
        seen.add(key)
        # The signer splits "udid:name" on the first colon, so the name must
        # not carry one.
        name = name.replace(":", " ").strip()
        print("%s:%s" % (udid, name) if name else udid)


if __name__ == "__main__":
    main()
PY
}

resolve_app() {
  if [ -n "$APP" ]; then
    [ -f "$APP" ] || die "the app to sign does not exist: $APP"
    APP="$(cd "$(dirname "$APP")" && pwd)/$(basename "$APP")"
    return
  fi
  local dir="$ROOT/release/ios" best="" candidate
  for candidate in "$dir"/SuperCraftOS-iOS-Device-WithKeyboard-unsigned*.ipa; do
    [ -f "$candidate" ] || continue
    if [ -z "$best" ] || [ "$candidate" -nt "$best" ]; then best="$candidate"; fi
  done
  [ -n "$best" ] || die "no unsigned device build found in $dir, build one first or pass --app"
  APP="$best"
}

resolve_devices() {
  if [ "${#UDIDS[@]}" -gt 0 ]; then
    return
  fi
  [ -f "$DEVICES_FILE" ] || die "no devices given and no device list at $DEVICES_FILE, pass --udid"
  local lines
  lines="$(read_devices_json "$DEVICES_FILE")"
  [ -n "$lines" ] || die "the device list at $DEVICES_FILE has no usable devices, pass --udid"
  local line
  while IFS= read -r line; do
    [ -n "$line" ] && UDIDS+=("$line")
  done <<< "$lines"
}

device_name() {
  local entry="$1"
  case "$entry" in
    *:*) printf '%s' "${entry#*:}" ;;
    *) printf '' ;;
  esac
}

device_udid() {
  local entry="$1"
  printf '%s' "${entry%%:*}"
}

print_devices() {
  local entry udid name
  for entry in "${UDIDS[@]}"; do
    udid="$(device_udid "$entry")"
    name="$(device_name "$entry")"
    if [ -n "$name" ]; then
      printf '    %s  %s\n' "$udid" "$name"
    else
      printf '    %s\n' "$udid"
    fi
  done
}

# A prompt of the signer is a line that ends with a colon. Its log lines do
# not, which keeps a line like "SMS 2FA required" or "2FA code already sent"
# from being mistaken for the real two factor prompt.
is_prompt_line() {
  local trimmed="${1%"${1##*[![:space:]]}"}"
  case "$trimmed" in
    *:) return 0 ;;
  esac
  return 1
}

# What kind of prompt is this line? The signer asks for a two factor code,
# for a team when the account has more than one, and for the certificates to
# revoke when the certificate limit is reached. It asks for the password only
# when the environment variable is empty, which this script never allows.
relay_kind() {
  local line="$1" lower
  is_prompt_line "$line" || return 1
  lower="${line,,}"
  case "$lower" in
    *"password"*) printf 'password' ;;
    *"two factor"*|*"two-factor"*|*"verification code"*|*"security code"*|*"2fa code"*|*"2fa-code"*) printf '2fa' ;;
    *"select a team"*) printf 'team' ;;
    *"certificate limit"*) printf 'certs' ;;
    *) return 1 ;;
  esac
}

# Answer one prompt. The two factor code is typed here, without the echo, and
# goes straight into the signer's standard input. It returns 1 when the line
# is not a prompt at all, and sets RELAY_HANDLED when it answered one.
relay_answer() {
  local line="$1" apple_id="$2" kind answer
  RELAY_HANDLED=0
  kind="$(relay_kind "$line")" || return 1
  RELAY_HANDLED=1
  case "$kind" in
    2fa)
      answer="$(prompt_secret "Two factor code for $apple_id: ")"
      if [ -z "$answer" ]; then
        printf '\n  no two factor code given, the signer is told so and this account fails\n'
        # An empty line is still sent, so the signer does not wait forever.
        printf '\n' >&9 || true
        return 0
      fi
      printf '%s\n' "$answer" >&9 || true
      unset answer
      ;;
    team)
      answer="$(prompt_line "Team number [1]: ")"
      printf '%s\n' "${answer:-1}" >&9 || true
      ;;
    certs)
      # The certificates to revoke are listed after this line, so the answer
      # waits until the list has been read.
      PENDING_CERTS=1
      CERT_COUNT=0
      ;;
    password)
      printf '%s\n' "$SUPERCRAFTOS_APPLE_PASSWORD" >&9 || true
      ;;
  esac
  return 0
}

# Answer the certificate question, once the list of certificates is there.
answer_certs() {
  local apple_id="$1" answer
  answer="$(prompt_line "Certificate numbers to revoke [${CERT_COUNT:-1}]: ")"
  printf '%s\n' "${answer:-${CERT_COUNT:-1}}" >&9 || true
}

# Read the signer's output, show it, and answer what it asks for. The output
# is read a character at a time, because the password prompt of the signer has
# no newline at the end of it. A read that times out means the signer is
# waiting, which is also when the certificate list is complete.
relay_loop() {
  local apple_id="$1" buffer="" char status silent=0
  while :; do
    if IFS= read -r -N 1 -t 1 char; then
      silent=0
      if [ "$char" = $'\n' ]; then
        printf '%s\n' "$buffer"
        if [ "$PENDING_CERTS" = 1 ]; then
          case "$buffer" in
            "("*) CERT_COUNT=$((CERT_COUNT + 1)) ;;
            *) answer_certs "$apple_id"; PENDING_CERTS=0 ;;
          esac
        else
          relay_answer "$buffer" "$apple_id" || true
        fi
        buffer=""
      else
        buffer+="$char"
        # A prompt that is not terminated by a newline. The password is the
        # only one the signer prints that way.
        case "$buffer" in
          *": ")
            if relay_answer "$buffer" "$apple_id"; then
              printf '%s' "$buffer"
              [ "$RELAY_HANDLED" = 1 ] && buffer=""
            fi
            ;;
        esac
      fi
    else
      status=$?
      if [ "$status" -gt 128 ]; then
        # Nothing came for a second.
        if [ "$PENDING_CERTS" = 1 ]; then
          answer_certs "$apple_id"
          PENDING_CERTS=0
        fi
        silent=$((silent + 1))
        if [ "$silent" -ge 300 ]; then
          # The signer has been quiet for five minutes. It is probably waiting
          # for a two factor code it did not announce.
          printf '\n  the signer has been quiet for five minutes, asking for a two factor code\n'
          relay_answer "Enter the two factor code:" "$apple_id" || true
          silent=0
        fi
        continue
      fi
      break
    fi
  done
}

# Run the signer for one account. The password is exported for this one
# invocation and unset again straight after.
run_signer() {
  local password="$1" apple_id="$2" out_ipa="$3" workdir fifo status
  workdir="$(mktemp -d "${TMPDIR:-/tmp}/supercraftos-sign.XXXXXX")" || return 1
  fifo="$workdir/stdin"
  if ! mkfifo "$fifo"; then
    rm -rf "$workdir"
    return 1
  fi
  if ! exec 9<>"$fifo"; then
    rm -rf "$workdir"
    return 1
  fi
  PENDING_CERTS=0
  CERT_COUNT=0
  (
    export SUPERCRAFTOS_APPLE_PASSWORD="$password"
    trap 'unset SUPERCRAFTOS_APPLE_PASSWORD' EXIT
    "$SIGNER" --apple-id "$apple_id" "${UDID_ARGS[@]}" --app "$APP" --out "$out_ipa" \
      < "$fifo" 2>&1 | relay_loop "$apple_id"
    exit "${PIPESTATUS[0]}"
  )
  status=$?
  exec 9>&-
  rm -rf "$workdir"
  return "$status"
}

# Sign the app with one account. A failure is recorded, never fatal.
sign_account() {
  local apple_id="$1" out_ipa="$2" password status detail

  printf '\n\033[1;35m--> %s\033[0m\n' "$apple_id"

  if [ "$SHARED_PASSWORD" = 1 ] && [ -n "${SHARED_PASSWORD_VALUE:-}" ]; then
    password="$SHARED_PASSWORD_VALUE"
  else
    password="$(prompt_secret "Apple ID password for $apple_id: ")"
  fi
  if [ -z "$password" ]; then
    record_result "$apple_id" "skipped" "$out_ipa" "no password given"
    printf '  no password given, this account is skipped\n'
    return 0
  fi
  if [ "$SHARED_PASSWORD" = 1 ]; then
    SHARED_PASSWORD_VALUE="$password"
  fi

  status=0
  run_signer "$password" "$apple_id" "$out_ipa" || status=$?
  unset password

  if [ "$status" -eq 0 ] && [ -f "$out_ipa" ]; then
    detail="$(human_size "$(wc -c < "$out_ipa" | tr -d '[:space:]')")"
    record_result "$apple_id" "ok" "$out_ipa" "$detail"
    printf '  signed bundle written to %s\n' "$out_ipa"
    return 0
  fi

  if [ ! -f "$out_ipa" ]; then
    detail="the signer exited with status $status and wrote no bundle"
  else
    detail="the signer exited with status $status"
  fi
  record_result "$apple_id" "failed" "$out_ipa" "$detail"
  printf '  this account failed, continuing with the next one\n'
  return 1
}

record_result() {
  RESULTS_ID+=("$1")
  RESULTS_STATE+=("$2")
  RESULTS_PATH+=("$3")
  RESULTS_DETAIL+=("$4")
}

print_summary() {
  local index total=0 first_ok=""
  say "summary"
  printf '  %-30s %-8s %s\n' "APPLE ID" "STATE" "BUNDLE"
  printf '  %-30s %-8s %s\n' "------------------------------" "--------" "------------------------------"
  for index in "${!RESULTS_ID[@]}"; do
    local entry=""
    if [ "${RESULTS_STATE[$index]}" = "ok" ]; then
      entry="${RESULTS_PATH[$index]} (${RESULTS_DETAIL[$index]})"
      total=$((total + 1))
      [ -n "$first_ok" ] || first_ok="${RESULTS_PATH[$index]}"
    else
      entry="${RESULTS_DETAIL[$index]}"
    fi
    printf '  %-30s %-8s %s\n' "${RESULTS_ID[$index]}" "${RESULTS_STATE[$index]}" "$entry"
  done
  printf '\n  %d of %d accounts produced a signed bundle\n' "$total" "${#RESULTS_ID[@]}"
  if [ -n "$first_ok" ]; then
    printf '\n  Install one on a device with:\n'
    printf '    ideviceinstaller -i %s\n' "$first_ok"
    printf '  or with xcrun devicectl device install app, or through Sideloadly.\n'
    printf '  A free Apple ID profile lasts 7 days, SideStore renews it.\n'
  fi
}

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --app)
        [ $# -ge 2 ] || die "--app needs a value"
        APP="$2"
        shift 2
        ;;
      --out-dir|--out)
        [ $# -ge 2 ] || die "--out-dir needs a value"
        OUT_DIR="$2"
        shift 2
        ;;
      --udid)
        [ $# -ge 2 ] || die "--udid needs a value"
        UDIDS+=("$2")
        shift 2
        ;;
      --apple-id)
        [ $# -ge 2 ] || die "--apple-id needs a value"
        local part
        local -a parts=()
        IFS=',' read -r -a parts <<< "$2"
        for part in "${parts[@]}"; do
          [ -n "$part" ] && APPLE_IDS+=("$part")
        done
        shift 2
        ;;
      --devices)
        [ $# -ge 2 ] || die "--devices needs a value"
        DEVICES_FILE="$2"
        shift 2
        ;;
      --signer)
        [ $# -ge 2 ] || die "--signer needs a value"
        SIGNER="$2"
        shift 2
        ;;
      --shared-password)
        SHARED_PASSWORD=1
        shift
        ;;
      --list-devices)
        LIST_DEVICES=1
        shift
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        printf 'error: unknown argument: %s\n' "$1" >&2
        usage >&2
        exit 2
        ;;
    esac
  done
}

main() {
  parse_args "$@"

  [ -n "$APP" ] || APP="${SUPERCRAFTOS_APP:-}"
  [ -n "$OUT_DIR" ] || OUT_DIR="${SUPERCRAFTOS_OUT:-}"
  [ -n "$SIGNER" ] || SIGNER="${SUPERCRAFTOS_SIGNER:-}"
  [ -n "$DEVICES_FILE" ] || DEVICES_FILE="${SUPERCRAFTOS_DEVICES:-}"
  [ -n "$OUT_DIR" ] || OUT_DIR="$ROOT/release/ios/signed"
  [ -n "$SIGNER" ] || SIGNER="$ROOT/tools/sign-for-devices"
  [ -n "$DEVICES_FILE" ] || DEVICES_FILE="$ROOT/data/ios-devices.json"
  if [ "${#APPLE_IDS[@]}" -eq 0 ]; then
    APPLE_IDS=("${DEFAULT_APPLE_IDS[@]}")
  fi

  resolve_app
  resolve_devices

  # The signer takes the device list as repeated --udid arguments.
  UDID_ARGS=()
  local entry
  for entry in "${UDIDS[@]}"; do
    UDID_ARGS+=(--udid "$entry")
  done

  if [ "$LIST_DEVICES" = 1 ]; then
    print_devices
    exit 0
  fi

  if [ ! -x "$SIGNER" ]; then
    die "the signer is not there: $SIGNER"
  fi

  say "plan"
  printf '  app      %s\n' "$APP"
  printf '  output   %s\n' "$OUT_DIR"
  printf '  signer   %s\n' "$SIGNER"
  printf '  accounts %s\n' "${#APPLE_IDS[@]}"
  printf '  devices\n'
  print_devices

  if [ "$DRY_RUN" = 1 ]; then
    printf '\n  dry run, nothing was signed\n'
    exit 0
  fi

  mkdir -p "$OUT_DIR" || die "could not create $OUT_DIR"

  local apple_id slug
  for apple_id in "${APPLE_IDS[@]}"; do
    slug="$(sanitize "$apple_id")"
    sign_account "$apple_id" "$OUT_DIR/$slug.ipa" || true
  done

  print_summary
}

main "$@"
