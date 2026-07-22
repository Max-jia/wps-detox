"""
WPS D-tox — 一鍵 PDF 批次備份
用 LibreOffice headless 把文檔轉成 PDF，存到安全備份資料夾
"""

import os
import sys
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from datetime import datetime

from engine.inventory import InventoryResult, DocEntry, _format_size
from engine.inventory import WPS_PRIVATE_FORMATS


# ── LibreOffice 偵測 ─────────────────────────

def find_libreoffice() -> Optional[str]:
    """
    找 LibreOffice 的 soffice 執行檔路徑
    找不到回傳 None
    """
    # macOS
    if sys.platform == "darwin":
        candidates = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "/Applications/OpenOffice.app/Contents/MacOS/soffice",
        ]
    # Windows
    elif sys.platform == "win32":
        candidates = [
            "C:\\Program Files\\LibreOffice\\program\\soffice.exe",
            "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe",
        ]
    # Linux
    else:
        candidates = [
            "/usr/bin/soffice",
            "/usr/lib/libreoffice/program/soffice",
        ]

    for path in candidates:
        if os.path.exists(path):
            return path

    # 試試 which
    for cmd in ["soffice", "libreoffice"]:
        found = shutil.which(cmd)
        if found:
            return found

    return None


def get_install_guide() -> str:
    """回傳 LibreOffice 安裝指南（按平台）"""
    if sys.platform == "darwin":
        return "brew install --cask libreoffice"
    elif sys.platform == "win32":
        return "下載：https://www.libreoffice.org/download/  → 安裝後重新打開本工具"
    else:
        return "sudo apt install libreoffice"


# ── 備份結果 ─────────────────────────────────

@dataclass
class BackupResult:
    success: List[str] = field(default_factory=list)     # 成功轉換的檔案路徑
    skipped_wps_format: List[str] = field(default_factory=list)  # 跳過的 WPS 私有格式
    failed: List[tuple] = field(default_factory=list)    # (檔案路徑, 錯誤訊息)
    total_size: int = 0          # 成功備份的總大小
    skipped_size: int = 0        # 跳過的總大小


def backup_to_pdf(
    documents: List[DocEntry],
    output_dir: str = None,
    on_progress: Callable = None,
) -> BackupResult:
    """
    批次把文檔轉成 PDF

    Args:
        documents: 要轉換的文檔列表
        output_dir: 輸出目錄，預設為桌面上的「WPS 備份檔案」
        on_progress: 進度回調 (current, total, filename, status)

    Returns:
        BackupResult
    """
    result = BackupResult()

    # 檢查 LibreOffice
    soffice = find_libreoffice()
    if not soffice:
        # 沒有 LO，全部標為失敗
        for doc in documents:
            result.failed.append((doc.filepath, "LibreOffice 未安裝"))
        return result

    # 輸出目錄
    if output_dir is None:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        output_dir = os.path.join(
            desktop,
            f"WPS备份档案_{datetime.now().strftime('%Y%m%d')}",
        )
    os.makedirs(output_dir, exist_ok=True)

    total = len(documents)

    for i, doc in enumerate(documents):
        status = "processing"

        # 跳過 WPS 私有格式
        if doc.extension.lower() in WPS_PRIVATE_FORMATS:
            result.skipped_wps_format.append(doc.filepath)
            result.skipped_size += doc.size
            status = "skipped_wps"
            if on_progress:
                on_progress(i + 1, total, doc.filename, status)
            continue

        # 生成輸出檔名（保留原始檔名，改副檔名為 .pdf）
        base = os.path.splitext(doc.filename)[0]
        pdf_name = f"{base}.pdf"
        pdf_path = os.path.join(output_dir, pdf_name)

        # 避免覆蓋同名檔案
        counter = 1
        while os.path.exists(pdf_path):
            pdf_name = f"{base}_{counter}.pdf"
            pdf_path = os.path.join(output_dir, pdf_name)
            counter += 1

        try:
            subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to", "pdf",
                    "--outdir", output_dir,
                    doc.filepath,
                ],
                check=True,
                timeout=60,  # 單個檔案最多等 60 秒
                capture_output=True,
            )

            # LibreOffice 產生的檔案名可能跟我們預期的不一樣
            # 它會用原始檔名（不含路徑），只改副檔名
            expected = os.path.join(output_dir, f"{base}.pdf")
            if os.path.exists(expected) and expected != pdf_path:
                os.rename(expected, pdf_path)

            if os.path.exists(pdf_path):
                result.success.append(pdf_path)
                result.total_size += os.path.getsize(pdf_path)
                status = "done"
            else:
                result.failed.append((doc.filepath, "轉換後找不到輸出檔案"))
                status = "failed"

        except subprocess.TimeoutExpired:
            result.failed.append((doc.filepath, "轉換超時（>60 秒）"))
            status = "failed"
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode("utf-8", errors="replace")[:100] if e.stderr else "未知錯誤"
            result.failed.append((doc.filepath, err_msg))
            status = "failed"
        except Exception as e:
            result.failed.append((doc.filepath, str(e)[:100]))
            status = "failed"

        if on_progress:
            on_progress(i + 1, total, doc.filename, status)

    return result


def get_backup_summary(result: BackupResult) -> str:
    """產生備份結果的文字摘要"""
    lines = []
    lines.append(f"✅ 成功備份：{len(result.success)} 個 PDF")
    lines.append(f"   總大小：{_format_size(result.total_size)}")
    if result.skipped_wps_format:
        lines.append(f"🔒 跳過 WPS 私有格式：{len(result.skipped_wps_format)} 個")
        lines.append(f"   （.wps/.et/.dps 格式需先用 WPS 另存為標準格式）")
    if result.failed:
        lines.append(f"❌ 失敗：{len(result.failed)} 個")
    return "\n".join(lines)


# ── CLI 測試 ──────────────────────────────────

if __name__ == "__main__":
    from engine.inventory import scan_documents

    soffice = find_libreoffice()
    if soffice:
        print(f"✅ 找到 LibreOffice：{soffice}")
    else:
        print("❌ 未安裝 LibreOffice")
        print(f"   安裝指令：{get_install_guide()}")
        print("   安裝後再執行本工具即可使用 PDF 備份功能")

    print("\n📋 掃描文檔...")
    docs = scan_documents()

    if soffice and docs.documents:
        standard_docs = [d for d in docs.documents if not d.is_wps_format]
        print(f"   找到 {len(standard_docs)} 個可轉換文檔")
        print(f"   {len([d for d in docs.documents if d.is_wps_format])} 個 WPS 私有格式將被跳過\n")

        def progress(cur, total, name, status):
            icons = {"done": "✅", "skipped_wps": "🔒", "failed": "❌", "processing": "⏳"}
            icon = icons.get(status, "  ")
            print(f"   [{cur}/{total}] {icon} {name}")

        result = backup_to_pdf(docs.documents, on_progress=progress)
        print(f"\n{get_backup_summary(result)}")
