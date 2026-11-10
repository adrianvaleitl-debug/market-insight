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

# PyInstaller 6 stores --add-data files in the _internal directory.
# Keep the shortcut icon path aligned with the packaged application layout.
$iconCandidates = @(
    (Join-Path $folder "_internal\market_insight.ico"),
    (Join-Path $folder "market_insight.ico")
)
$icon = $iconCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($icon) {
    $link.IconLocation = "$icon,0"
} elseif (Test-Path $exe) {
    # The executable also contains the same icon as its application resource.
    $link.IconLocation = "$exe,0"
}
$link.Save()
