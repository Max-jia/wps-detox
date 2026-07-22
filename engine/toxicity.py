"""
WPS D-tox — 毒性分數引擎
結合掃描結果 + 文檔盤點，算出 WPS 對你電腦的「毒性指數」
"""

import os
import json
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from engine.scanner import ScanResult, _format_size
from engine.inventory import InventoryResult


@dataclass
class ToxicityScore:
    """WPS 毒性評分"""
    total: int              # 0-100，越低越毒

    # 四個維度
    junk_score: int         # 垃圾堆積 (0-40)
    lockin_score: int       # 格式綁架 (0-30)
    zombie_score: int       # 殭屍文檔 (0-20)
    clutter_score: int      # 空間侵略 (0-10)

    # 原始數據
    junk_size_bytes: int = 0
    private_format_count: int = 0
    zombie_doc_count: int = 0
    zombie_doc_size_bytes: int = 0
    total_doc_count: int = 0
    total_doc_size_bytes: int = 0

    # 診斷訊息
    level: str = ""          # "healthy" | "warning" | "danger" | "critical"
    level_emoji: str = ""
    level_label: str = ""
    level_color: str = ""    # hex color
    one_liner: str = ""      # 一句話診斷
    tips: list = field(default_factory=list)


def calculate_toxicity(
    junk: Optional[ScanResult] = None,
    inventory: Optional[InventoryResult] = None,
) -> ToxicityScore:
    """
    根據掃描和盤點結果，算出 WPS 毒性分數

    分數越低 = WPS 對你的電腦越毒
    """

    # ── 維度 1：垃圾堆積 (0-40 分) ──
    junk_size = junk.total_junk_size if junk else 0

    if junk_size == 0:
        junk_score = 40
    elif junk_size < 50 * 1024 * 1024:    # < 50 MB
        junk_score = 35
    elif junk_size < 200 * 1024 * 1024:   # < 200 MB
        junk_score = 25
    elif junk_size < 500 * 1024 * 1024:   # < 500 MB
        junk_score = 15
    elif junk_size < 2 * 1024 * 1024 * 1024:  # < 2 GB
        junk_score = 8
    else:                                    # ≥ 2 GB
        junk_score = 0

    # ── 維度 2：格式綁架 (0-30 分) ──
    private_count = inventory.wps_only_count if inventory else 0

    if private_count == 0:
        lockin_score = 30
    elif private_count <= 3:
        lockin_score = 22
    elif private_count <= 10:
        lockin_score = 14
    elif private_count <= 30:
        lockin_score = 7
    else:
        lockin_score = 0

    # ── 維度 3：殭屍文檔 (0-20 分) ──
    # 超過一年沒動過的文檔佔比
    if inventory and inventory.total_count > 0:
        from engine.inventory import get_old_docs
        old_docs = get_old_docs(inventory, days=365)
        zombie_ratio = len(old_docs) / inventory.total_count
        zombie_count = len(old_docs)
        zombie_size = sum(d.size for d in old_docs)
    else:
        zombie_ratio = 0
        zombie_count = 0
        zombie_size = 0

    if zombie_ratio < 0.1:
        zombie_score = 20
    elif zombie_ratio < 0.3:
        zombie_score = 15
    elif zombie_ratio < 0.5:
        zombie_score = 10
    elif zombie_ratio < 0.7:
        zombie_score = 5
    else:
        zombie_score = 0

    # ── 維度 4：空間侵略 (0-10 分) ──
    total_footprint = junk_size + (inventory.total_size if inventory else 0)

    if total_footprint < 100 * 1024 * 1024:     # < 100 MB
        clutter_score = 10
    elif total_footprint < 500 * 1024 * 1024:   # < 500 MB
        clutter_score = 8
    elif total_footprint < 2 * 1024 * 1024 * 1024:  # < 2 GB
        clutter_score = 5
    elif total_footprint < 10 * 1024 * 1024 * 1024: # < 10 GB
        clutter_score = 2
    else:
        clutter_score = 0

    # ── 總分 ──
    total = junk_score + lockin_score + zombie_score + clutter_score

    # ── 診斷 ──
    level, emoji, label, color, one_liner, tips = _diagnose(
        total, junk_score, lockin_score, zombie_score, clutter_score,
        junk_size, private_count, zombie_count, zombie_size
    )

    return ToxicityScore(
        total=total,
        junk_score=junk_score,
        lockin_score=lockin_score,
        zombie_score=zombie_score,
        clutter_score=clutter_score,
        junk_size_bytes=junk_size,
        private_format_count=private_count,
        zombie_doc_count=zombie_count,
        zombie_doc_size_bytes=zombie_size,
        total_doc_count=inventory.total_count if inventory else 0,
        total_doc_size_bytes=inventory.total_size if inventory else 0,
        level=level,
        level_emoji=emoji,
        level_label=label,
        level_color=color,
        one_liner=one_liner,
        tips=tips,
    )


