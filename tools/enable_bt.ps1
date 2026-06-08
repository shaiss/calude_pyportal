# Enable the Bluetooth radio via the WinRT Radio API.
# Must run under Windows PowerShell 5.1 (has WinRT projection + the AsTask await shim).
$ErrorActionPreference = 'Stop'
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime

    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1)

    function Await($op, $resultType) {
        $m = $asTaskGeneric.MakeGenericMethod($resultType)
        $t = $m.Invoke($null, @($op))
        $t.Wait(-1) | Out-Null
        $t.Result
    }

    [void][Windows.Devices.Radios.Radio, Windows.System.Devices, ContentType = WindowsRuntime]
    [void][Windows.Devices.Radios.RadioAccessStatus, Windows.System.Devices, ContentType = WindowsRuntime]
    [void][Windows.Devices.Radios.RadioState, Windows.System.Devices, ContentType = WindowsRuntime]
    [void][Windows.Devices.Radios.RadioKind, Windows.System.Devices, ContentType = WindowsRuntime]

    $access = Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])
    Write-Output "radio-access: $access"

    $radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
    $bt = $radios | Where-Object { $_.Kind -eq [Windows.Devices.Radios.RadioKind]::Bluetooth } | Select-Object -First 1
    if (-not $bt) { Write-Output 'NO_BT_RADIO'; exit 3 }

    Write-Output ("bt-radio: '" + $bt.Name + "' state=" + $bt.State)
    if ($bt.State -ne [Windows.Devices.Radios.RadioState]::On) {
        $r = Await ($bt.SetStateAsync([Windows.Devices.Radios.RadioState]::On)) ([Windows.Devices.Radios.RadioAccessStatus])
        Write-Output "set-on-result: $r"
        Start-Sleep -Milliseconds 1000
        Write-Output ("bt-radio-now: state=" + $bt.State)
    }
    else {
        Write-Output 'already-ON'
    }
}
catch {
    Write-Output ("ENABLE_BT_ERROR: " + $_.Exception.Message)
    exit 1
}
