"""
WPS D-tox — 命令列主程式
用於測試引擎，GUI 版請執行 ui/app.py
"""

import sys
import os

# 確保能找到 engine 模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.scanner import scan_junk, print_scan_result
from engine.cleaner import clean_junk_groups, print_clean_result
from engine.inventory import scan_documents, print_inventory_result


def show_banner():
    print(r"""
  ╔══════════════════════════════════════════╗
  ║       🧪  WPS 解毒器  D-tox            ║
  ║       幫你逃離 WPS 的第一步            ║
  ╚══════════════════════════════════════════╝
    """)


def show_menu():
    print("""
  請選擇：
  [1] 🔍 掃描 WPS 垃圾檔案
  [2] 🧹 掃描 + 清理（一鍵）
  [3] 📋 文檔盤點
  [4] 🚀 全部執行（掃描 → 清理 → 盤點）
  [0] 離開
    """)


def main():
    show_banner()

    while True:
        show_menu()
        choice = input("  輸入選項 [1-4, 0]: ").strip()

        if choice == "1":
            print("\n  🔍 正在掃描 WPS 垃圾...\n")
            result = scan_junk()
            print_scan_result(result)

        elif choice == "2":
            print("\n  🔍 正在掃描 WPS 垃圾...\n")
            result = scan_junk()

            if not result.junk_groups:
                print("  ✅ 沒有可清理的垃圾。")
                continue

            print_scan_result(result)

            confirm = input("  確定要清理以上所有垃圾嗎？[y/N]: ").strip().lower()
            if confirm == "y":
                print("\n  🧹 正在清理...")
                clean_result = clean_junk_groups(result.junk_groups)
                print_clean_result(clean_result)
            else:
                print("  已取消。")

        elif choice == "3":
            print("\n  📋 正在盤點文檔（這可能需要一兩分鐘）...\n")
            result = scan_documents()
            print_inventory_result(result)

        elif choice == "4":
            # 掃描
            print("\n  🔍 正在掃描 WPS 垃圾...\n")
            junk = scan_junk()
            print_scan_result(junk)

            if junk.junk_groups:
                print("\n  🧹 正在自動清理...\n")
                clean = clean_junk_groups(junk.junk_groups)
                print_clean_result(clean)

            # 盤點
            print("\n  📋 正在盤點文檔...\n")
            docs = scan_documents()
            print_inventory_result(docs)

        elif choice == "0":
            print("\n  再見！👋\n")
            break

        else:
            print("\n  ❌ 無效選項，請輸入 1-4 或 0")


if __name__ == "__main__":
    main()
