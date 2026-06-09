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

# Runtime modules that belong on the device. Deliberately NOT a blanket flash\*.py copy:
# boot.py / passthrough*.py / run_bridge.py / buddy.py are flashing & bring-up utilities,
# and boot.py in particular changes USB behavior -- they must never land as runtime code.
# Convention: every device module beyond buddy_audio is named bud_*.py.
$modules = @('buddy_audio.py')
$modules += Get-ChildItem (Join-Path $flash 'bud_*.py') | ForEach-Object { $_.Name }
foreach ($name in $modules) {
    Copy-Item (Join-Path $flash $name) (Join-Path $Drive $name) -Force
    Write-Output ("  {0,-16} -> {1}" -f $name, (Join-Path $Drive $name))
}
# THE app last, as code.py (so a partial copy never leaves a half-updated app running)
Copy-Item (Join-Path $flash 'buddy_ui.py') (Join-Path $Drive 'code.py') -Force
Write-Output ("  {0,-16} -> {1}" -f 'buddy_ui.py', (Join-Path $Drive 'code.py'))
Write-Output ("Deployed. Auto-reload will apply it (ESP32 re-advertises; app reconnects in ~30-60s).")
Write-Output ("Verify:  python tools\cam.py 0     # grab a webcam frame")
