' Yide voice - silent background launcher (no console window).
' Put a SHORTCUT to this file into shell:startup to auto-start on login.
' (Runs yide_voice.py in the same folder. If you use a venv, replace "python" below.)
Dim sh, here
Set sh = CreateObject("WScript.Shell")
here = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
sh.Run "python """ & here & "yide_voice.py""", 0, False
