"""
打包腳本：把 WPS 解毒器打包成 Windows .exe
執行方式：python build.py
"""

import subprocess
import sys
import os


def build_gui():
    """打包 GUI 版"""
    print("📦 正在打包 GUI 版...")

    # 根據平台決定路徑分隔符
    sep = ";" if sys.platform == "win32" else ":"

    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",                    # 不顯示終端機視窗
        "--name", "WPS-Detox",
        "--add-data", f"engine{sep}engine",
        "--hidden-import", "customtkinter",
        "--clean",
        "--noconfirm",
        "ui/app.py",
    ]

    subprocess.run(cmd, check=True)
    print("✅ GUI 版打包完成：dist/WPS-Detox.exe" if sys.platform == "win32" else "✅ GUI 版打包完成：dist/WPS-Detox")


def build_cli():
    """打包命令列版"""
    print("📦 正在打包 CLI 版...")

    cmd = [
        "pyinstaller",
        "--onefile",
        "--name", "wps-detox-cli",
        "--clean",
        "--noconfirm",
        "main.py",
    ]

    subprocess.run(cmd, check=True)
    print("✅ CLI 版打包完成：dist/wps-detox-cli.exe" if sys.platform == "win32" else "✅ CLI 版打包完成：dist/wps-detox-cli")


if __name__ == "__main__":
    print("🧪 WPS 解毒器 — 打包工具\n")

    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        build_cli()
    else:
        build_gui()

    print("\n📁 輸出目錄：dist/")
