"""
QuickFaceBlur — Windows 실행 파일(.exe) 및 설치형 패키지 빌드 스크립트 (Step 5)

사용법 (Windows PowerShell / CMD):
  1) 기본 포터블 폴더 빌드 (dist/QuickFaceBlur/QuickFaceBlur.exe - 권장, 가장 빠른 구동 속도):
     python build_exe.py

  2) 단일 실행 파일 빌드 (dist/QuickFaceBlur.exe):
     python build_exe.py --onefile

  3) 포터블 폴더 빌드 후 Inno Setup 설치 파일(QuickFaceBlur_Setup.exe)까지 자동 생성:
     python build_exe.py --installer
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageDraw

from src.detector import FALLBACK_MODEL_URLS, resolve_model_path

APP_NAME = "QuickFaceBlur"
APP_VERSION = "1.0.0"
MODEL_REL_PATH = "models/scrfd_2.5g_bnkps.onnx"
ICON_REL_PATH = "assets/icon.ico"

# 용량 비대화를 막기 위해 제외할 불필요 패키지 및 미사용 Qt 모듈 (SPEC 7.1)
EXCLUDED_MODULES = [
    "torch",
    "torchvision",
    "scipy",
    "matplotlib",
    "pandas",
    "tkinter",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtPositioning",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
]


def ensure_model_downloaded(project_root: Path) -> Path:
    """번들링 전 scrfd_2.5g_bnkps.onnx 모델 파일이 로컬에 존재하는지 확인하고 없으면 다운로드한다."""
    model_path = project_root / MODEL_REL_PATH
    model_path.parent.mkdir(parents=True, exist_ok=True)
    if model_path.exists() and model_path.stat().st_size > 2_000_000:
        print(f"[빌드 준비] ONNX 모델 확인 완료: {model_path} ({model_path.stat().st_size / (1024*1024):.2f} MB)")
        return model_path

    print("[빌드 준비] ONNX 모델 다운로드 중...")
    import urllib.request

    for url in FALLBACK_MODEL_URLS:
        try:
            urllib.request.urlretrieve(url, str(model_path))
            if model_path.exists() and model_path.stat().st_size > 2_000_000:
                print(f"[빌드 준비] 다운로드 완료: {model_path}")
                return model_path
        except Exception as exc:
            print(f"[경고] 미러 다운로드 실패 ({url}): {exc}")

    raise RuntimeError("ONNX 모델 파일 다운로드에 실패했습니다.")


def ensure_app_icon(project_root: Path) -> Path:
    """Windows 실행 파일 및 바탕화면 단축 아이콘용 .ico 파일을 생성한다."""
    icon_path = project_root / ICON_REL_PATH
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    if icon_path.exists():
        return icon_path

    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 둥근 다크 블루 배경
    draw.rounded_rectangle((12, 12, size - 12, size - 12), radius=56, fill=(29, 78, 216, 255))
    # 보케 블러 타원 심볼
    draw.ellipse((56, 44, size - 56, size - 44), fill=(56, 189, 248, 220), outline=(255, 255, 255, 240), width=8)
    draw.ellipse((84, 78, size - 84, size - 78), fill=(22, 163, 74, 230))

    img.save(
        str(icon_path),
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"[빌드 준비] 앱 아이콘 생성 완료: {icon_path}")
    return icon_path


def build_pyinstaller_command(project_root: Path, onefile: bool = False) -> list[str]:
    model_path = ensure_model_downloaded(project_root)
    icon_path = ensure_app_icon(project_root)

    # Windows는 ';', macOS/Linux는 ':'를 PyInstaller --add-data 구분자로 사용
    sep = ";" if os.name == "nt" else ":"
    add_model_arg = f"{model_path}{sep}models"
    add_assets_arg = f"{project_root / 'assets'}{sep}assets"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",  # 콘솔 창 숨김 (GUI 전용)
        f"--name={APP_NAME}",
        f"--icon={icon_path}",
        f"--add-data={add_model_arg}",
        f"--add-data={add_assets_arg}",
        "--collect-binaries=onnxruntime",
    ]

    for doc_name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        doc_path = project_root / doc_name
        if doc_path.exists():
            cmd.append(f"--add-data={doc_path}{sep}.")

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    for mod in EXCLUDED_MODULES:
        cmd.extend(["--exclude-module", mod])

    cmd.append(str(project_root / "main.py"))
    return cmd


def compile_inno_setup_installer(project_root: Path):
    """Windows 환경에서 Inno Setup(ISCC.exe)이 설치되어 있으면 설치형 Setup.exe를 생성한다."""
    iss_path = project_root / "installer.iss"
    if not iss_path.exists():
        print(f"[안내] {iss_path} 파일이 없어 인스톨러 빌드를 건너뜁니다.")
        return

    candidates = [
        shutil.which("ISCC"),
        shutil.which("ISCC.exe"),
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    iscc_bin = next((c for c in candidates if c and os.path.exists(c)), None)
    if not iscc_bin:
        print(
            "[안내] Inno Setup 6 (ISCC.exe)를 찾을 수 없습니다.\n"
            "  -> Inno Setup 설치 후 `ISCC.exe installer.iss`를 실행하면\n"
            "     `dist/QuickFaceBlur_Setup_v1.0.0.exe` 윈도우 설치 프로그램이 생성됩니다."
        )
        return

    print(f"[인스톨러 빌드] Inno Setup 컴파일 시작: {iscc_bin}")
    subprocess.run([iscc_bin, str(iss_path)], check=True)
    print(f"[인스톨러 완료] dist/{APP_NAME}_Setup_v{APP_VERSION}.exe 생성 완료!")


def main():
    parser = argparse.ArgumentParser(description="QuickFaceBlur PyInstaller & Windows Installer 빌드 스크립트")
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="단일 .exe 실행 파일로 빌드 (기본값: 구동 속도가 빠른 폴더형 --onedir)",
    )
    parser.add_argument(
        "--installer",
        action="store_true",
        help="빌드 완료 후 Inno Setup으로 Windows 설치 마법사(QuickFaceBlur_Setup.exe) 생성",
    )
    parser.add_argument(
        "--portable-zip",
        action="store_true",
        help="폴더형(--onedir) 빌드 결과물을 배포용 포터블 ZIP 파일로 압축",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="모델/아이콘 준비 및 PyInstaller 명령어만 출력하고 종료",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    cmd = build_pyinstaller_command(project_root, onefile=args.onefile)

    print("\n[PyInstaller 빌드 명령어]")
    print(" ".join(f'"{c}"' if " " in c else c for c in cmd))

    if args.dry_run:
        print("\n[--dry-run 완료] 리소스 검증 및 명령어 생성이 정상 완료되었습니다.")
        return

    # PyInstaller 설치 여부 확인
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[패키지 설치] PyInstaller가 설치되어 있지 않아 자동 설치합니다...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    subprocess.run(cmd, cwd=str(project_root), check=True)

    if args.onefile:
        out_target = project_root / "dist" / (f"{APP_NAME}.exe" if os.name == "nt" else APP_NAME)
    else:
        out_target = project_root / "dist" / APP_NAME
        for doc_name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            src_doc = project_root / doc_name
            if src_doc.exists() and out_target.exists():
                shutil.copy2(src_doc, out_target / doc_name)
    print(f"\n✅ [빌드 성공] 결과물 경로: {out_target}")

    if args.portable_zip and not args.onefile and out_target.exists():
        zip_base = project_root / "dist" / f"{APP_NAME}_Win11_Portable_v{APP_VERSION}"
        zip_file = Path(f"{zip_base}.zip")
        if zip_file.exists():
            zip_file.unlink()
        shutil.make_archive(str(zip_base), "zip", root_dir=project_root / "dist", base_dir=APP_NAME)
        print(f"[포터블 ZIP 완료] {zip_file} ({zip_file.stat().st_size / (1024 * 1024):.2f} MB)")

    if args.installer and not args.onefile:
        compile_inno_setup_installer(project_root)


if __name__ == "__main__":
    main()
