"""
WPS D-tox — 体检报告卡片
风格：医院化验单 — 干净、清晰、像真的
"""

import os
import sys
import random
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

from engine.scanner import ScanResult, _format_size
from engine.inventory import InventoryResult
from engine.toxicity import ToxicityScore, calculate_toxicity


# ── 字体 ─────────────────────────────────────

def _find_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = []
    if sys.platform == "darwin":
        candidates = [
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
        ]
    elif sys.platform == "win32":
        candidates = [
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/msyh.ttc",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── 诊断 ─────────────────────────────────────

from dataclasses import dataclass

@dataclass
class Diagnosis:
    name: str
    emoji: str
    detail: str
    level: int


def _diagnose(score: ToxicityScore) -> Diagnosis:
    junk_gb = score.junk_size_bytes / (1024 ** 3)
    private_n = score.private_format_count
    zombie_ratio = score.zombie_doc_count / max(score.total_doc_count, 1)
    footprint_gb = (score.junk_size_bytes + score.total_doc_size_bytes) / (1024 ** 3)

    severe = sum([junk_gb > 1, private_n > 5, zombie_ratio > 0.5])

    if severe >= 2:
        return Diagnosis("WPS 重度依赖症（晚期）", "🏥",
                         "建议立即办理出院，转入替代软件观察病房", 4)
    if junk_gb > 1:
        return Diagnosis("C 盘脂肪肝（中度）", "🫁",
                         f"WPS 已沉积 {_format_size(score.junk_size_bytes)} 脂肪组织", 3)
    if private_n > 5:
        return Diagnosis("格式依赖综合征", "💊",
                         f"{private_n} 个文件需长期服用 WPS 才能打开，停药风险极高", 3)
    if zombie_ratio > 0.5:
        return Diagnosis("文档代谢异常", "🧬",
                         "大部分文档超过一年没有新陈代谢，堆积在硬盘持续占用空间", 2)
    if footprint_gb > 2:
        return Diagnosis("轻度空间水肿", "💧",
                         f"WPS 相关文件占用 {_format_size(int(footprint_gb * 1024**3))}，超出正常范围", 1)
    return Diagnosis("暂时健康", "✅", "各项指标在正常范围内，建议定期复查", 0)


def _build_test_items(score: ToxicityScore) -> list:
    items = []

    junk_mb = score.junk_size_bytes / (1024 ** 2)
    junk_flag = "↑" if junk_mb > 200 else ("⚠" if junk_mb > 50 else "✔")
    items.append(("WPS 垃圾沉积量", _format_size(score.junk_size_bytes),
                  "< 50 MB", junk_flag, junk_mb > 50))

    private_n = score.private_format_count
    private_flag = "↑" if private_n > 5 else ("⚠" if private_n > 0 else "✔")
    items.append(("私有格式依赖度", f"{private_n} 个", "0 个",
                  private_flag, private_n > 0))

    if score.total_doc_count > 0:
        zombie_pct = int(score.zombie_doc_count / score.total_doc_count * 100)
    else:
        zombie_pct = 0
    zombie_flag = "↑" if zombie_pct > 50 else ("⚠" if zombie_pct > 30 else "✔")
    items.append(("文档新陈代谢率", f"{zombie_pct}% 僵尸", "< 30%",
                  zombie_flag, zombie_pct > 30))

    total_gb = (score.junk_size_bytes + score.total_doc_size_bytes) / (1024 ** 3)
    total_flag = "↑" if total_gb > 5 else ("⚠" if total_gb > 1 else "✔")
    items.append(("WPS 总体占用", _format_size(score.junk_size_bytes + score.total_doc_size_bytes),
                  "< 1 GB", total_flag, total_gb > 1))

    doc_flag = "↑" if score.total_doc_count > 500 else "✔"
    items.append(("文档总数", f"{score.total_doc_count} 个", "< 500 个",
                  doc_flag, score.total_doc_count > 500))

    score_flag = "↓" if score.total < 50 else ("⚠" if score.total < 75 else "✔")
    items.append(("电脑健康指数", f"{score.total}/100", "> 75",
                  score_flag, score.total < 75))

    return items


# ── 主图片生成 ──────────────────────────────

MARGIN = 80
W, H = 1080, 2200


def generate_victim_card(score: ToxicityScore) -> Image.Image:

    identity = _diagnose(score)
    items = _build_test_items(score)

    # 底色：干干净净的淡黄纸
    bg = "#FDFBF7"
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # ── 颜色 ──
    RED = "#C62828"
    DARK = "#1a1a1a"
    GRAY = "#777777"
    LIGHT_GRAY = "#aaaaaa"
    LINE = "#e0dcd5"

    def text(x, y, s, size=24, color=DARK, anchor="lt"):
        font = _find_font(size)
        draw.text((x, y), s, fill=color, font=font, anchor=anchor)

    def text_center(y, s, size=24, color=DARK):
        font = _find_font(size)
        bbox = draw.textbbox((0, 0), s, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, y), s, fill=color, font=font)

    def hline(y, color=LINE):
        draw.line([(MARGIN, y), (W - MARGIN, y)], fill=color, width=1)

    def section_title(y, title):
        text(MARGIN, y, title, size=34, color=RED)
        hline(y + 44, RED)

    # ═══════════════════════════════════════════
    # 页眉：红头
    # ═══════════════════════════════════════════
    header_h = 220
    draw.rectangle([0, 0, W, header_h], fill=RED)

    text_center(40, "WPS 生态系统附属电脑医院", size=30, color="white")
    text_center(96, "员 工 入 职 体 检 报 告", size=56, color="white")

    report_id = f"报告编号：WPS-TJ-{datetime.now().strftime('%Y%m%d')}{random.randint(100,999)}"
    report_date = f"体检日期：{datetime.now().strftime('%Y年%m月%d日')}"
    text_center(168, f"{report_id}    |    {report_date}", size=22, color="#ffcdd2")

    # ═══════════════════════════════════════════
    # 基本信息
    # ═══════════════════════════════════════════
    y = header_h + 60
    hostname = os.uname().nodename if hasattr(os, 'uname') else "本地电脑"
    line1 = f"受检电脑：{hostname}　　操作系统：{sys.platform}"
    line2 = "检测工具：WPS 解毒器 D-tox v1.0"
    text_center(y, line1, size=24, color=GRAY)
    text_center(y + 34, line2, size=24, color=GRAY)
    hline(y + 76, LINE)

    # ═══════════════════════════════════════════
    # 化验项目表
    # ═══════════════════════════════════════════
    y += 65
    section_title(y, "化验项目")
    y += 68

    # 表头
    cx = [MARGIN + 10, 380, 570, 740, 880]
    headers = ["检验项目", "实测值", "参考范围", "判定", "说明"]
    for i, h in enumerate(headers):
        text(cx[i], y, h, size=24, color=GRAY)

    y += 14
    hline(y, LINE)
    y += 20

    # 表行
    for name, value, ref, flag, abnormal in items:
        row_h = 72
        idx = items.index((name, value, ref, flag, abnormal))
        if idx % 2 == 0:
            draw.rectangle([MARGIN, y - 4, W - MARGIN, y + row_h - 6], fill="#F5F2EC")

        flag_color = RED if flag in ("↑", "↓") else ("#E67E22" if flag == "⚠" else "#2E7D32")
        desc = _flag_desc(flag, name)
        text(cx[0], y + 6, name, size=28, color=DARK)
        text(cx[1], y + 6, value, size=28, color="#333")
        text(cx[2], y + 6, ref, size=24, color=GRAY)
        text(cx[3], y + 6, flag, size=34, color=flag_color)
        text(cx[4], y + 6, desc, size=22, color=LIGHT_GRAY)
        y += row_h

    y += 14
    hline(y, LINE)

    # ═══════════════════════════════════════════
    # 诊断结论
    # ═══════════════════════════════════════════
    y += 55
    section_title(y, "体检结论")
    y += 70

    # 诊断框
    box_h = 180
    draw.rounded_rectangle(
        [MARGIN, y, W - MARGIN, y + box_h],
        radius=10, outline=RED, width=4, fill="#FFF8F8"
    )
    draw.rectangle([MARGIN + 6, y + 28, MARGIN + 14, y + box_h - 28], fill=RED)

    text(MARGIN + 44, y + 28, f"{identity.emoji}  {identity.name}", size=42, color=RED)
    text(MARGIN + 44, y + 82, identity.detail, size=28, color="#555")
    text(MARGIN + 44, y + 128, f"综合健康指数：{score.total}/100 分", size=24, color=GRAY)
    y += box_h + 45

    # ═══════════════════════════════════════════
    # 医嘱
    # ═══════════════════════════════════════════
    section_title(y, "医嘱")
    y += 68

    advices = []
    n = 1
    if score.junk_size_bytes > 10 * 1024 * 1024:
        advices.append(f"{n}. 立即清理 {_format_size(score.junk_size_bytes)} WPS 垃圾缓存，恢复电脑正常机能"); n += 1
    if score.private_format_count > 0:
        advices.append(f"{n}. 尽快将 {score.private_format_count} 个 WPS 私有格式转为标准格式，避免文件永久依赖 WPS"); n += 1
    if score.zombie_doc_count > 0 and score.zombie_doc_count / max(score.total_doc_count, 1) > 0.3:
        advices.append(f"{n}. 整理 {score.zombie_doc_count} 个僵尸文档，删除无用、备份重要文件"); n += 1
    advices.append(f"{n}. 考虑迁移至开源办公软件（OnlyOffice / LibreOffice），降低对 WPS 的依赖"); n += 1
    advices.append(f"{n}. 每 3 个月复查一次，监测 WPS 对电脑的影响")

    for advice in advices:
        text(MARGIN + 10, y, advice, size=26, color="#333")
        y += 52

    # ═══════════════════════════════════════════
    # 底部
    # ═══════════════════════════════════════════
    y += 60
    hline(y, LINE)
    y += 40

    text_center(y, "本报告由 WPS 解毒器自动生成  ·  数据仅储存在你的电脑上", size=20, color=LIGHT_GRAY)
    y += 40
    text_center(y, "🧪 WPS 解毒器  D-tox  ·  你也来测 👇", size=28, color=GRAY)

    # 红章（右下角）
    stamp_x, stamp_y = W - 180, y - 10
    draw.ellipse([stamp_x - 60, stamp_y - 60, stamp_x + 60, stamp_y + 60],
                 outline=RED, width=5)
    text(stamp_x, stamp_y - 10, "已体检", size=28, color=RED, anchor="mm")
    text(stamp_x, stamp_y + 24, "WPS-DT", size=16, color=RED, anchor="mm")

    return img


