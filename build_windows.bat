@echo off
chcp 65001 >nul
setlocal

echo ========================================================
echo  QuickFaceBlur - Windows 설치형/포터블 앱 자동 빌드
echo ========================================================

if not exist ".venv_win" (
    echo [1/4] 깨끗한 가상환경(.venv_win) 생성 중...
    python -m venv .venv_win
)

echo [2/4] 필수 최소 패키지(5종) 및 PyInstaller 설치 중...
call .venv_win\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

echo [3/4] Step 2/3/4 단위 테스트 검증 중...
python tests\test_step2_detector.py
if errorlevel 1 (
    echo [오류] 모델 검출기 테스트 실패!
    exit /b 1
)

echo [4/4] PyInstaller 실행 파일 및 Windows 설치 프로그램 빌드 중...
python build_exe.py --installer

echo ========================================================
echo  빌드 완료!
echo  - 포터블 폴더: dist\QuickFaceBlur\QuickFaceBlur.exe
echo  - 설치 마법사: dist\QuickFaceBlur_Setup_v1.0.0.exe (Inno Setup 설치 시)
echo ========================================================
pause
