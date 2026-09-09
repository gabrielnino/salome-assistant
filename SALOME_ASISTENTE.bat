@echo off
title SALOME - Asistente de Camara
echo.
echo  =============================================
echo    SALOME - Asistente Independiente de Camara
echo  =============================================
echo.
echo  Comandos de voz:
echo    "iniciar"    - empieza a grabar
echo    "detener"    - para la grabacion
echo    "reiniciar"  - reinicia la grabacion
echo    "zoom mas"   - acerca la camara
echo    "zoom menos" - aleja la camara
echo    "analiza"    - feedback de IA sobre lo grabado
echo    "transcribe" - muestra lo transcrito
echo    "salir"      - cierra el asistente
echo.
python "C:\Users\luisg\.gemini\config\salome_assistant.py"
pause
