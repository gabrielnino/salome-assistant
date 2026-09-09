"""
SALOMÉ — Asistente de Cámara Independiente
==========================================
Controla la cámara del Pixel 8 Pro por voz sin depender de AGY.

Comandos de voz:
  "iniciar"    → empieza a grabar
  "detener"    → para la grabación
  "reiniciar"  → detiene y vuelve a grabar
  "zoom más"   → acerca la cámara
  "zoom menos" → aleja la cámara
  "analiza"    → Salomé da feedback del contenido hablado
  "transcribe" → muestra lo transcrito hasta ahora
  "salir"      → cierra el asistente

Mientras graba, Salomé transcribe lo que el usuario dice en tiempo real
y al pedir "analiza" usa DeepSeek para dar retroalimentación.
"""

import os, sys, json, time, threading, subprocess, queue, re, io
import tempfile, datetime, textwrap
from pathlib import Path

# Silenciar advertencias de Hugging Face sobre symlinks en Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import sounddevice as sd
import numpy as np
import requests

# ── Configuración ─────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

# Intentar cargar desde .env local o F:\windows\.env
if not os.getenv("DEEPSEEK_API_KEY") and os.path.exists(r"F:\windows\.env"):
    load_dotenv(r"F:\windows\.env")

DEEPSEEK_API_KEY   = os.getenv("DEEPSEEK_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

ADB  = os.getenv("ADB_PATH", r"C:\Users\luisg\Desktop\scrcpy-win64-v3.3.4\scrcpy-win64-v3.3.4\adb.exe")
SCRCPY = os.getenv("SCRCPY_PATH", r"C:\Users\luisg\Desktop\scrcpy-win64-v3.3.4\scrcpy-win64-v3.3.4\scrcpy.exe")
SALOME_SPEAK = os.getenv("SALOME_SPEAK_PATH", r"C:\Users\luisg\.gemini\config\salome_speak.py")

SAMPLE_RATE  = int(os.getenv("SAMPLE_RATE", "16000"))   # Hz para Whisper
CHUNK_SECS   = float(os.getenv("CHUNK_SECONDS", "3"))    # segundos por chunk de escucha (más ágil)
SILENCE_DB   = float(os.getenv("SILENCE_THRESHOLD_DB", "-55")) # umbral de silencio (-55 dB)

# Buscar automáticamente micrófono Shokz si no hay índice explícito
def find_microphone_device():
    env_dev = os.getenv("AUDIO_DEVICE_INDEX", "")
    if env_dev.strip():
        return int(env_dev.strip())
    # Buscar dispositivo Shokz
    try:
        for idx, dev in enumerate(sd.query_devices()):
            if dev['max_input_channels'] > 0 and 'shokz' in dev['name'].lower():
                return idx
    except Exception:
        pass
    return None

AUDIO_DEVICE = find_microphone_device()

# ── Logging estructurado (Harness Standard) ──────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
DEBUG_LOG_FILE = LOG_DIR / f"salome_debug_{TIMESTAMP}.log"

IS_DEBUG = "--debug" in sys.argv or "-d" in sys.argv

import logging
logging.basicConfig(
    level=logging.DEBUG if IS_DEBUG else logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(DEBUG_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

dev_name = "Default de Windows"
if AUDIO_DEVICE is not None:
    try:
        dev_name = sd.query_devices(AUDIO_DEVICE)['name']
    except Exception:
        dev_name = f"Index {AUDIO_DEVICE}"

logging.info(f"Salomé iniciada. Modo depuración: {IS_DEBUG}. Micrófono: '{dev_name}' (Index: {AUDIO_DEVICE}). Archivo log: {DEBUG_LOG_FILE}")

# ── Estado global ──────────────────────────────────────────────────────────────
state = {
    "recording": False,
    "scrcpy_proc": None,
    "record_file": None,
    "transcript": [],   # lista de fragmentos transcritos
    "running": True,
    "zoom_level": 1.0,  # 1.0 = normal
}
audio_queue = queue.Queue()

# ── Hablar con Salomé ──────────────────────────────────────────────────────────
def speak(text: str):
    """Reproduce texto con voz de Salomé (pausa media, proceso detached)."""
    logging.info(f"Salomé habla: {text}")
    subprocess.Popen(
        ["python", SALOME_SPEAK, text],
        creationflags=0x00000008  # DETACHED_PROCESS
    )
    time.sleep(0.3)

# ── ADB helpers ───────────────────────────────────────────────────────────────
def adb(*args) -> str:
    try:
        r = subprocess.run([ADB] + list(args), capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except Exception as e:
        return f"error: {e}"

def phone_screen_size():
    out = adb("shell", "wm", "size")
    m = re.search(r'(\d+)x(\d+)', out)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 1080, 2400  # Pixel 8 Pro default

def tap(x, y):
    adb("shell", "input", "tap", str(x), str(y))

def zoom_in():
    """Simula pinch-out (zoom +) con adb input swipe multi-touch."""
    w, h = phone_screen_size()
    cx, cy = w // 2, h // 2
    # Volume Up como zoom (funciona en app de cámara de Google)
    adb("shell", "input", "keyevent", "KEYCODE_VOLUME_UP")
    state["zoom_level"] = min(state["zoom_level"] + 0.5, 8.0)
    speak(f"Zoom al {state['zoom_level']:.1f}x")

def zoom_out():
    w, h = phone_screen_size()
    adb("shell", "input", "keyevent", "KEYCODE_VOLUME_DOWN")
    state["zoom_level"] = max(state["zoom_level"] - 0.5, 1.0)
    speak(f"Zoom al {state['zoom_level']:.1f}x")

def open_camera():
    """Abre la app de cámara en modo video."""
    adb("shell", "am", "start", "-a", "android.media.action.VIDEO_CAPTURE")
    time.sleep(2)

def start_recording():
    """Inicia scrcpy con grabación de video de cámara trasera."""
    if state["recording"]:
        speak("Ya estoy grabando.")
        return
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    outfile = os.path.join(os.path.expanduser("~"), "Desktop", f"video_{ts}.mp4")
    state["record_file"] = outfile
    state["transcript"] = []

    # Cerrar app de cámara si está abierta
    adb("shell", "am", "force-stop", "com.google.android.GoogleCamera")
    time.sleep(1)

    # Lanzar scrcpy con grabación
    proc = subprocess.Popen(
        [SCRCPY,
         "--video-source=camera",
         "--camera-facing=back",
         f"--record={outfile}",
         "--max-size=1080",
         "--window-title=SALOME GRABANDO",
         "--window-x=400", "--window-y=100"],
        cwd=os.path.dirname(SCRCPY),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    state["scrcpy_proc"] = proc
    state["recording"] = True
    time.sleep(2)
    speak(f"Grabando. El video se guardará en tu escritorio como video_{ts}.mp4")

def stop_recording():
    """Detiene la grabación."""
    if not state["recording"]:
        speak("No estoy grabando en este momento.")
        return
    if state["scrcpy_proc"]:
        state["scrcpy_proc"].terminate()
        state["scrcpy_proc"] = None
    state["recording"] = False
    speak(f"Grabación detenida. Video guardado en el escritorio.")

def restart_recording():
    stop_recording()
    time.sleep(1.5)
    start_recording()

# ── Transcripción con Whisper ──────────────────────────────────────────────────
_whisper_model = None

def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
            print("✅ Whisper small cargado (offline)")
        except ImportError:
            _whisper_model = "google"
            print("⚠️  Usando Google STT (online)")
    return _whisper_model

def transcribe_audio(audio_np: np.ndarray) -> str:
    """Transcribe un chunk de audio numpy a texto."""
    model = get_whisper()

    if model == "google":
        # Fallback: Google Speech Recognition
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        wav_io = io.BytesIO()
        import wave
        with wave.open(wav_io, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes((audio_np * 32767).astype(np.int16).tobytes())
        wav_io.seek(0)
        with sr.AudioFile(wav_io) as source:
            audio = recognizer.record(source)
        try:
            return recognizer.recognize_google(audio, language="es-CO")
        except:
            return ""
    else:
        # faster-whisper
        wav_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        import wave
        with wave.open(wav_file.name, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes((audio_np * 32767).astype(np.int16).tobytes())
        segs, _ = model.transcribe(wav_file.name, language="es", beam_size=3)
        os.unlink(wav_file.name)
        return " ".join(s.text for s in segs).strip()

# ── Análisis con DeepSeek ──────────────────────────────────────────────────────
def analyze_content():
    """Pide a DeepSeek que analice el contenido transcrito y dé feedback."""
    transcript_text = " ".join(state["transcript"])
    if not transcript_text.strip():
        speak("Aún no tengo suficiente transcripción para analizar. Sigue hablando.")
        return

    speak("Dame un momento que estoy analizando lo que dijiste.")

    prompt = f"""Eres Salomé, una asistente de grabación amigable con acento colombiano.
El usuario está grabando un video y ha dicho lo siguiente hasta ahora:

\"\"\"{transcript_text}\"\"\"

Analiza el contenido y dile al usuario:
1. De qué trata lo que está grabando
2. Qué está haciendo bien
3. Qué podría mejorar (claridad, ritmo, estructura)
4. Una sugerencia específica para el siguiente segmento

Responde de forma conversacional, cálida y directa, en máximo 4 oraciones. En español colombiano."""

    try:
        r = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300
            },
            timeout=30
        )
        feedback = r.json()["choices"][0]["message"]["content"].strip()
        speak(feedback)
    except Exception as e:
        speak(f"No pude conectarme para analizar: {e}")

# ── Detección de comandos ──────────────────────────────────────────────────────
COMMANDS = {
    # iniciar grabación
    r"inici[a-z]*|empez[a-z]*|comenz[a-z]*|graba[a-z]*|arranca[a-z]*": "start",
    # detener
    r"deten[a-z]*|par[a-z]*\s*grab|stop|termina[a-z]*|acab[a-z]*": "stop",
    # reiniciar
    r"reinici[a-z]*|vuelv[a-z]*\s*a\s*grab|otra\s*vez": "restart",
    # zoom in
    r"zoom\s*(m[aá]s|in|\+|adelante|acerca)|acerca[a-z]*|aument[a-z]*\s*zoom": "zoom_in",
    # zoom out
    r"zoom\s*(men[o0]s|out|\-|aleja|aleja)|aleja[a-z]*|reduc[a-z]*\s*zoom": "zoom_out",
    # analizar
    r"anali[a-z]*|retroaliment[a-z]*|qu[eé]\s*(tal\s*)?estoy|c[oó]mo\s*voy": "analyze",
    # transcribir
    r"transcrib[a-z]*|qu[eé]\s*dij[a-z]*|muestra\s*la\s*transcripci": "show_transcript",
    # salir
    r"salir|cerrar|hasta\s*luego|adios|chao": "exit",
}

def detect_command(text: str) -> str | None:
    text_lower = text.lower().strip()
    for pattern, cmd in COMMANDS.items():
        if re.search(pattern, text_lower):
            return cmd
    return None

def execute_command(cmd: str, text: str):
    if cmd == "start":
        start_recording()
    elif cmd == "stop":
        stop_recording()
    elif cmd == "restart":
        restart_recording()
    elif cmd == "zoom_in":
        zoom_in()
    elif cmd == "zoom_out":
        zoom_out()
    elif cmd == "analyze":
        threading.Thread(target=analyze_content, daemon=True).start()
    elif cmd == "show_transcript":
        t = " ".join(state["transcript"])
        if t:
            print(f"\n📝 TRANSCRIPCIÓN:\n{textwrap.fill(t, 70)}\n")
            speak(f"Hasta ahora has dicho: {t[:200]}")
        else:
            speak("Todavía no tengo transcripción.")
    elif cmd == "exit":
        speak("Hasta luego. Cerrando Salomé.")
        stop_recording()
        state["running"] = False

# ── Loop de audio ──────────────────────────────────────────────────────────────
def audio_callback(indata, frames, time_info, status):
    audio_queue.put(indata.copy())

def listen_loop():
    """Captura audio continuamente y transcribe en chunks."""
    buffer = []
    buffer_secs = 0.0
    chunk_size = int(SAMPLE_RATE * 0.1)  # 100ms callbacks

    stream_args = {
        "samplerate": SAMPLE_RATE,
        "channels": 1,
        "dtype": "float32",
        "blocksize": chunk_size,
        "callback": audio_callback
    }
    if AUDIO_DEVICE is not None:
        stream_args["device"] = AUDIO_DEVICE

    with sd.InputStream(**stream_args):
        logging.info(f"🎙️  Escuchando en micrófono (Dispositivo: {AUDIO_DEVICE if AUDIO_DEVICE is not None else 'Default'}, Umbral: {SILENCE_DB} dB)...")
        while state["running"]:
            try:
                chunk = audio_queue.get(timeout=1.0)
                buffer.append(chunk)
                buffer_secs += len(chunk) / SAMPLE_RATE

                if buffer_secs >= CHUNK_SECS:
                    audio_np = np.concatenate(buffer).flatten()
                    buffer = []
                    buffer_secs = 0.0

                    # Skip if mostly silence
                    rms = 20 * np.log10(np.sqrt(np.mean(audio_np**2)) + 1e-9)
                    if rms < SILENCE_DB:
                        logging.debug(f"Audio chunk descartado por silencio (RMS: {rms:.1f} dB < {SILENCE_DB} dB)")
                        continue

                    logging.debug(f"Procesando chunk de audio con volumen RMS: {rms:.1f} dB")
                    # Transcribe in background thread
                    threading.Thread(
                        target=process_audio_chunk,
                        args=(audio_np.copy(),),
                        daemon=True
                    ).start()
            except queue.Empty:
                continue

def process_audio_chunk(audio_np: np.ndarray):
    """Transcribe chunk y detecta si es comando o contenido."""
    text = transcribe_audio(audio_np)
    if not text or len(text.strip()) < 3:
        return

    mode_label = "GRABANDO" if state['recording'] else "ESCUCHA"
    logging.info(f"[{mode_label}] Audio transcrito: \"{text}\"")

    # Detectar comando de voz
    cmd = detect_command(text)
    if cmd:
        logging.info(f"Comando de voz reconocido: '{cmd}' a partir del texto: '{text}'")
        execute_command(cmd, text)
    elif state["recording"]:
        logging.debug(f"Agregando a transcripción acumulada: {text}")
        state["transcript"].append(text)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  SALOMÉ — Asistente de Cámara Independiente")
    print("  Pixel 8 Pro | DeepSeek | edge-tts")
    print("=" * 55)
    print("\nComandos de voz disponibles:")
    print("  'iniciar'    → empieza a grabar")
    print("  'detener'    → para la grabación")
    print("  'reiniciar'  → reinicia la grabación")
    print("  'zoom más'   → acerca la cámara")
    print("  'zoom menos' → aleja la cámara")
    print("  'analiza'    → feedback de DeepSeek sobre lo grabado")
    print("  'transcribe' → muestra lo transcrito")
    print("  'salir'      → cierra el asistente")
    print("\nCargando Whisper...\n")

    # Pre-cargar Whisper
    get_whisper()

    # Verificar ADB
    devices = adb("devices")
    if "device" in devices:
        print(f"✅ Pixel 8 Pro conectado\n")
        speak("Hola, soy Salomé. Estoy lista para ayudarte a grabar. Di 'iniciar' cuando quieras empezar.")
    else:
        print("⚠️  Pixel no detectado — conecta el cable USB\n")
        speak("Hola, soy Salomé. No veo el celular conectado. Por favor conecta el cable USB y asegúrate que la depuración USB esté activa.")

    # Iniciar loop de escucha
    try:
        listen_loop()
    except KeyboardInterrupt:
        speak("Cerrando. Hasta luego.")
        stop_recording()
        print("\nSalomé cerrada.")

if __name__ == "__main__":
    main()
