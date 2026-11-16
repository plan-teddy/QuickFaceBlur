import ctypes
import json
import locale
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QLocale

DEFAULT_LANGUAGE = "en"
SYSTEM_LANGUAGE_PREF = "system"

# 지원 언어 목록 (표시 순서는 기본 영어 우선, 이후 요청된 언어 및 한국어)
LANGUAGE_NAMES: Dict[str, str] = {
    "en": "English",
    "de": "Deutsch",
    "ja": "日本語",
    "fr": "Français",
    "es": "Español",
    "vi": "Tiếng Việt",
    "th": "ไทย",
    "ko": "한국어",
}

SUPPORTED_LANGUAGES: List[str] = list(LANGUAGE_NAMES.keys())


TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "app.display_name": "QuickFaceBlur — One-Click Auto Face Blur",
        "app.short_name": "QuickFaceBlur",
        # System Tray
        "tray.open_window": "Open QuickFaceBlur",
        "tray.open_photos": "📂 Open Photos...",
        "tray.settings": "⚙️ Settings...",
        "tray.quit": "Quit",
        # Top Toolbar
        "toolbar.open": "📂 Open Photos",
        "toolbar.open_tooltip": "Select one or multiple photos to load.",
        "toolbar.all_on": "👁️ All On",
        "toolbar.all_on_tooltip": "Turn blur on for all detected and manual regions.",
        "toolbar.all_off": "🙈 All Off",
        "toolbar.all_off_tooltip": "Turn blur off for all regions in the current photo.",
        "toolbar.guides": "🔍 Show Guides",
        "toolbar.guides_tooltip": "Show or hide ellipse guide outlines over face regions.",
        "toolbar.copy": "📋 Copy",
        "toolbar.copy_tooltip": "Copy the full-resolution blurred image to clipboard (Ctrl+C).",
        "toolbar.save": "💾 Save HD",
        "toolbar.save_tooltip": "Save the current photo at original full resolution.",
        "toolbar.save_all": "📦 Save All",
        "toolbar.save_all_tooltip": "Save all photos in the list at once.",
        "toolbar.settings": "⚙️ Settings",
        "toolbar.settings_tooltip": "Change display language and default preferences.",
        # Left Photo List
        "photos.section_title": "Photos ({count})",
        "photos.add": "+ Add",
        "photos.add_tooltip": "Add more photos to the list.",
        "photos.remove": "- Remove",
        "photos.remove_tooltip": "Remove the selected photo from the list.",
        "photos.clear": "Clear",
        "photos.clear_tooltip": "Clear all photos from the list.",
        "photos.item_summary": "{total} faces ({blurred} blurred)",
        # Canvas Placeholder
        "canvas.placeholder": (
            "📷 Drag & drop photos here (multiple supported)\n"
            "or click [📂 Open Photos] above\n\n"
            "(Supported formats: JPG, PNG, WEBP, BMP, TIFF)"
        ),
        # Right Panel - Language & Settings
        "lang.section_title": "Language",
        "lang.auto_option": "🌐 Auto (System — {detected})",
        "lang.open_settings_btn": "⚙️ More Settings...",
        # Right Panel - Blur Style
        "style.section_title": "Blur Style",
        "style.bokeh": "Bokeh Blur (Default)",
        "style.mosaic": "Mosaic (Pixelate)",
        # Right Panel - Sliders
        "slider.section_title": "Blur & Detection",
        "slider.strength": "Blur Strength",
        "slider.scale": "Region Size",
        "slider.confidence": "Detection Sensitivity",
        "slider.confidence_hint": "Lower detects smaller faces · Higher reduces false positives",
        # Right Panel - Privacy
        "privacy.section_title": "Privacy Options",
        "privacy.strip_metadata": "🛡️ Strip Metadata (EXIF / GPS)",
        "privacy.strip_metadata_hint": "Removes GPS location, device, and date info when saving",
        # Right Panel - Quick Guide
        "guide.section_title": "Quick Guide",
        "guide.html": (
            '<p style="margin: 0 0 7px 0;">• <b>Click face</b>: Toggle blur on / off</p>'
            '<p style="margin: 0 0 7px 0;">• <b>Drag empty area</b>: Add custom blur ellipse</p>'
            '<p style="margin: 0 0 2px 0;">• <b>Right-click custom</b>: Delete custom ellipse</p>'
        ),
        "guide.clear_manual": "🗑️ Clear Manual Regions",
        "shortcut.install_btn": "📌 Create Desktop Shortcut",
        # Footer Status Bar
        "status.empty": "Drag & drop photos into the window or click [📂 Open Photos] to get started.",
        "status.no_faces": "No faces detected. Drag on the photo to add a blur region manually.",
        "status.faces_detected": (
            "{total} face(s) detected ({blurred} blurred) | "
            "💡 Click face: Toggle blur | Drag empty space: Add blur | Right-click manual: Delete"
        ),
        "status.copied": "📋 Full-resolution image ({w}x{h}) copied to clipboard! (Press Ctrl+V to paste)",
        "status.saved_single": "✅ Saved ({meta_msg}): {path}",
        "status.saved_batch": "✅ Saved all {count} photo(s) ({meta_msg}): {dir}",
        # Dialogs & File Pickers
        "dialog.ok": "OK",
        "dialog.cancel": "Cancel",
        "dialog.close": "Done",
        "dialog.open_saved_folder": "📂 Open Folder",
        "file_dialog.open_title": "Select Photo Files (Multiple Allowed)",
        "file_dialog.open_filter": "Image Files (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;All Files (*.*)",
        "file_dialog.save_title": "Save High-Resolution Blurred Photo",
        "file_dialog.save_filter": "JPEG Image (*.jpg *.jpeg);;PNG Image (*.png);;WEBP Image (*.webp)",
        "file_dialog.save_all_title": "Select Folder to Save All Photos ({count})",
        # Model Download & Errors
        "model.downloading_title": "Downloading AI Model",
        "model.downloading_message": "First launch: Downloading AI face detection model...",
        "model.init_failed_title": "AI Model Initialization Failed",
        "model.init_failed_message": "An error occurred while preparing the face detection model:\n{error}",
        "error.cannot_read_image": "Unable to read image file: {path}",
        "error.open_failed_title": "Failed to Open Photo",
        "error.open_failed_message": "Could not load photo:\n{path}\n({error})",
        "error.encode_failed": "Failed to encode output image.",
        # Clipboard & Save Messages
        "clipboard.done_title": "Copied to Clipboard",
        "clipboard.done_message": (
            "✅ The high-resolution blurred photo has been copied to your clipboard!\n\n"
            "You can now paste it directly (Ctrl+V) into messengers, documents, blogs, or image editors."
        ),
        "save.meta_stripped": "Metadata (EXIF/GPS) stripped",
        "save.meta_kept": "Original metadata preserved",
        "save.done_title": "Photo Saved",
        "save.done_message": (
            "✅ High-resolution blurred photo saved successfully!\n"
            "• Privacy: {meta_msg}\n\n"
            "Saved to:\n{path}"
        ),
        "save.failed_title": "Save Failed",
        "save.failed_message": "An error occurred while saving the photo:\n{error}",
        "save_all.done_title": "Batch Save Complete",
        "save_all.done_message": (
            "✅ All {count} high-resolution photo(s) have been saved!\n"
            "• Privacy: {meta_msg}\n\n"
            "Saved folder:\n{dir}"
        ),
        # Shortcut Messages
        "shortcut.win_only_title": "Desktop Shortcut",
        "shortcut.win_only_message": "Automatic desktop shortcut creation is supported on Windows.",
        "shortcut.done_title": "Desktop Shortcut Created",
        "shortcut.done_message": (
            "✅ The [{app_name}] icon has been created on your Desktop!\n\n"
            "Double-click the icon anytime to launch QuickFaceBlur."
        ),
        "shortcut.failed_title": "Shortcut Creation Failed",
        "shortcut.failed_message": "An error occurred while creating the desktop shortcut:\n{error}",
        # Settings Dialog
        "settings.window_title": "Settings — QuickFaceBlur",
        "settings.header_title": "Settings",
        "settings.header_subtitle": "Customize display language and default privacy options.",
        "settings.lang_group": "Display Language",
        "settings.lang_label": "App Language",
        "settings.lang_desc": (
            "Select 'Auto' to match your system language on launch (defaults to English if unsupported). "
            "Changes apply immediately."
        ),
        "settings.detected_system": "Detected system language: {detected}",
        "settings.defaults_group": "Default Preferences",
        "settings.default_guides": "Show guide outlines by default",
        "settings.default_strip_meta": "Strip EXIF / GPS metadata when saving by default",
        "settings.reset_btn": "Reset to Defaults",
        # Installer & Uninstaller
        "installer.window_title": "QuickFaceBlur v1.0.0 — Setup Wizard",
        "installer.header_title": "QuickFaceBlur Setup Wizard",
        "installer.header_subtitle": "One-Click Auto Face Blur Desktop App (v1.0.0)",
        "installer.install_path": "• Install location: {install_dir}",
        "installer.chk_desktop": "Create [{app_name}] shortcut on Desktop",
        "installer.chk_startmenu": "Register in Start Menu and Windows Installed Apps",
        "installer.chk_launch": "Launch QuickFaceBlur immediately after installation",
        "installer.status_ready": "Click [🚀 Install Now] below to begin installation.",
        "installer.status_copying": "Copying application files to installation folder...",
        "installer.status_registering": "Registering taskbar icon, shortcuts, and app info...",
        "installer.status_done": "✅ Installation complete!",
        "installer.btn_install": "🚀 Install Now",
        "installer.done_title": "Installation Complete",
        "installer.done_message": (
            "✅ QuickFaceBlur has been installed successfully!\n\n"
            "You can launch it anytime from the [{app_name}] icon on your Desktop."
        ),
        "installer.failed_title": "Installation Error",
        "installer.failed_message": "An error occurred during installation:\n{error}",
        "uninstaller.done_title": "QuickFaceBlur Uninstalled",
        "uninstaller.done_message": "QuickFaceBlur shortcuts and registration entries have been removed.",
    },
    "de": {
        "app.display_name": "QuickFaceBlur — Automatische Gesichtsunschärfe",
        "app.short_name": "QuickFaceBlur",
        "tray.open_window": "QuickFaceBlur öffnen",
        "tray.open_photos": "📂 Fotos öffnen...",
        "tray.settings": "⚙️ Optionen...",
        "tray.quit": "Beenden",
        "toolbar.open": "📂 Fotos öffnen",
        "toolbar.open_tooltip": "Ein oder mehrere Fotos gleichzeitig auswählen und laden.",
        "toolbar.all_on": "👁️ Alle an",
        "toolbar.all_on_tooltip": "Unschärfe für alle Gesichter und Bereiche aktivieren.",
        "toolbar.all_off": "🙈 Alle aus",
        "toolbar.all_off_tooltip": "Unschärfe für alle Bereiche im aktuellen Foto deaktivieren.",
        "toolbar.guides": "🔍 Hilfslinien",
        "toolbar.guides_tooltip": "Hilfslinien um erkannte Gesichter ein- oder ausblenden.",
        "toolbar.copy": "📋 Kopieren",
        "toolbar.copy_tooltip": "Ergebnisbild in voller Auflösung kopieren (Strg+C).",
        "toolbar.save": "💾 Speichern",
        "toolbar.save_tooltip": "Aktuelles Foto in voller Originalauflösung speichern.",
        "toolbar.save_all": "📦 Alle speichern",
        "toolbar.save_all_tooltip": "Alle Fotos in der Liste auf einmal speichern.",
        "toolbar.settings": "⚙️ Optionen",
        "toolbar.settings_tooltip": "Anzeigesprache und Standardeinstellungen ändern.",
        "photos.section_title": "Fotos ({count})",
        "photos.add": "+ Neu",
        "photos.add_tooltip": "Weitere Fotos zur Liste hinzufügen.",
        "photos.remove": "- Löschen",
        "photos.remove_tooltip": "Ausgewähltes Foto aus der Liste entfernen.",
        "photos.clear": "Leeren",
        "photos.clear_tooltip": "Alle Fotos aus der Liste entfernen.",
        "photos.item_summary": "{total} Gesichter ({blurred} aktiv)",
        "canvas.placeholder": (
            "📷 Fotos (auch mehrere) hierher ziehen\n"
            "oder oben auf [📂 Fotos öffnen] klicken\n\n"
            "(Unterstützte Formate: JPG, PNG, WEBP, BMP, TIFF)"
        ),
        "lang.section_title": "Sprache",
        "lang.auto_option": "🌐 Automatisch (System — {detected})",
        "lang.open_settings_btn": "⚙️ Weitere Optionen...",
        "style.section_title": "Unschärfe-Stil",
        "style.bokeh": "Bokeh-Unschärfe (Standard)",
        "style.mosaic": "Mosaik (Verpixelt)",
        "slider.section_title": "Unschärfe & Erkennung",
        "slider.strength": "Unschärfestärke",
        "slider.scale": "Bereichsgröße",
        "slider.confidence": "Erkennungsempfindlichkeit",
        "slider.confidence_hint": "Niedriger erkennt kleine Gesichter · Höher reduziert Fehlalarme",
        "privacy.section_title": "Datenschutz-Optionen",
        "privacy.strip_metadata": "🛡️ Metadaten (EXIF / GPS) entfernen",
        "privacy.strip_metadata_hint": "Löscht beim Speichern automatisch GPS-Standort, Gerät und Datum",
        "guide.section_title": "Kurzanleitung",
        "guide.html": (
            '<p style="margin: 0 0 7px 0;">• <b>Gesicht anklicken</b>: Unschärfe ein / aus</p>'
            '<p style="margin: 0 0 7px 0;">• <b>Freien Bereich ziehen</b>: Eigene Ellipse hinzufügen</p>'
            '<p style="margin: 0 0 2px 0;">• <b>Rechtsklick auf Manuell</b>: Eigene Ellipse löschen</p>'
        ),
        "guide.clear_manual": "🗑️ Manuelle Bereiche löschen",
        "shortcut.install_btn": "📌 Desktop-Verknüpfung erstellen",
        "status.empty": "Fotos in das Fenster ziehen oder auf [📂 Fotos öffnen] klicken, um zu starten.",
        "status.no_faces": "Keine Gesichter erkannt. Ziehen Sie mit der Maus, um manuell einen Bereich hinzuzufügen.",
        "status.faces_detected": (
            "{total} Gesicht(er) erkannt ({blurred} unkenntlich) | "
            "💡 Klick: Ein/Aus | Ziehen: Bereich hinzufügen | Rechtsklick: Manuell löschen"
        ),
        "status.copied": "📋 Bild in Originalauflösung ({w}x{h}) kopiert! (Einfügen mit Strg+V)",
        "status.saved_single": "✅ Gespeichert ({meta_msg}): {path}",
        "status.saved_batch": "✅ Alle {count} Foto(s) gespeichert ({meta_msg}): {dir}",
        "dialog.ok": "OK",
        "dialog.cancel": "Abbrechen",
        "dialog.close": "Fertig",
        "dialog.open_saved_folder": "📂 Ordner öffnen",
        "file_dialog.open_title": "Fotos auswählen (Mehrfachauswahl möglich)",
        "file_dialog.open_filter": "Bilddateien (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;Alle Dateien (*.*)",
        "file_dialog.save_title": "Foto in hoher Qualität speichern",
        "file_dialog.save_filter": "JPEG-Bild (*.jpg *.jpeg);;PNG-Bild (*.png);;WEBP-Bild (*.webp)",
        "file_dialog.save_all_title": "Zielordner für alle Fotos ({count}) auswählen",
        "model.downloading_title": "KI-Modell wird heruntergeladen",
        "model.downloading_message": "Erster Start: KI-Gesichtserkennungsmodell wird heruntergeladen...",
        "model.init_failed_title": "KI-Modell-Initialisierung fehlgeschlagen",
        "model.init_failed_message": "Beim Vorbereiten des Gesichtserkennungsmodells ist ein Fehler aufgetreten:\n{error}",
        "error.cannot_read_image": "Bilddatei kann nicht gelesen werden: {path}",
        "error.open_failed_title": "Foto konnte nicht geöffnet werden",
        "error.open_failed_message": "Das Foto konnte nicht geladen werden:\n{path}\n({error})",
        "error.encode_failed": "Bildkodierung fehlgeschlagen.",
        "clipboard.done_title": "In Zwischenablage kopiert",
        "clipboard.done_message": (
            "✅ Das bearbeitete Foto in hoher Auflösung wurde in die Zwischenablage kopiert!\n\n"
            "Sie können es direkt mit Strg+V in Messenger, Dokumente oder Bildprogramme einfügen."
        ),
        "save.meta_stripped": "Metadaten (EXIF/GPS) entfernt",
        "save.meta_kept": "Original-Metadaten beibehalten",
        "save.done_title": "Foto gespeichert",
        "save.done_message": (
            "✅ Das Foto wurde erfolgreich in hoher Qualität gespeichert!\n"
            "• Datenschutz: {meta_msg}\n\n"
            "Speicherort:\n{path}"
        ),
        "save.failed_title": "Speichern fehlgeschlagen",
        "save.failed_message": "Beim Speichern des Fotos ist ein Fehler aufgetreten:\n{error}",
        "save_all.done_title": "Stapelspeicherung abgeschlossen",
        "save_all.done_message": (
            "✅ Alle {count} Foto(s) wurden in hoher Qualität gespeichert!\n"
            "• Datenschutz: {meta_msg}\n\n"
            "Zielordner:\n{dir}"
        ),
        "shortcut.win_only_title": "Desktop-Verknüpfung",
        "shortcut.win_only_message": "Die automatische Erstellung von Desktop-Verknüpfungen wird unter Windows unterstützt.",
        "shortcut.done_title": "Desktop-Verknüpfung erstellt",
        "shortcut.done_message": (
            "✅ Das Symbol [{app_name}] wurde auf Ihrem Desktop erstellt!\n\n"
            "Starten Sie QuickFaceBlur jederzeit per Doppelklick."
        ),
        "shortcut.failed_title": "Verknüpfung fehlgeschlagen",
        "shortcut.failed_message": "Fehler beim Erstellen der Desktop-Verknüpfung:\n{error}",
        "settings.window_title": "Einstellungen — QuickFaceBlur",
        "settings.header_title": "Einstellungen",
        "settings.header_subtitle": "Anzeigesprache und Standard-Datenschutzoptionen anpassen.",
        "settings.lang_group": "Anzeigesprache",
        "settings.lang_label": "Programmsprache",
        "settings.lang_desc": (
            "Mit 'Automatisch' wird beim Start die Systemsprache übernommen (Standard: Englisch). "
            "Änderungen werden sofort übernommen."
        ),
        "settings.detected_system": "Erkannte Systemsprache: {detected}",
        "settings.defaults_group": "Standardeinstellungen",
        "settings.default_guides": "Hilfslinien standardmäßig anzeigen",
        "settings.default_strip_meta": "EXIF- / GPS-Metadaten beim Speichern standardmäßig entfernen",
        "settings.reset_btn": "Auf Standard zurücksetzen",
        "installer.window_title": "QuickFaceBlur v1.0.0 — Installationsassistent",
        "installer.header_title": "QuickFaceBlur Installationsassistent",
        "installer.header_subtitle": "Automatische Ein-Klick-Gesichtsunschärfe für den Desktop (v1.0.0)",
        "installer.install_path": "• Installationspfad: {install_dir}",
        "installer.chk_desktop": "Desktop-Symbol für [{app_name}] erstellen",
        "installer.chk_startmenu": "Im Startmenü und unter Installierte Apps registrieren",
        "installer.chk_launch": "Programm direkt nach der Installation starten",
        "installer.status_ready": "Klicken Sie unten auf [🚀 Jetzt installieren], um zu beginnen.",
        "installer.status_copying": "Programmdateien werden kopiert...",
        "installer.status_registering": "Taskleistensymbol, Verknüpfungen und App-Infos werden registriert...",
        "installer.status_done": "✅ Installation abgeschlossen!",
        "installer.btn_install": "🚀 Jetzt installieren",
        "installer.done_title": "Installation abgeschlossen",
        "installer.done_message": (
            "✅ QuickFaceBlur wurde erfolgreich installiert!\n\n"
            "Sie können das Programm jederzeit über das Desktop-Symbol [{app_name}] starten."
        ),
        "installer.failed_title": "Installationsfehler",
        "installer.failed_message": "Während der Installation ist ein Fehler aufgetreten:\n{error}",
        "uninstaller.done_title": "Deinstallation abgeschlossen",
        "uninstaller.done_message": "QuickFaceBlur-Verknüpfungen und Registrierungseinträge wurden entfernt.",
    },
    "ja": {
        "app.display_name": "QuickFaceBlur — ワンクリック自動顔ぼかし",
        "app.short_name": "QuickFaceBlur",
        "tray.open_window": "QuickFaceBlur を開く",
        "tray.open_photos": "📂 写真を開く...",
        "tray.settings": "⚙️ 設定...",
        "tray.quit": "終了",
        "toolbar.open": "📂 写真を開く",
        "toolbar.open_tooltip": "1枚または複数の写真を同時に選択して読み込みます。",
        "toolbar.all_on": "👁️ すべてON",
        "toolbar.all_on_tooltip": "すべての顔・手動エリアのぼかしをオンにします。",
        "toolbar.all_off": "🙈 すべてOFF",
        "toolbar.all_off_tooltip": "すべての顔・手動エリアのぼかしをオフにします。",
        "toolbar.guides": "🔍 ガイド表示",
        "toolbar.guides_tooltip": "検出された顔のガイド枠を表示／非表示にします。",
        "toolbar.copy": "📋 コピー",
        "toolbar.copy_tooltip": "高画質の処理済み画像をクリップボードにコピーします (Ctrl+C)。",
        "toolbar.save": "💾 高画質保存",
        "toolbar.save_tooltip": "現在の写真を元の高解像度で保存します。",
        "toolbar.save_all": "📦 一括保存",
        "toolbar.save_all_tooltip": "リスト内のすべての写真をまとめて保存します。",
        "toolbar.settings": "⚙️ 設定",
        "toolbar.settings_tooltip": "表示言語や初期設定を変更します。",
        "photos.section_title": "写真リスト ({count}枚)",
        "photos.add": "+ 追加",
        "photos.add_tooltip": "写真をリストに追加します。",
        "photos.remove": "- 除外",
        "photos.remove_tooltip": "選択中の写真をリストから除外します。",
        "photos.clear": "クリア",
        "photos.clear_tooltip": "リストの写真をすべてクリアします。",
        "photos.item_summary": "{total}人 (ぼかし {blurred})",
        "canvas.placeholder": (
            "📷 写真ファイル（複数可）をここにドラッグ＆ドロップするか\n"
            "上部の [📂 写真を開く] ボタンを押してください\n\n"
            "（対応形式: JPG, PNG, WEBP, BMP, TIFF）"
        ),
        "lang.section_title": "表示言語",
        "lang.auto_option": "🌐 自動 (システム言語 — {detected})",
        "lang.open_settings_btn": "⚙️ 詳細設定を開く...",
        "style.section_title": "ぼかしスタイル",
        "style.bokeh": "ボケぼかし (標準)",
        "style.mosaic": "モザイク (ピクセル化)",
        "slider.section_title": "ぼかし・検出設定",
        "slider.strength": "ぼかしの強さ",
        "slider.scale": "範囲のサイズ",
        "slider.confidence": "顔検出の感度",
        "slider.confidence_hint": "下げると小さな顔も検出・上げると誤検出を抑制",
        "privacy.section_title": "プライバシー保護",
        "privacy.strip_metadata": "🛡️ メタデータ (EXIF・位置情報) を削除",
        "privacy.strip_metadata_hint": "保存時に撮影場所(GPS)・機種・日時情報を自動削除します",
        "guide.section_title": "かんたん操作ガイド",
        "guide.html": (
            '<p style="margin: 0 0 7px 0;">• <b>顔をクリック</b>: その顔のぼかし ON / OFF</p>'
            '<p style="margin: 0 0 7px 0;">• <b>空白をドラッグ</b>: 手動ぼかし楕円を追加</p>'
            '<p style="margin: 0 0 2px 0;">• <b>手動枠を右クリック</b>: 追加した楕円を削除</p>'
        ),
        "guide.clear_manual": "🗑️ 手動追加エリアを削除",
        "shortcut.install_btn": "📌 デスクトップにショートカットを作成",
        "status.empty": "写真（複数可）をウィンドウにドロップするか、[📂 写真を開く] ボタンを押してください。",
        "status.no_faces": "顔が検出されませんでした。マウスでドラッグして手動でぼかし範囲を追加できます。",
        "status.faces_detected": (
            "合計 {total}人の顔を検出（ぼかし適用: {blurred}人） | "
            "💡 顔クリック: ON/OFF | 空白ドラッグ: 手動追加 | 手動枠右クリック: 削除"
        ),
        "status.copied": "📋 高画質画像 ({w}x{h}) をクリップボードにコピーしました！(Ctrl+V で貼り付け可能)",
        "status.saved_single": "✅ 保存完了 ({meta_msg}): {path}",
        "status.saved_batch": "✅ 全 {count}枚を一括保存しました ({meta_msg}): {dir}",
        "dialog.ok": "OK",
        "dialog.cancel": "キャンセル",
        "dialog.close": "完了",
        "dialog.open_saved_folder": "📂 保存先フォルダを開く",
        "file_dialog.open_title": "写真ファイルを選択（複数選択可）",
        "file_dialog.open_filter": "画像ファイル (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;すべてのファイル (*.*)",
        "file_dialog.save_title": "高画質ぼかし写真を保存",
        "file_dialog.save_filter": "JPEG 画像 (*.jpg *.jpeg);;PNG 画像 (*.png);;WEBP 画像 (*.webp)",
        "file_dialog.save_all_title": "すべての写真（{count}枚）の保存先フォルダを選択",
        "model.downloading_title": "AIモデルをダウンロード中",
        "model.downloading_message": "初回起動: AI顔検出モデルをダウンロードしています...",
        "model.init_failed_title": "AIモデルの初期化に失敗",
        "model.init_failed_message": "顔検出モデルの準備中にエラーが発生しました:\n{error}",
        "error.cannot_read_image": "画像ファイルを読み込めません: {path}",
        "error.open_failed_title": "写真を開けませんでした",
        "error.open_failed_message": "写真を読み込めませんでした:\n{path}\n({error})",
        "error.encode_failed": "画像のエンコードに失敗しました。",
        "clipboard.done_title": "クリップボードにコピー完了",
        "clipboard.done_message": (
            "✅ ぼかし処理済みの高画質写真をクリップボードにコピーしました！\n\n"
            "LINE、SNS、ブログ、Word、画像編集ソフトなどにそのまま貼り付け（Ctrl+V）できます。"
        ),
        "save.meta_stripped": "メタデータ(EXIF/GPS)削除済み",
        "save.meta_kept": "元のメタデータを保持",
        "save.done_title": "写真の保存完了",
        "save.done_message": (
            "✅ 高画質ぼかし写真を保存しました！\n"
            "• プライバシー保護: {meta_msg}\n\n"
            "保存先:\n{path}"
        ),
        "save.failed_title": "保存失敗",
        "save.failed_message": "写真の保存中にエラーが発生しました:\n{error}",
        "save_all.done_title": "一括保存が完了しました",
        "save_all.done_message": (
            "✅ 全 {count}枚の高画質写真を保存しました！\n"
            "• プライバシー保護: {meta_msg}\n\n"
            "保存先フォルダ:\n{dir}"
        ),
        "shortcut.win_only_title": "デスクトップショートカット",
        "shortcut.win_only_message": "デスクトップショートカットの自動作成は Windows 環境で動作します。",
        "shortcut.done_title": "ショートカット作成完了",
        "shortcut.done_message": (
            "✅ デスクトップに [{app_name}] アイコンを作成しました！\n\n"
            "アイコンをダブルクリックしていつでもすぐに起動できます。"
        ),
        "shortcut.failed_title": "ショートカット作成失敗",
        "shortcut.failed_message": "ショートカットの作成中にエラーが発生しました:\n{error}",
        "settings.window_title": "設定 — QuickFaceBlur",
        "settings.header_title": "設定",
        "settings.header_subtitle": "表示言語とデフォルトのプライバシー設定を変更します。",
        "settings.lang_group": "表示言語 (Language)",
        "settings.lang_label": "アプリの言語",
        "settings.lang_desc": (
            "「自動」を選ぶと起動時にOSのシステム言語を自動反映します（未対応言語の場合は英語）。"
            "変更はすぐに反映されます。"
        ),
        "settings.detected_system": "検出されたシステム言語: {detected}",
        "settings.defaults_group": "初期設定",
        "settings.default_guides": "起動時にガイド枠を表示する",
        "settings.default_strip_meta": "保存時にメタデータ (EXIF・GPS) を削除する",
        "settings.reset_btn": "初期設定に戻す",
        "installer.window_title": "QuickFaceBlur v1.0.0 — セットアップウィザード",
        "installer.header_title": "QuickFaceBlur セットアップ",
        "installer.header_subtitle": "ワンクリック自動顔ぼかしデスクトップアプリ (v1.0.0)",
        "installer.install_path": "• インストール先: {install_dir}",
        "installer.chk_desktop": "デスクトップに [{app_name}] アイコンを作成する",
        "installer.chk_startmenu": "スタートメニューとインストール済みアプリに登録する",
        "installer.chk_launch": "インストール完了後にすぐ起動する",
        "installer.status_ready": "下の [🚀 今すぐインストール] ボタンを押すと開始します。",
        "installer.status_copying": "プログラムファイルをコピーしています...",
        "installer.status_registering": "アイコンとショートカットを登録しています...",
        "installer.status_done": "✅ インストールが完了しました！",
        "installer.btn_install": "🚀 今すぐインストール",
        "installer.done_title": "インストール完了",
        "installer.done_message": (
            "✅ QuickFaceBlur のインストールが完了しました！\n\n"
            "デスクトップの [{app_name}] アイコンからいつでも起動できます。"
        ),
        "installer.failed_title": "インストールエラー",
        "installer.failed_message": "インストール中にエラーが発生しました:\n{error}",
        "uninstaller.done_title": "アンインストール完了",
        "uninstaller.done_message": "QuickFaceBlur のショートカットと登録情報を削除しました。",
    },
    "fr": {
        "app.display_name": "QuickFaceBlur — Floutage automatique des visages",
        "app.short_name": "QuickFaceBlur",
        "tray.open_window": "Ouvrir QuickFaceBlur",
        "tray.open_photos": "📂 Ouvrir des photos...",
        "tray.settings": "⚙️ Options...",
        "tray.quit": "Quitter",
        "toolbar.open": "📂 Ouvrir",
        "toolbar.open_tooltip": "Sélectionner une ou plusieurs photos à importer.",
        "toolbar.all_on": "👁️ Tout activer",
        "toolbar.all_on_tooltip": "Activer le flou sur tous les visages et zones.",
        "toolbar.all_off": "🙈 Tout masquer",
        "toolbar.all_off_tooltip": "Désactiver le flou sur toutes les zones de la photo.",
        "toolbar.guides": "🔍 Guides",
        "toolbar.guides_tooltip": "Afficher ou masquer les contours de guidage.",
        "toolbar.copy": "📋 Copier",
        "toolbar.copy_tooltip": "Copier l'image haute définition dans le presse-papiers (Ctrl+C).",
        "toolbar.save": "💾 Enregistrer",
        "toolbar.save_tooltip": "Enregistrer la photo actuelle en pleine résolution.",
        "toolbar.save_all": "📦 Tout enregistrer",
        "toolbar.save_all_tooltip": "Enregistrer toutes les photos de la liste en une fois.",
        "toolbar.settings": "⚙️ Options",
        "toolbar.settings_tooltip": "Modifier la langue d'affichage et les préférences.",
        "photos.section_title": "Photos ({count})",
        "photos.add": "+ Ajout",
        "photos.add_tooltip": "Ajouter d'autres photos à la liste.",
        "photos.remove": "- Retirer",
        "photos.remove_tooltip": "Retirer la photo sélectionnée de la liste.",
        "photos.clear": "Vider",
        "photos.clear_tooltip": "Vider toutes les photos de la liste.",
        "photos.item_summary": "{total} visages ({blurred} flous)",
        "canvas.placeholder": (
            "📷 Glissez-déposez vos photos ici (plusieurs possibles)\n"
            "ou cliquez sur [📂 Ouvrir] en haut\n\n"
            "(Formats pris en charge : JPG, PNG, WEBP, BMP, TIFF)"
        ),
        "lang.section_title": "Langue",
        "lang.auto_option": "🌐 Automatique (Système — {detected})",
        "lang.open_settings_btn": "⚙️ Plus d'options...",
        "style.section_title": "Style de flou",
        "style.bokeh": "Flou Bokeh (Par défaut)",
        "style.mosaic": "Mosaïque (Pixélisé)",
        "slider.section_title": "Flou et détection",
        "slider.strength": "Intensité du flou",
        "slider.scale": "Taille de la zone",
        "slider.confidence": "Sensibilité de détection",
        "slider.confidence_hint": "Plus bas détecte les petits visages · Plus haut réduit les faux positifs",
        "privacy.section_title": "Confidentialité",
        "privacy.strip_metadata": "🛡️ Supprimer métadonnées (EXIF / GPS)",
        "privacy.strip_metadata_hint": "Efface automatiquement le lieu (GPS), l'appareil et la date à l'enregistrement",
        "guide.section_title": "Guide rapide",
        "guide.html": (
            '<p style="margin: 0 0 7px 0;">• <b>Clic sur un visage</b> : Activer / désactiver le flou</p>'
            '<p style="margin: 0 0 7px 0;">• <b>Glisser sur zone vide</b> : Ajouter un flou manuel</p>'
            '<p style="margin: 0 0 2px 0;">• <b>Clic droit sur zone manuelle</b> : Supprimer la zone</p>'
        ),
        "guide.clear_manual": "🗑️ Effacer les zones manuelles",
        "shortcut.install_btn": "📌 Créer un raccourci Bureau",
        "status.empty": "Glissez-déposez des photos dans la fenêtre ou cliquez sur [📂 Ouvrir] pour commencer.",
        "status.no_faces": "Aucun visage détecté. Faites glisser la souris pour ajouter une zone de flou manuellement.",
        "status.faces_detected": (
            "{total} visage(s) détecté(s) ({blurred} flouté(s)) | "
            "💡 Clic visage : ON/OFF | Glisser vide : Ajouter | Clic droit manuel : Supprimer"
        ),
        "status.copied": "📋 Image haute résolution ({w}x{h}) copiée dans le presse-papiers ! (Ctrl+V pour coller)",
        "status.saved_single": "✅ Enregistré ({meta_msg}) : {path}",
        "status.saved_batch": "✅ {count} photo(s) enregistrée(s) ({meta_msg}) : {dir}",
        "dialog.ok": "OK",
        "dialog.cancel": "Annuler",
        "dialog.close": "Terminé",
        "dialog.open_saved_folder": "📂 Ouvrir le dossier",
        "file_dialog.open_title": "Sélectionner des photos (sélection multiple possible)",
        "file_dialog.open_filter": "Fichiers image (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;Tous les fichiers (*.*)",
        "file_dialog.save_title": "Enregistrer la photo floutée haute qualité",
        "file_dialog.save_filter": "Image JPEG (*.jpg *.jpeg);;Image PNG (*.png);;Image WEBP (*.webp)",
        "file_dialog.save_all_title": "Choisir le dossier pour enregistrer les {count} photos",
        "model.downloading_title": "Téléchargement du modèle IA",
        "model.downloading_message": "Premier lancement : téléchargement du modèle IA de détection des visages...",
        "model.init_failed_title": "Échec d'initialisation du modèle IA",
        "model.init_failed_message": "Une erreur est survenue lors de la préparation du modèle de détection :\n{error}",
        "error.cannot_read_image": "Impossible de lire le fichier image : {path}",
        "error.open_failed_title": "Impossible d'ouvrir la photo",
        "error.open_failed_message": "Impossible de charger la photo :\n{path}\n({error})",
        "error.encode_failed": "Échec de l'encodage de l'image.",
        "clipboard.done_title": "Copié dans le presse-papiers",
        "clipboard.done_message": (
            "✅ La photo floutée haute résolution a été copiée dans le presse-papiers !\n\n"
            "Vous pouvez la coller directement (Ctrl+V) dans vos messageries, documents ou logiciels."
        ),
        "save.meta_stripped": "Métadonnées (EXIF/GPS) supprimées",
        "save.meta_kept": "Métadonnées d'origine conservées",
        "save.done_title": "Photo enregistrée",
        "save.done_message": (
            "✅ La photo haute résolution a été enregistrée avec succès !\n"
            "• Confidentialité : {meta_msg}\n\n"
            "Emplacement :\n{path}"
        ),
        "save.failed_title": "Échec de l'enregistrement",
        "save.failed_message": "Une erreur est survenue lors de l'enregistrement :\n{error}",
        "save_all.done_title": "Enregistrement groupé terminé",
        "save_all.done_message": (
            "✅ Les {count} photo(s) haute résolution ont été enregistrées !\n"
            "• Confidentialité : {meta_msg}\n\n"
            "Dossier :\n{dir}"
        ),
        "shortcut.win_only_title": "Raccourci Bureau",
        "shortcut.win_only_message": "La création automatique de raccourci Bureau est disponible sous Windows.",
        "shortcut.done_title": "Raccourci Bureau créé",
        "shortcut.done_message": (
            "✅ L'icône [{app_name}] a été créée sur votre Bureau !\n\n"
            "Double-cliquez dessus à tout moment pour lancer QuickFaceBlur."
        ),
        "shortcut.failed_title": "Échec de création du raccourci",
        "shortcut.failed_message": "Erreur lors de la création du raccourci Bureau :\n{error}",
        "settings.window_title": "Paramètres — QuickFaceBlur",
        "settings.header_title": "Paramètres",
        "settings.header_subtitle": "Personnalisez la langue d'affichage et les options par défaut.",
        "settings.lang_group": "Langue d'affichage",
        "settings.lang_label": "Langue de l'application",
        "settings.lang_desc": (
            "Choisissez « Automatique » pour utiliser la langue du système au démarrage (anglais par défaut). "
            "Les changements s'appliquent immédiatement."
        ),
        "settings.detected_system": "Langue système détectée : {detected}",
        "settings.defaults_group": "Préférences par défaut",
        "settings.default_guides": "Afficher les contours de guidage par défaut",
        "settings.default_strip_meta": "Supprimer les métadonnées EXIF et GPS par défaut à l'enregistrement",
        "settings.reset_btn": "Réinitialiser",
        "installer.window_title": "QuickFaceBlur v1.0.0 — Assistant d'installation",
        "installer.header_title": "Installation de QuickFaceBlur",
        "installer.header_subtitle": "Application de floutage automatique des visages (v1.0.0)",
        "installer.install_path": "• Dossier d'installation : {install_dir}",
        "installer.chk_desktop": "Créer une icône [{app_name}] sur le Bureau",
        "installer.chk_startmenu": "Ajouter au menu Démarrer et aux applications installées",
        "installer.chk_launch": "Lancer l'application immédiatement après l'installation",
        "installer.status_ready": "Cliquez sur [🚀 Installer maintenant] ci-dessous pour démarrer.",
        "installer.status_copying": "Copie des fichiers du programme...",
        "installer.status_registering": "Configuration des icônes et raccourcis...",
        "installer.status_done": "✅ Installation terminée !",
        "installer.btn_install": "🚀 Installer maintenant",
        "installer.done_title": "Installation terminée",
        "installer.done_message": (
            "✅ QuickFaceBlur a été installé avec succès !\n\n"
            "Lancez l'application à tout moment depuis l'icône [{app_name}] sur le Bureau."
        ),
        "installer.failed_title": "Erreur d'installation",
        "installer.failed_message": "Une erreur est survenue pendant l'installation :\n{error}",
        "uninstaller.done_title": "Désinstallation terminée",
        "uninstaller.done_message": "Les raccourcis et entrées de registre de QuickFaceBlur ont été supprimés.",
    },
    "es": {
        "app.display_name": "QuickFaceBlur — Desenfoque facial automático",
        "app.short_name": "QuickFaceBlur",
        "tray.open_window": "Abrir QuickFaceBlur",
        "tray.open_photos": "📂 Abrir fotos...",
        "tray.settings": "⚙️ Ajustes...",
        "tray.quit": "Salir",
        "toolbar.open": "📂 Abrir fotos",
        "toolbar.open_tooltip": "Selecciona una o varias fotos para cargar.",
        "toolbar.all_on": "👁️ Activar todo",
        "toolbar.all_on_tooltip": "Activar desenfoque en todos los rostros y áreas.",
        "toolbar.all_off": "🙈 Desactivar",
        "toolbar.all_off_tooltip": "Desactivar desenfoque en todas las áreas de la foto actual.",
        "toolbar.guides": "🔍 Guías",
        "toolbar.guides_tooltip": "Mostrar u ocultar las líneas guía sobre los rostros.",
        "toolbar.copy": "📋 Copiar",
        "toolbar.copy_tooltip": "Copiar imagen en alta resolución al portapapeles (Ctrl+C).",
        "toolbar.save": "💾 Guardar HD",
        "toolbar.save_tooltip": "Guardar la foto actual en su resolución original.",
        "toolbar.save_all": "📦 Guardar todo",
        "toolbar.save_all_tooltip": "Guardar todas las fotos de la lista a la vez.",
        "toolbar.settings": "⚙️ Ajustes",
        "toolbar.settings_tooltip": "Cambiar idioma de la interfaz y preferencias.",
        "photos.section_title": "Fotos ({count})",
        "photos.add": "+ Añadir",
        "photos.add_tooltip": "Añadir más fotos a la lista.",
        "photos.remove": "- Quitar",
        "photos.remove_tooltip": "Quitar la foto seleccionada de la lista.",
        "photos.clear": "Vaciar",
        "photos.clear_tooltip": "Quitar todas las fotos de la lista.",
        "photos.item_summary": "{total} rostros ({blurred} difum.)",
        "canvas.placeholder": (
            "📷 Arrastra y suelta tus fotos aquí (varias a la vez)\n"
            "o haz clic en [📂 Abrir fotos] arriba\n\n"
            "(Formatos compatibles: JPG, PNG, WEBP, BMP, TIFF)"
        ),
        "lang.section_title": "Idioma",
        "lang.auto_option": "🌐 Automático (Sistema — {detected})",
        "lang.open_settings_btn": "⚙️ Más ajustes...",
        "style.section_title": "Estilo de desenfoque",
        "style.bokeh": "Desenfoque Bokeh (Predet.)",
        "style.mosaic": "Mosaico (Pixelado)",
        "slider.section_title": "Desenfoque y detección",
        "slider.strength": "Intensidad de desenfoque",
        "slider.scale": "Tamaño del área",
        "slider.confidence": "Sensibilidad de detección",
        "slider.confidence_hint": "Más bajo detecta rostros pequeños · Más alto reduce falsas detecciones",
        "privacy.section_title": "Opciones de privacidad",
        "privacy.strip_metadata": "🛡️ Eliminar metadatos (EXIF y GPS)",
        "privacy.strip_metadata_hint": "Borra automáticamente ubicación (GPS), dispositivo y fecha al guardar",
        "guide.section_title": "Guía rápida",
        "guide.html": (
            '<p style="margin: 0 0 7px 0;">• <b>Clic en rostro</b>: Activar / desactivar desenfoque</p>'
            '<p style="margin: 0 0 7px 0;">• <b>Arrastrar área vacía</b>: Añadir elipse manual</p>'
            '<p style="margin: 0 0 2px 0;">• <b>Clic derecho en manual</b>: Eliminar área manual</p>'
        ),
        "guide.clear_manual": "🗑️ Borrar áreas manuales",
        "shortcut.install_btn": "📌 Crear acceso directo en Escritorio",
        "status.empty": "Arrastra fotos a la ventana o pulsa [📂 Abrir fotos] para empezar.",
        "status.no_faces": "No se detectaron rostros. Arrastra con el ratón para añadir un área de desenfoque.",
        "status.faces_detected": (
            "{total} rostro(s) detectado(s) ({blurred} con desenfoque) | "
            "💡 Clic: ON/OFF | Arrastrar: Añadir | Clic derecho manual: Borrar"
        ),
        "status.copied": "📋 ¡Imagen en alta resolución ({w}x{h}) copiada al portapapeles! (Ctrl+V para pegar)",
        "status.saved_single": "✅ Guardado ({meta_msg}): {path}",
        "status.saved_batch": "✅ Se guardaron {count} foto(s) ({meta_msg}): {dir}",
        "dialog.ok": "Aceptar",
        "dialog.cancel": "Cancelar",
        "dialog.close": "Listo",
        "dialog.open_saved_folder": "📂 Abrir carpeta",
        "file_dialog.open_title": "Seleccionar fotos (selección múltiple disponible)",
        "file_dialog.open_filter": "Archivos de imagen (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;Todos los archivos (*.*)",
        "file_dialog.save_title": "Guardar foto desenfocada en alta calidad",
        "file_dialog.save_filter": "Imagen JPEG (*.jpg *.jpeg);;Imagen PNG (*.png);;Imagen WEBP (*.webp)",
        "file_dialog.save_all_title": "Seleccionar carpeta para guardar las {count} fotos",
        "model.downloading_title": "Descargando modelo de IA",
        "model.downloading_message": "Primer inicio: descargando modelo de detección facial de IA...",
        "model.init_failed_title": "Error al iniciar el modelo de IA",
        "model.init_failed_message": "Ocurrió un error al preparar el modelo de detección facial:\n{error}",
        "error.cannot_read_image": "No se puede leer el archivo de imagen: {path}",
        "error.open_failed_title": "Error al abrir la foto",
        "error.open_failed_message": "No se pudo cargar la foto:\n{path}\n({error})",
        "error.encode_failed": "Error al codificar la imagen.",
        "clipboard.done_title": "Copiado al portapapeles",
        "clipboard.done_message": (
            "✅ ¡La foto desenfocada en alta resolución se copió al portapapeles!\n\n"
            "Puedes pegarla directamente (Ctrl+V) en chats, documentos, blogs o editores."
        ),
        "save.meta_stripped": "Metadatos (EXIF/GPS) eliminados",
        "save.meta_kept": "Metadatos originales conservados",
        "save.done_title": "Foto guardada",
        "save.done_message": (
            "✅ ¡La foto en alta calidad se guardó correctamente!\n"
            "• Privacidad: {meta_msg}\n\n"
            "Ubicación:\n{path}"
        ),
        "save.failed_title": "Error al guardar",
        "save.failed_message": "Ocurrió un error al guardar la foto:\n{error}",
        "save_all.done_title": "Guardado por lotes completado",
        "save_all.done_message": (
            "✅ ¡Se guardaron las {count} foto(s) en alta calidad!\n"
            "• Privacidad: {meta_msg}\n\n"
            "Carpeta:\n{dir}"
        ),
        "shortcut.win_only_title": "Acceso directo",
        "shortcut.win_only_message": "La creación automática de accesos directos funciona en Windows.",
        "shortcut.done_title": "Acceso directo creado",
        "shortcut.done_message": (
            "✅ ¡Se ha creado el icono [{app_name}] en tu Escritorio!\n\n"
            "Haz doble clic en cualquier momento para abrir QuickFaceBlur."
        ),
        "shortcut.failed_title": "Error al crear acceso directo",
        "shortcut.failed_message": "Ocurrió un error al crear el acceso directo:\n{error}",
        "settings.window_title": "Ajustes — QuickFaceBlur",
        "settings.header_title": "Ajustes",
        "settings.header_subtitle": "Configura el idioma de visualización y las opciones predeterminadas.",
        "settings.lang_group": "Idioma de visualización",
        "settings.lang_label": "Idioma de la aplicación",
        "settings.lang_desc": (
            "Selecciona 'Automático' para usar el idioma del sistema al iniciar (inglés por defecto). "
            "Los cambios se aplican al instante."
        ),
        "settings.detected_system": "Idioma del sistema detectado: {detected}",
        "settings.defaults_group": "Preferencias predeterminadas",
        "settings.default_guides": "Mostrar líneas guía de forma predeterminada",
        "settings.default_strip_meta": "Eliminar metadatos EXIF y GPS al guardar por defecto",
        "settings.reset_btn": "Restablecer valores",
        "installer.window_title": "QuickFaceBlur v1.0.0 — Asistente de instalación",
        "installer.header_title": "Instalador de QuickFaceBlur",
        "installer.header_subtitle": "Desenfoque facial automático en un clic para escritorio (v1.0.0)",
        "installer.install_path": "• Ruta de instalación: {install_dir}",
        "installer.chk_desktop": "Crear icono de [{app_name}] en el Escritorio",
        "installer.chk_startmenu": "Registrar en el Menú Inicio y Aplicaciones instaladas",
        "installer.chk_launch": "Ejecutar el programa al finalizar la instalación",
        "installer.status_ready": "Pulsa [🚀 Instalar ahora] abajo para comenzar.",
        "installer.status_copying": "Copiando archivos del programa...",
        "installer.status_registering": "Registrando iconos y accesos directos...",
        "installer.status_done": "✅ ¡Instalación completada!",
        "installer.btn_install": "🚀 Instalar ahora",
        "installer.done_title": "Instalación completada",
        "installer.done_message": (
            "✅ ¡QuickFaceBlur se ha instalado correctamente!\n\n"
            "Puedes iniciarlo cuando quieras desde el icono [{app_name}] en tu Escritorio."
        ),
        "installer.failed_title": "Error de instalación",
        "installer.failed_message": "Ocurrió un error durante la instalación:\n{error}",
        "uninstaller.done_title": "Desinstalación completada",
        "uninstaller.done_message": "Se han eliminado los accesos directos y registros de QuickFaceBlur.",
    },
    "vi": {
        "app.display_name": "QuickFaceBlur — Làm mờ khuôn mặt tự động",
        "app.short_name": "QuickFaceBlur",
        "tray.open_window": "Mở QuickFaceBlur",
        "tray.open_photos": "📂 Mở ảnh...",
        "tray.settings": "⚙️ Cài đặt...",
        "tray.quit": "Thoát",
        "toolbar.open": "📂 Mở ảnh",
        "toolbar.open_tooltip": "Chọn một hoặc nhiều ảnh cùng lúc để tải lên.",
        "toolbar.all_on": "👁️ Bật tất cả",
        "toolbar.all_on_tooltip": "Bật làm mờ cho tất cả khuôn mặt và vùng chọn.",
        "toolbar.all_off": "🙈 Tắt tất cả",
        "toolbar.all_off_tooltip": "Tắt làm mờ cho tất cả các vùng trong ảnh hiện tại.",
        "toolbar.guides": "🔍 Khung dẫn",
        "toolbar.guides_tooltip": "Hiện hoặc ẩn đường viền hướng dẫn quanh khuôn mặt.",
        "toolbar.copy": "📋 Sao chép",
        "toolbar.copy_tooltip": "Sao chép ảnh kết quả chất lượng cao vào bộ nhớ tạm (Ctrl+C).",
        "toolbar.save": "💾 Lưu HD",
        "toolbar.save_tooltip": "Lưu ảnh hiện tại ở độ phân giải gốc sắc nét.",
        "toolbar.save_all": "📦 Lưu tất cả",
        "toolbar.save_all_tooltip": "Lưu hàng loạt tất cả ảnh trong danh sách.",
        "toolbar.settings": "⚙️ Cài đặt",
        "toolbar.settings_tooltip": "Thay đổi ngôn ngữ hiển thị và tùy chọn mặc định.",
        "photos.section_title": "Danh sách ảnh ({count})",
        "photos.add": "+ Thêm",
        "photos.add_tooltip": "Thêm ảnh vào danh sách.",
        "photos.remove": "- Xóa",
        "photos.remove_tooltip": "Xóa ảnh đang chọn khỏi danh sách.",
        "photos.clear": "Xóa hết",
        "photos.clear_tooltip": "Xóa toàn bộ ảnh khỏi danh sách.",
        "photos.item_summary": "{total} mặt (mờ {blurred})",
        "canvas.placeholder": (
            "📷 Kéo và thả ảnh (hỗ trợ nhiều ảnh) vào đây\n"
            "hoặc nhấn nút [📂 Mở ảnh] ở phía trên\n\n"
            "(Định dạng hỗ trợ: JPG, PNG, WEBP, BMP, TIFF)"
        ),
        "lang.section_title": "Ngôn ngữ",
        "lang.auto_option": "🌐 Tự động (Hệ thống — {detected})",
        "lang.open_settings_btn": "⚙️ Cài đặt khác...",
        "style.section_title": "Kiểu làm mờ",
        "style.bokeh": "Làm mờ Bokeh (Mặc định)",
        "style.mosaic": "Làm mờ Ô vuông (Pixel)",
        "slider.section_title": "Làm mờ & Nhận diện",
        "slider.strength": "Độ mạnh làm mờ",
        "slider.scale": "Kích thước vùng mờ",
        "slider.confidence": "Độ nhạy nhận diện mặt",
        "slider.confidence_hint": "Giảm để nhận diện mặt nhỏ · Tăng để giảm nhận diện nhầm",
        "privacy.section_title": "Bảo vệ quyền riêng tư",
        "privacy.strip_metadata": "🛡️ Xóa siêu dữ liệu (EXIF / GPS)",
        "privacy.strip_metadata_hint": "Tự động xóa vị trí chụp (GPS), thiết bị và ngày giờ khi lưu",
        "guide.section_title": "Hướng dẫn nhanh",
        "guide.html": (
            '<p style="margin: 0 0 7px 0;">• <b>Nhấp vào mặt</b>: Bật / tắt làm mờ khuôn mặt đó</p>'
            '<p style="margin: 0 0 7px 0;">• <b>Kéo vùng trống</b>: Vẽ thêm vùng làm mờ thủ công</p>'
            '<p style="margin: 0 0 2px 0;">• <b>Chuột phải vùng vẽ</b>: Xóa vùng thêm thủ công</p>'
        ),
        "guide.clear_manual": "🗑️ Xóa vùng thêm thủ công",
        "shortcut.install_btn": "📌 Tạo lối tắt ngoài Màn hình chính",
        "status.empty": "Kéo thả ảnh vào cửa sổ hoặc nhấn [📂 Mở ảnh] để bắt đầu.",
        "status.no_faces": "Không phát hiện khuôn mặt nào. Hãy kéo chuột trên ảnh để tự thêm vùng làm mờ.",
        "status.faces_detected": (
            "Phát hiện {total} khuôn mặt (đang làm mờ: {blurred}) | "
            "💡 Nhấp mặt: Bật/Tắt | Kéo vùng trống: Thêm mờ | Chuột phải: Xóa vùng vẽ"
        ),
        "status.copied": "📋 Đã sao chép ảnh chất lượng cao ({w}x{h}) vào bộ nhớ tạm! (Nhấn Ctrl+V để dán)",
        "status.saved_single": "✅ Đã lưu ({meta_msg}): {path}",
        "status.saved_batch": "✅ Đã lưu tất cả {count} ảnh ({meta_msg}): {dir}",
        "dialog.ok": "Đồng ý",
        "dialog.cancel": "Hủy",
        "dialog.close": "Xong",
        "dialog.open_saved_folder": "📂 Mở thư mục lưu",
        "file_dialog.open_title": "Chọn tệp ảnh (Có thể chọn nhiều ảnh)",
        "file_dialog.open_filter": "Tệp hình ảnh (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;Tất cả tệp (*.*)",
        "file_dialog.save_title": "Lưu ảnh đã làm mờ chất lượng cao",
        "file_dialog.save_filter": "Ảnh JPEG (*.jpg *.jpeg);;Ảnh PNG (*.png);;Ảnh WEBP (*.webp)",
        "file_dialog.save_all_title": "Chọn thư mục lưu tất cả {count} ảnh",
        "model.downloading_title": "Đang tải mô hình AI",
        "model.downloading_message": "Lần chạy đầu: Đang tải mô hình AI nhận diện khuôn mặt...",
        "model.init_failed_title": "Khởi tạo mô hình AI thất bại",
        "model.init_failed_message": "Đã xảy ra lỗi khi chuẩn bị mô hình nhận diện khuôn mặt:\n{error}",
        "error.cannot_read_image": "Không thể đọc tệp hình ảnh: {path}",
        "error.open_failed_title": "Mở ảnh thất bại",
        "error.open_failed_message": "Không thể tải ảnh:\n{path}\n({error})",
        "error.encode_failed": "Mã hóa hình ảnh thất bại.",
        "clipboard.done_title": "Đã sao chép vào bộ nhớ tạm",
        "clipboard.done_message": (
            "✅ Ảnh đã làm mờ chất lượng cao đã được sao chép vào bộ nhớ tạm!\n\n"
            "Bạn có thể dán trực tiếp (Ctrl+V) vào Zalo, Messenger, Word, trình duyệt hoặc phần mềm sửa ảnh."
        ),
        "save.meta_stripped": "Đã xóa siêu dữ liệu (EXIF/GPS)",
        "save.meta_kept": "Giữ nguyên siêu dữ liệu gốc",
        "save.done_title": "Lưu ảnh hoàn tất",
        "save.done_message": (
            "✅ Đã lưu ảnh chất lượng cao thành công!\n"
            "• Quyền riêng tư: {meta_msg}\n\n"
            "Vị trí lưu:\n{path}"
        ),
        "save.failed_title": "Lưu ảnh thất bại",
        "save.failed_message": "Đã xảy ra lỗi khi lưu ảnh:\n{error}",
        "save_all.done_title": "Lưu hàng loạt hoàn tất",
        "save_all.done_message": (
            "✅ Đã lưu thành công tất cả {count} ảnh chất lượng cao!\n"
            "• Quyền riêng tư: {meta_msg}\n\n"
            "Thư mục lưu:\n{dir}"
        ),
        "shortcut.win_only_title": "Lối tắt Màn hình chính",
        "shortcut.win_only_message": "Tính năng tự động tạo lối tắt Màn hình chính hỗ trợ trên Windows.",
        "shortcut.done_title": "Đã tạo lối tắt",
        "shortcut.done_message": (
            "✅ Đã tạo biểu tượng [{app_name}] trên Màn hình chính!\n\n"
            "Nhấp đúp vào biểu tượng bất cứ lúc nào để mở QuickFaceBlur."
        ),
        "shortcut.failed_title": "Tạo lối tắt thất bại",
        "shortcut.failed_message": "Đã xảy ra lỗi khi tạo lối tắt:\n{error}",
        "settings.window_title": "Cài đặt — QuickFaceBlur",
        "settings.header_title": "Cài đặt",
        "settings.header_subtitle": "Tùy chỉnh ngôn ngữ hiển thị và các thiết lập mặc định.",
        "settings.lang_group": "Ngôn ngữ hiển thị",
        "settings.lang_label": "Ngôn ngữ ứng dụng",
        "settings.lang_desc": (
            "Chọn 'Tự động' để áp dụng ngôn ngữ hệ thống khi khởi động (mặc định là Tiếng Anh nếu chưa hỗ trợ). "
            "Thay đổi được áp dụng ngay lập tức."
        ),
        "settings.detected_system": "Ngôn ngữ hệ thống phát hiện: {detected}",
        "settings.defaults_group": "Tùy chọn mặc định",
        "settings.default_guides": "Hiển thị khung dẫn hướng theo mặc định",
        "settings.default_strip_meta": "Xóa siêu dữ liệu EXIF / GPS khi lưu theo mặc định",
        "settings.reset_btn": "Khôi phục mặc định",
        "installer.window_title": "QuickFaceBlur v1.0.0 — Trình cài đặt",
        "installer.header_title": "Trình cài đặt QuickFaceBlur",
        "installer.header_subtitle": "Ứng dụng làm mờ khuôn mặt tự động chỉ với một cú nhấp (v1.0.0)",
        "installer.install_path": "• Thư mục cài đặt: {install_dir}",
        "installer.chk_desktop": "Tạo biểu tượng [{app_name}] ngoài Màn hình chính",
        "installer.chk_startmenu": "Đăng ký vào Start Menu và danh sách Ứng dụng đã cài đặt",
        "installer.chk_launch": "Chạy chương trình ngay sau khi cài đặt xong",
        "installer.status_ready": "Nhấn nút [🚀 Cài đặt ngay] bên dưới để bắt đầu.",
        "installer.status_copying": "Đang sao chép tệp chương trình...",
        "installer.status_registering": "Đang đăng ký biểu tượng và lối tắt...",
        "installer.status_done": "✅ Cài đặt hoàn tất!",
        "installer.btn_install": "🚀 Cài đặt ngay",
        "installer.done_title": "Cài đặt hoàn tất",
        "installer.done_message": (
            "✅ QuickFaceBlur đã được cài đặt thành công!\n\n"
            "Bạn có thể mở ứng dụng bất cứ lúc nào từ biểu tượng [{app_name}] trên Màn hình chính."
        ),
        "installer.failed_title": "Lỗi cài đặt",
        "installer.failed_message": "Đã xảy ra lỗi trong quá trình cài đặt:\n{error}",
        "uninstaller.done_title": "Đã gỡ cài đặt QuickFaceBlur",
        "uninstaller.done_message": "Đã xóa các lối tắt và thông tin đăng ký của QuickFaceBlur.",
    },
    "th": {
        "app.display_name": "QuickFaceBlur — เบลอใบหน้าอัตโนมัติในคลิกเดียว",
        "app.short_name": "QuickFaceBlur",
        "tray.open_window": "เปิด QuickFaceBlur",
        "tray.open_photos": "📂 เปิดรูปภาพ...",
        "tray.settings": "⚙️ ตั้งค่า...",
        "tray.quit": "ออก",
        "toolbar.open": "📂 เปิดรูป",
        "toolbar.open_tooltip": "เลือกรูปภาพ 1 รูปหรือหลายรูปพร้อมกันเพื่อเปิดใช้งาน",
        "toolbar.all_on": "👁️ เปิดหมด",
        "toolbar.all_on_tooltip": "เปิดการเบลอสำหรับทุกใบหน้าและพื้นที่ทั้งหมด",
        "toolbar.all_off": "🙈 ปิดหมด",
        "toolbar.all_off_tooltip": "ปิดการเบลอทั้งหมดในรูปภาพปัจจุบัน",
        "toolbar.guides": "🔍 กรอบ",
        "toolbar.guides_tooltip": "แสดงหรือซ่อนเส้นกรอบรอบใบหน้าที่ตรวจพบ",
        "toolbar.copy": "📋 คัดลอก",
        "toolbar.copy_tooltip": "คัดลอกรูปภาพความละเอียดสูงไปยังคลิปบอร์ด (Ctrl+C)",
        "toolbar.save": "💾 บันทึก",
        "toolbar.save_tooltip": "บันทึกรูปภาพปัจจุบันด้วยความละเอียดต้นฉบับ",
        "toolbar.save_all": "📦 บันทึกหมด",
        "toolbar.save_all_tooltip": "บันทึกรูปภาพทั้งหมดในรายการในครั้งเดียว",
        "toolbar.settings": "⚙️ ตั้งค่า",
        "toolbar.settings_tooltip": "เปลี่ยนภาษาที่แสดงและการตั้งค่าเริ่มต้น",
        "photos.section_title": "รายการรูปภาพ ({count})",
        "photos.add": "+ เพิ่ม",
        "photos.add_tooltip": "เพิ่มรูปภาพเข้าสู่รายการ",
        "photos.remove": "- ลบ",
        "photos.remove_tooltip": "ลบรูปภาพที่เลือกออกจากรายการ",
        "photos.clear": "ล้าง",
        "photos.clear_tooltip": "ล้างรูปภาพทั้งหมดออกจากรายการ",
        "photos.item_summary": "{total} หน้า (เบลอ {blurred})",
        "canvas.placeholder": (
            "📷 ลากและวางไฟล์รูปภาพ (เลือกหลายรูปได้) ที่นี่\n"
            "หรือคลิกปุ่ม [📂 เปิดรูป] ด้านบน\n\n"
            "(รองรับไฟล์: JPG, PNG, WEBP, BMP, TIFF)"
        ),
        "lang.section_title": "ภาษา (Language)",
        "lang.auto_option": "🌐 อัตโนมัติ (ระบบ — {detected})",
        "lang.open_settings_btn": "⚙️ ตั้งค่าเพิ่มเติม...",
        "style.section_title": "รูปแบบการเบลอ",
        "style.bokeh": "เบลอโบเก้ (ค่าเริ่มต้น)",
        "style.mosaic": "โมเสก (พิกเซล)",
        "slider.section_title": "การเบลอและการตรวจจับ",
        "slider.strength": "ความเข้มการเบลอ",
        "slider.scale": "ขนาดพื้นที่เบลอ",
        "slider.confidence": "ความไวในการตรวจจับใบหน้า",
        "slider.confidence_hint": "ลดค่าเพื่อตรวจจับใบหน้าเล็ก · เพิ่มค่าเพื่อลดการตรวจจับผิดพลาด",
        "privacy.section_title": "ตัวเลือกความเป็นส่วนตัว",
        "privacy.strip_metadata": "🛡️ ลบข้อมูลเมตา (EXIF และพิกัด GPS)",
        "privacy.strip_metadata_hint": "ลบพิกัดสถานที่ถ่ายภาพ (GPS) อุปกรณ์ และวันที่โดยอัตโนมัติเมื่อบันทึก",
        "guide.section_title": "วิธีใช้งานด่วน",
        "guide.html": (
            '<p style="margin: 0 0 7px 0;">• <b>คลิกที่ใบหน้า</b>: เปิด / ปิดการเบลอใบหน้านั้น</p>'
            '<p style="margin: 0 0 7px 0;">• <b>ลากเมาส์บนพื้นที่ว่าง</b>: วาดวงรีเบลอเพิ่มเติมเอง</p>'
            '<p style="margin: 0 0 2px 0;">• <b>คลิกขวาวงที่วาดเอง</b>: ลบพื้นที่ที่เพิ่มเอง</p>'
        ),
        "guide.clear_manual": "🗑️ ลบพื้นที่ที่เพิ่มเอง",
        "shortcut.install_btn": "📌 สร้างทางลัดบนเดสก์ท็อป",
        "status.empty": "ลากรูปภาพเข้ามาในหน้าต่าง หรือกดปุ่ม [📂 เปิดรูป] เพื่อเริ่มต้นใช้งาน",
        "status.no_faces": "ไม่พบใบหน้า ลองใช้เมาส์ลากบนรูปเพื่อเพิ่มพื้นที่เบลอด้วยตนเอง",
        "status.faces_detected": (
            "ตรวจพบใบหน้า {total} คน (เบลอ {blurred} คน) | "
            "💡 คลิกใบหน้า: เปิด/ปิด | ลากพื้นที่ว่าง: เพิ่มเบลอ | คลิกขวาวงที่วาดเอง: ลบ"
        ),
        "status.copied": "📋 คัดลอกรูปภาพความละเอียดสูง ({w}x{h}) ไปยังคลิปบอร์ดแล้ว! (กด Ctrl+V เพื่อวาง)",
        "status.saved_single": "✅ บันทึกเรียบร้อย ({meta_msg}): {path}",
        "status.saved_batch": "✅ บันทึกครบทั้ง {count} รูปเรียบร้อย ({meta_msg}): {dir}",
        "dialog.ok": "ตกลง",
        "dialog.cancel": "ยกเลิก",
        "dialog.close": "เสร็จสิ้น",
        "dialog.open_saved_folder": "📂 เปิดโฟลเดอร์ที่บันทึก",
        "file_dialog.open_title": "เลือกไฟล์รูปภาพ (เลือกหลายรูปพร้อมกันได้)",
        "file_dialog.open_filter": "ไฟล์รูปภาพ (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;ไฟล์ทั้งหมด (*.*)",
        "file_dialog.save_title": "บันทึกรูปภาพเบลอความละเอียดสูง",
        "file_dialog.save_filter": "รูปภาพ JPEG (*.jpg *.jpeg);;รูปภาพ PNG (*.png);;รูปภาพ WEBP (*.webp)",
        "file_dialog.save_all_title": "เลือกโฟลเดอร์สำหรับบันทึกรูปภาพทั้งหมด ({count} รูป)",
        "model.downloading_title": "กำลังดาวน์โหลดโมเดล AI",
        "model.downloading_message": "เปิดใช้งานครั้งแรก: กำลังดาวน์โหลดโมเดล AI ตรวจจับใบหน้า...",
        "model.init_failed_title": "เริ่มต้นโมเดล AI ไม่สำเร็จ",
        "model.init_failed_message": "เกิดข้อผิดพลาดขณะเตรียมโมเดลตรวจจับใบหน้า:\n{error}",
        "error.cannot_read_image": "ไม่สามารถอ่านไฟล์รูปภาพได้: {path}",
        "error.open_failed_title": "เปิดรูปภาพไม่สำเร็จ",
        "error.open_failed_message": "ไม่สามารถโหลดรูปภาพได้:\n{path}\n({error})",
        "error.encode_failed": "การเข้ารหัสรูปภาพล้มเหลว",
        "clipboard.done_title": "คัดลอกไปยังคลิปบอร์ดแล้ว",
        "clipboard.done_message": (
            "✅ คัดลอกรูปภาพเบลอความละเอียดสูงไปยังคลิปบอร์ดเรียบร้อยแล้ว!\n\n"
            "สามารถกดวาง (Ctrl+V) ลงใน LINE, แชท, เอกสาร หรือโปรแกรมแต่งรูปได้ทันที"
        ),
        "save.meta_stripped": "ลบข้อมูลเมตา (EXIF/GPS) แล้ว",
        "save.meta_kept": "คงข้อมูลเมตาต้นฉบับไว้",
        "save.done_title": "บันทึกรูปภาพสำเร็จ",
        "save.done_message": (
            "✅ บันทึกรูปภาพเบลอความละเอียดสูงเรียบร้อยแล้ว!\n"
            "• ความเป็นส่วนตัว: {meta_msg}\n\n"
            "ตำแหน่งที่บันทึก:\n{path}"
        ),
        "save.failed_title": "บันทึกไม่สำเร็จ",
        "save.failed_message": "เกิดข้อผิดพลาดขณะบันทึกรูปภาพ:\n{error}",
        "save_all.done_title": "บันทึกทั้งหมดเสร็จสมบูรณ์",
        "save_all.done_message": (
            "✅ บันทึกรูปภาพความละเอียดสูงครบทั้ง {count} รูปแล้ว!\n"
            "• ความเป็นส่วนตัว: {meta_msg}\n\n"
            "โฟลเดอร์ที่บันทึก:\n{dir}"
        ),
        "shortcut.win_only_title": "ทางลัดบนเดสก์ท็อป",
        "shortcut.win_only_message": "การสร้างทางลัดบนเดสก์ท็อปอัตโนมัติรองรับบนระบบ Windows",
        "shortcut.done_title": "สร้างทางลัดเรียบร้อยแล้ว",
        "shortcut.done_message": (
            "✅ สร้างไอคอน [{app_name}] บนเดสก์ท็อปเรียบร้อยแล้ว!\n\n"
            "ดับเบิลคลิกที่ไอคอนเพื่อเปิดใช้งานได้ทันทีทุกเมื่อ"
        ),
        "shortcut.failed_title": "สร้างทางลัดไม่สำเร็จ",
        "shortcut.failed_message": "เกิดข้อผิดพลาดขณะสร้างทางลัดบนเดสก์ท็อป:\n{error}",
        "settings.window_title": "ตั้งค่า — QuickFaceBlur",
        "settings.header_title": "ตั้งค่า",
        "settings.header_subtitle": "ปรับแต่งภาษาที่แสดงผลและตัวเลือกความเป็นส่วนตัวเริ่มต้น",
        "settings.lang_group": "ภาษาที่แสดงผล (Language)",
        "settings.lang_label": "ภาษาของแอปพลิเคชัน",
        "settings.lang_desc": (
            "เลือก 'อัตโนมัติ' เพื่อใช้ภาษาตามระบบปฏิบัติการเมื่อเปิดแอป (ค่าเริ่มต้นคือภาษาอังกฤษหากไม่รองรับ) "
            "การเปลี่ยนภาษาจะมีผลทันที"
        ),
        "settings.detected_system": "ภาษาของระบบที่ตรวจพบ: {detected}",
        "settings.defaults_group": "การตั้งค่าเริ่มต้น",
        "settings.default_guides": "แสดงเส้นกรอบไกด์เป็นค่าเริ่มต้น",
        "settings.default_strip_meta": "ลบข้อมูล EXIF และพิกัด GPS เมื่อบันทึกเป็นค่าเริ่มต้น",
        "settings.reset_btn": "คืนค่าเริ่มต้น",
        "installer.window_title": "QuickFaceBlur v1.0.0 — ตัวช่วยติดตั้ง",
        "installer.header_title": "ตัวช่วยติดตั้ง QuickFaceBlur",
        "installer.header_subtitle": "โปรแกรมเบลอใบหน้าอัตโนมัติในคลิกเดียวสำหรับเดสก์ท็อป (v1.0.0)",
        "installer.install_path": "• ตำแหน่งติดตั้ง: {install_dir}",
        "installer.chk_desktop": "สร้างไอคอน [{app_name}] บนเดสก์ท็อป",
        "installer.chk_startmenu": "ลงทะเบียนในเมนู Start และรายการแอปที่ติดตั้งของ Windows",
        "installer.chk_launch": "เปิดโปรแกรมทันทีหลังติดตั้งเสร็จสิ้น",
        "installer.status_ready": "คลิกปุ่ม [🚀 ติดตั้งทันที] ด้านล่างเพื่อเริ่มการติดตั้ง",
        "installer.status_copying": "กำลังคัดลอกไฟล์โปรแกรมไปยังโฟลเดอร์ติดตั้ง...",
        "installer.status_registering": "กำลังลงทะเบียนไอคอนและทางลัด...",
        "installer.status_done": "✅ ติดตั้งเสร็จสมบูรณ์!",
        "installer.btn_install": "🚀 ติดตั้งทันที",
        "installer.done_title": "ติดตั้งเสร็จสมบูรณ์",
        "installer.done_message": (
            "✅ ติดตั้ง QuickFaceBlur เรียบร้อยแล้ว!\n\n"
            "คุณสามารถดับเบิลคลิกไอคอน [{app_name}] บนเดสก์ท็อปเพื่อใช้งานได้ทันที"
        ),
        "installer.failed_title": "ข้อผิดพลาดในการติดตั้ง",
        "installer.failed_message": "เกิดข้อผิดพลาดระหว่างการติดตั้ง:\n{error}",
        "uninstaller.done_title": "ถอนการติดตั้ง QuickFaceBlur แล้ว",
        "uninstaller.done_message": "ลบทางลัดและข้อมูลการลงทะเบียนของ QuickFaceBlur เรียบร้อยแล้ว",
    },
    "ko": {
        "app.display_name": "QuickFaceBlur — 원클릭 자동 얼굴 블러",
        "app.short_name": "QuickFaceBlur (자동 얼굴 블러)",
        "tray.open_window": "QuickFaceBlur 창 열기",
        "tray.open_photos": "📂 사진 열기...",
        "tray.settings": "⚙️ 설정...",
        "tray.quit": "종료",
        "toolbar.open": "📂 사진 열기",
        "toolbar.open_tooltip": "사진을 1장 또는 여러 장 동시에 선택하여 불러옵니다.",
        "toolbar.all_on": "👁️ 전체 켜기",
        "toolbar.all_on_tooltip": "현재 사진의 모든 검출/수동 영역 블러를 켭니다.",
        "toolbar.all_off": "🙈 전체 끄기",
        "toolbar.all_off_tooltip": "현재 사진의 모든 영역 블러를 끕니다.",
        "toolbar.guides": "🔍 가이드 점선 표시",
        "toolbar.guides_tooltip": "얼굴 영역의 가이드 테두리 표시 여부를 전환합니다.",
        "toolbar.copy": "📋 클립보드 복사",
        "toolbar.copy_tooltip": "결과 이미지를 클립보드에 바로 복사합니다 (Ctrl+C)",
        "toolbar.save": "💾 고화질 저장",
        "toolbar.save_tooltip": "현재 사진을 원본 고해상도로 저장합니다.",
        "toolbar.save_all": "📦 전체 저장",
        "toolbar.save_all_tooltip": "목록에 있는 모든 사진을 한 번에 저장합니다.",
        "toolbar.settings": "⚙️ 설정",
        "toolbar.settings_tooltip": "표시 언어 및 기본 환경설정을 변경합니다.",
        "photos.section_title": "사진 목록 ({count}장)",
        "photos.add": "+ 추가",
        "photos.add_tooltip": "목록에 사진을 추가합니다.",
        "photos.remove": "- 제외",
        "photos.remove_tooltip": "현재 선택된 사진을 목록에서 제외합니다.",
        "photos.clear": "비우기",
        "photos.clear_tooltip": "목록의 모든 사진을 비웁니다.",
        "photos.item_summary": "{total}명 (블러 {blurred})",
        "canvas.placeholder": (
            "📷 사진 파일(여러 장 가능)을 여기에 끌어다 놓거나\n"
            "상단의 [📂 사진 열기] 버튼을 눌러주세요\n\n"
            "(지원 형식: JPG, PNG, WEBP, BMP, TIFF)"
        ),
        "lang.section_title": "언어 (Language)",
        "lang.auto_option": "🌐 자동 (시스템 언어 — {detected})",
        "lang.open_settings_btn": "⚙️ 상세 설정 열기...",
        "style.section_title": "블러 스타일",
        "style.bokeh": "보케 블러 (기본)",
        "style.mosaic": "모자이크 (픽셀화)",
        "slider.section_title": "블러 및 감지 설정",
        "slider.strength": "블러 강도",
        "slider.scale": "영역 크기",
        "slider.confidence": "얼굴 감지 민감도",
        "slider.confidence_hint": "낮추면 작은 얼굴 추가 검출 · 높이면 오검출 감소",
        "privacy.section_title": "개인정보 보호 옵션",
        "privacy.strip_metadata": "🛡️ 메타데이터(EXIF·위치정보) 제거",
        "privacy.strip_metadata_hint": "저장 시 촬영 위치(GPS)·기기·날짜 정보 자동 삭제",
        "guide.section_title": "간편 조작 안내",
        "guide.html": (
            '<p style="margin: 0 0 7px 0;">• <b>얼굴 클릭</b>: 해당 얼굴 블러 켜기 / 끄기</p>'
            '<p style="margin: 0 0 7px 0;">• <b>빈 곳 드래그</b>: 직접 블러 원 추가</p>'
            '<p style="margin: 0 0 2px 0;">• <b>수동 원 우클릭</b>: 직접 추가한 원 삭제</p>'
        ),
        "guide.clear_manual": "🗑️ 수동 추가 영역 삭제",
        "shortcut.install_btn": "📌 바탕화면에 바로가기 설치",
        "status.empty": "사진(여러 장 가능)을 창 안으로 끌어다 놓거나 [📂 사진 열기] 버튼을 눌러 시작하세요.",
        "status.no_faces": "감지된 얼굴이 없습니다. 마우스로 드래그하여 직접 블러 영역을 추가해 보세요.",
        "status.faces_detected": (
            "총 {total}명의 얼굴 감지됨 (블러 적용: {blurred}명) | "
            "💡 얼굴 클릭: 블러 켜기/끄기 | 빈 곳 드래그: 직접 블러 추가 | 수동 영역 우클릭: 삭제"
        ),
        "status.copied": "📋 클립보드에 고화질 결과 이미지({w}x{h})가 복사되었습니다! (Ctrl+V로 붙여넣기 가능)",
        "status.saved_single": "✅ 저장 완료 ({meta_msg}): {path}",
        "status.saved_batch": "✅ 전체 {count}장 일괄 저장 완료 ({meta_msg}): {dir}",
        "dialog.ok": "확인",
        "dialog.cancel": "취소",
        "dialog.close": "완료",
        "dialog.open_saved_folder": "📂 저장 폴더 열기",
        "file_dialog.open_title": "사진 파일 선택 (여러 장 동시 선택 가능)",
        "file_dialog.open_filter": "이미지 파일 (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;모든 파일 (*.*)",
        "file_dialog.save_title": "고화질 블러 사진 저장",
        "file_dialog.save_filter": "JPEG 이미지 (*.jpg *.jpeg);;PNG 이미지 (*.png);;WEBP 이미지 (*.webp)",
        "file_dialog.save_all_title": "전체 사진({count}장)을 저장할 폴더 선택",
        "model.downloading_title": "모델 다운로드 중",
        "model.downloading_message": "최초 실행: AI 얼굴 검출 모델을 다운로드하고 있습니다...",
        "model.init_failed_title": "AI 모델 초기화 실패",
        "model.init_failed_message": "얼굴 검출 모델을 준비하는 중 오류가 발생했습니다:\n{error}",
        "error.cannot_read_image": "이미지 파일을 읽을 수 없습니다: {path}",
        "error.open_failed_title": "사진 열기 실패",
        "error.open_failed_message": "사진을 불러올 수 없습니다:\n{path}\n({error})",
        "error.encode_failed": "이미지 인코딩에 실패했습니다.",
        "clipboard.done_title": "클립보드 복사 완료",
        "clipboard.done_message": (
            "✅ 블러 처리된 고화질 사진이 클립보드에 복사되었습니다!\n\n"
            "카카오톡, 블로그, 워드, 그림판 등에서 바로 붙여넣기(Ctrl+V) 하실 수 있습니다."
        ),
        "save.meta_stripped": "메타데이터(EXIF/GPS) 제거됨",
        "save.meta_kept": "원본 메타데이터 유지됨",
        "save.done_title": "사진 저장 완료",
        "save.done_message": (
            "✅ 고화질 블러 사진이 성공적으로 저장되었습니다!\n"
            "• 개인정보 보호: {meta_msg}\n\n"
            "저장 위치:\n{path}"
        ),
        "save.failed_title": "저장 실패",
        "save.failed_message": "사진 저장 중 오류가 발생했습니다:\n{error}",
        "save_all.done_title": "전체 사진 일괄 저장 완료",
        "save_all.done_message": (
            "✅ 총 {count}장의 고화질 사진이 모두 저장되었습니다!\n"
            "• 개인정보 보호: {meta_msg}\n\n"
            "저장 폴더:\n{dir}"
        ),
        "shortcut.win_only_title": "바탕화면 바로가기 안내",
        "shortcut.win_only_message": "바탕화면 바로가기 자동 생성은 Windows 환경에서 동작합니다.",
        "shortcut.done_title": "바탕화면 바로가기 설치 완료",
        "shortcut.done_message": (
            "✅ 바탕화면에 [{app_name}] 아이콘이 생성되었습니다!\n\n"
            "이제 바탕화면의 아이콘을 더블클릭하여 언제든 바로 실행하실 수 있습니다."
        ),
        "shortcut.failed_title": "바로가기 생성 실패",
        "shortcut.failed_message": "바탕화면 바로가기를 만드는 중 오류가 발생했습니다:\n{error}",
        "settings.window_title": "설정 — QuickFaceBlur",
        "settings.header_title": "환경설정",
        "settings.header_subtitle": "표시 언어 및 기본 개인정보 보호 옵션을 설정합니다.",
        "settings.lang_group": "표시 언어 (Language)",
        "settings.lang_label": "프로그램 언어",
        "settings.lang_desc": (
            "'자동'을 선택하면 실행 시 OS 시스템 언어를 자동으로 반영합니다(미지원 언어는 영어 기본 적용). "
            "변경 즉시 화면에 반영됩니다."
        ),
        "settings.detected_system": "감지된 시스템 언어: {detected}",
        "settings.defaults_group": "기본 실행 옵션",
        "settings.default_guides": "시작 시 얼굴 가이드 점선 표시",
        "settings.default_strip_meta": "저장 시 메타데이터(EXIF·GPS) 제거 기본 활성화",
        "settings.reset_btn": "기본값 복원",
        "installer.window_title": "QuickFaceBlur v1.0.0 — 설치 마법사",
        "installer.header_title": "QuickFaceBlur 설치 마법사",
        "installer.header_subtitle": "원클릭 자동 얼굴 블러 데스크톱 프로그램 (v1.0.0)",
        "installer.install_path": "• 설치 경로: {install_dir}",
        "installer.chk_desktop": "바탕화면에 [{app_name}] 아이콘 만들기",
        "installer.chk_startmenu": "시작 메뉴 및 Windows 설치된 앱 목록에 등록하기",
        "installer.chk_launch": "설치 완료 후 즉시 프로그램 실행하기",
        "installer.status_ready": "아래 [🚀 지금 설치하기] 버튼을 누르면 설치가 시작됩니다.",
        "installer.status_copying": "프로그램 파일을 설치 폴더로 복사하고 있습니다...",
        "installer.status_registering": "작업 표시줄 아이콘, 바탕화면 바로가기 및 앱 정보를 등록하고 있습니다...",
        "installer.status_done": "✅ 설치가 완료되었습니다!",
        "installer.btn_install": "🚀 지금 설치하기",
        "installer.done_title": "설치 완료",
        "installer.done_message": (
            "✅ QuickFaceBlur 설치가 완료되었습니다!\n\n"
            "이제 바탕화면의 [{app_name}] 아이콘을\n"
            "더블클릭하여 언제든 편리하게 사용하실 수 있습니다."
        ),
        "installer.failed_title": "설치 오류",
        "installer.failed_message": "설치 중 오류가 발생했습니다:\n{error}",
        "uninstaller.done_title": "QuickFaceBlur 제거 완료",
        "uninstaller.done_message": "QuickFaceBlur 바로가기 및 등록 정보가 제거되었습니다.",
    },
}