def _diagnose(total, junk_s, lockin_s, zombie_s, clutter_s,
              junk_bytes, private_n, zombie_n, zombie_bytes):
    """根據分數產生一句話診斷和建議"""

    # 找最差的維度（扣分最多的）
    dims = [
        ("垃圾堆積", junk_s, 40),
        ("格式綁架", lockin_s, 30),
        ("殭屍文檔", zombie_s, 20),
        ("空間侵略", clutter_s, 10),
    ]
    dims.sort(key=lambda d: d[1] / d[2])  # 按得分率排序，最差的在前
    worst_dim = dims[0]

    if total >= 80:
        level, emoji, label, color = "healthy", "🟢", "健康", "#4CAF50"
        one_liner = "WPS 對你的電腦影響不大，繼續保持 👏"
        tips = ["目前沒有需要處理的問題"]
    elif total >= 50:
        level, emoji, label, color = "warning", "🟡", "注意", "#FF9800"
        tips = []
        if worst_dim[0] == "垃圾堆積":
            one_liner = f"WPS 默默堆了 {_format_size(junk_bytes)} 垃圾，該清一清了"
            tips.append("用本工具的「一鍵清理」秒解決")
        elif worst_dim[0] == "格式綁架":
            one_liner = f"有 {private_n} 個檔案被 WPS 私有格式鎖住"
            tips.append("建議盡快轉成標準格式（.docx/.xlsx），避免以後打不開")
        elif worst_dim[0] == "殭屍文檔":
            one_liner = f"{zombie_n} 個文檔已超過一年沒動，像雜物堆在角落"
            tips.append("可以整理想法：刪掉不要的、備份重要的")
        else:
            one_liner = "WPS 開始佔用不少空間了"
            tips.append("清理垃圾 + 整理文檔，一次搞定")
    elif total >= 20:
        level, emoji, label, color = "danger", "🟠", "警告", "#F44336"
        tips = []
        if worst_dim[0] == "垃圾堆積":
            one_liner = f"WPS 在你電腦裡堆了 {_format_size(junk_bytes)} 垃圾！"
            tips.append("馬上清理，C 盤/系統碟可能快爆了")
        elif worst_dim[0] == "格式綁架":
            one_liner = f"{private_n} 個檔案被 WPS 鎖住，你正在被綁架"
            tips.append("每多一個 .wps 檔案，你就越難離開 WPS")
            tips.append("立刻開始轉換格式，拿回檔案所有權")
        elif worst_dim[0] == "殭屍文檔":
            one_liner = f"你有 {zombie_n} 個殭屍文檔，佔了 {_format_size(zombie_bytes)}"
            tips.append("這些文檔你可能永遠不會再打開了")
            tips.append("清理殭屍 = 釋放空間 + 思緒更清楚")
        else:
            one_liner = "WPS 正在系統性地侵蝕你的電腦空間"
            tips.append("你需要採取行動了——清理 + 搬家")
    else:
        level, emoji, label, color = "critical", "🔴", "危險", "#D32F2F"
        one_liner = f"你的電腦正在被 WPS 綁架！健康度只剩 {total}/100"
        tips = [
            "立刻清理垃圾——這是最快能做的事",
            "轉換所有 .wps/.et/.dps 私有格式",
            "認真考慮換掉 WPS，你的檔案不該被一個軟體鎖住",
        ]

    return level, emoji, label, color, one_liner, tips


# ── 分享卡片 ────────────────────────────────────────

