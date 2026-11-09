$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Market Insight.lnk"
$target = Join-Path $env:WINDIR "System32\wscript.exe"
$arguments = '"' + (Join-Path $folder "Start_Market_Insight.vbs") + '"'
$wsh = New-Object -ComObject WScript.Shell
$link = $wsh.CreateShortcut($shortcutPath)
$link.TargetPath = $target
$link.Arguments = $arguments
$link.WorkingDirectory = $folder
$link.Description = "Open Market Insight"
$link.Save()
Write-Host "Shortcut created: $shortcutPath"
