"""
QuickFaceBlur — macOS 네이티브 앱 번들(.app) 및 설치용 디스크 이미지(.dmg) 빌드 스크립트

사용법 (macOS Terminal):
  1) 기본 .app 번들 빌드 (dist/QuickFaceBlur.app):
     python build_macos.py

  2) .app 번들 빌드 후 드래그 앤 드롭 설치용 .dmg 생성 (dist/QuickFaceBlur_macOS_<arch>_v1.0.0.dmg):
     python build_macos.py --dmg

  3) 리소스(ONNX 모델, .icns 아이콘) 준비 및 빌드 명령어 검증만 수행:
     python build_macos.py --dry-run
"""

import argparse
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

from build_exe import APP_NAME, APP_VERSION, EXCLUDED_MODULES, ensure_app_icon, ensure_model_downloaded

BUNDLE_ID = "com.quickfaceblur.app"
ICNS_REL_PATH = "assets/icon.icns"


def ensure_macos_icns(project_root: Path) -> Path:
    """assets/icon.ico 원본을 바탕으로 macOS Retina용 고해상도 assets/icon.icns 파일을 생성한다."""
    icns_path = project_root / ICNS_REL_PATH
    icns_path.parent.mkdir(parents=True, exist_ok=True)
    if icns_path.exists() and icns_path.stat().st_size > 4096:
        return icns_path

    ico_path = ensure_app_icon(project_root)
    with Image.open(ico_path) as base_img:
        rgba_1024 = base_img.convert("RGBA").resize(
            (1024, 1024), Image.Resampling.LANCZOS
        )

    iconutil_bin = shutil.which("iconutil")
    if sys.platform == "darwin" and iconutil_bin:
        with tempfile.TemporaryDirectory() as tmpdir:
            iconset_dir = Path(tmpdir) / "icon.iconset"
            iconset_dir.mkdir(parents=True, exist_ok=True)

            icon_specs = [
                ("icon_16x16.png", 16),
                ("icon_16x16@2x.png", 32),
                ("icon_32x32.png", 32),
                ("icon_32x32@2x.png", 64),
                ("icon_128x128.png", 128),
                ("icon_128x128@2x.png", 256),
                ("icon_256x256.png", 256),
                ("icon_256x256@2x.png", 512),
                ("icon_512x512.png", 512),
                ("icon_512x512@2x.png", 1024),
            ]
            for filename, px in icon_specs:
                resized = rgba_1024.resize((px, px), Image.Resampling.LANCZOS)
                resized.save(iconset_dir / filename, format="PNG")

            subprocess.run(
                [iconutil_bin, "-c", "icns", str(iconset_dir), "-o", str(icns_path)],
                check=True,
            )
            print(f"[macOS 빌드 준비] Retina 앱 아이콘 생성 완료: {icns_path}")
            return icns_path

    rgba_1024.save(str(icns_path), format="ICNS")
    print(f"[macOS 빌드 준비] Pillow ICNS 생성 완료: {icns_path}")
    return icns_path


def build_pyinstaller_macos_command(project_root: Path) -> list[str]:
    model_path = ensure_model_downloaded(project_root)
    icns_path = ensure_macos_icns(project_root)

    sep = ";" if os.name == "nt" else ":"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        f"--name={APP_NAME}",
        f"--icon={icns_path}",
        f"--osx-bundle-identifier={BUNDLE_ID}",
        f"--add-data={model_path}{sep}models",
        f"--add-data={project_root / 'assets'}{sep}assets",
        "--collect-binaries=onnxruntime",
    ]

    for doc_name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        doc_path = project_root / doc_name
        if doc_path.exists():
            cmd.append(f"--add-data={doc_path}{sep}.")

    for mod in EXCLUDED_MODULES:
        cmd.extend(["--exclude-module", mod])

    cmd.append(str(project_root / "main.py"))
    return cmd


def patch_macos_info_plist(app_bundle: Path):
    """
    생성된 QuickFaceBlur.app/Contents/Info.plist에 Retina 스케일링, 다국어 로케일 목록,
    이미지 파일 드래그 앤 드롭(Open With) 문서 타입을 등록한다.
    """
    plist_path = app_bundle / "Contents" / "Info.plist"
    if not plist_path.exists():
        return

    with plist_path.open("rb") as fp:
        info = plistlib.load(fp)

    info["CFBundleName"] = APP_NAME
    info["CFBundleDisplayName"] = APP_NAME
    info["CFBundleIdentifier"] = BUNDLE_ID
    info["CFBundleShortVersionString"] = APP_VERSION
    info["CFBundleVersion"] = APP_VERSION
    info["LSMinimumSystemVersion"] = "11.0"
    info["NSHighResolutionCapable"] = True
    info["NSHumanReadableCopyright"] = "Copyright © 2026 QuickFaceBlur Contributors"
    info["CFBundleLocalizations"] = ["en", "de", "ja", "fr", "es", "vi", "th", "ko"]
    info["CFBundleDocumentTypes"] = [
        {
            "CFBundleTypeName": "Image File",
            "CFBundleTypeRole": "Viewer",
            "LSHandlerRank": "Alternate",
            "CFBundleTypeExtensions": [
                "jpg",
                "jpeg",
                "png",
                "webp",
                "bmp",
                "tif",
                "tiff",
            ],
        }
    ]

    with plist_path.open("wb") as fp:
        plistlib.dump(info, fp)


