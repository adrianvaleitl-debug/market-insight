Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = folder
exePath = folder & "\Market Insight.exe"
If fso.FileExists(exePath) Then
    shell.Run """" & exePath & """", 0, False
Else
    shell.Run "pyw -3 """ & folder & "\market_insight.py""", 0, False
End If
