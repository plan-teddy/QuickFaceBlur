import ctypes
from ctypes import wintypes
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QWidget

APP_USER_MODEL_ID = "QuickFaceBlur.Desktop.App.1.0"
INSTALLER_USER_MODEL_ID = "QuickFaceBlur.Desktop.Installer.1.0"
APP_DISPLAY_NAME = "QuickFaceBlur — One-Click Auto Face Blur"
APP_SHORT_NAME = "QuickFaceBlur"
APP_VERSION = "1.0.0"
APP_PUBLISHER = "QuickFaceBlur"

# OS별 내장 다국어(일어/태국어/베트남어/유럽어/한국어) 시스템 폰트 폴백 스택 구성
if sys.platform == "win32":
    FONT_FALLBACK_FAMILIES = [
        "Pretendard",
        "Segoe UI",
        "Yu Gothic UI",
        "Meiryo",
        "Leelawadee UI",
        "Tahoma",
        "Malgun Gothic",
    ]
elif sys.platform == "darwin":
    FONT_FALLBACK_FAMILIES = [
        "Pretendard",
        "Hiragino Sans",
        "Thonburi",
        "Apple SD Gothic Neo",
    ]
else:
    FONT_FALLBACK_FAMILIES = [
        "Pretendard",
        "Noto Sans",
        "Noto Sans CJK JP",
        "Noto Sans Thai",
        "DejaVu Sans",
    ]

FONT_FAMILY_CSS = ", ".join(f'"{fam}"' for fam in FONT_FALLBACK_FAMILIES)


if sys.platform == "win32":
    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", wintypes.BYTE * 8),
        ]

    class PROPERTYKEY(ctypes.Structure):
        _fields_ = [
            ("fmtid", GUID),
            ("pid", wintypes.DWORD),
        ]

    class PROPVARIANT(ctypes.Structure):
        _fields_ = [
            ("vt", wintypes.USHORT),
            ("wReserved1", wintypes.USHORT),
            ("wReserved2", wintypes.USHORT),
            ("wReserved3", wintypes.USHORT),
            ("pwszVal", wintypes.LPWSTR),
            ("ullVal_pad", ctypes.c_ulonglong),
        ]

    IID_IPropertyStore = GUID(
        0x886D8EEB,
        0x8CF2,
        0x4446,
        (wintypes.BYTE * 8)(0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99),
    )

    FMTID_AppUserModel = GUID(
        0x9F4C2855,
        0x9F79,
        0x4B39,
        (wintypes.BYTE * 8)(0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3),
    )

    PKEY_AppUserModel_RelaunchCommand = PROPERTYKEY(FMTID_AppUserModel, 2)
    PKEY_AppUserModel_RelaunchIconResource = PROPERTYKEY(FMTID_AppUserModel, 3)
    PKEY_AppUserModel_RelaunchDisplayNameResource = PROPERTYKEY(FMTID_AppUserModel, 4)
    PKEY_AppUserModel_ID = PROPERTYKEY(FMTID_AppUserModel, 5)

    VT_LPWSTR = 31
    VT_EMPTY = 0


def _set_propstore_strings(prop_store_ptr: ctypes.c_void_p, kv_pairs: list) -> bool:
    """COM IPropertyStore 포인터에 문자열 속성들을 기록하고 Commit한다."""
    if sys.platform != "win32" or not prop_store_ptr or not prop_store_ptr.value:
        return False

    try:
        vtable = ctypes.cast(
            prop_store_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        SetValueProto = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.POINTER(PROPERTYKEY),
            ctypes.POINTER(PROPVARIANT),
        )
        CommitProto = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)
        ReleaseProto = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)

        set_value_fn = SetValueProto(vtable[6])
        commit_fn = CommitProto(vtable[7])
        release_fn = ReleaseProto(vtable[2])

        try:
            for pkey, text_val in kv_pairs:
                if not text_val:
                    continue
                pv = PROPVARIANT()
                pv.vt = VT_LPWSTR
                pv.pwszVal = text_val
                set_value_fn(prop_store_ptr, ctypes.byref(pkey), ctypes.byref(pv))
            hr = commit_fn(prop_store_ptr)
            return hr == 0
        finally:
            release_fn(prop_store_ptr)
    except Exception:
        return False


