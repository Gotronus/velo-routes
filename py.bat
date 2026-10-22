@echo off
set A=C:\Users\axelg\anaconda3
set PATH=%A%;%A%\Library\bin;%A%\Library\mingw-w64\bin;%A%\Library\usr\bin;%A%\Scripts;%A%\DLLs;%PATH%
cd /d C:\Users\axelg\Documents\velo-routes
"%A%\python.exe" %*