def _flag_desc(flag: str, item_name: str) -> str:
    """给判定符号配一句简短说明"""
    mapping = {
        "WPS 垃圾沉积量": {
            "↑": "垃圾堆积过多",
            "⚠": "略超正常值",
            "✔": "暂无垃圾",
        },
        "私有格式依赖度": {
            "↑": "文件被锁定",
            "⚠": "建议关注",
            "✔": "无锁定文件",
        },
        "文档新陈代谢率": {
            "↑": "僵尸文件过多",
            "⚠": "部分文件陈旧",
            "✔": "代谢正常",
        },
    }
    if item_name in mapping and flag in mapping[item_name]:
        return mapping[item_name][flag]
    return {"↑": "偏高", "⚠": "临界", "✔": "正常", "↓": "偏低"}.get(flag, "")


def save_victim_card(score: ToxicityScore, output_path: str = None) -> str:
    identity = _diagnose(score)
    img = generate_victim_card(score)

    if output_path is None:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        slug = identity.name.replace(" ", "-").replace("（", "-").replace("）", "")
        output_path = os.path.join(
            desktop,
            f"wps-体检报告-{slug}-{datetime.now().strftime('%m%d')}.png",
        )

    img.save(output_path, "PNG")
    return output_path


if __name__ == "__main__":
    from engine.scanner import scan_junk
    from engine.inventory import scan_documents

    print("🏥 正在进行 WPS 入职体检...\n")
    junk = scan_junk()
    docs = scan_documents()
    score = calculate_toxicity(junk, docs)
    identity = _diagnose(score)

    print(f"  诊断：{identity.emoji} {identity.name}")
    print(f"  说明：{identity.detail}\n")

    path = save_victim_card(score)
    print(f"📸 体检报告已保存：{path}")
