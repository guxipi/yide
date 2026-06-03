@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
REM ============================================================
REM  翼德 · playtest 录屏按钮(钉到任务栏 = 一颗开始/结束按钮)
REM  点一下:开始录(屏幕 + 麦克风,最小化在后台)
REM  再点一下:停止录,文件落到 项目\QA\playtest\raw\<时间戳>.mkv
REM ------------------------------------------------------------
REM  用前改两处(SETUP.md 有图文步骤):
REM   1) MIC = 你的麦克风设备名(ffmpeg -list_devices true -f dshow -i dummy 查)
REM   2) VENC = 显卡编码器:N 卡 h264_nvenc / A 卡 h264_amf / 没独显 libx264
REM  用 .mkv 容器:就算异常退出文件也还能用(不怕没优雅停)。
REM ============================================================

set "MIC=麦克风 (Realtek(R) Audio)"
set "VENC=h264_nvenc"

REM 录像存到"当前项目"的 QA\playtest\raw(把本 bat 的工作目录设成项目根,或在项目根双击)
set "OUTDIR=%CD%\QA\playtest\raw"
set "MARK=%TEMP%\yide-playtest.lock"

if exist "%MARK%" goto :stop

:start
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
for /f "tokens=2 delims==." %%i in ('wmic os get localdatetime /value 2^>nul') do set "dt=%%i"
set "STAMP=%dt:~0,8%-%dt:~8,6%"
set "OUT=%OUTDIR%\%STAMP%.mkv"
echo %OUT%> "%MARK%"
echo [翼德] ● 开始录制 ^> %OUT%
echo        玩的时候大声说出哪里不对(中文就行)。再点一次本按钮停止。
start "yide-playtest-ffmpeg" /min ffmpeg -y -f gdigrab -framerate 30 -i desktop ^
  -f dshow -i audio="%MIC%" ^
  -c:v %VENC% -preset fast -b:v 6M -pix_fmt yuv420p ^
  -c:a aac -b:a 128k "%OUT%"
timeout /t 2 >nul
goto :eof

:stop
echo [翼德] ■ 停止录制...
REM 不带 /f:发关闭事件让 ffmpeg 自己收尾;.mkv 容器即便没收尾也可用
taskkill /im ffmpeg.exe >nul 2>&1
set /p RECFILE=<"%MARK%"
del "%MARK%" >nul 2>&1
echo [翼德] ✓ 已停:%RECFILE%
echo        (可选录屏方案)整段录像已存;主力反馈走 Unity 冻帧标注,见 SETUP.md。
timeout /t 4 >nul
goto :eof
