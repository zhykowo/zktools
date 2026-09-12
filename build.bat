uv run nuitka --enable-plugin=pyside6 --windows-console-mode=disable --standalone --output-dir=dist main.py

robocopy tools dist\main.dist\tools /E /NJH /NJS /NP
robocopy assets dist\main.dist\assets /E /NJH /NJS /NP
robocopy "." "dist\main.dist" "config_dev.json" /NJH /NJS /NP
robocopy "." "dist\main.dist" "config.json" /NJH /NJS /NP

pause
