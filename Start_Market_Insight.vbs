Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = folder
' Use the windowless Python launcher directly. No cmd.exe window is created.
shell.Run "pyw -3 """ & folder & "\market_insight.py""", 0, False
