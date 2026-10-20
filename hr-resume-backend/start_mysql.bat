@echo off
chcp 65001 >nul
title MySQL 启动工具

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [提示] 需要管理员权限，正在请求提权...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ========================================
echo          MySQL 启动工具
echo ========================================
echo.

:: 检查服务是否存在
sc query MySQL >nul 2>&1
if %errorLevel% neq 0 (
    echo [错误] 未找到 MySQL 服务，请确认 MySQL 已正确安装。
    echo.
    pause
    exit /b 1
)

:: 检查当前状态
for /f "tokens=3" %%a in ('sc query MySQL ^| findstr STATE') do set STATE=%%a

if /i "%STATE%"=="RUNNING" (
    echo [状态] MySQL 已经在运行中，无需重复启动。
    echo.
    echo 连接信息:
    echo   地址: localhost:3306
    echo   数据库: hr_resume
    echo   配置文件: D:\mysql\my.ini
    goto :end
)

echo [状态] MySQL 当前已停止，正在启动...
echo.

net start MySQL

if %errorLevel% equ 0 (
    echo.
    echo [成功] MySQL 启动成功！
    echo.
    echo 连接信息:
    echo   地址: localhost:3306
    echo   数据库: hr_resume
    echo   配置文件: D:\mysql\my.ini
) else (
    echo.
    echo [失败] MySQL 启动失败，错误码: %errorLevel%
    echo.
    echo 可能的原因:
    echo   1. 端口 3306 被占用
    echo   2. 数据目录权限不足
    echo   3. 配置文件 my.ini 有误
    echo.
    echo 请查看 Windows 事件查看器中的 MySQL 错误日志。
)

:end
echo.
echo ========================================
pause
