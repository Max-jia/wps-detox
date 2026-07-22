"""
WPS D-tox — 替代品推薦引擎
根據用戶文檔使用習慣，推薦最適合的 WPS 替代品
"""

from dataclasses import dataclass, field
from typing import List, Optional
from engine.inventory import InventoryResult, DocEntry, get_docs_by_category, _format_size


# ── 替代品資料庫 ─────────────────────────────

@dataclass
class Alternative:
    name: str
    tagline: str          # 一句話
    score: int            # 0-100 適合度
    icon: str
    pros: List[str]
    cons: List[str]
    url: str
    free: bool
    reason: str           # 為什麼推薦給你


# 所有替代品
ALTERNATIVES = {
    "onlyoffice": Alternative(
        name="OnlyOffice",
        tagline="格式相容性最強，介面最像 Office",
        score=0, icon="📎",
        pros=["MS Office 格式近乎完美相容", "介面現代、學習成本低", "桌面版免費", "支援即時協作"],
        cons=["需要註冊帳號才能用協作功能", "行動端較弱"],
        url="https://www.onlyoffice.com/zh/desktop.aspx",
        free=True,
        reason="",
    ),
    "libreoffice": Alternative(
        name="LibreOffice",
        tagline="100% 開源自由，隱私最安全",
        score=0, icon="🦎",
        pros=["完全免費、無廣告、無內購", "開源社群維護，不上傳任何數據", "六大組件齊全"],
        cons=["介面較傳統（像 Office 2003）", "複雜排版偶爾走位"],
        url="https://zh-cn.libreoffice.org/download/",
        free=True,
        reason="",
    ),
    "yozo": Alternative(
        name="永中 Office",
        tagline="中國自主研發，政企首選",
        score=0, icon="🏛️",
        pros=["支援 OFD 公文格式", "無廣告、無彈窗", "低配置電腦也能順跑"],
        cons=["介面較老派", "社群資源較少"],
        url="https://www.yozosoft.com/",
        free=True,
        reason="",
    ),
    "feishu": Alternative(
        name="飛書文檔",
        tagline="協作體驗最好，介面最美",
        score=0, icon="🐦",
        pros=["介面設計一流", "多人協作絲滑流暢", "AI 助手整合好"],
        cons=["不適合離線使用", "表格功能不如桌面版強", "需註冊飛書帳號"],
        url="https://www.feishu.cn/product/docs",
        free=True,
        reason="",
    ),
    "tencent": Alternative(
        name="騰訊文檔",
        tagline="微信生態原生，分享最方便",
        score=0, icon="💬",
        pros=["微信/QQ 直接打開", "無需安裝", "收集表功能好用"],
        cons=["離線功能弱", "大檔案容易卡"],
        url="https://docs.qq.com/",
        free=True,
        reason="",
    ),
}


# ── 相容性檢查 ───────────────────────────────

@dataclass
class CompatibilityReport:
    total_docs: int
    standard_count: int       # 標準格式（換什麼軟體都能開）
    wps_private_count: int    # WPS 私有格式（只有 WPS 能開）
    can_leave: bool           # 能不能直接離開 WPS
    warnings: List[str] = field(default_factory=list)
    doc_profile: dict = field(default_factory=dict)  # {"文件": 100, "表格": 50, ...}


def analyze_compatibility(inventory: InventoryResult) -> CompatibilityReport:
    """分析文檔相容性：能不能安全離開 WPS"""
    grouped = get_docs_by_category(inventory)

    profile = {}
    for cat, docs in grouped.items():
        profile[cat] = len(docs)

    warnings = []
    if inventory.wps_only_count > 0:
        wps_docs = [d for d in inventory.documents if d.is_wps_format]
        wps_types = set(d.extension for d in wps_docs)
        warnings.append(
            f"⚠️ 你有 {inventory.wps_only_count} 個 WPS 私有格式檔案"
            f"（{', '.join(wps_types)}），這些只有 WPS 能打開。"
            f"建議用 WPS 打開後「另存新檔」為標準格式（.docx/.xlsx/.pptx）"
        )

    can_leave = inventory.wps_only_count == 0

    return CompatibilityReport(
        total_docs=inventory.total_count,
        standard_count=inventory.standard_count,
        wps_private_count=inventory.wps_only_count,
        can_leave=can_leave,
        warnings=warnings,
        doc_profile=profile,
    )


# ── 推薦引擎 ─────────────────────────────────

