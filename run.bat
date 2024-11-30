@echo off
REM Navigate to the directory containing your virtual environment
cd /d "venv"

REM Activate the virtual environment
call Scripts\activate

REM Execute the Python script with an input parameter
python main.py %1

REM Deactivate the virtual environment (optional)
deactivate
