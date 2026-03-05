import os, sys
import re
try:
    import torch
except Exception:
    # Fallback shim when torch is not installed (silences linter; forces CPU)
    class _CudaShim:
        @staticmethod
        def is_available():
            return False

    class _TorchShim:
        cuda = _CudaShim()

        @staticmethod
        def device(name):
            # return the device name (e.g. "cpu") as a lightweight stand-in for torch.device
            return name

    torch = _TorchShim()

from pathlib import Path
from datetime import timedelta
from collections import defaultdict

from faster_whisper import WhisperModel
from pyannote.audio import Pipeline
from pyannote.core import Segment


def ts_plain(secs: float) -> str:
    """Human-readable timestamp without milliseconds."""
    s = str(timedelta(seconds=float(secs)))
    return s.split(".")[0]


def ts_srt(secs: float) -> str:
    """SRT timestamp: HH:MM:SS,mmm"""
    total_ms = int(round(float(secs) * 1000))
    if total_ms < 0:
        total_ms = 0
    hours = total_ms // 3_600_000
    rem = total_ms % 3_600_000
    minutes = rem // 60_000
    rem = rem % 60_000
    seconds = rem // 1000
    millis = rem % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def extract_date_time_from_filename(audio_path: Path):
    """
    Extract date/time from filenames like:
    2026-03-03_11-45_Title.wav or 2026-03-03_11-45__Title.wav
    Returns (date_str, time_str) or (None, None) when not matched.
    """
    m = re.match(
        r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<hour>\d{2})-(?P<minute>\d{2})(?:_|$)",
        audio_path.stem,
    )
    if not m:
        return None, None
    return m.group("date"), f"{m.group('hour')}:{m.group('minute')}"


def normalize_asr_model_name(raw_name: str) -> str:
    """Normalize common ASR model aliases to concrete faster-whisper model ids."""
    value = (raw_name or "").strip().lower()
    aliases = {
        "turbo": "large-v3-turbo",
        "large-v3-turbo": "large-v3-turbo",
        "large-v3": "large-v3",
    }
    return aliases.get(value, (raw_name or "").strip())


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except Exception:
        return default


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        return float(raw)
    except Exception:
        return default