def recommend_alternatives(
    inventory: InventoryResult,
) -> List[Alternative]:
    """
    根據用戶文檔使用習慣，推薦排序後的替代品列表
    """

    grouped = get_docs_by_category(inventory)
    doc_count = len(grouped.get("文件", []))
    sheet_count = len(grouped.get("表格", []))
    slide_count = len(grouped.get("簡報", []))
    total = inventory.total_count or 1

    results = []

    # ── OnlyOffice — 最全面的桌面替代品 ──
    oo = ALTERNATIVES["onlyoffice"]
    # 表格多 → 加分（OnlyOffice 的 Excel 相容性最好）
    sheet_ratio = sheet_count / total
    oo_score = 70 + int(sheet_ratio * 25)
    if inventory.wps_only_count == 0:
        oo_score += 5
    oo_score = min(100, oo_score)
    oo.score = oo_score
    oo.reason = (
        f"你的文檔 {int(sheet_ratio*100)}% 是表格，OnlyOffice 的 Excel 相容性是替代品中最強的"
        if sheet_ratio > 0.3
        else "格式相容性最全面，適合大多數從 WPS 轉移的用戶"
    )
    results.append(oo)

    # ── LibreOffice — 隱私優先 ──
    lo = ALTERNATIVES["libreoffice"]
    lo_score = 65
    if doc_count > sheet_count:
        lo_score += 10  # 文件多 → LibreOffice Writer 強項
    if inventory.wps_only_count == 0:
        lo_score += 5
    lo_score = min(100, lo_score)
    lo.score = lo_score
    lo.reason = (
        "你的文檔以文件為主，LibreOffice Writer 功能強大且完全免費"
        if doc_count > sheet_count
        else "如果你在意隱私、不想被任何廠商綁定，這是最佳選擇"
    )
    results.append(lo)

    # ── 永中 Office — 中國本土 ──
    yz = ALTERNATIVES["yozo"]
    yz.score = 60
    yz.reason = "如果你需要處理 OFD 公文格式（政府/事業單位），永中是唯一選擇"
    results.append(yz)

    # ── 飛書文檔 — 協作場景 ──
    fs = ALTERNATIVES["feishu"]
    fs_score = 55
    if slide_count / total > 0.1:
        fs_score += 15  # 簡報多 → 飛書文檔協作強
    fs.score = min(100, fs_score)
    fs.reason = (
        "你的簡報較多，飛書文檔的協作簡報體驗是業界最好的"
        if slide_count / total > 0.1
        else "如果團隊協作是主要場景，飛書文檔的體驗領先"
    )
    results.append(fs)

    # ── 騰訊文檔 — 微信生態 ──
    tc = ALTERNATIVES["tencent"]
    tc.score = 55
    tc.reason = "如果你常在微信接收和分享文檔，騰訊文檔最方便"
    results.append(tc)

    # 按分數排序
    results.sort(key=lambda r: r.score, reverse=True)

    return results


# ── 逃離路線圖 ───────────────────────────────

@dataclass
class EscapePlan:
    ready: bool
    summary: str
    steps: List[str]
    top_alternative: Alternative


def make_escape_plan(
    inventory: InventoryResult,
) -> EscapePlan:
    """生成逃離 WPS 的個人化行動計畫"""

    compat = analyze_compatibility(inventory)
    alts = recommend_alternatives(inventory)
    top = alts[0]

    steps = []

    # 第 1 步：清理垃圾
    steps.append("🧹 清理 WPS 垃圾緩存，釋放磁碟空間")

    # 第 2 步：處理私有格式
    if not compat.can_leave:
        steps.append(
            f"🔓 用 WPS 打開 {compat.wps_private_count} 個私有格式檔案 → "
            f"另存為標準格式（.docx/.xlsx/.pptx）"
        )
    else:
        steps.append("✅ 你的檔案全部是標準格式，無需轉換")

    # 第 3 步：安裝替代品
    steps.append(f"📥 下載安裝 {top.name}：{top.url}")

    # 第 4 步：設為預設
    steps.append(
        f"⚙️ 把 .docx/.xlsx/.pptx 的預設開啟程式從 WPS 改為 {top.name}"
    )

    # 第 5 步：卸載（可選）
    steps.append("🗑️ 確認一切正常後，卸載 WPS")

    if compat.can_leave:
        summary = f"🎉 好消息！你的 {compat.total_docs} 個文檔全部是標準格式，可以直接離開 WPS。推薦安裝 {top.name} 作為替代品。"
    else:
        summary = (
            f"⚠️ 你有 {compat.wps_private_count} 個 WPS 私有格式檔案需要先轉換，"
            f"其他 {compat.standard_count} 個檔案隨時可以搬走。"
        )

    return EscapePlan(
        ready=compat.can_leave,
        summary=summary,
        steps=steps,
        top_alternative=top,
    )


# ── CLI 測試 ──────────────────────────────────

if __name__ == "__main__":
    from engine.inventory import scan_documents

    print("📋 分析文檔相容性...\n")
    docs = scan_documents()

    compat = analyze_compatibility(docs)
    print(f"  總文檔：{compat.total_docs}")
    print(f"  標準格式：{compat.standard_count}")
    print(f"  WPS 私有格式：{compat.wps_private_count}")
    print(f"  能否直接離開：{'✅ 可以' if compat.can_leave else '⚠️ 需先轉換'}")
    if compat.warnings:
        for w in compat.warnings:
            print(f"  {w}")

    print(f"\n  文檔分布：")
    for cat, count in compat.doc_profile.items():
        bar = "█" * (count // max(compat.total_docs // 20, 1))
        print(f"  {cat}: {count} {bar}")

    print(f"\n🔮 推薦替代品：\n")
    alts = recommend_alternatives(docs)
    for i, alt in enumerate(alts):
        star = "⭐" if i == 0 else "  "
        print(f"  {star} {alt.icon} {alt.name} — 適合度 {alt.score}%")
        print(f"     {alt.tagline}")
        print(f"     {alt.reason}")

    plan = make_escape_plan(docs)
    print(f"\n🚀 逃離路線圖：\n")
    print(f"  {plan.summary}\n")
    for step in plan.steps:
        print(f"  {step}")
