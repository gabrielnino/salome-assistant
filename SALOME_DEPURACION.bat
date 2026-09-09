@echo off
title SALOME - Asistente de Camara [MODO DEPURACION]
echo.
echo  ======================================================
echo    SALOME - Modo Depuracion y Registro Completo
echo  ======================================================
echo.
echo  Los logs detallados se guardaran en:
echo    F:\windows\projects\salome-assistant\logs\
echo.
echo  Presiona Ctrl+C en cualquier momento para salir.
echo.
python "F:\windows\projects\salome-assistant\salome_assistant.py" --debug
pause
