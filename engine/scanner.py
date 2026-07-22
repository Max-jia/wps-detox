"""
WPS D-tox — 掃描引擎
找出 WPS 在電腦上藏的所有垃圾檔案和文檔
支援：Windows / macOS
"""

import os
import glob
import platform
from dataclasses import dataclass, field
from typing import List, Tuple

SYSTEM = platform.system()  # "Windows" | "Darwin" | "Linux"


@dataclass
class JunkGroup:
    """一組垃圾檔案"""
    category: str          # 類別名，如「緩存檔案」
    description: str       # 一句話說明這坨是什麼
    path: str              # 目錄路徑
    file_count: int = 0
    total_size: int = 0    # bytes
    files: List[str] = field(default_factory=list)
    can_safe_delete: bool = True  # 刪了會不會影響文檔


@dataclass
class ScanResult:
    """掃描結果"""
    junk_groups: List[JunkGroup] = field(default_factory=list)
    total_junk_size: int = 0   # bytes
    total_junk_count: int = 0


# ── 平台：Windows ──────────────────────────────────

def _get_wps_paths_windows() -> List[str]:
    """Windows 上 WPS 可能藏東西的所有目錄"""
    paths = []
    home = os.path.expanduser("~")

    appdata = os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming"))
    paths.append(os.path.join(appdata, "Kingsoft", "office6"))

    local_appdata = os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local"))
    paths.append(os.path.join(local_appdata, "Kingsoft", "office6"))

    programdata = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
    paths.append(os.path.join(programdata, "Kingsoft", "office6"))

    paths.append(os.path.join(home, "Documents", "WPS Cloud Files"))
    paths.append(os.path.join(home, "Documents", "kingsoft"))

    return paths


# ── 平台：macOS ────────────────────────────────────

def _discover_wps_containers_mac() -> List[str]:
    """
    動態搜尋 macOS 上的 WPS 沙盒容器目錄
    WPS 在不同版本用了不同的 bundle identifier：
      - com.kingsoft.wpsoffice.mac（國際版 / 新版）
      - cn.kingsoft.wps.mac（中國版 / 舊版）
    """
    containers_dir = os.path.expanduser("~/Library/Containers")
    if not os.path.exists(containers_dir):
        return []

    containers = []
    keywords = ["kingsoft", "wps"]

    try:
        for name in os.listdir(containers_dir):
            name_lower = name.lower()
            if any(kw in name_lower for kw in keywords):
                containers.append(os.path.join(containers_dir, name))
    except PermissionError:
        pass

    return containers


def _get_wps_paths_mac() -> List[str]:
    """macOS 上 WPS 可能藏東西的所有目錄"""
    paths = []
    home = os.path.expanduser("~")

    # 沙盒容器內的路徑（每個找到的容器都加）
    for container in _discover_wps_containers_mac():
        data = os.path.join(container, "Data")
        paths.append(os.path.join(data, "Library", "Application Support", "Kingsoft", "office6"))
        paths.append(os.path.join(data, ".kingsoft", "office6"))
        paths.append(os.path.join(data, "Library", "Application Support", "Kingsoft", "WPS Cloud Files"))

    # 非沙盒路徑（舊版 WPS Mac 或直接安裝版）
    library = os.path.join(home, "Library")
    paths.append(os.path.join(library, "Application Support", "Kingsoft", "office6"))
    paths.append(os.path.join(library, "Application Support", "Kingsoft", "WPS Office"))

    # 系統級緩存
    paths.append(os.path.join(library, "Caches", "com.kingsoft.wpsoffice.mac"))
    paths.append(os.path.join(library, "Caches", "cn.kingsoft.wps.mac"))

    # WPS 雲文檔緩存（有時在文檔目錄）
    paths.append(os.path.join(home, "Documents", "WPS Cloud Files"))

    return paths


# ── 統一路徑查詢 ────────────────────────────────────

def _get_wps_paths() -> List[str]:
    """根據目前作業系統，回傳所有 WPS 相關目錄"""
    if SYSTEM == "Windows":
        return _get_wps_paths_windows()
    elif SYSTEM == "Darwin":
        return _get_wps_paths_mac()
    else:
        # Linux 基本沒人用 WPS desktop，但留個入口
        home = os.path.expanduser("~")
        return [
            os.path.join(home, ".config", "Kingsoft"),
            os.path.join(home, ".local", "share", "Kingsoft"),
            os.path.join(home, ".cache", "Kingsoft"),
        ]


# ── 掃描核心邏輯（跨平台通用）────────────────────

