uv run nuitka --enable-plugin=pyside6 --windows-console-mode=disable --standalone --output-dir=dist main.py
xcopy /E /I tools dist\main.dist\tools
pause