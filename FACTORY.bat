@echo off
chcp 65001 >nul 2>&1
title AI Software Factory

:MENU
cls
echo.
echo  ==========================================
echo    AI SOFTWARE FACTORY - COMMAND CENTER
echo  ==========================================
echo.
echo  PROJECT:
echo    [1] revit - RevitAddinSolution
echo    [2] navis - NavisAddinSolution
echo    [3] trend - TrendingUpdate
echo.
echo  COMMAND:
echo    [S] status  - Xem tien do pipeline
echo    [N] next    - Lay prompt buoc tiep theo
echo    [D] done    - Danh dau buoc xong, next buoc
echo    [C] codex   - Chay Codex review tu dong
echo    [M] commit  - Huong dan sync + commit
echo    [R] reset   - Reset pipeline tu buoc 2
echo.
echo    [Q] Thoat
echo  ------------------------------------------
set /p choice="  Chon (vi du: 1N hoac 2S): "

if /i "%choice%"=="Q" goto :EOF
if /i "%choice%"=="q" goto :EOF

:: Parse project (ky tu dau)
set proj=revit
if "%choice:~0,1%"=="2" set proj=navis
if "%choice:~0,1%"=="3" set proj=trend

:: Parse command (ky tu thu 2)
set cmd=status
set cmdchar=%choice:~1,1%
if /i "%cmdchar%"=="s" set cmd=status
if /i "%cmdchar%"=="n" set cmd=next
if /i "%cmdchar%"=="d" set cmd=done
if /i "%cmdchar%"=="c" set cmd=codex
if /i "%cmdchar%"=="m" set cmd=commit
if /i "%cmdchar%"=="r" set cmd=reset

echo.
echo  ==========================================
echo  Running: python harness.py %proj% %cmd%
echo  ==========================================
echo.
python "E:\AI_SOFTWARE_FACTORY\harness.py" %proj% %cmd%
echo.
pause
goto MENU
