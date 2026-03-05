# meeting-transcriber

Lokales Meeting-Transkriptionsprojekt für Windows:
- Aufnahme als WAV (mono, 16 kHz) via `ffmpeg`
- Speech-to-Text mit `faster-whisper`
- Sprecher-Diarisierung mit `pyannote-audio`
- Ausgabe als `.txt`, `.srt`, `.md`

Ziel: **lokal laufen**, mit GPU-Beschleunigung wenn verfügbar (CUDA), sonst CPU-Fallback.

---

## Voraussetzungen

- Windows 10/11
- [Miniforge3](https://github.com/conda-forge/miniforge) (mit `mamba`)
- `ffmpeg` im PATH (oder via Conda-Umgebung)
- Optional: NVIDIA GPU + aktuelle Treiber für CUDA-Beschleunigung
- Hugging Face Token für Diarisierung (`pyannote` Modelle)

---

## Umgebungen (portable Windows Setup)

Es gibt zwei Profile:

- **`environment-cuda.yml`** → Desktop mit NVIDIA GPU (CUDA)
- **`environment-cpu.yml`** → CPU-only (z. B. Laptop ohne CUDA)

> Das Python-Skript erkennt CUDA zur Laufzeit (`torch.cuda.is_available()`) und nutzt ansonsten CPU.

### 1) CUDA-Profil erstellen

```powershell
mamba env create -f environment-cuda.yml
mamba activate meeting-transcriber-cuda
```

### 2) CPU-Profil erstellen

```powershell
mamba env create -f environment-cpu.yml
mamba activate meeting-transcriber-cpu
```

---

## Hugging Face Token setzen

PowerShell (temporär in aktueller Session):

```powershell
$env:HUGGINGFACE_TOKEN = "hf_xxx..."
```

Optional zusätzlich:

```powershell
$env:DIARIZATION_MODEL = "pyannote/speaker-diarization-community-1"
$env:ASR_MODEL = "large-v3-turbo"  # alternativ: large-v3
$env:LANGUAGE = "de"               # oder "auto"
```

---

## Aufnahme starten (PowerShell)

Im Repository ist eine Funktion `Start-MeetingRec` enthalten (`function Start-MeetingRec.ps1`).

Beispiel:

```powershell
. .\function Start-MeetingRec.ps1
recmeet -Meeting "Projekt Kickoff"
```

Das erzeugt u. a. eine WAV-Datei im Zielordner (`$HOME\Recordings` standardmäßig).

---

## Transkription + Diarisierung ausführen

```powershell
python .\transcribe_meeting.py "C:\Users\<USER>\Recordings\2026-03-05_09-00__Projekt_Kickoff.wav"
```

Erzeugte Dateien (neben der WAV):
- `*_transcript.txt`
- `*_transcript.srt`
- `*_transcript.md`

---

## Wichtige Parameter (Env Vars)

- `ASR_MODEL` (default: `large-v3-turbo`)
- `LANGUAGE` (default: `en`, empfohlen für DE: `de` oder `auto`)
- `ASR_VAD_FILTER` (default: `true`)
- `ASR_VAD_MIN_SILENCE_MS` (default: `300`)
- `ASR_BEAM_SIZE` (default: `5`)
- `ASR_NO_SPEECH_THRESHOLD` (default: `1.0`)
- `ASR_LOGPROB_THRESHOLD` (default: `-1.0`)
- `ASR_TEMPERATURE` (default: `0.0`)
- `ASR_CONDITION_ON_PREVIOUS_TEXT` (default: `true`)
- `ASR_INITIAL_PROMPT` (optional)
- `DIARIZATION_MODEL` (default: `pyannote/speaker-diarization-community-1`)

---

## Troubleshooting

### `HUGGINGFACE_TOKEN is not set`
Token als Env Var setzen (siehe oben).

### CUDA wird nicht genutzt
- NVIDIA Treiber prüfen
- CUDA-Profil (`meeting-transcriber-cuda`) aktiv?
- Ausgabe im Script prüfen (`CUDA available: True/False`)

### Schlechte Erkennung bei Deutsch
- `LANGUAGE=de` testen
- optional `ASR_INITIAL_PROMPT` mit domänenspezifischen Begriffen setzen

---

## Roadmap / To-Do

- [ ] HF-Cache + echter Offline-Modus (nach initialem Modell-Download)
- [ ] Audio-Device Konfiguration ohne Hardcoding
- [ ] Optionales Mapping von Sprecherlabels (`SPK1`) auf Namen
- [ ] CLI-Wrapper (z. B. `transcribe.ps1`) für einfacheren Start

---

## Lizenz

Aktuell nicht festgelegt.