def _scan_directory(path: str) -> Tuple[int, int, List[str]]:
    """
    掃描一個目錄，回傳 (檔案數, 總大小, 檔案列表)
    如果目錄不存在，回傳 (0, 0, [])
    """
    if not os.path.exists(path):
        return 0, 0, []

    total_size = 0
    file_count = 0
    all_files = []

    try:
        for root, dirs, files in os.walk(path):
            for f in files:
                filepath = os.path.join(root, f)
                try:
                    size = os.path.getsize(filepath)
                    total_size += size
                    file_count += 1
                    all_files.append(filepath)
                except (OSError, PermissionError):
                    continue
    except PermissionError:
        pass

    return file_count, total_size, all_files


def _format_size(size_bytes: int) -> str:
    """把 bytes 轉成可讀格式"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def scan_junk() -> ScanResult:
    """
    掃描所有 WPS 垃圾
    自動偵測平台，回傳 ScanResult
    """
    result = ScanResult()

    targets = [
        {"category": "雲文檔緩存", "subdir": "cache",
         "desc": "WPS 雲文檔在本地留的緩存副本，刪了不影響雲端檔案"},
        {"category": "自動備份", "subdir": "backup",
         "desc": "WPS 自動儲存的備份檔，通常每幾分鐘存一次"},
        {"category": "臨時檔案", "subdir": "temp",
         "desc": "編輯過程中的暫存檔，理論上關閉文檔時就該清掉"},
        {"category": "日誌檔案", "subdir": "log",
         "desc": "WPS 運行的記錄檔，對正常使用沒有任何影響"},
        {"category": "崩潰轉儲", "subdir": "dumps",
         "desc": "WPS 崩潰時產生的診斷檔案，通常很大且用不到"},
        {"category": "更新殘留", "subdir": "update",
         "desc": "WPS 更新後沒清乾淨的安裝包殘留"},
    ]

    base_paths = _get_wps_paths()

    for target in targets:
        group = JunkGroup(
            category=target["category"],
            description=target["desc"],
            path="",
        )

        for base in base_paths:
            search_path = os.path.join(base, target["subdir"])
            count, size, files = _scan_directory(search_path)
            group.file_count += count
            group.total_size += size
            group.files.extend(files)
            if count > 0:
                group.path = search_path

        if group.file_count > 0:
            result.junk_groups.append(group)
            result.total_junk_size += group.total_size
            result.total_junk_count += group.file_count

    # 另外掃描根目錄下的 .bak / .tmp / .wbk 檔案
    root_junk = JunkGroup(
        category="分散的暫存檔",
        description="散落在 WPS 目錄各處的 .bak / .tmp / .wbk 殘留檔",
        path="各 WPS 目錄",
    )

    junk_extensions = ["*.bak", "*.tmp", "*.wbk", "~*.*"]
    for base in base_paths:
        if not os.path.exists(base):
            continue
        for ext in junk_extensions:
            pattern = os.path.join(base, "**", ext)
            try:
                for f in glob.glob(pattern, recursive=True):
                    try:
                        size = os.path.getsize(f)
                        root_junk.file_count += 1
                        root_junk.total_size += size
                        root_junk.files.append(f)
                    except OSError:
                        continue
            except Exception:
                continue

    if root_junk.file_count > 0:
        result.junk_groups.append(root_junk)
        result.total_junk_size += root_junk.total_size
        result.total_junk_count += root_junk.file_count

    return result


def get_platform_name() -> str:
    """回傳目前平台的可讀名稱"""
    names = {"Windows": "Windows", "Darwin": "macOS", "Linux": "Linux"}
    return names.get(SYSTEM, SYSTEM)


# ── CLI 輸出 ────────────────────────────────────────

def print_scan_result(result: ScanResult):
    """在終端機漂亮地印出掃描結果"""
    print("\n" + "=" * 60)
    print(f"  🔍 WPS 解毒器 — 掃描結果（{get_platform_name()}）")
    print("=" * 60)

    if not result.junk_groups:
        print("\n  ✅ 沒找到任何 WPS 垃圾！你的電腦很乾淨。")
        return

    for group in result.junk_groups:
        icon = "🗑️" if group.can_safe_delete else "⚠️"
        print(f"\n  {icon} {group.category}")
        print(f"     {group.description}")
        print(f"     📁 {group.path}")
        print(f"     📄 {group.file_count} 個檔案，共 {_format_size(group.total_size)}")

    print(f"\n  {'─' * 56}")
    print(f"  📊 總計：{result.total_junk_count} 個垃圾檔案")
    print(f"  💾 可釋放空間：{_format_size(result.total_junk_size)}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    print(f"🖥️  目前平台：{get_platform_name()}")
    result = scan_junk()
    print_scan_result(result)