def generate_share_card(score: ToxicityScore) -> str:
    """
    生成一個可分享的 HTML 卡片
    回傳 HTML 字串，用戶可以截圖分享到社群
    """
    # 計算各維度的滿分
    dims = [
        ("🗑️ 垃圾堆積", score.junk_score, 40, _format_size(score.junk_size_bytes)),
        ("🔒 格式綁架", score.lockin_score, 30, f"{score.private_format_count} 個私有格式"),
        ("🧟 殭屍文檔", score.zombie_score, 20, f"{score.zombie_doc_count} 個"),
        ("📦 空間侵略", score.clutter_score, 10,
         _format_size(score.junk_size_bytes + score.total_doc_size_bytes)),
    ]

    dims_html = ""
    for label, score_val, max_val, detail in dims:
        pct = score_val / max_val
        bar_color = "#4CAF50" if pct > 0.7 else ("#FF9800" if pct > 0.4 else "#F44336")
        dims_html += f"""
        <div class="dim">
            <div class="dim-header">
                <span class="dim-label">{label}</span>
                <span class="dim-score">{score_val}/{max_val}</span>
            </div>
            <div class="dim-bar-bg">
                <div class="dim-bar" style="width:{pct*100}%;background:{bar_color}"></div>
            </div>
            <div class="dim-detail">{detail}</div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WPS 解毒器 - 我的 WPS 健康報告</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #1a1a2e;
    display: flex; justify-content: center; align-items: center;
    min-height: 100vh; padding: 20px;
}}
.card {{
    background: linear-gradient(135deg, #16213e 0%, #1a1a2e 100%);
    border: 1px solid #2a2a4a;
    border-radius: 20px;
    padding: 36px 32px;
    max-width: 440px;
    width: 100%;
    box-shadow: 0 20px 60px rgba(0,0,0,0.4);
}}
.header {{
    display: flex; align-items: center; gap: 12px;
    margin-bottom: 24px;
}}
.header .icon {{ font-size: 32px; }}
.header .title {{ color: #fff; font-size: 20px; font-weight: 700; }}
.header .subtitle {{ color: #888; font-size: 12px; margin-top: 2px; }}
.score-circle {{
    width: 120px; height: 120px;
    border-radius: 50%;
    background: conic-gradient({score.level_color} {score.total}%, #2a2a4a {score.total}%);
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    margin: 0 auto 12px;
    position: relative;
}}
.score-circle::before {{
    content: '';
    width: 96px; height: 96px;
    border-radius: 50%;
    background: #16213e;
    position: absolute;
}}
.score-num {{
    color: #fff; font-size: 36px; font-weight: 800;
    position: relative; z-index: 1;
}}
.score-label {{
    color: {score.level_color}; font-size: 12px; font-weight: 600;
    position: relative; z-index: 1;
}}
.one-liner {{
    text-align: center; color: #ccc; font-size: 15px;
    margin-bottom: 24px; line-height: 1.5;
}}
.dims {{ margin-bottom: 20px; }}
.dim {{
    background: rgba(255,255,255,0.03);
    border-radius: 10px; padding: 12px 14px;
    margin-bottom: 8px;
}}
.dim-header {{
    display: flex; justify-content: space-between;
    margin-bottom: 6px;
}}
.dim-label {{ color: #aaa; font-size: 13px; }}
.dim-score {{ color: #fff; font-size: 13px; font-weight: 600; }}
.dim-bar-bg {{
    height: 4px; background: #2a2a4a;
    border-radius: 2px; overflow: hidden; margin-bottom: 4px;
}}
.dim-bar {{ height: 100%; border-radius: 2px; transition: width 0.6s; }}
.dim-detail {{ color: #666; font-size: 11px; }}
.footer {{
    display: flex; justify-content: space-between;
    align-items: center; padding-top: 16px;
    border-top: 1px solid #2a2a4a;
}}
.footer-brand {{ color: #666; font-size: 12px; }}
.footer-cta {{ color: {score.level_color}; font-size: 12px; font-weight: 600; }}
</style>
</head>
<body>
<div class="card">
    <div class="header">
        <span class="icon">🧪</span>
        <div>
            <div class="title">WPS 解毒器</div>
            <div class="subtitle">我的 WPS 健康報告 · {datetime.now().strftime("%Y.%m.%d")}</div>
        </div>
    </div>

    <div class="score-circle">
        <div class="score-num">{score.total}</div>
        <div class="score-label">{score.level_label}</div>
    </div>

    <div class="one-liner">{score.one_liner}</div>

    <div class="dims">{dims_html}</div>

    <div class="footer">
        <span class="footer-brand">🧪 WPS 解毒器 D-tox</span>
        <span class="footer-cta">你也來測 →</span>
    </div>
</div>
</body>
</html>"""

    return html


def save_share_card(score: ToxicityScore, output_path: str = None) -> str:
    """
    儲存分享卡片為 HTML 檔案
    回傳檔案路徑
    """
    if output_path is None:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        output_path = os.path.join(desktop, "wps-health-report.html")

    html = generate_share_card(score)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


def print_toxicity(score: ToxicityScore):
    """在終端機漂亮地印出毒性報告"""
    print("\n" + "=" * 60)
    print(f"  🧪 WPS 健康度報告")
    print("=" * 60)

    bar_len = 30
    filled = int(score.total / 100 * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\n  {score.level_emoji} 健康度：{score.total}/100  {score.level_label}")
    print(f"  [{bar}]")
    print(f"\n  📝 {score.one_liner}")

    print(f"\n  各維度分析：")
    dims = [
        ("🗑️ 垃圾堆積", score.junk_score, 40),
        ("🔒 格式綁架", score.lockin_score, 30),
        ("🧟 殭屍文檔", score.zombie_score, 20),
        ("📦 空間侵略", score.clutter_score, 10),
    ]
    for label, val, max_val in dims:
        bar_filled = int(val / max_val * 20)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        print(f"  {label:12s} [{bar}] {val}/{max_val}")

    if score.tips:
        print(f"\n  💡 建議：")
        for tip in score.tips:
            print(f"     • {tip}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    from engine.scanner import scan_junk
    from engine.inventory import scan_documents

    print("正在分析你的 WPS 健康度...")
    junk = scan_junk()
    docs = scan_documents()
    score = calculate_toxicity(junk, docs)
    print_toxicity(score)

    # 生成分享卡片
    path = save_share_card(score)
    print(f"📸 分享卡片已儲存：{path}")
