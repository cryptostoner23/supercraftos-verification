# Revyl Skill — Mobile E2E Testing Platform

## What Revyl Provides

Revyl is a mobile real-device testing platform for iOS and Android apps. It enables:

- **Build management**: Build and upload app artifacts (simulator `.app` bundles, `.ipa` files) to cloud runners
- **Device testing**: Run tests on real iOS devices with full device session control
- **Test definitions**: YAML-based test definitions with `step_type` blocks (tap, scroll, input, etc.)
- **Build registration**: Register external builds (e.g., from Bitrise) via URL upload or presigned S3 URL
- **Device sessions**: Start, control, and stop live device sessions for interactive testing
- **Test execution**: Run E2E test journeys against registered builds
- **Reports**: Detailed test execution reports with screenshots, logs, and artifacts

## Environment Constraints (CRITICAL)

**This skill must NOT be run on Linux.** Revyl's cloud build runners require macOS for iOS builds. The local `revyl` CLI can run on Linux for:
- Authentication (`revyl auth login`)
- Build upload (`revyl build upload`)
- Test definition creation and push (`revyl test create`, `revyl test push`)
- Test execution (`revyl test run`)
- Build listing and status (`revyl build list`, `revyl build status`)

iOS app builds (Xcode compilation) MUST run on macOS — either via Bitrise cloud runners or a local Mac with Xcode installed.

## Official Documentation Sources

- Revyl docs: https://docs.revyl.com/
- Revyl CLI reference: https://docs.revyl.com/cli/
- Revyl API: https://backend.revyl.ai/api/v1/
- Revyl app: https://app.revyl.ai/

## Revyl CLI Commands

### Authentication

```bash
# Login with API key
REVYL_API_KEY='<key>' /path/to/revyl auth login --api-key

# Check auth status
/revyl auth status
```

### Build Management

```bash
# List builds for an app
/revyl build list --app <app-id>

# Build from source on Revyl cloud runners (macOS only)
/revyl build --profile <profile-name> --platform ios --version <version> --branch <branch>

# Upload an existing build artifact
/revyl build upload --file <path-to-app.zip> --platform ios --app <app-id> --version <version>

# Register a build from a URL (Bitrise artifact URL, etc.)
/revyl build upload --url <artifact-url> --platform ios --app <app-id> --version <version>

# Check build status
/revyl build status <build-id>

# List test executions for a build
/revyl build runs <build-id>
```

### Test Definitions

```bash
# List tests
/revyl test list

# Create a test interactively
/revyl test create <name> --platform ios --app <app-id> --build-id <build-id>

# Create from YAML file
/revyl test create --from-file .revyl/tests/<name>.yaml --app <app-id>

# Push local test definitions to server
/revyl test push --force

# Run a test
/revyl test run <test-name>

# Cancel a running test
/revyl test cancel <test-name>

# Check test status
/revyl test status <test-name>

# Get test report
/revyl test report <test-name>
```

## Test Definition YAML Schema

```yaml
# Revyl test definition format (test push schema)
app_link: <app-uuid>
metadata:
  name: <test-name>
  platform: ios
build:
  version_id: <build-version-id>
tags:
  - smoke
  - ios
blocks:
  - step_type: tap
    description: Install the SuperCraftOS IPA on the device
  - step_type: tap
    description: Launch the app from the home screen
  - step_type: tap
    description: Verify the app launches successfully without crashing
```

Valid `step_type` values: `tap`, `scroll`, `input`, `wait`, `assert`, `swipe`, `pinch`, `rotate`

## Revyl API Endpoints (backend.revyl.ai)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/apps/{app_id}/builds` | GET | List builds |
| `/api/v1/apps/{app_id}/builds` | POST | Register a build (requires `upload_id` + `version`) |
| `/api/v1/files/upload-url` | POST | Get presigned S3 upload URL (requires `filename`, `content_type`, `file_size`) |
| `/api/v1/tests/get_tests` | GET | List tests |

