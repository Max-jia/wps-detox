"""
WPS D-tox — 清理引擎
負責安全地刪除掃描到的垃圾檔案
"""

import os
import shutil
from typing import List, Tuple
from dataclasses import dataclass, field
from engine.scanner import ScanResult, JunkGroup, _format_size


@dataclass
class CleanResult:
    """清理結果"""
    groups_cleaned: List[dict] = field(default_factory=list)
    total_files_deleted: int = 0
    total_space_freed: int = 0      # bytes
    failed_files: List[str] = field(default_factory=list)
    skipped_files: int = 0          # 用戶選擇跳過的


def _delete_file_safe(filepath: str) -> bool:
    """安全刪除一個檔案，失敗就回傳 False"""
    try:
        os.remove(filepath)
        return True
    except (OSError, PermissionError):
        return False


def _delete_directory_safe(dirpath: str) -> bool:
    """安全刪除一個目錄（含所有內容），失敗就回傳 False"""
    try:
        shutil.rmtree(dirpath)
        return True
    except (OSError, PermissionError):
        # 如果整個目錄刪不掉，試試逐檔刪除
        if os.path.exists(dirpath):
            success = True
            for root, dirs, files in os.walk(dirpath, topdown=False):
                for f in files:
                    fp = os.path.join(root, f)
                    if not _delete_file_safe(fp):
                        success = False
                for d in dirs:
                    dp = os.path.join(root, d)
                    try:
                        os.rmdir(dp)
                    except OSError:
                        pass
            try:
                os.rmdir(dirpath)
            except OSError:
                pass
            return success
        return True  # 目錄已不存在，當作成功


def clean_junk_groups(selected_groups: List[JunkGroup],
                      on_progress=None) -> CleanResult:
    """
    清理選定的垃圾組

    Args:
        selected_groups: 用戶選擇要清理的 JunkGroup 列表
        on_progress: 進度回調函數，簽名: on_progress(current, total, filename)

    Returns:
        CleanResult: 清理結果摘要
    """
    result = CleanResult()
    total_files = sum(g.file_count for g in selected_groups)
    processed = 0

    for group in selected_groups:
        group_result = {
            "category": group.category,
            "files_deleted": 0,
            "space_freed": 0,
        }

        # 方式一：如果整個 group 是對應一個目錄，直接刪目錄
        # 這比逐檔刪除快得多
        if group.path and os.path.exists(group.path):
            dir_size_before = group.total_size
            success = _delete_directory_safe(group.path)
            if success:
                group_result["files_deleted"] = group.file_count
                group_result["space_freed"] = dir_size_before
                processed += group.file_count
                if on_progress:
                    on_progress(processed, total_files, group.path)
                result.groups_cleaned.append(group_result)
                result.total_files_deleted += group.file_count
                result.total_space_freed += dir_size_before
                continue

        # 方式二：逐檔刪除（用於分散在各處的檔案）
        for filepath in group.files:
            file_size = 0
            try:
                file_size = os.path.getsize(filepath)
            except OSError:
                pass

            if _delete_file_safe(filepath):
                group_result["files_deleted"] += 1
                group_result["space_freed"] += file_size
                result.total_files_deleted += 1
                result.total_space_freed += file_size
            else:
                result.failed_files.append(filepath)

            processed += 1
            if on_progress:
                on_progress(processed, total_files, filepath)

        if group_result["files_deleted"] > 0:
            result.groups_cleaned.append(group_result)

    return result


def print_clean_result(result: CleanResult):
    """在終端機漂亮地印出清理結果"""
    print("\n" + "=" * 60)
    print("  ✨ WPS 解毒器 — 清理完成")
    print("=" * 60)

    for g in result.groups_cleaned:
        print(f"\n  ✅ {g['category']}")
        print(f"     刪除 {g['files_deleted']} 個檔案，釋放 {_format_size(g['space_freed'])}")

    if result.failed_files:
        print(f"\n  ⚠️  {len(result.failed_files)} 個檔案刪除失敗（可能被 WPS 佔用中）")
        print(f"     建議關閉 WPS 後再試一次")

    print(f"\n  {'─' * 56}")
    print(f"  🎉 共刪除 {result.total_files_deleted} 個垃圾檔案")
    print(f"  💾 釋放空間：{_format_size(result.total_space_freed)}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    from engine.scanner import scan_junk
    result = scan_junk()
    if result.junk_groups:
        clean_result = clean_junk_groups(result.junk_groups)
        print_clean_result(clean_result)
    else:
        print("沒有可清理的檔案。")
