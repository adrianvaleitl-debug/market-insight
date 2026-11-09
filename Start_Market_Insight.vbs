Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = "pythonw.exe"
shell.CurrentDirectory = folder
shell.Run "pyw -3 """ & folder & "\market_insight.py""", 0, False