def normalize_language_code(raw_tag: Optional[str]) -> Optional[str]:
    """
    'en-US', 'de_DE.UTF-8', 'ja-JP', 'th_TH', 'vi', 'fr-CA' 등 다양한 로케일 문자열에서
    지원 언어 코드(en, de, ja, fr, es, vi, th, ko)를 추출한다.
    일치하지 않거나 비어 있으면 None을 반환한다.
    """
    if not raw_tag:
        return None
    cleaned = raw_tag.strip()
    if not cleaned:
        return None
    cleaned = cleaned.split(".")[0].split("@")[0].strip()
    if cleaned.upper() in ("C", "POSIX", "UTF-8", "UTF8"):
        return None

    primary = cleaned.replace("-", "_").split("_")[0].lower()
    if primary in LANGUAGE_NAMES:
        return primary
    return None


def _detect_windows_ui_locale() -> Optional[str]:
    if sys.platform != "win32":
        return None
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        win_tag = locale.windows_locale.get(int(lang_id))
        return normalize_language_code(win_tag)
    except Exception:
        return None


def detect_system_language(override_tag: Optional[str] = None) -> str:
    """
    실행 중인 OS의 시스템 UI 언어를 감지하여 지원 언어 코드를 반환한다.
    지원 목록에 없는 언어이거나 감지 실패 시 기본값인 영어('en')를 반환한다.
    """
    if override_tag is not None:
        matched = normalize_language_code(override_tag)
        return matched if matched else DEFAULT_LANGUAGE

    env_override = os.environ.get("QFB_SYSTEM_LANG")
    if env_override is not None:
        matched = normalize_language_code(env_override)
        return matched if matched else DEFAULT_LANGUAGE

    # 1. Qt QLocale 시스템 선호 UI 언어 목록 확인 (Windows Display Language / macOS Preferred Languages)
    try:
        sys_locale = QLocale.system()
        for tag in sys_locale.uiLanguages():
            matched = normalize_language_code(tag)
            if matched:
                return matched
        matched = normalize_language_code(sys_locale.name())
        if matched:
            return matched
    except Exception:
        pass

    # 2. Windows 네이티브 UI 언어 ID 확인
    win_lang = _detect_windows_ui_locale()
    if win_lang:
        return win_lang

    # 3. 환경 변수(LANGUAGE, LC_ALL, LC_MESSAGES, LANG) 확인
    for env_key in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(env_key, "")
        if not val:
            continue
        for part in val.split(":"):
            matched = normalize_language_code(part)
            if matched:
                return matched

    return DEFAULT_LANGUAGE


