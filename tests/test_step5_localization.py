import os
from pathlib import Path
import string
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.detector import SCRFDDetector
from src.i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    SYSTEM_LANGUAGE_PREF,
    TRANSLATIONS,
    AppSettingsStore,
    I18nManager,
    detect_system_language,
)
from src.installer_gui import InstallerWizardDialog
from src.main_window import MainWindow, save_image_safe
from src.models import FaceRegion
from src.settings_dialog import SettingsDialog


class TestStep5Localization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.detector = SCRFDDetector()

    def test_01_translation_catalog_completeness(self):
        self.assertEqual(DEFAULT_LANGUAGE, "en")
        required_langs = {"en", "de", "ja", "fr", "es", "vi", "th", "ko"}
        self.assertTrue(required_langs.issubset(set(SUPPORTED_LANGUAGES)))

        en_table = TRANSLATIONS["en"]
        en_keys = set(en_table.keys())
        formatter = string.Formatter()

        def extract_placeholders(text: str):
            return {fname for _, fname, _, _ in formatter.parse(text) if fname is not None}

        for lang in SUPPORTED_LANGUAGES:
            lang_table = TRANSLATIONS[lang]
            self.assertEqual(
                set(lang_table.keys()),
                en_keys,
                f"[{lang}] 번역 키 집합이 기본 영어(en)와 일치해야 합니다.",
            )
            for key, val in lang_table.items():
                self.assertTrue(val.strip(), f"[{lang}] '{key}' 번역 문자열이 비어 있습니다.")
                self.assertEqual(
                    extract_placeholders(val),
                    extract_placeholders(en_table[key]),
                    f"[{lang}] '{key}' 포맷 플레이스홀더가 기본 영어와 일치해야 합니다.",
                )

    def test_02_system_language_detection_and_english_fallback(self):
        cases = {
            "en-US": "en",
            "en_GB.UTF-8": "en",
            "de-DE": "de",
            "de_AT.UTF-8": "de",
            "ja-JP": "ja",
            "ja": "ja",
            "fr-FR": "fr",
            "fr_CA": "fr",
            "es-ES": "es",
            "es_MX": "es",
            "vi-VN": "vi",
            "th-TH": "th",
            "ko-KR": "ko",
            # 미지원 언어 및 비정상 로케일은 기본값 영어('en')로 폴백되어야 함
            "zh-CN": "en",
            "pt-BR": "en",
            "it_IT": "en",
            "ar-SA": "en",
            "C": "en",
            "POSIX": "en",
            "": "en",
        }
        for raw_locale, expected in cases.items():
            detected = detect_system_language(override_tag=raw_locale)
            self.assertEqual(
                detected,
                expected,
                f"시스템 로케일 '{raw_locale}' 감지 결과는 '{expected}'이어야 합니다 (실제: '{detected}').",
            )

    def test_03_startup_system_lang_and_persistent_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            # 1) 최초 실행 시(설정 파일 없음): 시스템 언어를 자동 감지하여 적용 (미지원 로케일 시 영어 기본)
            store_1 = AppSettingsStore(settings_path=settings_file)
            self.assertEqual(store_1.language_preference, SYSTEM_LANGUAGE_PREF)

            i18n_unsupported = I18nManager(settings_store=store_1, system_lang_override="pt-BR")
            self.assertEqual(i18n_unsupported.current_language, "en")

            i18n_french = I18nManager(settings_store=store_1, system_lang_override="fr-FR")
            self.assertEqual(i18n_french.current_language, "fr")

            win = MainWindow(detector=self.detector, i18n=i18n_french)
            win.show()
            self.app.processEvents()
            self.assertEqual(win.btn_open.text(), TRANSLATIONS["fr"]["toolbar.open"])

            # 2) 설정 대화상자(SettingsDialog)에서 언어를 베트남어('vi')로 변경 -> 즉시 UI 반영 및 파일 저장
            dlg = SettingsDialog(win, i18n=i18n_french, on_preferences_changed=win._on_default_preferences_updated)
            vi_idx = dlg.combo_language.findData("vi")
            self.assertGreaterEqual(vi_idx, 0)
            dlg.combo_language.setCurrentIndex(vi_idx)
            self.app.processEvents()

            self.assertEqual(i18n_french.current_language, "vi")
            self.assertEqual(win.btn_open.text(), TRANSLATIONS["vi"]["toolbar.open"])
            self.assertEqual(dlg.windowTitle(), TRANSLATIONS["vi"]["settings.window_title"])
            dlg.close()
            win.close()

            # 3) 앱 재실행 시뮬레이션: 시스템 언어가 독일어('de-DE')여도 사용자가 저장한 'vi' 설정이 유지되어야 함
            store_reloaded = AppSettingsStore(settings_path=settings_file)
            self.assertEqual(store_reloaded.language_preference, "vi")
            i18n_reloaded = I18nManager(settings_store=store_reloaded, system_lang_override="de-DE")
            self.assertEqual(i18n_reloaded.current_language, "vi")

            # 4) 다시 'system'(자동)으로 되돌리면 시스템 언어('de')가 즉시 반영되어야 함
            i18n_reloaded.set_language(SYSTEM_LANGUAGE_PREF, persist=True)
            self.assertEqual(i18n_reloaded.current_language, "de")

    def test_04_all_languages_live_retranslate_and_layout_bounds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            store = AppSettingsStore(settings_path=settings_file)
            i18n = I18nManager(settings_store=store, system_lang_override="en-US")

            win = MainWindow(detector=self.detector, i18n=i18n)
            win.resize(1240, 760)
            win.show()
            self.app.processEvents()

            sample_img = np.full((800, 1200, 3), 180, dtype=np.uint8)
            img_path = os.path.join(tmpdir, "sample_photo.jpg")
            save_image_safe(img_path, sample_img)
            win.load_images_from_paths([img_path])
            win.regions = [
                FaceRegion(bbox_norm=(0.3, 0.3, 0.5, 0.5), score=0.92, is_blurred=True),
            ]
            win.photo_entries[0].regions = win.regions
            win.refresh_preview(reset_view=True)

            installer_dlg = InstallerWizardDialog(
                source_dir=Path(__file__).resolve().parent.parent,
                i18n=i18n,
            )

            for lang in SUPPORTED_LANGUAGES:
                # 우측 빠른 언어 콤보박스로 실시간 전환 검증
                combo_idx = win.combo_language.findData(lang)
                self.assertGreaterEqual(combo_idx, 0)
                win.combo_language.setCurrentIndex(combo_idx)
                self.app.processEvents()

                self.assertEqual(i18n.current_language, lang)
                self.assertEqual(win.windowTitle(), TRANSLATIONS[lang]["app.display_name"])
                self.assertEqual(win.btn_open.text(), TRANSLATIONS[lang]["toolbar.open"])
                self.assertEqual(win.btn_settings.text(), TRANSLATIONS[lang]["toolbar.settings"])
                self.assertEqual(win.style_group.title(), TRANSLATIONS[lang]["style.section_title"])
                self.assertIn(
                    TRANSLATIONS[lang]["photos.item_summary"].format(total=1, blurred=1),
                    win.photo_list.item(0).text(),
                )
                self.assertEqual(
                    installer_dlg.windowTitle(),
                    TRANSLATIONS[lang]["installer.window_title"],
                )

                # 레이아웃 가로 폭 및 하단 버퍼 검증
                top_bar_hint_w = win.top_bar.sizeHint().width()
                self.assertLessEqual(
                    top_bar_hint_w,
                    1260,
                    f"[{lang}] 상단 툴바 너비({top_bar_hint_w}px)가 표준 화면 폭(1260px)을 초과했습니다.",
                )

                left_btns_hint_w = win.left_btn_layout.sizeHint().width()
                left_body_w = win.left_photo_group.body_widget.width()
                self.assertLessEqual(
                    left_btns_hint_w,
                    left_body_w,
                    f"[{lang}] 좌측 목록 하단 버튼 폭({left_btns_hint_w}px)이 패널 내부 폭({left_body_w}px)을 초과했습니다.",
                )

                left_bottom_y = win.left_photo_group.mapTo(
                    win, win.left_photo_group.rect().bottomLeft()
                ).y()
                bottom_buffer = win.height() - left_bottom_y
                self.assertGreaterEqual(
                    bottom_buffer,
                    40,
                    f"[{lang}] 좌측 패널 하단 버퍼({bottom_buffer}px)는 최소 40px 이상이어야 합니다.",
                )

            installer_dlg.close()
            win.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
