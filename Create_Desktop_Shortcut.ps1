param(
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Market Insight.lnk"

if ($Remove) {
    if (Test-Path $shortcutPath) { Remove-Item -LiteralPath $shortcutPath -Force }
    exit 0
}

$wsh = New-Object -ComObject WScript.Shell
$link = $wsh.CreateShortcut($shortcutPath)
$exe = Join-Path $folder "Market Insight.exe"
if (Test-Path $exe) {
    $link.TargetPath = $exe
} else {
    $link.TargetPath = Join-Path $env:WINDIR "System32\wscript.exe"
    $link.Arguments = '"' + (Join-Path $folder "Start_Market_Insight.vbs") + '"'
}
$link.WorkingDirectory = $folder
$link.Description = "Open Market Insight"
$icon = Join-Path $folder "market_insight.ico"
if (Test-Path $icon) { $link.IconLocation = "$icon,0" }
$link.Save()
