"""
salome_speak.py — TTS con voz Salomé (es-CO-SalomeNeural)
- Pausa cualquier video/audio que esté sonando antes de hablar
- Reanuda el media después de terminar
- Corre en proceso DETACHED (no se corta al cambiar ventana)
Uso: python salome_speak.py "texto a decir"
"""
import sys
import os
import subprocess
import tempfile

MEDIA_PAUSE_PS = r"""
$code = @"
using System.Runtime.InteropServices;
public class KB {
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint flags, int extra);
}
"@
Add-Type -TypeDefinition $code -Language CSharp
# VK_MEDIA_PLAY_PAUSE = 0xB3
[KB]::keybd_event(0xB3, 0, 0, 0)
[KB]::keybd_event(0xB3, 0, 2, 0)
"""

SPEAK_PS_TEMPLATE = r"""
# -- 1. Pausa media global --
$code = @"
using System.Runtime.InteropServices;
public class KB {{
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint flags, int extra);
}}
"@
Add-Type -TypeDefinition $code -Language CSharp -ErrorAction SilentlyContinue
[KB]::keybd_event(0xB3, 0, 0, 0)   # MEDIA_PLAY_PAUSE down
[KB]::keybd_event(0xB3, 0, 2, 0)   # MEDIA_PLAY_PAUSE up
Start-Sleep -Milliseconds 400

# -- 2. Reproducir Salome --
Add-Type -AssemblyName presentationCore
$p = New-Object System.Windows.Media.MediaPlayer
$p.Open([System.Uri]"{mp3}")
$p.Play()

# Esperar duracion real del audio
$elapsed = 0
while ($p.NaturalDuration.HasTimeSpan -eq $false -and $elapsed -lt 5) {{
    Start-Sleep -Milliseconds 200
    $elapsed += 0.2
}}
if ($p.NaturalDuration.HasTimeSpan) {{
    $total = $p.NaturalDuration.TimeSpan.TotalSeconds
    Start-Sleep -Seconds ([math]::Ceiling($total) + 0.5)
}}
$p.Close()

# -- 3. Reanudar media --
[KB]::keybd_event(0xB3, 0, 0, 0)   # MEDIA_PLAY_PAUSE down (resume)
[KB]::keybd_event(0xB3, 0, 2, 0)   # MEDIA_PLAY_PAUSE up
"""

def speak(text: str):
    mp3 = os.path.join(tempfile.gettempdir(), "salome_tts_out.mp3")

    # Generate audio with edge-tts
    subprocess.run(
        ["edge-tts", "--voice", "es-CO-SalomeNeural", "--text", text, "--write-media", mp3],
        check=True, capture_output=True
    )

    # Build the PS script with the mp3 path embedded
    mp3_uri = mp3.replace("\\", "/")
    ps_script = SPEAK_PS_TEMPLATE.replace("{mp3}", mp3_uri)

    # Launch as DETACHED process so it survives window switches
    subprocess.Popen(
        ["pwsh", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
        creationflags=0x00000008  # DETACHED_PROCESS
    )

if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hola, soy Salomé."
    speak(text)
