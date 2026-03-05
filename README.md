# meeting-transcriber

Local Windows meeting transcription project:
- Record meetings as WAV (mono, 16 kHz) using `ffmpeg`
- Speech-to-text with `faster-whisper`
- Speaker diarization with `pyannote-audio`
- Outputs: `.txt`, `.srt`, `.md`

Goal: run **locally**, use GPU acceleration when available (CUDA), otherwise CPU fallback.

---

## Requirements

- Windows 10/11
- [Miniforge3](https://github.com/conda-forge/miniforge) (with `mamba`)
- `ffmpeg` available on the machine
- Optional: NVIDIA GPU + current drivers for CUDA acceleration
- Hugging Face token for diarization (`pyannote` models)

### Install Miniforge3 via winget

Install Miniforge3 on Windows:

```powershell
winget install --id CondaForge.Miniforge3 --exact
```

Then open a new terminal and verify:

```powershell
mamba --version
```

### Install FFmpeg (Gyan build) via winget

Install FFmpeg from Gyan.dev package on Windows:

```powershell
winget install --id Gyan.FFmpeg --exact
```

Then verify:

```powershell
ffmpeg -version
```

---

## Environments (portable Windows setup)

Two environment profiles are provided:

- **`environment-cuda.yml`** → Desktop with NVIDIA GPU (CUDA)
- **`environment-cpu.yml`** → CPU-only (e.g. laptop without CUDA)

> The Python script checks CUDA at runtime (`torch.cuda.is_available()`) and falls back to CPU automatically.

### 1) Create CUDA profile

```powershell
mamba env create -f environment-cuda.yml
mamba activate meeting-transcriber-cuda
```

### 2) Create CPU profile

```powershell
mamba env create -f environment-cpu.yml
mamba activate meeting-transcriber-cpu
```

---

## Set Hugging Face token

PowerShell (temporary for current session):

```powershell
$env:HUGGINGFACE_TOKEN = "hf_xxx..."
```

Optional additional settings:

```powershell
$env:DIARIZATION_MODEL = "pyannote/speaker-diarization-community-1"
$env:ASR_MODEL = "large-v2"  # recommended for German; use large-v3 for English
$env:LANGUAGE = "de"         # or "auto"
```

---

## Record audio

You can either:

1) use the PowerShell helper function (`recmeet`), or
2) run `ffmpeg` directly.

### Option A: PowerShell function (`recmeet`)

Repository includes `function Start-MeetingRec.ps1`.

```powershell
. .\function Start-MeetingRec.ps1
recmeet -Meeting "Project Kickoff"
```

This creates a WAV file in `$HOME\Recordings` by default.

### List available audio devices (DirectShow)

```powershell
ffmpeg -list_devices true -f dshow -i dummy
```

Use the reported audio device name/identifier in `-i "audio=..."`.

### Option B: Direct ffmpeg command (PowerShell)

Equivalent command from the PowerShell function, with automatic start timestamp from `Get-Date`:

```powershell
$meeting = "Project Kickoff"
$date = Get-Date -Format 'yyyy-MM-dd'
$time = Get-Date -Format 'HH-mm'
$timeDisplay = $time -replace '-', ':'
$outFile = "C:\Users\<USER>\Recordings\${date}_${time}__Project_Kickoff.wav"

ffmpeg `
  -rtbufsize 512M `
  -f dshow `
  -i "audio=@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\wave_{8E14655A-AAA4-4247-B5F1-DC05EF76DA36}" `
  -ac 1 `
  -ar 16000 `
  -metadata title="$meeting" `
  -metadata comment="start=$date $timeDisplay" `
  "$outFile"
```

> Note: the `-i` audio device string is machine-specific. Replace it with your local input device.

---

## Run transcription + diarization

```powershell
python .\transcribe_meeting.py "C:\Users\<USER>\Recordings\2026-03-05_09-00__Project_Kickoff.wav"
```

