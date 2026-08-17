@echo off
rem zktools-cpp build script: qmake + MinGW + windeployqt
rem (ASCII only: cmd.exe parses .bat with ANSI codepage)
setlocal
set QTDIR=C:\Qt\6.11.1\mingw_64
set MINGW=C:\Qt\Tools\mingw1310_64\bin
set PATH=%QTDIR%\bin;%MINGW%;%PATH%

cd /d %~dp0

qmake zktools-cpp.pro
if errorlevel 1 goto :fail

mingw32-make -j%NUMBER_OF_PROCESSORS% release
if errorlevel 1 goto :fail

rem deploy runtime data (config.json / tools) and Qt DLLs
xcopy /Y /Q config.json release\ >nul
xcopy /Y /Q /E /I tools release\tools\ >nul
windeployqt --no-compiler-runtime release\zktools.exe
if errorlevel 1 goto :fail
xcopy /Y /Q "%MINGW%\libgcc_s_seh-1.dll" release\ >nul
xcopy /Y /Q "%MINGW%\libstdc++-6.dll" release\ >nul
xcopy /Y /Q "%MINGW%\libwinpthread-1.dll" release\ >nul

echo.
echo === BUILD OK: %~dp0release\zktools.exe ===
exit /b 0

:fail
echo.
echo === BUILD FAILED ===
exit /b 1