def register_aumid_in_registry(
    app_id: str,
    display_name: str,
    icon_path: Optional[str] = None,
) -> bool:
    """
    Windows 10/11 작업 표시줄이 pythonw.exe 기반 프로세스의 아이콘을
    정상적으로 식별할 수 있도록 HKCU\\Software\\Classes\\AppUserModelId에 등록한다.
    """
    if sys.platform != "win32":
        return False
    try:
        import winreg

        key_path = f"Software\\Classes\\AppUserModelId\\{app_id}"
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE
        ) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, display_name)
            if icon_path and os.path.exists(icon_path):
                abs_icon = os.path.abspath(icon_path)
                winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, abs_icon)
                winreg.SetValueEx(key, "IconBackgroundColor", 0, winreg.REG_SZ, "002563EB")
        return True
    except Exception:
        return False


def init_windows_app_id(
    icon_path: Optional[str] = None,
    app_id: str = APP_USER_MODEL_ID,
    display_name: str = APP_DISPLAY_NAME,
):
    """프로세스 시작 시 AppUserModelID 및 레지스트리 아이콘 매핑을 초기화한다."""
    if sys.platform != "win32":
        return
    register_aumid_in_registry(app_id, display_name, icon_path)
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


def apply_app_icon(app: QApplication, icon_path: Optional[str]):
    """QApplication 전역 아이콘을 설정하여 모든 대화상자와 작업 표시줄에 반영한다."""
    if icon_path and os.path.exists(icon_path):
        app.setWindowIcon(QIcon(os.path.abspath(icon_path)))


_LOADED_FONT_FAMILY: Optional[str] = None


def load_bundled_pretendard_fonts() -> str:
    """
    assets/fonts 폴더에 내장된 Pretendard(프리텐다드) OTF/TTF 폰트들을
    QFontDatabase에 등록하고 패밀리명을 반환한다.
    사용자의 Windows PC에 프리텐다드가 설치되어 있지 않아도 100% 동일하게 렌더링된다.
    """
    global _LOADED_FONT_FAMILY
    if _LOADED_FONT_FAMILY:
        return _LOADED_FONT_FAMILY

    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(getattr(sys, "_MEIPASS")) / "assets" / "fonts")
    base_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent
    candidates.append(base_dir / "assets" / "fonts")
    candidates.append(Path.cwd() / "assets" / "fonts")

    detected_family: Optional[str] = None
    for font_dir in candidates:
        if font_dir.exists() and font_dir.is_dir():
            for font_file in sorted(font_dir.iterdir()):
                if font_file.suffix.lower() in (".otf", ".ttf"):
                    fid = QFontDatabase.addApplicationFont(str(font_file.resolve()))
                    if fid >= 0:
                        fams = QFontDatabase.applicationFontFamilies(fid)
                        if fams and not detected_family:
                            detected_family = fams[0]
            if detected_family:
                break

    if not detected_family:
        detected_family = "Pretendard"
    _LOADED_FONT_FAMILY = detected_family
    return detected_family


def create_smooth_default_font(pixel_size: int = 19) -> QFont:
    """150% 등 소수점 배율 및 다국어(일어/태국어/베트남어 등)에서도 선명하게 보이는 기본 폰트(19px) 생성."""
    family = load_bundled_pretendard_fonts()
    font = QFont(family)
    families = [family] + [f for f in FONT_FALLBACK_FAMILIES if f != family]
    font.setFamilies(families)
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight.Medium)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def configure_light_theme_and_font(app: QApplication, pixel_size: int = 19):
    """OS 다크모드 설정과 무관하게 항상 깔끔한 밝은 테마(Light Theme)와 Pretendard 19px 기본 폰트를 적용한다."""
    load_bundled_pretendard_fonts()
    try:
        QGuiApplication.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except Exception:
        pass

    try:
        app.setStyle("Fusion")
    except Exception:
        pass

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#F1F5F9"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#0F172A"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F8FAFC"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#0F172A"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#0F172A"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#0F172A"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2563EB"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#64748B")
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#64748B")
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#64748B")
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor("#F1F5F9")
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor("#F1F5F9")
    )
    app.setPalette(palette)
    app.setFont(create_smooth_default_font(pixel_size))


