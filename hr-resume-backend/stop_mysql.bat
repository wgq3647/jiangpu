@echo off
chcp 65001 >nul
title MySQL 停止工具

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [提示] 需要管理员权限，正在请求提权...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ========================================
echo          MySQL 停止工具
echo ========================================
echo.

:: 检查服务是否存在
sc query MySQL >nul 2>&1
if %errorLevel% neq 0 (
    echo [错误] 未找到 MySQL 服务。
    echo.
    pause
    exit /b 1
)

:: 检查当前状态
for /f "tokens=3" %%a in ('sc query MySQL ^| findstr STATE') do set STATE=%%a

if /i "%STATE%"=="STOPPED" (
    echo [状态] MySQL 已经是停止状态，无需重复停止。
    goto :end
)

echo [状态] 正在停止 MySQL...
echo.

net stop MySQL

if %errorLevel% equ 0 (
    echo.
    echo [成功] MySQL 已停止。
) else (
    echo.
    echo [失败] MySQL 停止失败，错误码: %errorLevel%
)

:end
echo.
echo ========================================
pause