Generated files (next to the WAV):
- `*_transcript.txt`
- `*_transcript.srt`
- `*_transcript.md`

---

## Important parameters (env vars)

- `ASR_MODEL` (default: `large-v3-turbo`)
- `LANGUAGE` (default: `en`, for German typically `de` or `auto`)

### Recommended ASR model by language

Based on current project testing:
- **German meetings**: `ASR_MODEL=large-v2`
- **English meetings**: `ASR_MODEL=large-v3`

Example (German):

```powershell
$env:LANGUAGE = "de"
$env:ASR_MODEL = "large-v2"
```

Example (English):

```powershell
$env:LANGUAGE = "en"
$env:ASR_MODEL = "large-v3"
```
- `ASR_VAD_FILTER` (default: `true`)
- `ASR_VAD_MIN_SILENCE_MS` (default: `300`)
- `ASR_BEAM_SIZE` (default: `5`)
- `ASR_NO_SPEECH_THRESHOLD` (default: `1.0`)
- `ASR_LOGPROB_THRESHOLD` (default: `-1.0`)
- `ASR_TEMPERATURE` (default: `0.0`)
- `ASR_CONDITION_ON_PREVIOUS_TEXT` (default: `true`)
- `ASR_INITIAL_PROMPT` (optional)
- `DIARIZATION_MODEL` (default: `pyannote/speaker-diarization-community-1`)

### What `ASR_INITIAL_PROMPT` does and how to use it

`ASR_INITIAL_PROMPT` is a startup hint for Whisper. It gives the model context before transcription starts.

Use it to improve recognition of:
- domain-specific terms (e.g. PKI, OCSP, CRL, ADCS)
- company/product names
- person names and recurring vocabulary

PowerShell example:

```powershell
$env:ASR_INITIAL_PROMPT = "This is a German IT meeting about PKI, certificates, HSM, Active Directory."
python .\transcribe_meeting.py "C:\Users\<USER>\Recordings\2026-03-05_09-00__Project_Kickoff.wav"
```

Notes:
- Keep the prompt short and specific (1–3 sentences).
- It is a hint, not a strict custom dictionary.

---

## Troubleshooting

### `HUGGINGFACE_TOKEN is not set`
Set the token as env var (see above).

### CUDA is not used
- Check NVIDIA drivers
- Confirm CUDA profile (`meeting-transcriber-cuda`) is active
- Check script output (`CUDA available: True/False`)

### Audio device not visible in ffmpeg
1. Show devices via ffmpeg:
   ```powershell
   ffmpeg -list_devices true -f dshow -i dummy
   ```
2. Open classic Sound control panel:
   ```powershell
   mmsys.cpl
   ```
3. In **Recording** tab, right-click inside the device list and enable:
   - **Show Disabled Devices**
   - **Show Disconnected Devices**
4. Enable the required device and set permissions in Windows privacy settings:
   - **Settings → Privacy & security → Microphone**
   - Allow microphone access (system + desktop apps)

### German transcription quality is poor
- Try `LANGUAGE=de`
- Optionally set `ASR_INITIAL_PROMPT` with domain-specific terms

---

## Roadmap / To-Do

- [ ] HF cache + true offline mode (after initial model download)
- [ ] Audio device configuration without hardcoding
- [ ] Optional mapping of speaker labels (`SPK1`) to real names
- [ ] CLI wrapper (e.g. `transcribe.ps1`) for simpler execution

---

## Acknowledgments

Special thanks to the projects and teams behind the core building blocks used here:

- OpenAI Whisper: https://github.com/openai/whisper
- pyannote-audio: https://github.com/pyannote/pyannote-audio

## License

Licensed under the Apache License 2.0. See [LICENSE](./LICENSE).

Third-party components keep their own licenses (e.g., MIT). See:
- [NOTICE](./NOTICE)
- [THIRD_PARTY_LICENSES.md](./THIRD_PARTY_LICENSES.md)
