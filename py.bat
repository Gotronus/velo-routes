@echo off
set A=%USERPROFILE%\anaconda3
set PATH=%A%;%A%\Library\bin;%A%\Library\mingw-w64\bin;%A%\Library\usr\bin;%A%\Scripts;%A%\DLLs;%PATH%
cd /d "%~dp0"
"%A%\python.exe" %*
