"""Offline IPA/installer tests. No Apple session, signer service or network calls."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
import importlib.util
import io
from pathlib import Path
import plistlib
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("ios_device_install", ROOT / "scripts/ios_device_install.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)
UDID = "00008030-001A2B3C4D5E6F70"
APP_ID = "com.supercraftos.control"
APP_ROOT = "Payload/SuperCraftOS.app/"


def profile(identifier=APP_ID, *, expired=False, udid=UDID):
    return {"ExpirationDate": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=-1 if expired else 6),
            "ProvisionedDevices": [udid],
            "Entitlements": {"application-identifier": "TESTTEAM01." + identifier}}


def make_ipa(path, *, signed=False, extension=False, minimum="17.0", platform="iPhoneOS",
             expired=False, udid=UDID, bundle_version="1", extension_signed=True):
    """Synthetic metadata, not a real Mach-O or Apple code signature."""
    with zipfile.ZipFile(path, "w") as archive:
        bundles = [(APP_ROOT, APP_ID, minimum)]
        if extension:
            bundles.append((APP_ROOT + "PlugIns/Keyboard.appex/", APP_ID + ".keyboard", "26.0"))
        for index, (prefix, identifier, min_os) in enumerate(bundles):
            archive.writestr(prefix + "Info.plist", plistlib.dumps({
                "CFBundleIdentifier": identifier, "CFBundleVersion": bundle_version,
                "CFBundleExecutable": "Executable", "MinimumOSVersion": min_os,
                "CFBundleSupportedPlatforms": [platform],
                "SUPERCRAFTOSBackendURL": "https://agent.commetai.ca"}))
            executable = zipfile.ZipInfo(prefix + "Executable")
            executable.create_system = 3
            executable.external_attr = (stat.S_IFREG | 0o755) << 16
            archive.writestr(executable, b"fixture executable")
            if signed and (index == 0 or extension_signed):
                archive.writestr(prefix + "_CodeSignature/CodeResources", b"fixture marker")
                archive.writestr(prefix + "embedded.mobileprovision",
                                 plistlib.dumps(profile(identifier, expired=expired, udid=udid)))
    return path


class InstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.ipa = make_ipa(self.directory / "app.ipa")
        self.addCleanup(patch.stopall)
        patch.object(installer.urllib.request, "build_opener",
                     side_effect=AssertionError("network forbidden in offline tests")).start()

    def invoke(self, arguments):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            result = installer.main(arguments)
        return result, output.getvalue() + errors.getvalue()

    def prepare(self, *arguments):
        return self.invoke(["prepare", "--ipa", str(self.ipa), "--no-open", *arguments])

    def signed(self, *arguments):
        return self.invoke(["install-signed", "--ipa", str(self.ipa), "--udid", UDID, *arguments])

    def mock_mac(self, *, modern=True, fail_command=None):
        patch.object(installer.platform, "system", return_value="Darwin").start()
        patch.object(installer.shutil, "which", side_effect=lambda name: "/tools/" + name).start()
        self.commands = []

        def run(command, **kwargs):
            self.commands.append(command)
            if fail_command and fail_command(command):
                raise subprocess.CalledProcessError(1, command)
            if command[:3] == ["security", "cms", "-D"]:
                return subprocess.CompletedProcess(command, 0, Path(command[-1]).read_bytes(), b"")
            if command[-1] == "--help":
                usage = "Commands:\n  install PATH   Install IPA\n" if modern else " -i, --install FILE\n"
                return subprocess.CompletedProcess(command, 0, usage, "")
            if command[:5] == ["xcrun", "devicectl", "device", "install", "app"]:
                app = Path(command[-1])
                self.assertTrue(app.is_dir())
                self.assertTrue((app / "Executable").stat().st_mode & stat.S_IXUSR)
            return subprocess.CompletedProcess(command, 0, b"", b"")

        patch.object(installer.subprocess, "run", side_effect=run).start()

    def install_commands(self):
        return [cmd for cmd in self.commands
                if (cmd[0].endswith("ideviceinstaller") and "--help" not in cmd)
                or cmd[:5] == ["xcrun", "devicectl", "device", "install", "app"]]

    def test_prepare_reports_actual_floor_and_not_installed(self):
        result, output = self.prepare("--ios-version", "17.0")
        self.assertEqual(result, 0, output)
        self.assertIn("iOS/iPadOS 17.0", output)
        self.assertIn("NOT installed", output)
        self.assertIn("7 days", output)

    def test_extension_floor_is_checked_too(self):
        make_ipa(self.ipa, extension=True)
        result, output = self.prepare("--ios-version", "18.5")
        self.assertEqual(result, 1)
        self.assertIn("below the bundle minimum 26.0", output)

    def test_checksum_mismatch_is_failure(self):
        result, output = self.prepare("--sha256", "0" * 64)
        self.assertEqual(result, 1)
        self.assertNotIn("Prepared", output)

    def test_simulator_is_rejected(self):
        make_ipa(self.ipa, platform="iPhoneSimulator")
        result, output = self.prepare()
        self.assertEqual(result, 1)
        self.assertIn("not a simulator", output)

    def test_malformed_zip_is_failure(self):
        self.ipa.write_bytes(b"PK fake signing success")
        self.assertEqual(self.prepare()[0], 1)

    def test_traversal_and_symlink_are_rejected(self):
        for name, mode in [("../escape", stat.S_IFREG | 0o644),
                           (APP_ROOT + "link", stat.S_IFLNK | 0o777)]:
            with self.subTest(name=name):
                make_ipa(self.ipa)
                with zipfile.ZipFile(self.ipa, "a") as archive:
                    item = zipfile.ZipInfo(name)
                    item.external_attr = mode << 16
                    archive.writestr(item, b"/tmp")
                self.assertEqual(self.prepare()[0], 1)

    def test_failed_download_preserves_previous_file_and_cleans_temp(self):
        previous = self.ipa.read_bytes()
        opener = unittest.mock.Mock()
        opener.open.return_value = io.BytesIO(b"<html>not an IPA</html>")
        with patch.object(installer.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(zipfile.BadZipFile):
                installer.download("https://artifacts.example/app.ipa", self.ipa)
        self.assertEqual(self.ipa.read_bytes(), previous)
        self.assertEqual(list(self.directory.glob(".ipa-*")), [])

    def test_download_checks_hash_before_replacing_previous_file(self):
        previous = self.ipa.read_bytes()
        incoming = make_ipa(self.directory / "new.ipa", minimum="18.0").read_bytes()
        opener = unittest.mock.Mock()
        opener.open.return_value = io.BytesIO(incoming)
        with patch.object(installer.urllib.request, "build_opener", return_value=opener):
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                installer.download("https://artifacts.example/app.ipa", self.ipa, "0" * 64)
        self.assertEqual(self.ipa.read_bytes(), previous)

    def test_non_https_download_is_rejected_before_network(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            installer.download("http://artifacts.example/app.ipa", self.ipa)

    def test_signed_ipa_uses_selected_udid_and_modern_installer(self):
        make_ipa(self.ipa, signed=True)
        self.mock_mac()
        result, output = self.signed("--tool", "ideviceinstaller")
        self.assertEqual(result, 0, output)
        # The installer canonicalizes the IPA path (Path.resolve), so the
        # expectation must match that resolved form. On macOS /var is a symlink
        # to /private/var, so the raw and resolved paths differ there.
        self.assertEqual(self.install_commands(), [["/tools/ideviceinstaller", "-u", UDID, "install", str(self.ipa.resolve())]])
        self.assertIn("Open the app on the device to verify", output)

    def test_legacy_installer_interface(self):
        make_ipa(self.ipa, signed=True)
        self.mock_mac(modern=False)
        self.assertEqual(self.signed()[0], 0)
        self.assertEqual(self.install_commands()[0][1:4], ["-u", UDID, "-i"])

    def test_devicectl_receives_extracted_app_not_ipa(self):
        make_ipa(self.ipa, signed=True, extension=True)
        self.mock_mac()
        result, output = self.signed("--tool", "devicectl")
        self.assertEqual(result, 0, output)
        command = self.install_commands()[0]
        self.assertEqual(command[5:7], ["--device", UDID])
        self.assertTrue(command[-1].endswith("SuperCraftOS.app"))
        self.assertFalse(Path(command[-1]).exists(), "temporary extraction should be removed")
        self.assertEqual(len([c for c in self.commands if c[0] == "security"]), 2)

    def test_unsigned_and_unprovisioned_extension_stop_before_install(self):
        self.mock_mac()
        for signed, extension in [(False, False), (True, True)]:
            with self.subTest(extension=extension):
                make_ipa(self.ipa, signed=signed, extension=extension, extension_signed=False)
                self.assertEqual(self.signed()[0], 1)
                self.assertEqual(self.install_commands(), [])

    def test_expired_or_wrong_device_profile_stop_before_install(self):
        self.mock_mac()
        for settings in [{"expired": True}, {"udid": "different-device"}]:
            with self.subTest(settings=settings):
                make_ipa(self.ipa, signed=True, **settings)
                self.assertEqual(self.signed()[0], 1)
                self.assertEqual(self.install_commands(), [])

    def test_wrong_bundle_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "identifier"):
            installer.validate_profile(profile("com.example.other"), {"CFBundleIdentifier": APP_ID}, UDID)

    def test_codesign_failure_stops_before_install(self):
        make_ipa(self.ipa, signed=True)
        self.mock_mac(fail_command=lambda cmd: cmd[0] == "codesign")
        self.assertEqual(self.signed()[0], 1)
        self.assertEqual(self.install_commands(), [])

    def test_install_failure_does_not_report_success(self):
        make_ipa(self.ipa, signed=True)
        self.mock_mac(fail_command=lambda cmd: cmd[0].endswith("ideviceinstaller") and "--help" not in cmd)
        result, output = self.signed()
        self.assertEqual(result, 1)
        self.assertNotIn("Installer reported success", output)

    def test_shell_entry_points_prepare_local_file_without_credential_prompt(self):
        for script, mode in [("install_on_device.sh", []), ("supercraftos_install.sh", []),
                             ("install_ios.sh", ["free"])]:
            with self.subTest(script=script):
                result = subprocess.run(["bash", str(ROOT / "scripts" / script), *mode,
                                         "--ipa", str(self.ipa), "--no-open"],
                                        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("NOT installed", result.stdout)

    def test_old_pipe_bootstrap_fails_with_actionable_message(self):
        source = (ROOT / "scripts/supercraftos_install.sh").read_text()
        result = subprocess.run(["bash"], input=source, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("retired", result.stderr)
        self.assertIn("sideloadly.io", result.stderr)


if __name__ == "__main__":
    unittest.main()
