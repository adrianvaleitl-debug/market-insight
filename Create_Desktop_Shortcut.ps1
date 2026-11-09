$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Market Insight.lnk"
$target = Join-Path $env:WINDIR "System32\wscript.exe"
$arguments = '"' + (Join-Path $folder "Start_Market_Insight.vbs") + '"'
$icon = Join-Path $folder "market_insight.ico"
$wsh = New-Object -ComObject WScript.Shell
$link = $wsh.CreateShortcut($shortcutPath)
$link.TargetPath = $target
$link.Arguments = $arguments
$link.WorkingDirectory = $folder
$link.Description = "Open Market Insight"
if (Test-Path $icon) { $link.IconLocation = "$icon,0" }
$link.Save()
Write-Host "Shortcut created: $shortcutPath"
Write-Host "If the icon does not update immediately, right-click the desktop and choose Refresh."