def get_default_settings_path() -> Path:
    """사용자별 영구 설정 파일(settings.json) 경로를 반환한다."""
    env_path = os.environ.get("QFB_SETTINGS_PATH")
    if env_path:
        return Path(env_path)

    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "QuickFaceBlur" / "settings.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "QuickFaceBlur" / "settings.json"

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "QuickFaceBlur" / "settings.json"
    return Path.home() / ".config" / "QuickFaceBlur" / "settings.json"


class AppSettingsStore:
    """언어 및 기본 실행 옵션을 JSON 파일에 안전하게 로드·저장한다."""

    def __init__(self, settings_path: Optional[Path] = None):
        self.settings_path: Path = settings_path or get_default_settings_path()
        self.data: Dict[str, Any] = {
            "language": SYSTEM_LANGUAGE_PREF,
            "default_show_guides": True,
            "default_strip_metadata": True,
        }
        self.load()

    def load(self) -> Dict[str, Any]:
        try:
            if self.settings_path.exists():
                raw = json.loads(self.settings_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    lang = raw.get("language", SYSTEM_LANGUAGE_PREF)
                    if lang == SYSTEM_LANGUAGE_PREF or lang in LANGUAGE_NAMES:
                        self.data["language"] = lang
                    else:
                        self.data["language"] = DEFAULT_LANGUAGE
                    if isinstance(raw.get("default_show_guides"), bool):
                        self.data["default_show_guides"] = raw["default_show_guides"]
                    if isinstance(raw.get("default_strip_metadata"), bool):
                        self.data["default_strip_metadata"] = raw["default_strip_metadata"]
        except Exception:
            pass
        return self.data

    def save(self) -> bool:
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.settings_path.with_suffix(".json.tmp")
            tmp_path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp_path, self.settings_path)
            return True
        except OSError:
            return False

    @property
    def language_preference(self) -> str:
        val = self.data.get("language", SYSTEM_LANGUAGE_PREF)
        if val == SYSTEM_LANGUAGE_PREF or val in LANGUAGE_NAMES:
            return val
        return DEFAULT_LANGUAGE

    @language_preference.setter
    def language_preference(self, value: str):
        if value == SYSTEM_LANGUAGE_PREF or value in LANGUAGE_NAMES:
            self.data["language"] = value
        else:
            self.data["language"] = DEFAULT_LANGUAGE
        self.save()

    @property
    def default_show_guides(self) -> bool:
        return bool(self.data.get("default_show_guides", True))

    @default_show_guides.setter
    def default_show_guides(self, value: bool):
        self.data["default_show_guides"] = bool(value)
        self.save()

    @property
    def default_strip_metadata(self) -> bool:
        return bool(self.data.get("default_strip_metadata", True))

    @default_strip_metadata.setter
    def default_strip_metadata(self, value: bool):
        self.data["default_strip_metadata"] = bool(value)
        self.save()

    def reset_defaults(self):
        self.data = {
            "language": SYSTEM_LANGUAGE_PREF,
            "default_show_guides": True,
            "default_strip_metadata": True,
        }
        self.save()


