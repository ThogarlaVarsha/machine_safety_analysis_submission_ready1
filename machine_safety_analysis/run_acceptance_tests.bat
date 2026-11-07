@echo off
setlocal
cd /d "%~dp0"
echo Running unit tests...
python -m unittest discover -s tests -v
if errorlevel 1 goto failed

echo.
echo Running two full-scale reproducibility runs. This may take several minutes...
python tests\reproducibility_check.py
if errorlevel 1 goto failed

echo.
echo SUCCESS: all acceptance tests passed.
pause
exit /b 0
:failed
echo.
echo FAILED: review the error messages above.
pause
exit /b 1
