import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFileOpenEvent
from PySide6.QtWidgets import QApplication

from build_exe import build_pyinstaller_command
from build_macos import build_pyinstaller_macos_command, ensure_macos_icns
from main import QuickFaceBlurApplication, _extract_cli_image_args


class TestStep6MacOSAndPackaging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parent.parent
        cls.app = QApplication.instance() or QuickFaceBlurApplication([])

    def test_01_license_and_public_compliance_files_exist(self):
        required_files = [
            self.project_root / "LICENSE",
            self.project_root / "THIRD_PARTY_NOTICES.md",
            self.project_root / "README.md",
            self.project_root / "assets" / "fonts" / "OFL.txt",
        ]
        for path in required_files:
            self.assertTrue(path.exists(), f"공개 배포 필수 문서가 존재해야 합니다: {path}")
            self.assertGreater(path.stat().st_size, 100)

        notices = (self.project_root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("Non-Commercial", notices)
        self.assertIn("SIL Open Font License", notices)
        self.assertIn("LGPLv3", notices)

    def test_02_macos_icns_and_build_commands(self):
        icns_path = ensure_macos_icns(self.project_root)
        self.assertTrue(icns_path.exists())
        self.assertGreater(icns_path.stat().st_size, 4096)

        mac_cmd = build_pyinstaller_macos_command(self.project_root)
        joined_mac = " ".join(mac_cmd)
        self.assertIn("--osx-bundle-identifier=com.quickfaceblur.app", joined_mac)
        self.assertIn("icon.icns", joined_mac)

        win_cmd = build_pyinstaller_command(self.project_root, onefile=False)
        joined_win = " ".join(win_cmd)
        self.assertIn("--onedir", joined_win)
        self.assertIn("LICENSE", joined_win)

    def test_03_cli_image_args_and_file_open_event(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            valid_jpg = os.path.join(tmpdir, "photo.jpg")
            invalid_txt = os.path.join(tmpdir, "notes.txt")
            Path(valid_jpg).write_bytes(b"dummy")
            Path(invalid_txt).write_bytes(b"dummy")

            extracted = _extract_cli_image_args(
                ["main.py", "--some-flag", "-psn_0_12345", valid_jpg, invalid_txt]
            )
            self.assertEqual(len(extracted), 1)
            self.assertEqual(extracted[0], os.path.abspath(valid_jpg))

            if isinstance(self.app, QuickFaceBlurApplication):
                self.app.main_window = None
                self.app.pending_files.clear()
                ev = QFileOpenEvent(valid_jpg)
                handled = self.app.event(ev)
                self.assertTrue(handled)
                self.assertIn(valid_jpg, self.app.pending_files)
                self.app.pending_files.clear()


if __name__ == "__main__":
    unittest.main(verbosity=2)
