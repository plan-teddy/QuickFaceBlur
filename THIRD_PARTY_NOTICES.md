# Third-Party Licenses & Notices

QuickFaceBlur incorporates and interacts with the following third-party open-source components, fonts, and pretrained model weights.

---

## 1. Pretrained Face Detection Model — InsightFace SCRFD (`scrfd_2.5g_bnkps.onnx`)

- **Component:** `models/scrfd_2.5g_bnkps.onnx` (SCRFD-2.5GF with 5-point facial landmarks)
- **Upstream Project:** [InsightFace (`deepinsight/insightface`)](https://github.com/deepinsight/insightface)
- **License:** **Non-Commercial Research / Personal Use Only**
- **Notice:**
  While InsightFace's training and inference source code is released under the MIT License, the pretrained face detection model weights (`scrfd_2.5g_bnkps.onnx`) are available strictly for **non-commercial research and personal use**.
  Commercial deployment, paid distribution, or enterprise usage of the pretrained SCRFD weights requires separate commercial licensing from the InsightFace authors, or replacing the detector model with a commercially permissive alternative.

---

## 2. Bundled UI Font — Pretendard (`assets/fonts/Pretendard-*.otf`)

- **Component:** `Pretendard-Regular.otf`, `Pretendard-Medium.otf`, `Pretendard-SemiBold.otf`, `Pretendard-Bold.otf`
- **Author / Upstream:** Copyright (c) 2021 Kil Hyung-jin ([`orioncactus/pretendard`](https://github.com/orioncactus/pretendard)), incorporating Adobe Source Han Sans, Inter, and M PLUS 1p
- **License:** **SIL Open Font License, Version 1.1 (OFL-1.1)**
- **Full License Text:** Included at [`assets/fonts/OFL.txt`](assets/fonts/OFL.txt)

---

## 3. Desktop UI Framework — PySide6 / Qt for Python

- **Package:** `PySide6`
- **Upstream:** [The Qt Company — Qt for Python](https://www.qt.io/qt-for-python)
- **License:** **GNU Lesser General Public License v3.0 (LGPLv3)**
- **Notice:**
  QuickFaceBlur dynamically links against unmodified PySide6 / Qt6 shared libraries (`--onedir` on Windows and `.app` bundle frameworks on macOS) and provides full application source code and build scripts (`build_exe.py`, `build_macos.py`) so users can inspect, modify, or relink Qt libraries in accordance with the LGPLv3.
  See <https://www.gnu.org/licenses/lgpl-3.0.html>.

---

## 4. Core Python Libraries

| Package | License | Upstream |
| :--- | :--- | :--- |
| **ONNX Runtime** (`onnxruntime`) | MIT License | <https://github.com/microsoft/onnxruntime> |
| **OpenCV** (`opencv-python-headless`) | Apache License 2.0 | <https://github.com/opencv/opencv-python> |
| **NumPy** (`numpy`) | BSD 3-Clause License | <https://github.com/numpy/numpy> |
| **Pillow** (`Pillow`) | MIT-CMU / HPND License | <https://github.com/python-pillow/Pillow> |
