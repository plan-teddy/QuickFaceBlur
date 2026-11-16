# QuickFaceBlur

**One-Click Offline Automatic Face Blur Desktop App for macOS & Windows**

QuickFaceBlur is a fast, lightweight, 100% offline desktop application that automatically detects faces (including small and side-profile faces) and applies natural rotated-ellipse bokeh blur or pixel mosaic in milliseconds. All AI inference runs locally on your device—no photos are ever uploaded to any server.

---

## Key Features

- **100% Offline Local AI Detection:** Powered by `SCRFD-2.5GF` (`onnxruntime`) with 5-point facial landmarks—detects group photos, small faces, and tilted faces in ~20–80 ms on standard laptop CPUs.
- **Natural Rotated Ellipse Feathering:** Aligns each blur ellipse to eye-tilt angle with smooth Gaussian alpha feathering (Bokeh Blur or Pixel Mosaic).
- **One-Click Toggle & Custom Regions:**
  - **Left-click a face:** Instantly toggle blur ON / OFF (keep family or friends unblurred).
  - **Drag on empty space:** Draw a custom blur ellipse (e.g., license plates, badges, back of heads).
  - **Right-click a custom ellipse:** Delete the manually added region.
- **Batch Processing & Clipboard Copy:** Load multiple photos or entire folders via drag-and-drop, copy full-resolution results directly (`Ctrl+C` / `Cmd+C`), or batch-export all photos at once.
- **Privacy Protection (EXIF & GPS Stripping):** Automatically strips camera, date, and GPS location metadata when saving (configurable).
- **Multi-Language Localization (8 Languages):**
  - Default fallback language: **English (`en`)**
  - Automatically detects and applies your OS display language on startup, and supports instant live switching in **Settings (`⚙️`)**:
    - English (`en`), Deutsch (`de`), 日本語 (`ja`), Français (`fr`), Español (`es`), Tiếng Việt (`vi`), ไทย (`th`), 한국어 (`ko`).

---

## Download (macOS & Windows)

Prebuilt standalone packages (no Python installation required) are available on the **[Releases](https://github.com/plan-teddy/QuickFaceBlur/releases/latest)** page:

| Platform | Package | Notes |
| :--- | :--- | :--- |
| **macOS (Apple Silicon)** | `QuickFaceBlur_macOS_arm64_v1.0.0.dmg` | Drag `QuickFaceBlur.app` to `Applications` |
| **Windows 10 / 11 (Installer)** | `QuickFaceBlur_Setup_v1.0.0.exe` | Desktop & Start Menu shortcuts included |
| **Windows 10 / 11 (Portable)** | `QuickFaceBlur_Win11_Portable_v1.0.0.zip` | Unzip and run `QuickFaceBlur.exe` directly |

---

## Run from Source

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

pip install -r requirements.txt
python main.py
```

Run automated tests:

```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

---

## Build Standalone Desktop Packages

### macOS (`.app` Bundle & `.dmg` Disk Image)

```bash
pip install -r requirements.txt pyinstaller
python build_macos.py --dmg
```

- App bundle: `dist/QuickFaceBlur.app`
- Drag-to-Applications installer: `dist/QuickFaceBlur_macOS_<arch>_v1.0.0.dmg`
- *macOS Gatekeeper Note:* Because open-source builds use ad-hoc signing (`codesign --sign -`) rather than a paid Apple Developer ID certificate, if macOS displays an unverified developer prompt on first launch from a downloaded `.dmg`, run `xattr -cr /Applications/QuickFaceBlur.app` or allow it in **System Settings → Privacy & Security → Open Anyway**.

### Windows (`.exe` Portable & `Setup.exe` Installer)

```powershell
pip install -r requirements.txt pyinstaller
python build_exe.py --portable-zip --installer
```

- Portable folder: `dist/QuickFaceBlur/QuickFaceBlur.exe`
- Portable archive: `dist/QuickFaceBlur_Win11_Portable_v1.0.0.zip`
- Windows installer (when Inno Setup 6 is installed): `dist/QuickFaceBlur_Setup_v1.0.0.exe`

---

## 한국어 안내 (Korean Overview)

**QuickFaceBlur**는 인터넷 연결이나 외부 서버 전송 없이 내 PC/Mac에서 100% 로컬 AI로 동작하는 **원클릭 자동 얼굴 블러 데스크톱 앱**입니다.

- **초고속 얼굴 자동 감지 및 회전 타원 보케 블러:** 단체 사진의 작은 얼굴·측면 얼굴까지 빠르게 감지해 눈 각도에 맞춘 자연스러운 보케 블러/모자이크를 적용합니다.
- **간편한 클릭 편집:** 얼굴을 클릭해 블러를 켜고 끌 수 있으며, 빈 곳을 드래그해 직접 블러 영역을 추가하거나 우클릭으로 삭제할 수 있습니다.
- **다중 사진 일괄 저장 & EXIF/GPS 위치정보 자동 제거:** 여러 장의 사진을 한 번에 처리하고 촬영 위치(GPS) 등 개인정보 메타데이터를 깔끔하게 제거해 저장합니다.
- **8개국어 지원:** 실행 시 시스템 언어를 자동 감지하며(미지원 언어 시 영어 기본), 상단 `[⚙️ 설정]`에서 영어·독일어·일본어·프랑스어·스페인어·베트남어·태국어·한국어로 즉시 변경할 수 있습니다.

---

## License & Third-Party Notices

- **Application Source Code:** Licensed under the **[MIT License](LICENSE)**.
- **Pretrained AI Model Weights (`models/scrfd_2.5g_bnkps.onnx`):** Provided from [InsightFace](https://github.com/deepinsight/insightface) under **Non-Commercial Research / Personal Use Only** terms. Commercial use of the pretrained SCRFD weights requires separate licensing from InsightFace or substituting a commercially permissive detector model.
- **Bundled Font (`Pretendard`):** Licensed under the **SIL Open Font License 1.1** ([`assets/fonts/OFL.txt`](assets/fonts/OFL.txt)).
- **UI Framework (`PySide6` / Qt6):** Licensed under **LGPLv3**.

See **[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)** for full attribution and license details.
