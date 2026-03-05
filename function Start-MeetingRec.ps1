function Start-MeetingRec {
    param(
        [Parameter(Mandatory)]
        [string]$Meeting,

        [string]$OutDir = "$HOME\Recordings"
    )

    $date = Get-Date -Format 'yyyy-MM-dd'
    $time = Get-Date -Format 'HH-mm'
    $timeDisplay = $time -replace '-', ':'
    $ts   = "${date}_${time}"

    $safe = (($Meeting -replace '\s+', '_') -replace '[<>:"/\\|?*]', '_').Trim('_')
    if ([string]::IsNullOrWhiteSpace($safe)) {
        $safe = 'meeting'
    }

    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

    $baseName = "${ts}__${safe}"
    $wavFile  = Join-Path $OutDir "${baseName}.wav"
    $txtFile  = Join-Path $OutDir "${baseName}.txt"

    $txtContent = @"
Titel Meeting: $Meeting
Meeting Start: $date $timeDisplay
Teilnehmer:
Notizen:

"@

    Set-Content -Path $txtFile -Value $txtContent -Encoding UTF8
    Start-Process notepad.exe $txtFile

    ffmpeg `
      -rtbufsize 512M `
      -f dshow `
      -i 'audio=@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\wave_{8E14655A-AAA4-4247-B5F1-DC05EF76DA36}' `
      -ac 1 `
      -ar 16000 `
      -metadata title="$Meeting" `
      -metadata comment="start=$date $timeDisplay" `
      "$wavFile"
}

Set-Alias recmeet Start-MeetingRec