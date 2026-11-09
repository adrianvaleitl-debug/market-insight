Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
logFile = folder & "\startup_error.log"
command = "cmd.exe /c py -3 """ & folder & "\market_insight.py"" > """ & logFile & """ 2>&1"
shell.CurrentDirectory = folder
' Run hidden, but retain Python errors in startup_error.log for troubleshooting.
shell.Run command, 0, False