### Two-Step Build Registration via API

1. **Get presigned upload URL**:
   ```bash
   curl -s -X POST -H "Authorization: Bearer $REVYL_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"filename":"SuperCraftOS.json","content_type":"application/octet-stream","file_size":<bytes>}' \
     "https://backend.revyl.ai/api/v1/files/upload-url"
   ```

2. **Upload file to S3 presigned URL** (PUT with the file body)

3. **Register build**:
   ```bash
   curl -s -X POST -H "Authorization: Bearer $REVYL_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"upload_id":"<uuid>","version":"1.0.0"}' \
     "https://backend.revyl.ai/api/v1/apps/{app_id}/builds"
   ```

**Note**: The `files/upload-url` endpoint does NOT accept `.ipa` extensions. Use `.json` or another allowed extension (`.aac`, `.cer`, `.cfg`, `.conf`, `.crt`, `.csv`, `.der`, `.gif`, `.ini`, `.jpeg`, `.jpg`, `.json`, `.key`, `.m4a`, `.mp3`, `.mp4`, `.p12`, `.pdf`, `.pem`, `.pfx`, `.png`, `.properties`, `.storekit`, `.toml`, `.txt`, `.wav`, `.xml`, `.yaml`, `.yml`).

## Bitrise Integration Flow

1. Build the `.ipa` on Bitrise macOS Xcode stack via `bitrise.yml` `primary` workflow
2. Register the Bitrise build URL with Revyl:
   ```bash
   /revyl build upload --url "<bitrise-build-url>" --platform ios --app <app-id> --version <version>
   ```
3. OR manually upload via two-step API: get upload URL → upload `.ipa` → register build
4. Run Revyl E2E tests against the registered build:
   ```bash
   /revyl test run <test-name>
   ```

## SuperCraftOS Revyl Configuration

- **App ID**: `017e6103-7dbe-4ba3-a910-88575e966048` (SuperCraftOS iOS)
- **Org ID**: `c6a059b5-442d-4f41-afee-4dbacafabd6d`
- **Build version ID**: `834300f6-ff12-4a10-bf70-84eba1392252` (v1.0.0-build-17, pinned to main)
- **Build URL**: https://app.revyl.ai/apps/017e6103-7dbe-4ba3-a910-88575e966048/builds/c4011fff-3fd4-4871-be7d-71f6482d8526
- **Test definitions**: `.revyl/tests/` directory (18 test YAML files)
- **Revyl config**: `.revyl/config.yaml`

## Authentication

```bash
# Authenticate with Revyl API key
echo '<REVYL_API_KEY>' | /path/to/revyl auth login --api-key

# Or set as environment variable
export REVYL_API_KEY='<key>'
/path/to/revyl auth status
```

**Never commit API keys to the repository.** Store them in environment variables or secure secret management.

## Workflow for E2E Testing

```bash
# 1. Authenticate
echo "$REVYL_API_KEY" | revyl auth login --api-key

# 2. Verify build is registered
revyl build list --app 017e6103-7dbe-4ba3-a910-88575e966048

# 3. Run tests
revyl test run fresh-ipa-installation-and-launch
revyl test run onboarding-and-identity-configuration
revyl test run memory-creation-and-retrieval
# ... run all 18 tests

# 4. Check results
revyl test status <test-name>
revyl test report <test-name>
```

## Constraints & Limitations

- **No Linux Xcode builds**: `xcodebuild`, `xcodegen`, `ditto`, `brew` are macOS-only. iOS builds require Bitrise cloud runners or a Mac.
- **`.ipa` not directly uploadable**: Revyl's `files/upload-url` API rejects `.ipa` extensions. Use `.json` extension wrapper or register via `--url` from Bitrise artifact URL.
- **Build credits**: Bitrise cloud builds consume credits. Zero credits = no builds possible.
- **RDE access**: Bitrise Remote Dev Environments require workspace-level RDE User role permission (403 if not granted).