def apply_window_taskbar_icon(
    widget: QWidget,
    icon_path: Optional[str],
    app_id: str = APP_USER_MODEL_ID,
    display_name: str = APP_DISPLAY_NAME,
    relaunch_cmd: Optional[str] = None,
) -> bool:
    """
    최상위 윈도우(HWND)에 Win32 WM_SETICON, GCLP_HICON 및
    SHGetPropertyStoreForWindow(PKEY_AppUserModel_RelaunchIconResource)를 모두 적용하여,
    PE 리소스가 없는 pythonw.exe 실행 시에도 Windows 11 작업 표시줄 아이콘이 완벽히 표시되게 한다.
    """
    if not icon_path or not os.path.exists(icon_path):
        return False

    abs_icon = os.path.abspath(icon_path)
    widget.setWindowIcon(QIcon(abs_icon))

    if sys.platform != "win32":
        return True

    try:
        hwnd = int(widget.winId())
        if not hwnd:
            return False

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        LR_DEFAULTSIZE = 0x0040
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        GCLP_HICON = -14
        GCLP_HICONSM = -34

        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.LoadImageW.restype = wintypes.HANDLE

        hicon_big = user32.LoadImageW(None, abs_icon, IMAGE_ICON, 256, 256, LR_LOADFROMFILE)
        if not hicon_big:
            hicon_big = user32.LoadImageW(
                None, abs_icon, IMAGE_ICON, 48, 48, LR_LOADFROMFILE | LR_DEFAULTSIZE
            )
        hicon_small = user32.LoadImageW(None, abs_icon, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        if not hicon_small:
            hicon_small = hicon_big

        if hicon_big:
            user32.SendMessageW(wintypes.HWND(hwnd), WM_SETICON, ICON_BIG, hicon_big)
            if hasattr(user32, "SetClassLongPtrW"):
                user32.SetClassLongPtrW(wintypes.HWND(hwnd), GCLP_HICON, hicon_big)
        if hicon_small:
            user32.SendMessageW(wintypes.HWND(hwnd), WM_SETICON, ICON_SMALL, hicon_small)
            if hasattr(user32, "SetClassLongPtrW"):
                user32.SetClassLongPtrW(wintypes.HWND(hwnd), GCLP_HICONSM, hicon_small)

        # SHGetPropertyStoreForWindow를 통해 HWND 자체에 아이콘 리소스와 AUMID를 직접 각인
        shell32.SHGetPropertyStoreForWindow.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(GUID),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        shell32.SHGetPropertyStoreForWindow.restype = ctypes.c_long

        prop_store = ctypes.c_void_p()
        hr = shell32.SHGetPropertyStoreForWindow(
            wintypes.HWND(hwnd),
            ctypes.byref(IID_IPropertyStore),
            ctypes.byref(prop_store),
        )
        if hr == 0 and prop_store.value:
            cmd = relaunch_cmd or sys.executable
            props = [
                (PKEY_AppUserModel_ID, app_id),
                (PKEY_AppUserModel_RelaunchIconResource, f"{abs_icon},0"),
                (PKEY_AppUserModel_RelaunchDisplayNameResource, display_name),
                (PKEY_AppUserModel_RelaunchCommand, f'"{cmd}"'),
            ]
            _set_propstore_strings(prop_store, props)

        return True
    except Exception:
        return False


def stamp_shortcut_aumid(
    shortcut_path: str,
    icon_path: str,
    app_id: str = APP_USER_MODEL_ID,
    display_name: str = APP_DISPLAY_NAME,
    target_exe: Optional[str] = None,
) -> bool:
    """
    생성된 .lnk 바로가기 파일의 IPropertyStore에 System.AppUserModel.ID 및
    RelaunchIconResource를 기록하여 Windows 11 작업 표시줄 그룹핑 시 아이콘이 유실되지 않게 한다.
    """
    if sys.platform != "win32" or not os.path.exists(shortcut_path):
        return False

    try:
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        ole32.CoInitialize(None)

        GPS_READWRITE = 2
        shell32.SHGetPropertyStoreFromParsingName.argtypes = [
            wintypes.LPCWSTR,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(GUID),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        shell32.SHGetPropertyStoreFromParsingName.restype = ctypes.c_long

        prop_store = ctypes.c_void_p()
        hr = shell32.SHGetPropertyStoreFromParsingName(
            os.path.abspath(shortcut_path),
            None,
            GPS_READWRITE,
            ctypes.byref(IID_IPropertyStore),
            ctypes.byref(prop_store),
        )
        if hr == 0 and prop_store.value:
            abs_icon = os.path.abspath(icon_path)
            props = [
                (PKEY_AppUserModel_ID, app_id),
                (PKEY_AppUserModel_RelaunchIconResource, f"{abs_icon},0"),
                (PKEY_AppUserModel_RelaunchDisplayNameResource, display_name),
            ]
            if target_exe:
                props.append((PKEY_AppUserModel_RelaunchCommand, f'"{target_exe}"'))
            return _set_propstore_strings(prop_store, props)
    except Exception:
        pass
    return False


def create_windows_shortcut(
    target_exe: str,
    working_dir: str,
    shortcut_path: str,
    icon_path: str,
    app_id: str = APP_USER_MODEL_ID,
    description: str = APP_DISPLAY_NAME,
) -> bool:
    """Windows .lnk 바로가기를 생성하고 아이콘 및 AppUserModelID를 모두 각인한다."""
    if sys.platform != "win32":
        return False

    abs_target = os.path.abspath(target_exe)
    abs_work = os.path.abspath(working_dir)
    abs_lnk = os.path.abspath(shortcut_path)
    abs_icon = os.path.abspath(icon_path)

    ps_cmd = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$lnk = $ws.CreateShortcut('{abs_lnk}'); "
        f"$lnk.TargetPath = '{abs_target}'; "
        f"$lnk.WorkingDirectory = '{abs_work}'; "
        f"$lnk.Description = '{description}'; "
        f"if (Test-Path '{abs_icon}') {{ $lnk.IconLocation = '{abs_icon},0' }}; "
        "$lnk.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
        check=True,
        creationflags=0x08000000,
    )
    stamp_shortcut_aumid(
        shortcut_path=abs_lnk,
        icon_path=abs_icon,
        app_id=app_id,
        display_name=description,
        target_exe=abs_target,
    )
    return os.path.exists(abs_lnk)


def notify_shell_icon_cache_updated():
    """Windows 탐색기(Explorer)의 바로가기 및 작업 표시줄 아이콘 캐시를 즉시 새로고침한다."""
    if sys.platform != "win32":
        return
    try:
        SHCNE_ASSOCCHANGED = 0x08000000
        SHCNF_IDLIST = 0x0000
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
    except Exception:
        pass


def register_windows_uninstall_entry(
    install_dir: str,
    target_exe: str,
    icon_path: str,
    installer_exe: Optional[str] = None,
) -> bool:
    """
    Windows [설정 -> 앱 -> 설치된 앱 (프로그램 추가/제거)]에 정식 설치형 프로그램으로 등록한다.
    """
    if sys.platform != "win32":
        return False
    try:
        import winreg

        uninstall_key_path = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\QuickFaceBlur"
        abs_install = os.path.abspath(install_dir)
        abs_icon = os.path.abspath(icon_path)
        uninstaller = os.path.abspath(installer_exe) if installer_exe else os.path.abspath(target_exe)

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, uninstall_key_path, 0, winreg.KEY_WRITE
        ) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_SHORT_NAME)
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, f"{abs_icon},0")
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, APP_PUBLISHER)
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, abs_install)
            winreg.SetValueEx(
                key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstaller}" --uninstall'
            )
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, 165000)
        return True
    except Exception:
        return False


def unregister_windows_uninstall_entry():
    """Windows [설치된 앱] 레지스트리 항목 및 AUMID 클래스를 제거한다."""
    if sys.platform != "win32":
        return
    try:
        import winreg

        winreg.DeleteKey(
            winreg.HKEY_CURRENT_USER,
            "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\QuickFaceBlur",
        )
    except Exception:
        pass
    try:
        import winreg

        winreg.DeleteKey(
            winreg.HKEY_CURRENT_USER,
            f"Software\\Classes\\AppUserModelId\\{APP_USER_MODEL_ID}",
        )
    except Exception:
        pass
