@echo off
setlocal
cd /d "%~dp0"
echo Running Machine Safety Analysis - full dataset...
python src\safety_project.py --scale full --seed 20261022 --output output
if errorlevel 1 goto failed

echo.
echo Running automated project tests...
python -m unittest discover -s tests -v
if errorlevel 1 goto failed

echo.
echo SUCCESS: generation and automated tests passed.
echo See output\execution_report.json and output\validation_summary.json
pause
exit /b 0
:failed
echo.
echo FAILED: review the error messages above.
pause
exit /b 1
