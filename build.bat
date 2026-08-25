uv run nuitka --enable-plugin=pyside6 --windows-console-mode=disable --standalone --output-dir=dist main.py
robocopy tools dist\main.dist\tools /E /IS
robocopy assets dist\main.dist\assets /E /IS
pause