def codesign_macos_bundle(app_bundle: Path):
    """Apple Silicon(arm64) 환경에서 정상 실행되도록 Ad-hoc 코드 서명을 갱신한다."""
    codesign_bin = shutil.which("codesign")
    if sys.platform != "darwin" or not codesign_bin or not app_bundle.exists():
        return
    subprocess.run(
        [codesign_bin, "--force", "--deep", "--sign", "-", str(app_bundle)],
        check=True,
    )
    subprocess.run(
        [codesign_bin, "--verify", "--deep", "--strict", str(app_bundle)],
        check=True,
    )
    print(f"[macOS 서명 검증] Ad-hoc 코드 서명 및 무결성 확인 완료: {app_bundle}")


def create_macos_dmg(project_root: Path, app_bundle: Path) -> Path:
    """QuickFaceBlur.app과 Applications 바로가기를 담은 설치용 .dmg 디스크 이미지를 생성한다."""
    hdiutil_bin = shutil.which("hdiutil")
    if sys.platform != "darwin" or not hdiutil_bin:
        raise RuntimeError("macOS hdiutil 도구를 찾을 수 없습니다.")

    arch = platform.machine() or "universal"
    dmg_name = f"{APP_NAME}_macOS_{arch}_v{APP_VERSION}.dmg"
    dmg_path = project_root / "dist" / dmg_name
    if dmg_path.exists():
        dmg_path.unlink()

    with tempfile.TemporaryDirectory() as staging_str:
        staging_dir = Path(staging_str)
        staged_app = staging_dir / f"{APP_NAME}.app"
        shutil.copytree(app_bundle, staged_app, symlinks=True)
        os.symlink("/Applications", staging_dir / "Applications")

        for doc_name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            src_doc = project_root / doc_name
            if src_doc.exists():
                shutil.copy2(src_doc, staging_dir / doc_name)

        subprocess.run(
            [
                hdiutil_bin,
                "create",
                "-volname",
                APP_NAME,
                "-srcfolder",
                str(staging_dir),
                "-ov",
                "-format",
                "UDZO",
                str(dmg_path),
            ],
            check=True,
        )

    size_mb = dmg_path.stat().st_size / (1024 * 1024)
    print(f"[macOS DMG 완료] {dmg_path} ({size_mb:.2f} MB)")
    return dmg_path


def main():
    parser = argparse.ArgumentParser(description="QuickFaceBlur macOS .app & .dmg 빌드 스크립트")
    parser.add_argument(
        "--dmg",
        action="store_true",
        help=".app 빌드 완료 후 배포용 .dmg 디스크 이미지까지 생성",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="모델/.icns 아이콘 준비 및 PyInstaller 명령어만 출력하고 종료",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    cmd = build_pyinstaller_macos_command(project_root)

    print("\n[macOS PyInstaller 빌드 명령어]")
    print(" ".join(f'"{c}"' if " " in c else c for c in cmd))

    if args.dry_run:
        print("\n[--dry-run 완료] macOS 리소스 검증 및 명령어 생성이 정상 완료되었습니다.")
        return

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[패키지 설치] PyInstaller가 설치되어 있지 않아 자동 설치합니다...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    subprocess.run(cmd, cwd=str(project_root), check=True)

    app_bundle = project_root / "dist" / f"{APP_NAME}.app"
    if not app_bundle.exists():
        raise FileNotFoundError(f"빌드된 앱 번들을 찾을 수 없습니다: {app_bundle}")

    # PyInstaller --onedir + --windowed 모드에서 함께 생성되는 중복 폴더 정리(선택)
    raw_dir = project_root / "dist" / APP_NAME
    if raw_dir.exists() and raw_dir.is_dir():
        shutil.rmtree(raw_dir, ignore_errors=True)

    patch_macos_info_plist(app_bundle)
    codesign_macos_bundle(app_bundle)
    print(f"\n✅ [macOS 앱 빌드 성공] 실행 번들: {app_bundle}")

    if args.dmg:
        create_macos_dmg(project_root, app_bundle)


if __name__ == "__main__":
    main()
