# Deploy the buddy to the PyPortal Titano (CIRCUITPY = D:).
#
# CircuitPython auto-reload applies the change. BLE now lives on the ESP32 (native
# firmware), so the SAMD51 just re-inits the UART + resets the ESP32 to run mode on a
# soft reload -- no hard reset needed (the old NINA/_bleio constraint is gone).
#
# Usage:  tools\deploy.ps1            # deploy to D:
#         tools\deploy.ps1 -Drive E:  # deploy to a different CIRCUITPY drive
param([string]$Drive = 'D:')

$flash = Join-Path $PSScriptRoot '..\flash'
foreach ($pair in @(
    @{ src = 'buddy_audio.py'; dst = 'buddy_audio.py' },   # audio/haptic module
    @{ src = 'buddy_ui.py';    dst = 'code.py'        }     # THE app (deploy last)
)) {
    $s = Join-Path $flash $pair.src
    $d = Join-Path $Drive $pair.dst
    Copy-Item $s $d -Force
    Write-Output ("  {0,-16} -> {1}" -f $pair.src, $d)
}
Write-Output ("Deployed. Auto-reload will apply it (ESP32 re-advertises; app reconnects in ~30-60s).")
Write-Output ("Verify:  python tools\cam.py 0     # grab a webcam frame")
