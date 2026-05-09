@echo off
:: Build AgenArc standalone executable
:: Requires: pip install pyinstaller

echo Building AgenArc.exe ...
pyinstaller --clean --onefile ^
  --name AgenArc ^
  --add-data "agenarc/visualization/static/*;agenarc/visualization/static" ^
  --add-data "examples/my_first_agent.agrc;examples/my_first_agent.agrc" ^
  --hidden-import openai ^
  --hidden-import yaml ^
  --hidden-import jsonschema ^
  --hidden-import agenarc.engine.trace ^
  --hidden-import agenarc.cli.commands.init ^
  --hidden-import agenarc.cli.commands.visualize ^
  --exclude-module tkinter ^
  --exclude-module matplotlib ^
  agenarc/cli/__main__.py

echo Done: dist/AgenArc.exe
