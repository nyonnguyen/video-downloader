@echo off

python -m venv venv

REM Activate the virtual environment
call .\venv\Scripts\activate

REM Install the required packages
pip install -r requirements.txt
playwright install

REM Execute the Python script with an input parameter
python main.py %*

REM Deactivate the virtual environment (optional)
deactivate