def main():
    if len(sys.argv) < 2:
        print("Usage: python transcribe_meeting.py <audio.wav>")
        sys.exit(1)

    audio_path = Path(sys.argv[1]).resolve()
    if not audio_path.exists():
        sys.exit(f"File not found: {audio_path}")

    # ---------- ASR (Faster-Whisper) ----------
    # Preferred models:
    # - large-v3-turbo (faster)
    # - large-v3 (best quality)
    model_size_raw = os.getenv("ASR_MODEL", "large-v3-turbo")
    model_size = normalize_asr_model_name(model_size_raw)

    # LANGUAGE can be 'de', 'en', ... or 'auto'
    language = os.getenv("LANGUAGE", "en").strip()
    if not language:
        language = "en"

    # ASR tuning env vars (all with script defaults)
    asr_vad_filter = env_bool("ASR_VAD_FILTER", True)
    asr_vad_min_silence_ms = env_int("ASR_VAD_MIN_SILENCE_MS", 300)
    asr_beam_size = env_int("ASR_BEAM_SIZE", 5)
    # 1.0 is recall-friendly and avoids skipping uncertain early speech with v3/turbo.
    asr_no_speech_threshold = env_float("ASR_NO_SPEECH_THRESHOLD", 1.0)
    asr_logprob_threshold = env_float("ASR_LOGPROB_THRESHOLD", -1.0)
    asr_temperature = env_float("ASR_TEMPERATURE", 0.0)
    asr_condition_on_prev = env_bool("ASR_CONDITION_ON_PREVIOUS_TEXT", True)
    asr_initial_prompt = os.getenv("ASR_INITIAL_PROMPT", "").strip()

    use_cuda = torch.cuda.is_available()
    device = "cuda" if use_cuda else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"

    print("CUDA available:", use_cuda)
    print(f"ASR: loading Faster-Whisper '{model_size}' ({device} {compute_type})…")
    try:
        asr = WhisperModel(model_size, device=device, compute_type=compute_type)
    except Exception as exc:
        if model_size == "large-v3-turbo":
            sys.exit(
                "Could not load ASR model 'large-v3-turbo'. "
                "Ensure faster-whisper>=1.1.0, or use ASR_MODEL=large-v3.\n"
                f"Details: {exc}"
            )
        raise

    print(f"ASR: transcribing {audio_path.name}…")
    transcribe_kwargs = dict(
        vad_filter=asr_vad_filter,
        beam_size=asr_beam_size,
        no_speech_threshold=asr_no_speech_threshold,
        log_prob_threshold=asr_logprob_threshold,
        temperature=asr_temperature,
        condition_on_previous_text=asr_condition_on_prev,
    )
    if asr_vad_filter:
        transcribe_kwargs["vad_parameters"] = {
            "min_silence_duration_ms": asr_vad_min_silence_ms
        }
    # LANGUAGE=auto => let whisper autodetect
    if language and language.lower() != "auto":
        transcribe_kwargs["language"] = language
    if asr_initial_prompt:
        transcribe_kwargs["initial_prompt"] = asr_initial_prompt

    segments, _ = asr.transcribe(str(audio_path), **transcribe_kwargs)
    segs = list(segments)

    # ---------- Diarization (pyannote) ----------
    token = os.getenv("HUGGINGFACE_TOKEN", "").strip()
    if not token:
        sys.exit("HUGGINGFACE_TOKEN is not set.")

    diarization_model = os.getenv(
        "DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1"
    ).strip()
    if not diarization_model:
        diarization_model = "pyannote/speaker-diarization-community-1"

    print(f"Diarization: loading {diarization_model}…")
    pipeline = Pipeline.from_pretrained(
        diarization_model,
        token=token,
    )

    pipeline_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pipeline.to(pipeline_device)

    print(f"Diarization: running… (device={pipeline_device})")
    diar_out = pipeline(str(audio_path))

    # Normalize output across pyannote versions:
    # - legacy pipeline: returns Annotation directly
    # - newer pipeline: returns DiarizeOutput with speaker_diarization
    # - some wrappers may return dict-like outputs
    diar = None
    if hasattr(diar_out, "exclusive_speaker_diarization"):
        # Prefer exclusive diarization for ASR alignment (no overlap turns).
        diar = diar_out.exclusive_speaker_diarization
    elif hasattr(diar_out, "speaker_diarization"):
        diar = diar_out.speaker_diarization
    elif isinstance(diar_out, dict):
        diar = (
            diar_out.get("exclusive_speaker_diarization")
            or diar_out.get("speaker_diarization")
            or diar_out.get("annotation")
            or diar_out.get("diarization")
        )
    else:
        diar = getattr(diar_out, "annotation", diar_out)

    if not hasattr(diar, "itertracks") or not hasattr(diar, "crop"):
        raise TypeError(
            f"Unsupported diarization output type: {type(diar_out).__name__} "
            f"(normalized to {type(diar).__name__})"
        )

    def best_speaker(start: float, end: float) -> str:
        window = Segment(start, end)
        cropped = diar.crop(window)
        if len(list(cropped.itertracks())) == 0:
            return "SPK?"
        dur = defaultdict(float)
        for turn, _, label in cropped.itertracks(yield_label=True):
            inter = turn & window
            if inter:
                dur[label] += inter.duration
        if not dur:
            return "SPK?"
        return max(dur, key=dur.get)

    alias = {}

    def short(label: str) -> str:
        if label not in alias:
            alias[label] = f"SPK{len(alias) + 1}"
        return alias[label]

    # ---------- Outputs ----------
    base = audio_path.with_suffix("")
    txt = base.with_name(base.name + "_transcript.txt")
    srt = base.with_name(base.name + "_transcript.srt")
    md = base.with_name(base.name + "_transcript.md")
    meeting_date, meeting_time = extract_date_time_from_filename(audio_path)

    print("Writing outputs…")
    with open(txt, "w", encoding="utf-8") as ftxt, open(
        srt, "w", encoding="utf-8"
    ) as fsrt, open(md, "w", encoding="utf-8") as fmd:

        if meeting_date and meeting_time:
            frontmatter = (
                "---\n"
                f"date: {meeting_date}\n"
                f"time: {meeting_time}\n"
                "---\n\n"
            )
            ftxt.write(frontmatter)
            fmd.write(frontmatter)

        fmd.write("# Meeting-Transkript\n\n")
        idx = 1
        for seg in segs:
            start, end, text = seg.start, seg.end, (seg.text or "").strip()
            label = best_speaker(start, end)
            spk = short(label)

            line = f"[{ts_plain(start)}–{ts_plain(end)}] {spk}: {text}"
            ftxt.write(line + "\n")
            fmd.write(line + "\n\n")

            fsrt.write(
                f"{idx}\n{ts_srt(start)} --> {ts_srt(end)}\n[{spk}] {text}\n\n"
            )
            idx += 1

    print("Done.")
    print("Files:")
    print(" -", txt.name)
    print(" -", srt.name)
    print(" -", md.name)


if __name__ == "__main__":
    main()
