# Flash firmware.bin to the ESP32 in small chunks through the CircuitPython passthrough.
# Small chunks => small erase + short write (like the bootloader that flashed clean),
# avoiding the big-erase/long-write drops that wedge the bridge. Soft-reboot only on retry.
param(
  [int]$ChunkSize = 16384,
  [int]$MaxRetry  = 8
)
$ErrorActionPreference = 'Continue'
$esptool = 'C:\Users\Shai\AppData\Roaming\Python\Python312\Scripts\esptool.exe'
$fw   = 'C:\Users\Shai\pyportal-claude-buddy\esp32fw\.pio\build\nina\firmware.bin'
$base = 0x10000
$bytes = [System.IO.File]::ReadAllBytes($fw)
$tmp = 'C:\Users\Shai\pyportal-claude-buddy\esp32fw\.pio\build\nina\chunks'
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$n = [Math]::Ceiling($bytes.Length / $ChunkSize)
Write-Output ("firmware {0} bytes -> {1} chunks of {2}" -f $bytes.Length,$n,$ChunkSize)

function Soft-Reboot {
  $p = New-Object System.IO.Ports.SerialPort('COM7',115200,'None',8,'One'); $p.ReadTimeout=300
  try { $p.Open(); $p.DtrEnable=$true; Start-Sleep -Milliseconds 250; $p.Write([string][char]3); Start-Sleep -Milliseconds 350; $p.Write([string][char]4) } catch {}
  finally { try{if($p.IsOpen){$p.Close()}}catch{}; try{$p.Dispose()}catch{} }
  Start-Sleep -Seconds 3
}

$failed = @()
for ($c=0; $c -lt $n; $c++) {
  $start = $c * $ChunkSize
  $len = [Math]::Min($ChunkSize, $bytes.Length - $start)
  $sub = New-Object byte[] $len
  [Array]::Copy($bytes, $start, $sub, 0, $len)
  $cf = Join-Path $tmp ("chunk_{0}.bin" -f $c)
  [System.IO.File]::WriteAllBytes($cf, $sub)
  $off = '0x{0:X}' -f ($base + $start)
  $done = $false
  for ($i=1; $i -le $MaxRetry -and -not $done; $i++) {
    if ($i -gt 1) { Soft-Reboot }
    $out = & $esptool --chip esp32 --port COM8 --before no-reset --after no-reset --no-stub --baud 115200 write-flash $off $cf 2>&1
    if ($LASTEXITCODE -eq 0 -and (($out -join "`n") -match 'Hash of data verified')) { $done = $true }
  }
  $st = if ($done) { 'OK' } else { 'FAIL' }
  Write-Output ("chunk {0}/{1} @ {2} : {3}" -f $c,($n-1),$off,$st)
  if (-not $done) { $failed += $c }
}
Write-Output ("DONE. failed chunks: " + ($(if($failed.Count){$failed -join ','}else{'none'})))
