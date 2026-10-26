@echo off
cd /d "%~dp0"
python -m pip install pyinstaller opencv-python || exit /b 1

python -m PyInstaller --noconfirm --clean --windowed --name snimanje_ekrana snimanje_ekrana.py || exit /b 1
python -m PyInstaller --noconfirm --clean --console --name izvuci_telefon izvuci_telefon.py || exit /b 1
python -m PyInstaller --noconfirm --clean --console --name provjeri_adb provjeri_adb.py || exit /b 1

rem Sve u jedan folder: dist\SNIMANJE_ANDROID
if exist dist\SNIMANJE_ANDROID rmdir /s /q dist\SNIMANJE_ANDROID
xcopy /e /i /y dist\snimanje_ekrana dist\SNIMANJE_ANDROID >nul
xcopy /e /i /y dist\izvuci_telefon dist\SNIMANJE_ANDROID >nul
xcopy /e /i /y dist\provjeri_adb dist\SNIMANJE_ANDROID >nul
xcopy /e /i /y platform-tools dist\SNIMANJE_ANDROID\platform-tools\ >nul
xcopy /e /i /y scrcpy dist\SNIMANJE_ANDROID\scrcpy\ >nul
echo.
echo Gotovo: dist\SNIMANJE_ANDROID\snimanje_ekrana.exe
