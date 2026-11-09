param(
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Market Insight.lnk"

if ($Remove) {
    if (Test-Path $shortcutPath) {
        Remove-Item -LiteralPath $shortcutPath -Force
    }
    exit 0
}

$pythonw = $null
try {
    $candidate = (& py -3 -c "import sys, pathlib; print(pathlib.Path(sys.executable).with_name('pythonw.exe'))" 2>$null | Select-Object -First 1)
    if ($candidate -and (Test-Path $candidate.Trim())) {
        $pythonw = $candidate.Trim()
    }
} catch {}

$wsh = New-Object -ComObject WScript.Shell
$link = $wsh.CreateShortcut($shortcutPath)

if ($pythonw) {
    $link.TargetPath = $pythonw
    $link.Arguments = '"' + (Join-Path $folder "market_insight.py") + '"'
} else {
    $link.TargetPath = Join-Path $env:WINDIR "System32\wscript.exe"
    $link.Arguments = '"' + (Join-Path $folder "Start_Market_Insight.vbs") + '"'
}

$link.WorkingDirectory = $folder
$link.Description = "Open Market Insight"
$icon = Join-Path $folder "market_insight.ico"
if (Test-Path $icon) { $link.IconLocation = "$icon,0" }
$link.Save()
