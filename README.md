# Salomé — Asistente de Cámara con IA

> Asistente de voz independiente para controlar la cámara de un Pixel 8 Pro desde la PC. Escucha comandos, transcribe en tiempo real con Whisper, y da retroalimentación inteligente usando DeepSeek.

---

## ✨ Características

- 🎙️ **Control por voz** — sin tocar el teclado
- 📹 **Graba con la cámara trasera** del Pixel 8 Pro vía ADB + scrcpy
- 🔍 **Zoom in/out por voz** usando teclas de volumen del celular
- 📝 **Transcripción en tiempo real** con Whisper (offline, sin costo)
- 🧠 **Retroalimentación inteligente** con DeepSeek Chat API
- 🗣️ **Voz colombiana** (Salomé Neural, edge-tts) con pausa automática de media

---

## 🎤 Comandos de voz

| Dices | Acción |
|---|---|
| `"iniciar"` | Empieza a grabar |
| `"detener"` | Para la grabación |
| `"reiniciar"` | Detiene y vuelve a grabar |
| `"zoom más"` | Acerca la cámara |
| `"zoom menos"` | Aleja la cámara |
| `"analiza"` | Feedback de IA sobre lo que has grabado |
| `"transcribe"` | Muestra el texto transcrito hasta ahora |
| `"salir"` | Cierra el asistente |

---

## 🛠️ Requisitos

- Windows 10/11
- Python 3.10+
- Android con **Depuración USB activada** (Pixel 8 Pro recomendado)
- [scrcpy](https://github.com/Genymobile/scrcpy) instalado
- `adb.exe` disponible en PATH o configurado en `config.py`

---

## 📦 Instalación

```bash
git clone https://github.com/gabrielnino/salome-assistant.git
cd salome-assistant
pip install -r requirements.txt
```

### Configura tus API keys en `.env`:

```env
DEEPSEEK_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-v1-...
```

---

## 🚀 Uso

```bash
python salome_assistant.py
```

O doble clic en **`SALOME_ASISTENTE.bat`** (Windows).

---

## 🏗️ Arquitectura

```
Tu voz
  ↓ sounddevice (micrófono)
Whisper small (offline)
  ↓ transcripción
¿Comando?
  ├── Sí → ADB → controla Pixel 8 Pro
  └── No → acumula transcripción de contenido
              ↓ "analiza"
          DeepSeek Chat API
              ↓ feedback
          edge-tts Salomé (es-CO-SalomeNeural)
              ↓ pausa media → habla → reanuda
          Parlantes del PC
```

---

## 📁 Estructura del proyecto

```
salome-assistant/
├── salome_assistant.py   # Daemon principal
├── salome_speak.py       # Motor TTS con pausa de media
├── config.py             # Configuración de rutas y keys
├── requirements.txt      # Dependencias Python
├── .env.example          # Template de variables de entorno
├── SALOME_ASISTENTE.bat  # Lanzador Windows
└── README.md
```

---

## 🔧 Stack tecnológico

| Componente | Tecnología | Costo |
|---|---|---|
| STT (voz → texto) | faster-whisper `small` | Gratis (offline) |
| Análisis / coaching | DeepSeek Chat API | ~\$0.001/consulta |
| TTS (texto → voz) | edge-tts `es-CO-SalomeNeural` | Gratis |
| Control de cámara | ADB + scrcpy | Gratis |
| Fallback STT | Google Speech Recognition | Gratis |

---

## ⚙️ Configuración avanzada

Edita `config.py` para cambiar:
- Ruta de `adb.exe` y `scrcpy.exe`
- Umbral de silencio (dB)
- Tamaño del modelo Whisper (`tiny`, `small`, `medium`, `large`)
- Confianza mínima para ejecutar comandos

---

## 📄 Licencia

MIT — úsalo libremente.
