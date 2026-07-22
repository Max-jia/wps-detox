"""
WPS D-tox — 圖形介面 (GUI)
使用 customtkinter，Modern 風格
支援：Windows / macOS
"""

import sys
import os
import threading
import webbrowser
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import customtkinter as ctk
except ImportError:
    print("請先安裝 customtkinter：pip install customtkinter")
    sys.exit(1)

from engine.scanner import scan_junk, _format_size, get_platform_name
from engine.cleaner import clean_junk_groups
from engine.inventory import scan_documents, get_docs_by_category, get_large_docs
from engine.toxicity import calculate_toxicity
from engine.victim_card import save_victim_card
from engine.recommend import analyze_compatibility, recommend_alternatives, make_escape_plan


# ── 主題 ──────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

WINDOW_WIDTH = 920
WINDOW_HEIGHT = 680


class WPSDetoxApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("WPS 解毒器 D-tox")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(820, 580)

        self.junk_result = None
        self.inventory_result = None
        self.toxicity_score = None

        self._build_header()
        self._build_tabs()

    # ── 頂部 ──────────────────────────────────
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 0))

        ctk.CTkLabel(
            header,
            text=f"🧪 WPS 解毒器 · {get_platform_name()}",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text="掃描 → 清理 → 盤點 → 搬家，幫你逃離 WPS",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).pack(anchor="w", pady=(2, 0))

    # ── 分頁 ──────────────────────────────────
    def _build_tabs(self):
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=24, pady=16)

        self.tab_health = self.tabview.add("🧪 健康报告")
        self.tab_scan = self.tabview.add("🔍 扫描清理")
        self.tab_escape = self.tabview.add("🚀 逃离WPS")
        self.tab_inventory = self.tabview.add("📋 文档盘点")
        self.tab_about = self.tabview.add("ℹ️ 关于")

        self._build_health_tab()
        self._build_scan_tab()
        self._build_escape_tab()
        self._build_inventory_tab()
        self._build_about_tab()

    # ═══════════════════════════════════════════
    # 🧪 健康報告頁（首頁）
    # ═══════════════════════════════════════════
    def _build_health_tab(self):
        # 上方按鈕
        btn_frame = ctk.CTkFrame(self.tab_health, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(16, 8))

        self.btn_health = ctk.CTkButton(
            btn_frame,
            text="🔬 開始分析",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=44,
            command=self._start_health_analysis,
        )
        self.btn_health.pack(side="left", padx=(0, 8))

        self.btn_share = ctk.CTkButton(
            btn_frame,
            text="📸 分享報告",
            font=ctk.CTkFont(size=13),
            height=44,
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            state="disabled",
            command=self._share_report,
        )
        self.btn_share.pack(side="left")

        self.health_progress = ctk.CTkProgressBar(btn_frame)
        self.health_progress.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self.health_progress.set(0)

        # 結果顯示區
        self.health_frame = ctk.CTkScrollableFrame(
            self.tab_health, fg_color="transparent"
        )
        self.health_frame.pack(fill="both", expand=True)

        self.health_placeholder = ctk.CTkLabel(
            self.health_frame,
            text="按「開始分析」看看 WPS 對你電腦的毒性指數 🧪\n\n"
                 "我們會掃描垃圾 + 盤點文檔，算出一個 0-100 的健康分數\n"
                 "分數越低 = WPS 對你的電腦越毒",
            font=ctk.CTkFont(size=14),
            text_color="gray",
            justify="center",
        )
        self.health_placeholder.pack(pady=60)

    def _start_health_analysis(self):
        """背景執行：掃描 + 盤點 + 毒性分析"""
        self.btn_health.configure(state="disabled", text="⏳ 分析中...")
        self.btn_share.configure(state="disabled")
        self.health_progress.set(0.2)
        self.health_placeholder.pack_forget()

        for w in self.health_frame.winfo_children():
            w.destroy()

        def analyze():
            # 步驟 1：掃描垃圾
            self.after(0, lambda: self.health_progress.set(0.3))
            junk = scan_junk()
            self.junk_result = junk

            # 步驟 2：盤點文檔
            self.after(0, lambda: self.health_progress.set(0.6))
            docs = scan_documents()
            self.inventory_result = docs

            # 步驟 3：計算毒性
            self.after(0, lambda: self.health_progress.set(0.85))
            score = calculate_toxicity(junk, docs)
            self.toxicity_score = score

            self.after(0, lambda: self._show_health_result(score))

        threading.Thread(target=analyze, daemon=True).start()

    def _show_health_result(self, score):
        """顯示毒性報告"""
        self.btn_health.configure(state="normal", text="🔄 重新分析")
        self.btn_share.configure(state="normal")
        self.health_progress.set(1.0)

        for w in self.health_frame.winfo_children():
            w.destroy()

        # ── 圓形分數（用 Canvas 畫） ──
        score_card = ctk.CTkFrame(self.health_frame)
        score_card.pack(fill="x", pady=(0, 16))

        canvas_size = 160
        canvas = tk.Canvas(
            score_card, width=canvas_size, height=canvas_size,
            bg="#2b2b2b", highlightthickness=0,
        )
        canvas.pack(pady=(16, 8))

        # 畫圓環背景
        cx, cy, r, w = canvas_size // 2, canvas_size // 2, 65, 16
        canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                          start=90, extent=360,
                          width=w, outline="#3a3a4a",
                          style="arc")

        # 畫分數弧（從 12 點鐘方向順時針）
        extent = -score.total / 100 * 360
        canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                          start=90, extent=extent,
                          width=w, outline=score.level_color,
                          style="arc")

        # 分數數字
        canvas.create_text(cx, cy - 8, text=str(score.total),
                           fill="white", font=("Helvetica", 40, "bold"))
        canvas.create_text(cx, cy + 22, text=score.level_label,
                           fill=score.level_color, font=("Helvetica", 13, "bold"))

        # 一句話診斷
        ctk.CTkLabel(
            score_card,
            text=f"{score.level_emoji}  {score.one_liner}",
            font=ctk.CTkFont(size=14),
            text_color="#ccc",
        ).pack(pady=(0, 14))

        # ── 四個維度 ──
        dims = [
            ("🗑️ 垃圾堆積", score.junk_score, 40, _format_size(score.junk_size_bytes)),
            ("🔒 格式綁架", score.lockin_score, 30, f"{score.private_format_count} 個私有格式"),
            ("🧟 殭屍文檔", score.zombie_score, 20,
             f"{score.zombie_doc_count} 個（{_format_size(score.zombie_doc_size_bytes)}）"),
            ("📦 空間侵略", score.clutter_score, 10,
             _format_size(score.junk_size_bytes + score.total_doc_size_bytes)),
        ]

        for label, val, max_val, detail in dims:
            dim_frame = ctk.CTkFrame(self.health_frame)
            dim_frame.pack(fill="x", pady=3)

            row = ctk.CTkFrame(dim_frame, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=10)

            ctk.CTkLabel(
                row, text=label,
                font=ctk.CTkFont(size=13),
            ).pack(side="left")

            ctk.CTkLabel(
                row, text=f"{val}/{max_val}",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=score.level_color if val < max_val * 0.4 else "#aaa",
            ).pack(side="right")

            # 進度條
            bar_frame = ctk.CTkFrame(dim_frame, fg_color="#3a3a4a", height=6)
            bar_frame.pack(fill="x", padx=14, pady=(0, 4))
            bar_frame.configure(height=6)

            pct = val / max_val
            bar_color = "#4CAF50" if pct > 0.7 else ("#FF9800" if pct > 0.4 else "#F44336")
            inner = ctk.CTkFrame(bar_frame, fg_color=bar_color, height=6)
            inner.place(relx=0, rely=0, relwidth=pct, relheight=1)

            ctk.CTkLabel(
                dim_frame, text=detail,
                font=ctk.CTkFont(size=11),
                text_color="#666",
            ).pack(anchor="w", padx=14, pady=(0, 8))

        # ── 建議 ──
        if score.tips:
            tips_frame = ctk.CTkFrame(self.health_frame)
            tips_frame.pack(fill="x", pady=(8, 0))

            ctk.CTkLabel(
                tips_frame,
                text="💡 建議行動",
                font=ctk.CTkFont(size=14, weight="bold"),
            ).pack(anchor="w", padx=14, pady=(12, 4))

            for tip in score.tips:
                ctk.CTkLabel(
                    tips_frame,
                    text=f"  • {tip}",
                    font=ctk.CTkFont(size=12),
                    text_color="#aaa",
                ).pack(anchor="w", padx=14, pady=2)

            # 行動按鈕
            action_frame = ctk.CTkFrame(tips_frame, fg_color="transparent")
            action_frame.pack(fill="x", padx=14, pady=(10, 12))

            ctk.CTkButton(
                action_frame,
                text="🧹 去清理垃圾 →",
                font=ctk.CTkFont(size=12),
                command=lambda: self.tabview.set("🔍 扫描清理"),
            ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                action_frame,
                text="📋 去看文档盘点 →",
                font=ctk.CTkFont(size=12),
                fg_color="transparent",
                border_width=1,
                command=lambda: self.tabview.set("📋 文档盘点"),
            ).pack(side="left")

    def _share_report(self):
        """產生並打開受害者檔案 PNG"""
        if not self.toxicity_score:
            return

        path = save_victim_card(self.toxicity_score)
        # 用預設看圖軟體打開 PNG
        webbrowser.open("file://" + path)

        # 彈出提示
        dialog = ctk.CTkToplevel(self)
        dialog.title("受害者檔案已生成")
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="📸 受害者檔案已儲存！",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(24, 8))

        ctk.CTkLabel(
            dialog,
            text="圖片已存到桌面，用預覽程式打開了\n"
                 "直接截圖或 AirDrop 到手機 → 發朋友圈 🔥",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            justify="center",
        ).pack()

        ctk.CTkButton(
            dialog,
            text="知道了",
            command=dialog.destroy,
            width=100,
        ).pack(pady=(16, 0))

    # ═══════════════════════════════════════════
    # 🔍 扫描清理頁
    # ═══════════════════════════════════════════
    def _build_scan_tab(self):
        btn_frame = ctk.CTkFrame(self.tab_scan, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(16, 8))

        self.btn_scan = ctk.CTkButton(
            btn_frame,
            text="🔍 開始掃描",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            command=self._start_scan,
        )
        self.btn_scan.pack(side="left", padx=(0, 8))

        self.btn_clean = ctk.CTkButton(
            btn_frame,
            text="🧹 一鍵清理",
            font=ctk.CTkFont(size=14),
            height=40,
            fg_color="#C75050",
            hover_color="#A04040",
            state="disabled",
            command=self._start_clean,
        )
        self.btn_clean.pack(side="left", padx=(0, 8))

        self.progress = ctk.CTkProgressBar(btn_frame)
        self.progress.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.progress.set(0)

        self.scan_result_frame = ctk.CTkScrollableFrame(
            self.tab_scan, fg_color="transparent",
        )
        self.scan_result_frame.pack(fill="both", expand=True)

        self.scan_placeholder = ctk.CTkLabel(
            self.scan_result_frame,
            text="按「開始掃描」找出 WPS 在電腦上藏的垃圾檔案 👆",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        )
        self.scan_placeholder.pack(pady=40)

    def _start_scan(self):
        self.btn_scan.configure(state="disabled", text="⏳ 掃描中...")
        self.progress.set(0.3)
        self.scan_placeholder.pack_forget()

        for w in self.scan_result_frame.winfo_children():
            w.destroy()

        def scan_thread():
            result = scan_junk()
            self.junk_result = result
            self.after(0, lambda: self._show_scan_result(result))

        threading.Thread(target=scan_thread, daemon=True).start()

    def _show_scan_result(self, result):
        self.btn_scan.configure(state="normal", text="🔄 重新掃描")
        self.progress.set(1.0)

        for w in self.scan_result_frame.winfo_children():
            w.destroy()

        if not result.junk_groups:
            ctk.CTkLabel(
                self.scan_result_frame,
                text="✅ 沒找到任何 WPS 垃圾！你的電腦很乾淨。",
                font=ctk.CTkFont(size=16),
            ).pack(pady=20)
            return

        summary = ctk.CTkFrame(self.scan_result_frame)
        summary.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            summary,
            text=f"找到 {result.total_junk_count} 個垃圾檔案",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(12, 0))

        ctk.CTkLabel(
            summary,
            text=f"可釋放空間：{_format_size(result.total_junk_size)}",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#4CAF50",
        ).pack(anchor="w", padx=16, pady=(2, 12))

        for group in result.junk_groups:
            card = ctk.CTkFrame(self.scan_result_frame)
            card.pack(fill="x", pady=3)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(fill="x", padx=12, pady=8)

            ctk.CTkLabel(
                info,
                text=f"🗑️  {group.category}",
                font=ctk.CTkFont(size=14, weight="bold"),
            ).pack(anchor="w")

            ctk.CTkLabel(
                info,
                text=group.description,
                font=ctk.CTkFont(size=11),
                text_color="gray",
            ).pack(anchor="w")

            ctk.CTkLabel(
                info,
                text=f"{group.file_count} 個檔案 · {_format_size(group.total_size)}",
                font=ctk.CTkFont(size=12),
            ).pack(anchor="w")

        self.btn_clean.configure(state="normal")

    def _start_clean(self):
        if not self.junk_result or not self.junk_result.junk_groups:
            return

        self.btn_clean.configure(state="disabled", text="⏳ 清理中...")
        self.progress.set(0.5)

        def clean_thread():
            result = clean_junk_groups(
                self.junk_result.junk_groups,
                on_progress=lambda cur, total, f: self.after(
                    0, lambda: self.progress.set(0.5 + 0.5 * cur / max(total, 1))
                ),
            )
            self.after(0, lambda: self._show_clean_result(result))

        threading.Thread(target=clean_thread, daemon=True).start()

    def _show_clean_result(self, clean_result):
        self.btn_clean.configure(state="disabled", text="✅ 清理完成")
        self.progress.set(1.0)

        banner = ctk.CTkFrame(self.scan_result_frame, fg_color="#2E7D32")
        banner.pack(fill="x", pady=(0, 12),
                    before=self.scan_result_frame.winfo_children()[0])

        ctk.CTkLabel(
            banner,
            text=f"🎉 清理完成！釋放了 {_format_size(clean_result.total_space_freed)} 空間",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(padx=16, pady=12)

        if clean_result.failed_files:
            ctk.CTkLabel(
                self.scan_result_frame,
                text=f"⚠️ {len(clean_result.failed_files)} 個檔案刪除失敗（可能被 WPS 佔用中）",
                font=ctk.CTkFont(size=12),
                text_color="#FF9800",
            ).pack(fill="x", pady=(8, 0))

    # ═══════════════════════════════════════════
    # 🚀 逃离 WPS 页
    # ═══════════════════════════════════════════
    def _build_escape_tab(self):
        btn_frame = ctk.CTkFrame(self.tab_escape, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(16, 8))

        self.btn_escape = ctk.CTkButton(
            btn_frame,
            text="🔬 分析我的文档",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=44,
            command=self._start_escape_analysis,
        )
        self.btn_escape.pack(side="left")

        self.escape_progress = ctk.CTkProgressBar(btn_frame)
        self.escape_progress.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self.escape_progress.set(0)

        self.escape_frame = ctk.CTkScrollableFrame(
            self.tab_escape, fg_color="transparent",
        )
        self.escape_frame.pack(fill="both", expand=True)

        self.escape_placeholder = ctk.CTkLabel(
            self.escape_frame,
            text="按「分析我的文档」看看你能不能安全离开 WPS 🚀\n\n"
                 "我们会分析你的文档类型，检查格式相容性\n"
                 "然后告诉你最适合换什么软件、怎么换",
            font=ctk.CTkFont(size=14),
            text_color="gray",
            justify="center",
        )
        self.escape_placeholder.pack(pady=60)

    def _start_escape_analysis(self):
        self.btn_escape.configure(state="disabled", text="⏳ 分析中...")
        self.escape_progress.set(0.3)
        self.escape_placeholder.pack_forget()

        for w in self.escape_frame.winfo_children():
            w.destroy()

        def analyze():
            docs = scan_documents()
            self.inventory_result = docs
            compat = analyze_compatibility(docs)
            alts = recommend_alternatives(docs)
            plan = make_escape_plan(docs)
            self.after(0, lambda: self._show_escape_result(compat, alts, plan))

        threading.Thread(target=analyze, daemon=True).start()

    def _show_escape_result(self, compat, alts, plan):
        self.btn_escape.configure(state="normal", text="🔄 重新分析")
        self.escape_progress.set(1.0)

        for w in self.escape_frame.winfo_children():
            w.destroy()

        # ── 相容性結果 ──
        status_frame = ctk.CTkFrame(self.escape_frame)
        status_frame.pack(fill="x", pady=(0, 12))

        if compat.can_leave:
            status_color = "#4CAF50"
            status_emoji = "✅"
            status_text = "你可以安全离开 WPS！"
            status_detail = f"全部 {compat.total_docs} 个文档都是标准格式，换什么软件都能打开"
        else:
            status_color = "#FF9800"
            status_emoji = "⚠️"
            status_text = f"有 {compat.wps_private_count} 个文件需要先转换"
            status_detail = "其余文档都是标准格式，转换完就能离开"

        ctk.CTkLabel(
            status_frame,
            text=f"{status_emoji} {status_text}",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=status_color,
        ).pack(anchor="w", padx=16, pady=(12, 2))

        ctk.CTkLabel(
            status_frame,
            text=status_detail,
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).pack(anchor="w", padx=16, pady=(0, 12))

        # 文檔分布
        for cat, count in compat.doc_profile.items():
            total = max(compat.total_docs, 1)
            pct = count / total
            bar_len = int(pct * 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)

            row = ctk.CTkFrame(self.escape_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)

            ctk.CTkLabel(
                row, text=f"  {cat}", font=ctk.CTkFont(size=13), width=60,
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=bar, font=ctk.CTkFont(size=11, family="Courier"),
                text_color="#666",
            ).pack(side="left", padx=(4, 8))
            ctk.CTkLabel(
                row, text=f"{count} 个 ({int(pct*100)}%)",
                font=ctk.CTkFont(size=12), text_color="gray",
            ).pack(side="left")

        if compat.warnings:
            for w in compat.warnings:
                ctk.CTkLabel(
                    self.escape_frame,
                    text=w,
                    font=ctk.CTkFont(size=12),
                    text_color="#FF9800",
                    wraplength=800,
                ).pack(anchor="w", padx=16, pady=(6, 0))

        # ── 推薦替代品 ──
        ctk.CTkLabel(
            self.escape_frame,
            text="\n🔮 最适合你的替代品",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", pady=(16, 8))

        for i, alt in enumerate(alts):
            card = ctk.CTkFrame(self.escape_frame)
            card.pack(fill="x", pady=2)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=14, pady=10)

            # 排名標記
            star = "⭐ 首選" if i == 0 else f"  #{i+1}"
            star_color = "#FFD54F" if i == 0 else "gray"

            ctk.CTkLabel(
                inner,
                text=f"{alt.icon} {alt.name}",
                font=ctk.CTkFont(size=16, weight="bold"),
            ).pack(anchor="w")

            ctk.CTkLabel(
                inner,
                text=f"  {star} · 适合度 {alt.score}% · {alt.tagline}",
                font=ctk.CTkFont(size=12),
                text_color=star_color,
            ).pack(anchor="w")

            ctk.CTkLabel(
                inner,
                text=f"  💡 {alt.reason}",
                font=ctk.CTkFont(size=12),
                text_color="#aaa",
                wraplength=780,
            ).pack(anchor="w", pady=(2, 0))

        # ── 逃離路線圖 ──
        ctk.CTkLabel(
            self.escape_frame,
            text="\n🚀 你的逃离路线",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", pady=(16, 8))

        plan_card = ctk.CTkFrame(self.escape_frame)
        plan_card.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            plan_card,
            text=plan.summary,
            font=ctk.CTkFont(size=13),
            wraplength=800,
        ).pack(anchor="w", padx=16, pady=(12, 8))

        for j, step in enumerate(plan.steps):
            done = "✅" in step or "🎉" in step
            step_color = "#4CAF50" if done else "#ccc"
            ctk.CTkLabel(
                plan_card,
                text=f"  {j+1}. {step}",
                font=ctk.CTkFont(size=13),
                text_color=step_color,
            ).pack(anchor="w", padx=16, pady=3)

        # 下載按鈕
        ctk.CTkButton(
            plan_card,
            text=f"📥 下载 {plan.top_alternative.name}",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: webbrowser.open(plan.top_alternative.url),
        ).pack(padx=16, pady=(12, 14))

    # ═══════════════════════════════════════════
    # 📋 文档盘点頁
    # ═══════════════════════════════════════════
    def _build_inventory_tab(self):
        btn_frame = ctk.CTkFrame(self.tab_inventory, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(16, 8))

        self.btn_inv = ctk.CTkButton(
            btn_frame,
            text="📋 開始盤點",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            command=self._start_inventory,
        )
        self.btn_inv.pack(side="left")

        self.inv_progress = ctk.CTkProgressBar(btn_frame)
        self.inv_progress.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self.inv_progress.set(0)

        self.inv_result_frame = ctk.CTkScrollableFrame(
            self.tab_inventory, fg_color="transparent",
        )
        self.inv_result_frame.pack(fill="both", expand=True)

        self.inv_placeholder = ctk.CTkLabel(
            self.inv_result_frame,
            text="按「開始盤點」找出電腦裡所有的 WPS 文檔 📋",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        )
        self.inv_placeholder.pack(pady=40)

    def _start_inventory(self):
        self.btn_inv.configure(state="disabled", text="⏳ 掃描中...")
        self.inv_progress.set(0.3)
        self.inv_placeholder.pack_forget()

        for w in self.inv_result_frame.winfo_children():
            w.destroy()

        def inv_thread():
            result = scan_documents()
            self.inventory_result = result
            self.after(0, lambda: self._show_inventory_result(result))

        threading.Thread(target=inv_thread, daemon=True).start()

    def _show_inventory_result(self, result):
        self.btn_inv.configure(state="normal", text="🔄 重新盤點")
        self.inv_progress.set(1.0)

        for w in self.inv_result_frame.winfo_children():
            w.destroy()

        if not result.documents:
            ctk.CTkLabel(
                self.inv_result_frame,
                text="✅ 沒找到任何 Office 文檔。",
                font=ctk.CTkFont(size=16),
            ).pack(pady=20)
            return

        summary = ctk.CTkFrame(self.inv_result_frame)
        summary.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            summary,
            text=f"找到 {result.total_count} 個文檔 · 共 {_format_size(result.total_size)}",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(12, 4))

        status_text = f"✅ {result.standard_count} 個標準格式（可搬家）"
        if result.wps_only_count > 0:
            status_text += f" · 🔒 {result.wps_only_count} 個 WPS 私有格式（需轉換）"
        ctk.CTkLabel(
            summary,
            text=status_text,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=16, pady=(0, 12))

        grouped = get_docs_by_category(result)
        icons = {"文件": "📝", "表格": "📊", "簡報": "📽️", "PDF": "📕", "其他": "📎"}

        cat_frame = ctk.CTkFrame(self.inv_result_frame)
        cat_frame.pack(fill="x", pady=(0, 12))

        for cat, docs in grouped.items():
            icon = icons.get(cat, "📎")
            cat_size = sum(d.size for d in docs)
            ctk.CTkLabel(
                cat_frame,
                text=f"{icon} {cat}：{len(docs)} 個 · {_format_size(cat_size)}",
                font=ctk.CTkFont(size=13),
            ).pack(anchor="w", padx=16, pady=4)

        if result.documents:
            ctk.CTkLabel(
                self.inv_result_frame,
                text="🐘 最大的文檔：",
                font=ctk.CTkFont(size=14, weight="bold"),
            ).pack(anchor="w", pady=(12, 4))

            for doc in get_large_docs(result, 10):
                mod_str = doc.modified.strftime("%Y-%m-%d") if doc.modified else "未知"
                tag = "🔒" if doc.is_wps_format else "  "
                size_str = _format_size(doc.size)

                row = ctk.CTkFrame(self.inv_result_frame, fg_color="transparent")
                row.pack(fill="x", pady=1)

                ctk.CTkLabel(
                    row,
                    text=f"  {tag} {size_str:>10}  {doc.filename}",
                    font=ctk.CTkFont(size=11),
                ).pack(anchor="w")

    # ═══════════════════════════════════════════
    # ℹ️ 關於頁
    # ═══════════════════════════════════════════
    def _build_about_tab(self):
        content = ctk.CTkFrame(self.tab_about, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(
            content,
            text="關於 WPS 解毒器",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w")

        about_text = """
WPS 解毒器（D-tox）是一款免費工具，幫你：

🧪 健康報告 — 分析 WPS 對你電腦的毒性指數
🔍 掃描 — 找出 WPS 在電腦各角落藏的垃圾檔案
🧹 清理 — 一鍵釋放被佔用的磁碟空間
📋 盤點 — 清點所有文檔，分類歸檔

本工具不收集任何用戶資料，不上傳任何檔案。
所有操作都在你的電腦上完成。

Made with ❤️ for WPS 難民
        """
        ctk.CTkLabel(
            content,
            text=about_text.strip(),
            font=ctk.CTkFont(size=13),
            justify="left",
        ).pack(anchor="w", pady=(16, 0))


def main():
    app = WPSDetoxApp()
    app.mainloop()


if __name__ == "__main__":
    main()
