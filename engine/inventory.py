"""
WPS D-tox — 文檔盤點引擎
掃描電腦上所有 WPS 相關的文檔，分類展示
"""

import os
import glob
import platform
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class DocEntry:
    """一個文檔的資訊"""
    filepath: str
    filename: str
    extension: str         # e.g. ".docx"
    category: str          # "文件" | "表格" | "簡報" | "PDF" | "其他"
    size: int              # bytes
    modified: Optional[datetime] = None
    is_wps_format: bool = False  # 是否為 WPS 私有格式 (.wps/.et/.dps)


@dataclass
class InventoryResult:
    """文檔盤點結果"""
    documents: List[DocEntry] = field(default_factory=list)
    total_count: int = 0
    total_size: int = 0
    wps_only_count: int = 0     # WPS 私有格式數量
    standard_count: int = 0     # 標準格式（可搬家）數量


# 文檔格式分類
DOC_CATEGORIES = {
    "文件": [".doc", ".docx", ".wps", ".wpt", ".rtf", ".odt", ".txt", ".md"],
    "表格": [".xls", ".xlsx", ".et", ".ett", ".csv", ".ods"],
    "簡報": [".ppt", ".pptx", ".dps", ".dpt", ".odp"],
    "PDF": [".pdf"],
}

WPS_PRIVATE_FORMATS = {".wps", ".wpt", ".et", ".ett", ".dps", ".dpt"}

# 所有 WPS 能打開的格式
ALL_DOC_EXTENSIONS = set()
for exts in DOC_CATEGORIES.values():
    ALL_DOC_EXTENSIONS.update(exts)


def _categorize_extension(ext: str) -> str:
    """根據副檔名判斷文檔類別"""
    ext = ext.lower()
    for category, extensions in DOC_CATEGORIES.items():
        if ext in extensions:
            return category
    return "其他"


def _format_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def scan_documents(search_paths: List[str] = None) -> InventoryResult:
    """
    掃描電腦上的所有 WPS/Office 文檔

    Args:
        search_paths: 要掃描的目錄列表，預設為桌面 + 文檔 + 下載

    Returns:
        InventoryResult: 盤點結果
    """
    result = InventoryResult()

    if search_paths is None:
        home = os.path.expanduser("~")
        search_paths = [
            os.path.join(home, "Desktop"),
            os.path.join(home, "Documents"),
            os.path.join(home, "Downloads"),
            os.path.join(home, "OneDrive"),
        ]

        # Mac 專屬路徑
        if platform.system() == "Darwin":
            search_paths.append(os.path.join(home, "Desktop"))
            search_paths.append(os.path.join(home, "Documents"))
            search_paths.append(os.path.join(home, "Downloads"))
            # iCloud Drive
            icloud = os.path.join(home, "Library", "Mobile Documents", "com~apple~CloudDocs")
            if os.path.exists(icloud):
                search_paths.append(icloud)

        # Windows 專屬：其他磁碟
        if platform.system() == "Windows":
            for drive in ["D:", "E:", "F:"]:
                if os.path.exists(drive):
                    search_paths.append(drive + "\\")

    # 只掃描存在的路徑
    search_paths = [p for p in search_paths if os.path.exists(p)]

    seen = set()  # 避免重複

    for search_path in search_paths:
        for ext in ALL_DOC_EXTENSIONS:
            pattern = os.path.join(search_path, "**", f"*{ext}")
            try:
                for filepath in glob.glob(pattern, recursive=True):
                    # 跳過 WPS 系統目錄裡的檔案
                    if "kingsoft" in filepath.lower():
                        continue
                    if "wps" in os.path.basename(filepath.lower()) and "office6" in filepath.lower():
                        continue

                    norm_path = os.path.normpath(filepath).lower()
                    if norm_path in seen:
                        continue
                    seen.add(norm_path)

                    try:
                        stat = os.stat(filepath)
                        mod_time = datetime.fromtimestamp(stat.st_mtime)
                    except OSError:
                        mod_time = None

                    ext_lower = ext.lower()
                    doc = DocEntry(
                        filepath=filepath,
                        filename=os.path.basename(filepath),
                        extension=ext_lower,
                        category=_categorize_extension(ext_lower),
                        size=stat.st_size if stat else 0,
                        modified=mod_time,
                        is_wps_format=ext_lower in WPS_PRIVATE_FORMATS,
                    )
                    result.documents.append(doc)
            except Exception:
                continue

    # 按修改時間倒序（最新的在前面）
    result.documents.sort(
        key=lambda d: d.modified or datetime.min,
        reverse=True
    )

    result.total_count = len(result.documents)
    result.total_size = sum(d.size for d in result.documents)
    result.wps_only_count = sum(1 for d in result.documents if d.is_wps_format)
    result.standard_count = result.total_count - result.wps_only_count

    return result


def get_docs_by_category(result: InventoryResult) -> dict:
    """按類別分組文檔"""
    grouped = {}
    for doc in result.documents:
        if doc.category not in grouped:
            grouped[doc.category] = []
        grouped[doc.category].append(doc)
    return grouped


def get_large_docs(result: InventoryResult, top_n: int = 20) -> List[DocEntry]:
    """找出最大的 N 個文檔"""
    sorted_docs = sorted(result.documents, key=lambda d: d.size, reverse=True)
    return sorted_docs[:top_n]


def get_old_docs(result: InventoryResult, days: int = 365) -> List[DocEntry]:
    """找出超過 N 天沒動過的殭屍文檔"""
    cutoff = datetime.now().timestamp() - (days * 86400)
    return [
        d for d in result.documents
        if d.modified and d.modified.timestamp() < cutoff
    ]


def print_inventory_result(result: InventoryResult):
    """在終端機漂亮地印出文檔盤點結果"""
    print("\n" + "=" * 60)
    print("  📋 WPS 解毒器 — 文檔盤點")
    print("=" * 60)

    grouped = get_docs_by_category(result)
    icons = {"文件": "📝", "表格": "📊", "簡報": "📽️", "PDF": "📕", "其他": "📎"}

    for category, docs in grouped.items():
        icon = icons.get(category, "📎")
        total = sum(d.size for d in docs)
        print(f"\n  {icon} {category}：{len(docs)} 個，共 {_format_size(total)}")

    # 標出 WPS 私有格式
    if result.wps_only_count > 0:
        print(f"\n  ⚠️  {result.wps_only_count} 個 WPS 私有格式（.wps/.et/.dps）")
        print(f"     這些只有 WPS 能打開，搬家前需要先轉格式")

    # 最大的文件
    print(f"\n  🐘 最大的 5 個文檔：")
    for doc in get_large_docs(result, 5):
        mod_str = doc.modified.strftime("%Y-%m-%d") if doc.modified else "未知"
        tag = "🔒" if doc.is_wps_format else "  "
        print(f"     {tag} {_format_size(doc.size):>8}  {doc.filename}  ({mod_str})")

    # 殭屍文件
    old_docs = get_old_docs(result, 365)
    if old_docs:
        old_size = sum(d.size for d in old_docs)
        print(f"\n  🧟 超過一年沒動過的文檔：{len(old_docs)} 個，共 {_format_size(old_size)}")

    print(f"\n  {'─' * 56}")
    print(f"  📊 總計：{result.total_count} 個文檔")
    print(f"  💾 總佔用空間：{_format_size(result.total_size)}")
    print(f"  ✅ 標準格式（可搬家）：{result.standard_count} 個")
    if result.wps_only_count > 0:
        print(f"  🔒 WPS 私有格式（需轉換）：{result.wps_only_count} 個")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    result = scan_documents()
    print_inventory_result(result)