class I18nManager:
    """
    전역 다국어 번역 및 실시간 언어 전환 매니저.
    - 기본 폴백 언어: 영어('en')
    - 초기 설정값('system')일 때 OS 시스템 언어를 자동 감지하여 반영
    - 설정에서 언어 변경 시 즉시 UI 리스너들에게 알림 및 영구 저장
    """

    def __init__(
        self,
        settings_store: Optional[AppSettingsStore] = None,
        system_lang_override: Optional[str] = None,
    ):
        self.store: AppSettingsStore = settings_store or AppSettingsStore()
        self._system_lang_override: Optional[str] = system_lang_override
        self._listeners: List[Callable[[str], None]] = []
        self._current_language: str = self._resolve_active_language()
        self._apply_qt_locale()

    def _resolve_active_language(self) -> str:
        env_force = os.environ.get("QFB_LANG")
        if env_force:
            norm = normalize_language_code(env_force)
            return norm if norm else DEFAULT_LANGUAGE

        pref = self.store.language_preference
        if pref == SYSTEM_LANGUAGE_PREF:
            return detect_system_language(self._system_lang_override)
        if pref in LANGUAGE_NAMES:
            return pref
        return DEFAULT_LANGUAGE

    def _apply_qt_locale(self):
        try:
            QLocale.setDefault(QLocale(self._current_language))
        except Exception:
            pass

    @property
    def current_language(self) -> str:
        return self._current_language

    @property
    def language_preference(self) -> str:
        return self.store.language_preference

    def detected_system_language(self) -> str:
        return detect_system_language(self._system_lang_override)

    def detected_system_language_name(self) -> str:
        code = self.detected_system_language()
        return LANGUAGE_NAMES.get(code, LANGUAGE_NAMES[DEFAULT_LANGUAGE])

    def set_language(self, preference: str, persist: bool = True):
        """
        preference: 'system' 또는 지원 언어 코드 ('en', 'de', 'ja', 'fr', 'es', 'vi', 'th', 'ko').
        지원하지 않는 코드가 전달되면 기본 언어('en')로 안전하게 폴백한다.
        """
        if preference != SYSTEM_LANGUAGE_PREF and preference not in LANGUAGE_NAMES:
            normalized = normalize_language_code(preference)
            preference = normalized if normalized else DEFAULT_LANGUAGE

        if persist:
            self.store.language_preference = preference
        else:
            self.store.data["language"] = preference

        new_lang = (
            detect_system_language(self._system_lang_override)
            if preference == SYSTEM_LANGUAGE_PREF
            else preference
        )
        self._current_language = new_lang
        self._apply_qt_locale()
        self._notify_listeners()

    def refresh_from_system(self):
        new_lang = self._resolve_active_language()
        if new_lang != self._current_language:
            self._current_language = new_lang
            self._apply_qt_locale()
            self._notify_listeners()

    def tr(self, key: str, **kwargs: Any) -> str:
        lang_dict = TRANSLATIONS.get(self._current_language, TRANSLATIONS[DEFAULT_LANGUAGE])
        template = lang_dict.get(key)
        if template is None:
            template = TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
        if kwargs:
            try:
                return template.format(**kwargs)
            except Exception:
                return template
        return template

    def subscribe(self, callback: Callable[[str], None]):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[str], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self):
        for cb in list(self._listeners):
            try:
                cb(self._current_language)
            except Exception:
                pass


_GLOBAL_I18N: Optional[I18nManager] = None


def get_i18n() -> I18nManager:
    global _GLOBAL_I18N
    if _GLOBAL_I18N is None:
        _GLOBAL_I18N = I18nManager()
    return _GLOBAL_I18N


def set_global_i18n(manager: I18nManager) -> I18nManager:
    global _GLOBAL_I18N
    _GLOBAL_I18N = manager
    return _GLOBAL_I18N


def tr(key: str, **kwargs: Any) -> str:
    return get_i18n().tr(key, **kwargs)
