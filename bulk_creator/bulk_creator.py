import customtkinter as ctk
from tkinter import filedialog, messagebox
import pandas as pd
from datetime import datetime
import os
import csv
import time
import json
import platform

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

MULTILINE_FIELDS = {
    "asins", "target_asins", "keywords_broad", "keywords_phrase",
    "keywords_negative", "sku_list", "base_pt_expression",
    "landing_page_asins", "negative_keywords", "keyword_text",
    "neg_campaign_ids", "neg_ad_group_ids", "neg_keywords"
}

COLOR_MAP = {
    "sbv": "#E67E22",
    "sp_product": "#3498DB",
    "sp_auto": "#2ECC71",
    "sbkw": "#9B59B6",
    "sp_kw": "#1ABC9C",
    "neg_keyword": "#E74C3C",
}

COMBO_OPTIONS = {"neg_type": ["SP", "SB"], "neg_match_type": ["negativePhrase", "negativeExact"]}

STATUS_COLORS = {
    "idle": "#7F8C8D",
    "success": "#2ECC71",
    "error": "#E74C3C",
    "warning": "#F39C12",
}

FONT_HIERARCHY = {
    "H1": ("Arial", 24, "bold"),
    "H2": ("Arial", 20, "bold"),
    "H3": ("Arial", 16, "bold"),
    "Body": ("Arial", 16),
    "BodySmall": ("Arial", 14),
    "Caption": ("Arial", 12),
    "Mono": ("Consolas", 14),
}


class ScrollableFrame(ctk.CTkScrollableFrame):
    """通用可滚动框架"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)


class SimplePanel(ctk.CTkFrame):
    """简洁面板，无折叠功能"""

    def __init__(self, parent, title, fields, config, accent_color="#3498DB"):
        super().__init__(parent, corner_radius=8, fg_color=("gray90", "gray17"))

        self.header = ctk.CTkFrame(self, corner_radius=8, height=38,
                                    fg_color=accent_color)
        self.header.pack(fill="x", padx=2, pady=(2, 0))
        self.header.pack_propagate(False)

        self.title_label = ctk.CTkLabel(self.header, text=title,
                                         font=FONT_HIERARCHY["H3"], text_color="white")
        self.title_label.pack(side="left", padx=12)

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="x", padx=8, pady=8)

        self._build_fields(fields, config)

    def _build_fields(self, fields, config):
        for label_text, var_name, tooltip in fields:
            field_container = ctk.CTkFrame(self.content, fg_color="transparent")
            field_container.pack(fill="x", pady=4)

            input_row = ctk.CTkFrame(field_container, fg_color="transparent")
            input_row.pack(fill="x")

            label = ctk.CTkLabel(input_row, text=label_text, width=160, anchor="w",
                                  font=FONT_HIERARCHY["Body"])
            label.pack(side="left", padx=(0, 8))

            if var_name in MULTILINE_FIELDS:
                text_widget = ctk.CTkTextbox(input_row, height=80, font=FONT_HIERARCHY["Mono"])
                text_widget.insert("1.0", config[var_name].get())
                text_widget.pack(side="left", fill="x", expand=True)

                def on_text_change(event, var=config[var_name], widget=text_widget):
                    var.set(widget.get("1.0", "end").strip())
                text_widget.bind("<KeyRelease>", on_text_change)

            elif var_name == "match_type":
                combo = ctk.CTkComboBox(input_row, variable=config[var_name],
                                         values=["broad", "exact", "phrase"],
                                         width=300, state="readonly")
                combo.pack(side="left", fill="x", expand=True)
            elif var_name in COMBO_OPTIONS:
                combo = ctk.CTkComboBox(input_row, variable=config[var_name],
                                         values=COMBO_OPTIONS[var_name],
                                         width=300, state="readonly")
                combo.pack(side="left", fill="x", expand=True)
            else:
                entry = ctk.CTkEntry(input_row, textvariable=config[var_name], width=300,
                                      font=FONT_HIERARCHY["Body"])
                entry.pack(side="left", fill="x", expand=True)

            if tooltip:
                hint = ctk.CTkLabel(field_container, text=tooltip, font=FONT_HIERARCHY["Caption"],
                                     text_color="gray50", wraplength=500, anchor="w")
                hint.pack(fill="x", padx=(168, 0), pady=(2, 0))


class StatusLabel(ctk.CTkFrame):
    """带色彩状态指示器的状态栏"""

    def __init__(self, parent, initial_text="请填写配置并点击生成CSV"):
        super().__init__(parent, fg_color="transparent")
        self.status_var = ctk.StringVar(value=initial_text)
        self.status_color = STATUS_COLORS["idle"]

        self.indicator = ctk.CTkLabel(self, text="●", width=20,
                                       font=FONT_HIERARCHY["Body"], text_color=self.status_color)
        self.indicator.pack(side="left", padx=(0, 6))

        self.label = ctk.CTkLabel(self, textvariable=self.status_var,
                                   font=FONT_HIERARCHY["BodySmall"], anchor="w", wraplength=800)
        self.label.pack(side="left", fill="x", expand=True)

    def set_status(self, text, state="idle"):
        self.status_var.set(text)
        self.status_color = STATUS_COLORS.get(state, STATUS_COLORS["idle"])
        self.indicator.configure(text_color=self.status_color)
        self.label.configure(text_color=self.status_color)


class NegativeKeywordGrid(ctk.CTkFrame):
    """否定词根三列网格输入组件：Campaign ID / Ad Group ID / 否定词根"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.rows = []
        self._init_ui()

    def _init_ui(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(header_frame, text="Campaign ID", width=150,
                      font=FONT_HIERARCHY["BodySmall"], anchor="w").pack(side="left", padx=(0, 5))
        ctk.CTkLabel(header_frame, text="Ad Group ID（每行一个）", width=200,
                      font=FONT_HIERARCHY["BodySmall"], anchor="w").pack(side="left", padx=(0, 5))
        ctk.CTkLabel(header_frame, text="否定词根（每行一个）", width=200,
                      font=FONT_HIERARCHY["BodySmall"], anchor="w").pack(side="left")

        self.rows_container = ctk.CTkScrollableFrame(self, height=200, fg_color="transparent")
        self.rows_container.pack(fill="x")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(5, 0))

        ctk.CTkButton(btn_frame, text="+ 添加行", command=self._add_row, width=100, height=28,
                       font=FONT_HIERARCHY["BodySmall"]).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btn_frame, text="- 删除最后一行", command=self._remove_last_row, width=120, height=28,
                       font=FONT_HIERARCHY["BodySmall"]).pack(side="left")

        self._add_row()

    def _add_row(self):
        row_frame = ctk.CTkFrame(self.rows_container, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)

        campaign_entry = ctk.CTkEntry(row_frame, width=150, font=FONT_HIERARCHY["Mono"])
        campaign_entry.pack(side="left", padx=(0, 5))

        adgroup_textbox = ctk.CTkTextbox(row_frame, height=50, width=200, font=FONT_HIERARCHY["Mono"])
        adgroup_textbox.pack(side="left", padx=(0, 5))

        keyword_textbox = ctk.CTkTextbox(row_frame, height=50, width=200, font=FONT_HIERARCHY["Mono"])
        keyword_textbox.pack(side="left")

        self.rows.append({
            "frame": row_frame,
            "campaign": campaign_entry,
            "adgroups": adgroup_textbox,
            "keywords": keyword_textbox
        })

    def _remove_last_row(self):
        if len(self.rows) > 1:
            row = self.rows.pop()
            row["frame"].destroy()

    def get_data(self):
        """获取所有行数据"""
        result = []
        for row in self.rows:
            campaign = row["campaign"].get().strip()
            adgroups = [s.strip() for s in row["adgroups"].get("1.0", "end").strip().split("\n") if s.strip()]
            keywords = [s.strip() for s in row["keywords"].get("1.0", "end").strip().split("\n") if s.strip()]
            result.append({"campaign": campaign, "adgroups": adgroups, "keywords": keywords})
        return result


class AmazonAdBulkGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Amazon BULK 批量生成工具")
        self.root.geometry("1050x820")
        self.root.minsize(900, 700)

        self._build_tab_structure()
        self._init_all_tabs()

    def _build_tab_structure(self):
        """构建标签页核心结构"""
        self.header_frame = ctk.CTkFrame(self.root, height=50, fg_color="#1A1A2E",
                                          corner_radius=0)
        self.header_frame.pack(fill="x")
        self.header_frame.pack_propagate(False)

        ctk.CTkLabel(self.header_frame, text="⚡ Amazon BULK 批量生成工具",
                      font=FONT_HIERARCHY["H1"], text_color="#FF9900"
                      ).pack(side="left", padx=20, pady=10)

        self.notebook = ctk.CTkTabview(self.root, fg_color="#16213E",
                                        segmented_button_fg_color="#1A1A2E",
                                        segmented_button_selected_color="#FF9900",
                                        segmented_button_unselected_color="#333355")
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        self.tab_sbv = self.notebook.add("🎬 SBV 视频")
        self.tab_sp_product = self.notebook.add("📦 SP 商品")
        self.tab_sp_auto = self.notebook.add("🤖 SP 自动")
        self.tab_sbkw = self.notebook.add("🔑 SB_KW")
        self.tab_sp_kw = self.notebook.add("🎯 SP_KW")
        self.tab_neg_keyword = self.notebook.add("🚫 否定词根")

    def _create_scrollable_tab(self, tab_widget):
        container = ctk.CTkFrame(tab_widget, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)
        scroll_frame = ScrollableFrame(container, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True)
        return scroll_frame

    def _init_all_tabs(self):
        """初始化所有标签页"""
        self._init_sbv_tab()
        self._init_sp_product_tab()
        self._init_sp_auto_tab()
        self._init_sbkw_tab()
        self._init_sp_kw_tab()
        self._init_neg_keyword_tab()

    # ===================== SBV视频广告页面 =====================
    def _init_sbv_tab(self):
        self.sbv_config = {
            "product_name": ctk.StringVar(value="商品名称_SP_自动/手动_投放类型_投放词_日期"),
            "launch_date": ctk.StringVar(value=datetime.today().strftime("%Y%m%d")),
            "budget": ctk.StringVar(value="3.0"),
            "bid_amount": ctk.StringVar(value="0.5"),
            "brand_entity_id": ctk.StringVar(value="ENTIXXXX"),
            "video_asset_id": ctk.StringVar(value="amzn1.assetlXX1"),
            "asins": ctk.StringVar(value="B0XXX1\nB0XXX2\nB0XXX3"),
            "target_asins": ctk.StringVar(value=""),
            "keywords_broad": ctk.StringVar(value="dresses"),
            "keywords_phrase": ctk.StringVar(value="dresses"),
            "keywords_negative": ctk.StringVar(value="cocktail\npurple\ntie"),
            "campaign_loop_count": ctk.StringVar(value="2"),
            "ad_group_per_campaign": ctk.StringVar(value="3"),
            "output_file": ctk.StringVar(value=f"bulk_sbv多组_{datetime.today().strftime('%Y%m%d')}.csv")
        }

        content = self._create_scrollable_tab(self.tab_sbv)

        ctk.CTkLabel(content, text="SBV 视频广告批量生成",
                      font=FONT_HIERARCHY["H2"], text_color=COLOR_MAP["sbv"]
                      ).pack(pady=(10, 15))

        SimplePanel(content, "Campaign循环配置", [
            ("Campaign循环数量:", "campaign_loop_count", "生成的Campaign总数"),
            ("每Campaign广告组数:", "ad_group_per_campaign", "每个Campaign下的广告组数量"),
        ], config=self.sbv_config, accent_color=COLOR_MAP["sbv"]).pack(fill="x", pady=4)

        SimplePanel(content, "基本配置", [
            ("广告名称:", "product_name", "输入广告系列基础名称"),
            ("投放日期:", "launch_date", "格式: YYYYMMDD"),
            ("每日预算:", "budget", "单位: 美元"),
            ("CPC竞价:", "bid_amount", "建议先低竞价，没有曝光再慢慢调上去"),
            ("品牌实体ID:", "brand_entity_id", "例如: ENTIXXXX，目前只能通过下载报表查看"),
            ("视频资产ID:", "video_asset_id", "例如: amzn1.assetlXX1；可以直接在https://advertising.amazon.com/creative-assets查找"),
        ], config=self.sbv_config, accent_color=COLOR_MAP["sbv"]).pack(fill="x", pady=4)

        SimplePanel(content, "ASIN配置", [
            ("本品ASIN(必填):", "asins", "每行一个，可重复"),
            ("投放ASIN(可选):", "target_asins", "留空则生成关键词广告"),
        ], config=self.sbv_config, accent_color=COLOR_MAP["sbv"]).pack(fill="x", pady=4)

        SimplePanel(content, "关键词配置", [
            ("广泛匹配:", "keywords_broad", "每行一个关键词"),
            ("词组匹配:", "keywords_phrase", "每行一个关键词"),
            ("否定词根:", "keywords_negative", "每行一个否定关键词"),
        ], config=self.sbv_config, accent_color=COLOR_MAP["sbv"]).pack(fill="x", pady=4)

        SimplePanel(content, "输出配置", [
            ("输出文件名:", "output_file", "生成的CSV文件名"),
        ], config=self.sbv_config, accent_color="#555555").pack(fill="x", pady=4)

        self._build_action_bar(content, "sbv")

    # ===================== SP_商品广告页面 =====================
    def _init_sp_product_tab(self):
        self.sp_product_config = {
            "campaign_name": ctk.StringVar(value="商品名称_SP_手动_投放类型_投放词_日期_20251205"),
            "product_targeting_bid": ctk.StringVar(value="0.55"),
            "sku_list": ctk.StringVar(value="sku1\nsku2\nsku3\nsku4\nsku5"),
            "base_pt_expression": ctk.StringVar(value='category="2346727011" brand="16516030011"\ncategory="1234567890" brand="9876543210"'),
            "price_start": ctk.StringVar(value="10"),
            "price_end_max": ctk.StringVar(value="100"),
            "price_step": ctk.StringVar(value="10"),
            "keywords_negative": ctk.StringVar(value="cheap\nlow quality\nrefurbished"),
            "campaign_loop_count": ctk.StringVar(value="2"),
            "ad_group_per_campaign": ctk.StringVar(value="3"),
            "output_file": ctk.StringVar(value=f"sp_bulk_投放_{datetime.today().strftime('%Y%m%d')}.csv")
        }

        content = self._create_scrollable_tab(self.tab_sp_product)

        ctk.CTkLabel(content, text="SP 商品广告批量生成",
                      font=FONT_HIERARCHY["H2"], text_color=COLOR_MAP["sp_product"]
                      ).pack(pady=(10, 15))

        SimplePanel(content, "Campaign循环配置", [
            ("Campaign循环数量:", "campaign_loop_count", "生成的Campaign总数"),
            ("每Campaign广告组数:", "ad_group_per_campaign", "每个Campaign下的广告组数量"),
        ], config=self.sp_product_config, accent_color=COLOR_MAP["sp_product"]).pack(fill="x", pady=4)

        SimplePanel(content, "基本配置", [
            ("活动名称:", "campaign_name", "输入SP广告活动名称"),
            ("CPC竞价:", "product_targeting_bid", "单位: 美元"),
        ], config=self.sp_product_config, accent_color=COLOR_MAP["sp_product"]).pack(fill="x", pady=4)

        SimplePanel(content, "SKU配置", [
            ("广告SKU:", "sku_list", "每行一个，不能重复"),
        ], config=self.sp_product_config, accent_color=COLOR_MAP["sp_product"]).pack(fill="x", pady=4)

        SimplePanel(content, "产品定位配置", [
            ("投放:", "base_pt_expression", "直接复制ASIN或category列"),
        ], config=self.sp_product_config, accent_color=COLOR_MAP["sp_product"]).pack(fill="x", pady=4)

        SimplePanel(content, "价格区间配置", [
            ("起始价格:", "price_start", "类目投放价格起始值"),
            ("价格上限:", "price_end_max", "类目投放价格最大值"),
            ("价格步长:", "price_step", "类目投放价格间隔"),
        ], config=self.sp_product_config, accent_color="#E67E22").pack(fill="x", pady=4)

        SimplePanel(content, "关键词配置（否定词根）", [
            ("否定词根:", "keywords_negative", "每行一个否定关键词"),
        ], config=self.sp_product_config, accent_color=COLOR_MAP["sp_product"]).pack(fill="x", pady=4)

        SimplePanel(content, "输出配置", [
            ("输出文件名:", "output_file", "生成的CSV文件名"),
        ], config=self.sp_product_config, accent_color="#555555").pack(fill="x", pady=4)

        self._build_action_bar(content, "sp_product")

    # ===================== SP_自动广告页面 =====================
    def _init_sp_auto_tab(self):
        self.sp_auto_config = {
            "campaign_name": ctk.StringVar(value="商品名称_SP_自动_投放类型_日期_20251205"),
            "product_targeting_bid": ctk.StringVar(value="0.55"),
            "sku_list": ctk.StringVar(value="sku1\nsku2\nsku3\nsku4\nsku5"),
            "keywords_negative": ctk.StringVar(value="cheap\nlow quality\nrefurbished"),
            "campaign_loop_count": ctk.StringVar(value="2"),
            "ad_group_per_campaign": ctk.StringVar(value="3"),
            "output_file": ctk.StringVar(value=f"sp_bulk_自动_{datetime.today().strftime('%Y%m%d')}.csv")
        }

        content = self._create_scrollable_tab(self.tab_sp_auto)

        ctk.CTkLabel(content, text="SP 自动广告批量生成",
                      font=FONT_HIERARCHY["H2"], text_color=COLOR_MAP["sp_auto"]
                      ).pack(pady=(10, 15))

        info_frame = ctk.CTkFrame(content, fg_color="#1B3A2D", corner_radius=8)
        info_frame.pack(fill="x", pady=(0, 10), padx=4)
        ctk.CTkLabel(info_frame, text="🤖 自动投放模式：自动生成 close-match / loose-match / substitutes / complements 四种匹配类型",
                      font=FONT_HIERARCHY["Caption"], text_color="#2ECC71").pack(padx=12, pady=8)

        SimplePanel(content, "Campaign循环配置", [
            ("Campaign循环数量:", "campaign_loop_count", "生成的Campaign总数"),
            ("每Campaign广告组数:", "ad_group_per_campaign", "每个Campaign下的广告组数量"),
        ], config=self.sp_auto_config, accent_color=COLOR_MAP["sp_auto"]).pack(fill="x", pady=4)

        SimplePanel(content, "基本配置", [
            ("活动名称:", "campaign_name", "输入SP自动广告活动名称"),
            ("CPC竞价:", "product_targeting_bid", "单位: 美元"),
        ], config=self.sp_auto_config, accent_color=COLOR_MAP["sp_auto"]).pack(fill="x", pady=4)

        SimplePanel(content, "SKU配置", [
            ("广告SKU:", "sku_list", "每行一个，不能重复"),
        ], config=self.sp_auto_config, accent_color=COLOR_MAP["sp_auto"]).pack(fill="x", pady=4)

        SimplePanel(content, "关键词配置（否定词根）", [
            ("否定词根:", "keywords_negative", "每行一个否定关键词"),
        ], config=self.sp_auto_config, accent_color=COLOR_MAP["sp_auto"]).pack(fill="x", pady=4)

        SimplePanel(content, "输出配置", [
            ("输出文件名:", "output_file", "生成的CSV文件名"),
        ], config=self.sp_auto_config, accent_color="#555555").pack(fill="x", pady=4)

        self._build_action_bar(content, "sp_auto")

    # ===================== SB_KW广告页面 =====================
    def _init_sbkw_tab(self):
        self.sbkw_config = {
            "campaign_name": ctk.StringVar(value="圣诞促销活动"),
            "start_date": ctk.StringVar(value=datetime.now().strftime("%Y%m%d")),
            "brand_entity_id": ctk.StringVar(value="ENTI12345"),
            "budget": ctk.StringVar(value="10.0"),
            "campaign_loop_count": ctk.StringVar(value="2"),
            "ad_group_per_campaign": ctk.StringVar(value="3"),
            "landing_page_asins": ctk.StringVar(value="B0XXX1\nB0XXX2\nB0XXX3"),
            "brand_name": ctk.StringVar(value="我的品牌"),
            "brand_logo_asset_id": ctk.StringVar(value="amzn1.assetlibrary.12345"),
            "creative_headline": ctk.StringVar(value="圣诞特惠 限时折扣"),
            "keyword_text": ctk.StringVar(value="+christmas+gift+2024\n+new+year+gift\n+winter+accessory"),
            "match_type": ctk.StringVar(value="broad"),
            "bid_amount": ctk.StringVar(value="0.5"),
            "negative_keywords": ctk.StringVar(value="expensive\nout of stock\ndiscontinued"),
            "custom_image_id": ctk.StringVar(value="amzn1.asset.67890"),
            "output_file": ctk.StringVar(value=f"DEMOBULK_{datetime.now().strftime('%Y%m%d')}.csv")
        }

        content = self._create_scrollable_tab(self.tab_sbkw)

        ctk.CTkLabel(content, text="SB_KW 广告批量生成",
                      font=FONT_HIERARCHY["H2"], text_color=COLOR_MAP["sbkw"]
                      ).pack(pady=(10, 15))

        SimplePanel(content, "Campaign循环配置", [
            ("Campaign循环数量:", "campaign_loop_count", "生成的Campaign总数"),
            ("每Campaign广告组数:", "ad_group_per_campaign", "每个Campaign下的广告组数量"),
        ], config=self.sbkw_config, accent_color=COLOR_MAP["sbkw"]).pack(fill="x", pady=4)

        SimplePanel(content, "Campaign基础配置", [
            ("Campaign名称前缀:", "campaign_name", "自动加序号"),
            ("开始日期:", "start_date", "格式: YYYYMMDD"),
            ("品牌实体ID:", "brand_entity_id", "例如: ENTI12345"),
            ("每日预算:", "budget", "单位: 美元"),
        ], config=self.sbkw_config, accent_color=COLOR_MAP["sbkw"]).pack(fill="x", pady=4)

        SimplePanel(content, "产品配置", [
            ("Landing Page ASINs:", "landing_page_asins", "每行一个ASIN"),
            ("品牌名称:", "brand_name", "展示的品牌名称"),
            ("品牌Logo Asset ID:", "brand_logo_asset_id", "例如: amzn1.assetlibrary.12345"),
            ("创意标题:", "creative_headline", "广告创意标题"),
            ("自定义图片Asset ID:", "custom_image_id", "格式: amzn1.asset.67890"),
        ], config=self.sbkw_config, accent_color=COLOR_MAP["sbkw"]).pack(fill="x", pady=4)

        SimplePanel(content, "关键词配置", [
            ("关键词:", "keyword_text", "每行一个，支持+号精准匹配"),
            ("匹配类型:", "match_type", "broad/exact/phrase"),
            ("出价:", "bid_amount", "单位: 美元"),
            ("否定词根:", "negative_keywords", "每行一个词根"),
        ], config=self.sbkw_config, accent_color=COLOR_MAP["sbkw"]).pack(fill="x", pady=4)

        SimplePanel(content, "输出配置", [
            ("输出文件名:", "output_file", "生成的CSV文件名"),
        ], config=self.sbkw_config, accent_color="#555555").pack(fill="x", pady=4)

        self._build_action_bar(content, "sbkw")

    # ===================== SP_KW 关键词投放页面 =====================
    def _init_sp_kw_tab(self):
        self.sp_kw_config = {
            "campaign_name": ctk.StringVar(value="商品名称_SP_手动_关键词_日期"),
            "daily_budget": ctk.StringVar(value="5"),
            "start_date": ctk.StringVar(value=datetime.today().strftime("%Y%m%d")),
            "bidding_strategy": ctk.StringVar(value="Fixed bid"),
            "campaign_loop_count": ctk.StringVar(value="2"),
            "ad_group_per_campaign": ctk.StringVar(value="3"),
            "sku_list": ctk.StringVar(value="SKU1\nSKU2"),
            "ad_group_default_bid": ctk.StringVar(value="0.75"),
            "keyword_text": ctk.StringVar(value="backless top\nbackless shirt\nbackless crop top\nopen back tops for women"),
            "match_type": ctk.StringVar(value="broad"),
            "bid_amount": ctk.StringVar(value="0.48"),
            "placement_top": ctk.StringVar(value="20"),
            "placement_product_page": ctk.StringVar(value="0"),
            "placement_rest_of_search": ctk.StringVar(value="0"),
            "placement_amazon_business": ctk.StringVar(value="0"),
            "output_file": ctk.StringVar(value=f"sp_bulk_关键词_{datetime.today().strftime('%Y%m%d')}.csv")
        }

        content = self._create_scrollable_tab(self.tab_sp_kw)

        ctk.CTkLabel(content, text="SP_KW 关键词投放批量生成",
                      font=FONT_HIERARCHY["H2"], text_color=COLOR_MAP["sp_kw"]
                      ).pack(pady=(10, 15))

        info_frame = ctk.CTkFrame(content, fg_color="#1B3A2D", corner_radius=8)
        info_frame.pack(fill="x", pady=(0, 10), padx=4)
        ctk.CTkLabel(info_frame, text="🎯 SP手动关键词投放：为每个广告组生成关键词投放行，支持Broad/Exact/Phrase匹配",
                      font=FONT_HIERARCHY["Caption"], text_color="#1ABC9C").pack(padx=12, pady=8)

        SimplePanel(content, "Campaign循环配置", [
            ("Campaign循环数量:", "campaign_loop_count", "生成的Campaign总数"),
            ("每Campaign广告组数:", "ad_group_per_campaign", "每个Campaign下的广告组数量"),
        ], config=self.sp_kw_config, accent_color=COLOR_MAP["sp_kw"]).pack(fill="x", pady=4)

        SimplePanel(content, "基本配置", [
            ("活动名称:", "campaign_name", "输入SP关键词广告活动名称"),
            ("每日预算:", "daily_budget", "单位: 美元"),
            ("投放日期:", "start_date", "格式: YYYYMMDD"),
            ("竞价策略:", "bidding_strategy", "Fixed bid / Dynamic bids down / Dynamic bids up and down"),
        ], config=self.sp_kw_config, accent_color=COLOR_MAP["sp_kw"]).pack(fill="x", pady=4)

        SimplePanel(content, "SKU配置", [
            ("广告SKU:", "sku_list", "每行一个，不能重复"),
        ], config=self.sp_kw_config, accent_color=COLOR_MAP["sp_kw"]).pack(fill="x", pady=4)

        SimplePanel(content, "关键词配置", [
            ("关键词:", "keyword_text", "每行一个关键词"),
            ("匹配类型:", "match_type", "broad / exact / phrase"),
            ("关键词出价:", "bid_amount", "每个关键词的出价，单位: 美元"),
            ("广告组默认出价:", "ad_group_default_bid", "广告组默认出价，单位: 美元"),
        ], config=self.sp_kw_config, accent_color=COLOR_MAP["sp_kw"]).pack(fill="x", pady=4)

        SimplePanel(content, "竞价调整（Placement）", [
            ("Placement Top:", "placement_top", "首页顶部位置竞价调整百分比"),
            ("Placement Product Page:", "placement_product_page", "产品页面位置竞价调整百分比"),
            ("Placement Rest Of Search:", "placement_rest_of_search", "其余搜索位置竞价调整百分比"),
            ("Placement Amazon Business:", "placement_amazon_business", "Amazon Business位置竞价调整百分比"),
        ], config=self.sp_kw_config, accent_color="#E67E22").pack(fill="x", pady=4)

        SimplePanel(content, "输出配置", [
            ("输出文件名:", "output_file", "生成的CSV文件名"),
        ], config=self.sp_kw_config, accent_color="#555555").pack(fill="x", pady=4)

        self._build_action_bar(content, "sp_kw")

    # ===================== 否定词根标签页 =====================
    def _init_neg_keyword_tab(self):
        self.neg_keyword_config = {
            "neg_type": ctk.StringVar(value="SP"),
            "neg_match_type": ctk.StringVar(value="negativePhrase"),
            "output_file": ctk.StringVar(value=f"neg_keyword_{datetime.today().strftime('%Y%m%d')}.csv")
        }

        content = self._create_scrollable_tab(self.tab_neg_keyword)

        ctk.CTkLabel(content, text="🚫 否定词根批量生成",
                      font=FONT_HIERARCHY["H2"], text_color=COLOR_MAP["neg_keyword"]
                      ).pack(pady=(10, 15))

        info_frame = ctk.CTkFrame(content, fg_color="#3A1B1B", corner_radius=8)
        info_frame.pack(fill="x", pady=(0, 10), padx=4)
        ctk.CTkLabel(info_frame, text="🚫 否定词根批量生成：支持SP和SB两种广告类型的否定关键词批量生成",
                      font=FONT_HIERARCHY["Caption"], text_color="#E74C3C").pack(padx=12, pady=8)

        SimplePanel(content, "广告类型选择", [
            ("否词类型:", "neg_type", "选择SP或SB广告类型"),
        ], config=self.neg_keyword_config, accent_color=COLOR_MAP["neg_keyword"]).pack(fill="x", pady=4)

        target_panel = ctk.CTkFrame(content, corner_radius=8, fg_color=("gray90", "gray17"))
        target_panel.pack(fill="x", pady=4)

        target_header = ctk.CTkFrame(target_panel, corner_radius=8, height=38,
                                      fg_color=COLOR_MAP["neg_keyword"])
        target_header.pack(fill="x", padx=2, pady=(2, 0))
        target_header.pack_propagate(False)
        ctk.CTkLabel(target_header, text="目标配置", font=FONT_HIERARCHY["H3"], text_color="white").pack(side="left", padx=12)

        target_content = ctk.CTkFrame(target_panel, fg_color="transparent")
        target_content.pack(fill="x", padx=8, pady=8)

        self.neg_keyword_grid = NegativeKeywordGrid(target_content, fg_color="transparent")
        self.neg_keyword_grid.pack(fill="x")

        SimplePanel(content, "匹配类型", [
            ("匹配类型:", "neg_match_type", "选择否定关键词匹配类型"),
        ], config=self.neg_keyword_config, accent_color=COLOR_MAP["neg_keyword"]).pack(fill="x", pady=4)

        SimplePanel(content, "输出配置", [
            ("输出文件名:", "output_file", "生成的CSV文件名"),
        ], config=self.neg_keyword_config, accent_color="#555555").pack(fill="x", pady=4)

        self._build_action_bar(content, "neg_keyword")

    # ===================== 通用操作栏构建 =====================
    def _build_action_bar(self, parent, tab_key):
        """构建操作按钮栏+状态栏"""
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.pack(fill="x", pady=(15, 5))

        generate_cmd = {
            "sbv": self.generate_sbv_csv,
            "sp_product": self.generate_sp_product_csv,
            "sp_auto": self.generate_sp_auto_csv,
            "sbkw": self.generate_sbkw_csv,
            "sp_kw": self.generate_sp_kw_csv,
            "neg_keyword": self.generate_neg_keyword_csv,
        }[tab_key]

        reset_cmd = {
            "sbv": self.reset_sbv_config,
            "sp_product": self.reset_sp_product_config,
            "sp_auto": self.reset_sp_auto_config,
            "sbkw": self.reset_sbkw_config,
            "sp_kw": self.reset_sp_kw_config,
            "neg_keyword": self.reset_neg_keyword_config,
        }[tab_key]

        config_name = {
            "sbv": "sbv_config",
            "sp_product": "sp_product_config",
            "sp_auto": "sp_auto_config",
            "sbkw": "sbkw_config",
            "sp_kw": "sp_kw_config",
            "neg_keyword": "neg_keyword_config",
        }[tab_key]

        ctk.CTkButton(bar, text="⚡ 生成CSV", command=generate_cmd,
                       fg_color=COLOR_MAP[tab_key], hover_color=self._darken(COLOR_MAP[tab_key]),
                       font=FONT_HIERARCHY["H3"], width=140, height=38
                       ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(bar, text="📁 保存路径", command=lambda: self.choose_save_path(getattr(self, config_name)["output_file"]),
                       fg_color="#333355", hover_color="#444477",
                       font=FONT_HIERARCHY["BodySmall"], width=120, height=38
                       ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(bar, text="🔄 重置", command=reset_cmd,
                       fg_color="#333355", hover_color="#444477",
                       font=FONT_HIERARCHY["BodySmall"], width=90, height=38
                       ).pack(side="left")

        status = StatusLabel(parent)
        status.pack(fill="x", pady=(5, 10))

        setattr(self, f"{tab_key}_status", status)

    @staticmethod
    def _darken(hex_color, factor=0.8):
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"

    # ===================== 通用方法 =====================
    def choose_save_path(self, var):
        current_filename = var.get()
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=current_filename
        )
        if path:
            var.set(path)

    # ===================== 重置配置 =====================
    def reset_sbv_config(self):
        if messagebox.askyesno("确认", "是否重置SBV所有配置为默认值?"):
            for widget in self.tab_sbv.winfo_children():
                widget.destroy()
            self._init_sbv_tab()
            self.sbv_status.set_status("配置已重置为默认值", "idle")

    def reset_sp_product_config(self):
        if messagebox.askyesno("确认", "是否重置SP_商品所有配置为默认值?"):
            for widget in self.tab_sp_product.winfo_children():
                widget.destroy()
            self._init_sp_product_tab()
            self.sp_product_status.set_status("配置已重置为默认值", "idle")

    def reset_sp_auto_config(self):
        if messagebox.askyesno("确认", "是否重置SP_自动所有配置为默认值?"):
            for widget in self.tab_sp_auto.winfo_children():
                widget.destroy()
            self._init_sp_auto_tab()
            self.sp_auto_status.set_status("配置已重置为默认值", "idle")

    def reset_sbkw_config(self):
        if messagebox.askyesno("确认", "是否重置SB_KW所有配置为默认值?"):
            for widget in self.tab_sbkw.winfo_children():
                widget.destroy()
            self._init_sbkw_tab()
            self.sbkw_status.set_status("配置已重置为默认值", "idle")

    def reset_sp_kw_config(self):
        if messagebox.askyesno("确认", "是否重置SP_KW所有配置为默认值?"):
            for widget in self.tab_sp_kw.winfo_children():
                widget.destroy()
            self._init_sp_kw_tab()
            self.sp_kw_status.set_status("配置已重置为默认值", "idle")

    def reset_neg_keyword_config(self):
        if messagebox.askyesno("确认", "是否重置否定词根所有配置为默认值?"):
            for widget in self.tab_neg_keyword.winfo_children():
                widget.destroy()
            self._init_neg_keyword_tab()
            self.neg_keyword_status.set_status("配置已重置为默认值", "idle")

    # ===================== SBV：获取并验证配置 =====================
    def get_sbv_config(self):
        try:
            errors = []
            if not self.sbv_config["product_name"].get().strip():
                errors.append("广告名称不能为空")
            if not self.sbv_config["brand_entity_id"].get().strip():
                errors.append("品牌实体ID不能为空")
            if not self.sbv_config["video_asset_id"].get().strip():
                errors.append("视频资产ID不能为空")

            asins_text = self.sbv_config["asins"].get().strip()
            asins_list = [s.strip() for s in asins_text.split("\n") if s.strip()]
            if not asins_list:
                errors.append("请至少输入一个产品ASIN")
            else:
                for asin in asins_list:
                    if not asin.startswith("B0"):
                        errors.append(f"ASIN格式错误：{asin}")
                        break

            launch_date = self.sbv_config["launch_date"].get()
            if not launch_date.isdigit() or len(launch_date) != 8:
                errors.append("投放日期格式错误，应为YYYYMMDD")

            try:
                budget = float(self.sbv_config["budget"].get())
                if budget <= 0: errors.append("每日预算必须大于0")
            except ValueError:
                errors.append("每日预算必须是数字")

            try:
                bid_amount = float(self.sbv_config["bid_amount"].get())
                if bid_amount <= 0: errors.append("CPC竞价必须大于0")
            except ValueError:
                errors.append("CPC竞价必须是数字")

            try:
                campaign_loop_count = int(self.sbv_config["campaign_loop_count"].get())
                if campaign_loop_count <= 0: errors.append("Campaign循环数量必须大于0")
            except ValueError:
                errors.append("Campaign循环数量必须是整数")

            try:
                ad_group_per_campaign = int(self.sbv_config["ad_group_per_campaign"].get())
                if ad_group_per_campaign <= 0: errors.append("每Campaign广告组数必须大于0")
            except ValueError:
                errors.append("每Campaign广告组数必须是整数")

            keywords_broad = [s.strip() for s in self.sbv_config["keywords_broad"].get().split("\n") if s.strip()]
            keywords_phrase = [s.strip() for s in self.sbv_config["keywords_phrase"].get().split("\n") if s.strip()]
            if not keywords_broad and not keywords_phrase:
                errors.append("请至少输入一个关键词")

            output_file = self.sbv_config["output_file"].get()
            if not output_file:
                errors.append("输出文件名不能为空")

            if errors:
                messagebox.showerror("输入错误", "\n".join(errors))
                return None

            target_asins_list = [s.strip() for s in self.sbv_config["target_asins"].get().strip().split("\n") if s.strip()]
            negative_keywords_list = [s.strip() for s in self.sbv_config["keywords_negative"].get().strip().split("\n") if s.strip()]

            return {
                "product_name": self.sbv_config["product_name"].get(),
                "launch_date": launch_date, "budget": budget, "bid_amount": bid_amount,
                "brand_entity_id": self.sbv_config["brand_entity_id"].get(),
                "video_asset_id": self.sbv_config["video_asset_id"].get(),
                "asins": asins_list,
                "product_targeting": {"target_asins": target_asins_list},
                "keywords": {"broad": keywords_broad, "phrase": keywords_phrase, "negativePhrase": negative_keywords_list},
                "campaign_loop_count": campaign_loop_count,
                "ad_group_per_campaign": ad_group_per_campaign,
                "output_file": output_file
            }
        except Exception as e:
            messagebox.showerror("配置错误", f"配置转换出错: {str(e)}")
            return None

    # ===================== SP_商品：获取并验证配置 =====================
    def get_sp_product_config(self):
        try:
            errors = []
            if not self.sp_product_config["campaign_name"].get().strip():
                errors.append("活动名称不能为空")

            skus_list = [s.strip() for s in self.sp_product_config["sku_list"].get().strip().split("\n") if s.strip()]
            if not skus_list:
                errors.append("请至少输入一个SKU")
            elif len(skus_list) != len(set(skus_list)):
                errors.append("SKU列表中存在重复项")

            pt_expr_text = self.sp_product_config["base_pt_expression"].get().strip()
            if not pt_expr_text:
                errors.append("产品定位表达式不能为空")

            try:
                product_targeting_bid = float(self.sp_product_config["product_targeting_bid"].get())
                if product_targeting_bid <= 0: errors.append("CPC竞价必须大于0")
            except ValueError:
                errors.append("CPC竞价必须是数字")

            try:
                price_start = int(self.sp_product_config["price_start"].get())
                if price_start < 0: errors.append("起始价格不能为负数")
            except ValueError:
                errors.append("起始价格必须是整数")

            try:
                price_end_max = int(self.sp_product_config["price_end_max"].get())
                if price_end_max <= 0: errors.append("价格上限必须大于0")
            except ValueError:
                errors.append("价格上限必须是整数")

            try:
                price_step = int(self.sp_product_config["price_step"].get())
                if price_step <= 0: errors.append("价格步长必须大于0")
            except ValueError:
                errors.append("价格步长必须是整数")

            if price_start >= price_end_max:
                errors.append("起始价格必须小于价格上限")
            if price_step > (price_end_max - price_start):
                errors.append("价格步长不能超过价格范围")

            try:
                campaign_loop_count = int(self.sp_product_config["campaign_loop_count"].get())
                if campaign_loop_count <= 0: errors.append("Campaign循环数量必须大于0")
            except ValueError:
                errors.append("Campaign循环数量必须是整数")

            try:
                ad_group_per_campaign = int(self.sp_product_config["ad_group_per_campaign"].get())
                if ad_group_per_campaign <= 0: errors.append("每Campaign广告组数必须大于0")
            except ValueError:
                errors.append("每Campaign广告组数必须是整数")

            output_file = self.sp_product_config["output_file"].get()
            if not output_file: errors.append("输出文件名不能为空")

            if errors:
                messagebox.showerror("输入错误", "\n".join(errors))
                return None

            pt_expr_lines = [s.strip() for s in pt_expr_text.split("\n") if s.strip()]
            keywords_negative = [s.strip() for s in self.sp_product_config["keywords_negative"].get().strip().split("\n") if s.strip()]
            return {
                "campaign_name": self.sp_product_config["campaign_name"].get(),
                "product_targeting_bid": product_targeting_bid, "sku_list": skus_list,
                "base_pt_expression": pt_expr_lines,
                "price_start": price_start, "price_end_max": price_end_max, "price_step": price_step,
                "keywords_negative": keywords_negative,
                "campaign_loop_count": campaign_loop_count,
                "ad_group_per_campaign": ad_group_per_campaign,
                "output_file": output_file
            }
        except Exception as e:
            messagebox.showerror("配置错误", f"配置转换出错: {str(e)}")
            return None

    # ===================== SP_自动：获取并验证配置 =====================
    def get_sp_auto_config(self):
        try:
            errors = []
            if not self.sp_auto_config["campaign_name"].get().strip():
                errors.append("活动名称不能为空")

            skus_list = [s.strip() for s in self.sp_auto_config["sku_list"].get().strip().split("\n") if s.strip()]
            if not skus_list:
                errors.append("请至少输入一个SKU")
            elif len(skus_list) != len(set(skus_list)):
                errors.append("SKU列表中存在重复项")

            try:
                product_targeting_bid = float(self.sp_auto_config["product_targeting_bid"].get())
                if product_targeting_bid <= 0: errors.append("CPC竞价必须大于0")
            except ValueError:
                errors.append("CPC竞价必须是数字")

            try:
                campaign_loop_count = int(self.sp_auto_config["campaign_loop_count"].get())
                if campaign_loop_count <= 0: errors.append("Campaign循环数量必须大于0")
            except ValueError:
                errors.append("Campaign循环数量必须是整数")

            try:
                ad_group_per_campaign = int(self.sp_auto_config["ad_group_per_campaign"].get())
                if ad_group_per_campaign <= 0: errors.append("每Campaign广告组数必须大于0")
            except ValueError:
                errors.append("每Campaign广告组数必须是整数")

            output_file = self.sp_auto_config["output_file"].get()
            if not output_file: errors.append("输出文件名不能为空")

            if errors:
                messagebox.showerror("输入错误", "\n".join(errors))
                return None

            keywords_negative = [s.strip() for s in self.sp_auto_config["keywords_negative"].get().strip().split("\n") if s.strip()]
            return {
                "campaign_name": self.sp_auto_config["campaign_name"].get(),
                "product_targeting_bid": product_targeting_bid, "sku_list": skus_list,
                "keywords_negative": keywords_negative,
                "campaign_loop_count": campaign_loop_count,
                "ad_group_per_campaign": ad_group_per_campaign,
                "output_file": output_file
            }
        except Exception as e:
            messagebox.showerror("配置错误", f"配置转换出错: {str(e)}")
            return None

    # ===================== SB_KW：获取并验证配置 =====================
    def get_sbkw_config(self):
        try:
            errors = []
            try:
                campaign_loop_count = int(self.sbkw_config["campaign_loop_count"].get())
                if campaign_loop_count <= 0: errors.append("Campaign循环数量必须大于0")
            except ValueError:
                errors.append("Campaign循环数量必须是整数")

            try:
                ad_group_per_campaign = int(self.sbkw_config["ad_group_per_campaign"].get())
                if ad_group_per_campaign <= 0: errors.append("每个Campaign广告组数量必须大于0")
            except ValueError:
                errors.append("每个Campaign广告组数量必须是整数")

            try:
                budget = float(self.sbkw_config["budget"].get())
                if budget <= 0: errors.append("每日预算必须大于0")
            except ValueError:
                errors.append("每日预算必须是数字")

            try:
                bid_amount = float(self.sbkw_config["bid_amount"].get())
                if bid_amount <= 0: errors.append("出价金额必须大于0")
            except ValueError:
                errors.append("出价金额必须是数字")

            start_date = self.sbkw_config["start_date"].get()
            if not start_date.isdigit() or len(start_date) != 8:
                errors.append("开始日期必须是8位数字 (YYYYMMDD)")
            if not self.sbkw_config["campaign_name"].get().strip():
                errors.append("Campaign名称不能为空")
            if not self.sbkw_config["brand_entity_id"].get().strip():
                errors.append("品牌实体ID不能为空")

            landing_page_lines = [line.strip() for line in self.sbkw_config["landing_page_asins"].get().strip().split('\n') if line.strip()]
            if not landing_page_lines:
                errors.append("请至少输入一个Landing Page ASIN")
            else:
                for asin in landing_page_lines:
                    if not asin.startswith("B0"):
                        errors.append(f"ASIN格式错误：{asin}")
                        break

            keyword_lines = [line.strip() for line in self.sbkw_config["keyword_text"].get().strip().split('\n') if line.strip()]
            if not keyword_lines:
                errors.append("关键词不能为空")

            output_file = self.sbkw_config["output_file"].get()
            if not output_file: errors.append("输出文件名不能为空")

            if errors:
                messagebox.showerror("输入错误", "\n".join(errors))
                return None

            negative_keywords_list = [line.strip() for line in self.sbkw_config["negative_keywords"].get().strip().split('\n') if line.strip()]
            custom_image_id = self.sbkw_config["custom_image_id"].get().strip()
            custom_images = ""
            if custom_image_id:
                custom_images = json.dumps([{"assetId": custom_image_id, "crop": {"left": "0", "top": "0", "width": "1200", "height": "628"}}], separators=(',', ':'))

            return {
                "campaign_name_prefix": self.sbkw_config["campaign_name"].get(),
                "start_date": start_date, "brand_entity_id": self.sbkw_config["brand_entity_id"].get(),
                "budget": budget, "campaign_loop_count": campaign_loop_count,
                "ad_group_per_campaign": ad_group_per_campaign,
                "landing_page_asins_list": landing_page_lines,
                "landing_page_asins_str": ", ".join(landing_page_lines),
                "creative_asins_list": landing_page_lines,
                "creative_asins_str": ", ".join(landing_page_lines),
                "brand_name": self.sbkw_config["brand_name"].get(),
                "brand_logo_asset_id": self.sbkw_config["brand_logo_asset_id"].get(),
                "creative_headline": self.sbkw_config["creative_headline"].get(),
                "keyword_text_list": keyword_lines, "match_type": self.sbkw_config["match_type"].get(),
                "bid_amount": bid_amount, "negative_keywords": negative_keywords_list,
                "custom_images": custom_images, "output_file": output_file
            }
        except Exception as e:
            messagebox.showerror("配置错误", f"配置转换出错: {str(e)}")
            return None

    # ===================== SP_KW：获取并验证配置 =====================
    def get_sp_kw_config(self):
        try:
            errors = []
            if not self.sp_kw_config["campaign_name"].get().strip():
                errors.append("活动名称不能为空")

            try:
                daily_budget = float(self.sp_kw_config["daily_budget"].get())
                if daily_budget <= 0: errors.append("每日预算必须大于0")
            except ValueError:
                errors.append("每日预算必须是数字")

            start_date = self.sp_kw_config["start_date"].get()
            if not start_date.isdigit() or len(start_date) != 8:
                errors.append("投放日期格式错误，应为YYYYMMDD")

            try:
                campaign_loop_count = int(self.sp_kw_config["campaign_loop_count"].get())
                if campaign_loop_count <= 0: errors.append("Campaign循环数量必须大于0")
            except ValueError:
                errors.append("Campaign循环数量必须是整数")

            try:
                ad_group_per_campaign = int(self.sp_kw_config["ad_group_per_campaign"].get())
                if ad_group_per_campaign <= 0: errors.append("每Campaign广告组数必须大于0")
            except ValueError:
                errors.append("每Campaign广告组数必须是整数")

            skus_list = [s.strip() for s in self.sp_kw_config["sku_list"].get().strip().split("\n") if s.strip()]
            if not skus_list:
                errors.append("请至少输入一个SKU")
            elif len(skus_list) != len(set(skus_list)):
                errors.append("SKU列表中存在重复项")

            try:
                ad_group_default_bid = float(self.sp_kw_config["ad_group_default_bid"].get())
                if ad_group_default_bid <= 0: errors.append("广告组默认出价必须大于0")
            except ValueError:
                errors.append("广告组默认出价必须是数字")

            keyword_lines = [s.strip() for s in self.sp_kw_config["keyword_text"].get().strip().split("\n") if s.strip()]
            if not keyword_lines:
                errors.append("请至少输入一个关键词")

            match_type = self.sp_kw_config["match_type"].get()
            if match_type not in ["broad", "exact", "phrase"]:
                errors.append("匹配类型必须为broad/exact/phrase")

            try:
                bid_amount = float(self.sp_kw_config["bid_amount"].get())
                if bid_amount <= 0: errors.append("关键词出价必须大于0")
            except ValueError:
                errors.append("关键词出价必须是数字")

            try:
                placement_top = int(self.sp_kw_config["placement_top"].get())
                if placement_top < 0 or placement_top > 900: errors.append("Placement Top百分比应在0-900之间")
            except ValueError:
                errors.append("Placement Top必须是整数")

            try:
                placement_product_page = int(self.sp_kw_config["placement_product_page"].get())
                if placement_product_page < 0 or placement_product_page > 900: errors.append("Placement Product Page百分比应在0-900之间")
            except ValueError:
                errors.append("Placement Product Page必须是整数")

            try:
                placement_rest_of_search = int(self.sp_kw_config["placement_rest_of_search"].get())
                if placement_rest_of_search < 0 or placement_rest_of_search > 900: errors.append("Placement Rest Of Search百分比应在0-900之间")
            except ValueError:
                errors.append("Placement Rest Of Search必须是整数")

            try:
                placement_amazon_business = int(self.sp_kw_config["placement_amazon_business"].get())
                if placement_amazon_business < 0 or placement_amazon_business > 900: errors.append("Placement Amazon Business百分比应在0-900之间")
            except ValueError:
                errors.append("Placement Amazon Business必须是整数")

            output_file = self.sp_kw_config["output_file"].get()
            if not output_file: errors.append("输出文件名不能为空")

            if errors:
                messagebox.showerror("输入错误", "\n".join(errors))
                return None

            return {
                "campaign_name": self.sp_kw_config["campaign_name"].get(),
                "daily_budget": daily_budget,
                "start_date": start_date,
                "bidding_strategy": self.sp_kw_config["bidding_strategy"].get(),
                "campaign_loop_count": campaign_loop_count,
                "ad_group_per_campaign": ad_group_per_campaign,
                "sku_list": skus_list,
                "ad_group_default_bid": ad_group_default_bid,
                "keyword_text_list": keyword_lines,
                "match_type": match_type.capitalize(),
                "bid_amount": bid_amount,
                "placement_top": placement_top,
                "placement_product_page": placement_product_page,
                "placement_rest_of_search": placement_rest_of_search,
                "placement_amazon_business": placement_amazon_business,
                "output_file": output_file
            }
        except Exception as e:
            messagebox.showerror("配置错误", f"配置转换出错: {str(e)}")
            return None

    # ===================== 否定词根：获取并验证配置 =====================
    def get_neg_keyword_config(self):
        try:
            errors = []

            neg_type = self.neg_keyword_config["neg_type"].get()
            if neg_type not in ["SP", "SB"]:
                errors.append("否词类型必须为SP或SB")

            rows_data = self.neg_keyword_grid.get_data()
            if not rows_data:
                errors.append("请至少添加一行目标配置")
            else:
                for i, row in enumerate(rows_data):
                    if not row["campaign"]:
                        errors.append(f"第{i+1}行Campaign ID不能为空")
                    if not row["adgroups"]:
                        errors.append(f"第{i+1}行Ad Group ID不能为空")
                    if not row["keywords"]:
                        errors.append(f"第{i+1}行否定词根不能为空")

            neg_match_type = self.neg_keyword_config["neg_match_type"].get()
            if neg_match_type not in ["negativePhrase", "negativeExact"]:
                errors.append("匹配类型必须为negativePhrase或negativeExact")

            output_file = self.neg_keyword_config["output_file"].get()
            if not output_file:
                errors.append("输出文件名不能为空")

            if errors:
                messagebox.showerror("输入错误", "\n".join(errors))
                return None

            return {
                "neg_type": neg_type,
                "rows": rows_data,
                "neg_match_type": neg_match_type,
                "output_file": output_file
            }
        except Exception as e:
            messagebox.showerror("配置错误", f"配置转换出错: {str(e)}")
            return None

    # ===================== 生成CSV入口 =====================
    def generate_sbv_csv(self):
        try:
            config = self.get_sbv_config()
            if not config: return
            start_time = time.time()
            df = self.generate_ad_csv_integrated(config)
            elapsed = time.time() - start_time
            self.sbv_status.set_status(
                f"✅ 生成成功! 文件: {config['output_file']} | 记录数: {len(df)} | 耗时: {elapsed:.2f}秒", "success")
            messagebox.showinfo("成功", f"SBV文件已生成:\n{config['output_file']}")
        except Exception as e:
            self.sbv_status.set_status(f"❌ 错误: {str(e)}", "error")
            messagebox.showerror("错误", str(e))

    def generate_sp_product_csv(self):
        try:
            config = self.get_sp_product_config()
            if not config: return
            start_time = time.time()
            output_file, df, total_ad_groups, total_product_ads, total_pt_rows = self.generate_sp_product_bulk_table(config)
            elapsed = time.time() - start_time
            self.sp_product_status.set_status(
                f"✅ 生成成功! 文件: {output_file} | 记录数: {len(df)} | PT行数: {total_pt_rows} | 耗时: {elapsed:.2f}秒", "success")
            messagebox.showinfo("成功", f"SP_商品文件已生成:\n{output_file}")
        except Exception as e:
            self.sp_product_status.set_status(f"❌ 错误: {str(e)}", "error")
            messagebox.showerror("错误", str(e))

    def generate_sp_auto_csv(self):
        try:
            config = self.get_sp_auto_config()
            if not config: return
            start_time = time.time()
            output_file, df, total_ad_groups, total_product_ads, total_pt_rows = self.generate_sp_auto_bulk_table(config)
            elapsed = time.time() - start_time
            self.sp_auto_status.set_status(
                f"✅ 生成成功! 文件: {output_file} | 记录数: {len(df)} | PT行数: {total_pt_rows} | 耗时: {elapsed:.2f}秒", "success")
            messagebox.showinfo("成功", f"SP_自动文件已生成:\n{output_file}")
        except Exception as e:
            self.sp_auto_status.set_status(f"❌ 错误: {str(e)}", "error")
            messagebox.showerror("错误", str(e))

    def generate_sbkw_csv(self):
        try:
            config = self.get_sbkw_config()
            if not config: return
            start_time = time.time()
            df = self._create_sbkw_multi_campaign_dataframe(config)
            output_path = config["output_file"]
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            elapsed = time.time() - start_time
            self.sbkw_status.set_status(
                f"✅ 生成成功! 文件: {output_path} | 记录数: {len(df)} | 耗时: {elapsed:.2f}秒", "success")
            messagebox.showinfo("成功", f"SB_KW文件已生成:\n{output_path}")
        except Exception as e:
            self.sbkw_status.set_status(f"❌ 错误: {str(e)}", "error")
            messagebox.showerror("错误", str(e))

    def generate_sp_kw_csv(self):
        try:
            config = self.get_sp_kw_config()
            if not config: return
            start_time = time.time()
            output_file, df, total_ad_groups, total_product_ads, total_keyword_rows = self.generate_sp_kw_bulk_table(config)
            elapsed = time.time() - start_time
            self.sp_kw_status.set_status(
                f"✅ 生成成功! 文件: {output_file} | 记录数: {len(df)} | 关键词行数: {total_keyword_rows} | 耗时: {elapsed:.2f}秒", "success")
            messagebox.showinfo("成功", f"SP_KW文件已生成:\n{output_file}")
        except Exception as e:
            self.sp_kw_status.set_status(f"❌ 错误: {str(e)}", "error")
            messagebox.showerror("错误", str(e))

    def generate_neg_keyword_csv(self):
        try:
            config = self.get_neg_keyword_config()
            if not config: return
            start_time = time.time()

            if config["neg_type"] == "SP":
                df = self._generate_sp_negative_keywords(config)
            else:
                df = self._generate_sb_negative_keywords(config)

            output_path = config["output_file"]
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            df.to_csv(output_path, index=False, encoding='utf-8-sig')

            elapsed = time.time() - start_time
            self.neg_keyword_status.set_status(
                f"✅ 生成成功! 文件: {output_path} | 记录数: {len(df)} | 耗时: {elapsed:.2f}秒", "success")
            messagebox.showinfo("成功", f"否定词根文件已生成:\n{output_path}")
        except Exception as e:
            self.neg_keyword_status.set_status(f"❌ 错误: {str(e)}", "error")
            messagebox.showerror("错误", str(e))

    # ===================== SBV核心生成逻辑 =====================
    def generate_ad_csv_integrated(self, config):
        if isinstance(config["launch_date"], int):
            date_str = str(config["launch_date"])
        elif isinstance(config["launch_date"], datetime):
            date_str = config["launch_date"].strftime("%Y%m%d")
        else:
            date_str = config["launch_date"]

        main_keyword = ""
        if config["keywords"].get("broad") and len(config["keywords"]["broad"]) > 0:
            main_keyword = config["keywords"]["broad"][0].replace(" ", "_")
        elif config["keywords"].get("phrase") and len(config["keywords"]["phrase"]) > 0:
            main_keyword = config["keywords"]["phrase"][0].replace(" ", "_")

        columns = ["Product", "Entity", "Operation", "Campaign ID", "Portfolio ID",
                    "Ad Group ID", "Ad ID", "Keyword ID", "Product Targeting ID", "Campaign Name", "Ad Group Name", "Ad Name",
                    "Start Date", "End Date", "State", "Brand Entity ID", "Budget Type",
                    "Budget", "Bid Optimization", "Product Location", "Bid", "Placement",
                    "Percentage", "Keyword Text", "Match Type", "Native Language Keyword",
                    "Native Language Locale", "Product Targeting Expression",
                    "Landing Page URL", "Landing Page ASINs", "Landing Page Type",
                    "Brand Name", "Consent To Translate", "Brand Logo Asset ID",
                    "Brand Logo Crop", "Custom Images",
                    "Creative Headline", "Creative ASINs", "Video Asset IDs", "Subpages"]

        row_templates = {k: dict.fromkeys(columns, "") for k in
                         ["campaign", "adjustment", "ad_group", "video_ad", "keyword", "negative", "product_targeting"]}

        for k in ["campaign", "ad_group", "video_ad", "keyword", "negative", "product_targeting"]:
            row_templates[k]["State"] = "enabled"
        row_templates["adjustment"]["State"] = ""

        row_templates["adjustment"].update({"Entity": "Bidding Adjustment by Placement", "Percentage": 0.0})
        row_templates["ad_group"].update({"Entity": "Ad group"})
        row_templates["video_ad"].update({"Entity": "Video ad", "Landing Page Type": "Product detail page",
                                           "Consent To Translate": "False", "Video Asset IDs": config["video_asset_id"]})
        row_templates["keyword"].update({"Entity": "Keyword", "Bid": config["bid_amount"]})
        row_templates["negative"].update({"Entity": "Negative Keyword"})
        row_templates["product_targeting"].update({"Entity": "Product Targeting", "Bid": config["bid_amount"]})

        all_data = []
        pt_asins = config["product_targeting"].get("target_asins", [])

        for campaign_idx in range(config["campaign_loop_count"]):
            campaign_id = f"{config['product_name']}_{date_str}_{campaign_idx + 1}"
            campaign_name = campaign_id

            for template in row_templates.values():
                template.update({"Product": "Sponsored Brands", "Operation": "Create", "Campaign ID": campaign_id, "Portfolio ID": ""})

            row_templates["campaign"].update({"Entity": "Campaign", "Campaign Name": campaign_name, "Start Date": date_str,
                                               "Brand Entity ID": config["brand_entity_id"], "Budget Type": "Daily",
                                               "Budget": config["budget"], "Bid Optimization": "False"})

            all_data.append(row_templates["campaign"].copy())
            for placement in ["Home", "Other", "Detail Page"]:
                row = row_templates["adjustment"].copy()
                row["Placement"] = placement
                all_data.append(row)

            global_idx = 1

            for asin in config["asins"]:
                targets = pt_asins if pt_asins else [None]
                for target_asin in targets:
                    for ad_group_idx in range(config["ad_group_per_campaign"]):
                        ad_group_id = f"{asin}_{main_keyword}_{global_idx}" if main_keyword else f"{asin}_{global_idx}"
                        ad_group_row = row_templates["ad_group"].copy()
                        ad_group_row.update({"Ad Group ID": ad_group_id, "Ad Group Name": ad_group_id, "Ad Name": ad_group_id})
                        all_data.append(ad_group_row)

                        video_row = row_templates["video_ad"].copy()
                        video_row.update({"Ad Group ID": ad_group_id, "Ad Name": ad_group_id, "Landing Page ASINs": asin, "Creative ASINs": asin})
                        all_data.append(video_row)

                        for match_type in ["broad", "phrase"]:
                            for keyword in config["keywords"].get(match_type, []):
                                keyword_row = row_templates["keyword"].copy()
                                keyword_row.update({"Ad Group ID": ad_group_id, "Ad Name": ad_group_id, "Keyword Text": keyword, "Match Type": match_type})
                                all_data.append(keyword_row)

                        for keyword in config["keywords"].get("negativePhrase", []):
                            negative_row = row_templates["negative"].copy()
                            negative_row.update({"Ad Group ID": ad_group_id, "Ad Name": ad_group_id, "Keyword Text": keyword, "Match Type": "negativePhrase"})
                            all_data.append(negative_row)

                        if target_asin:
                            for expr_type in ["asin", "asin-expanded"]:
                                pt_row = row_templates["product_targeting"].copy()
                                pt_row.update({"Ad Group ID": ad_group_id, "Ad Name": ad_group_id,
                                               "Product Targeting Expression": f'{expr_type}="{target_asin}"'})
                                all_data.append(pt_row)
                        global_idx += 1

        df = pd.DataFrame(all_data, columns=columns)
        df.to_csv(config["output_file"], index=False, encoding='utf-8-sig')
        return df

    # ===================== SP_商品核心生成逻辑 =====================
    def generate_sp_product_bulk_table(self, config):
        rows = []
        header = ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID",
                   "Portfolio ID", "Ad ID", "Keyword ID", "Product Targeting ID",
                   "Campaign Name", "Ad Group Name", "Start Date", "End Date",
                   "Targeting Type", "State", "Daily Budget", "SKU(注意更新SKU)",
                   "Ad Group Default Bid", "Bid", "Keyword Text",
                   "Native Language Keyword", "Native Language Locale", "Match Type",
                   "Bidding Strategy", "Placement", "Percentage", "Product Targeting Expression"]

        daily_budget = 5.0
        start_date = datetime.today().strftime("%Y%m%d")
        total_ad_groups = 0
        total_product_ads = 0
        total_pt_rows = 0

        for campaign_idx in range(config["campaign_loop_count"]):
            campaign_id = f"{config['campaign_name']}_{campaign_idx + 1}"
            campaign_name = campaign_id

            rows.append(["Sponsored Products", "Campaign", "Create", campaign_id, "", "", "", "", "", campaign_name,
                          "", start_date, "", "MANUAL", "enabled", daily_budget, "", "", "", "", "", "", "", "Fixed bid", "", "", ""])

            for placement, percentage in zip(["placementTop", "placementProductPage", "placementRestOfSearch"], [0, 0, 0]):
                rows.append(["Sponsored Products", "Bidding Adjustment", "Create", campaign_id, "", "", "", "", "", "",
                              "", "", "", "", "", "", "", "", "", "", "", "", "", "", placement, percentage, ""])

            for ad_group_idx in range(config["ad_group_per_campaign"]):
                ad_group_id = f"{campaign_id}-{ad_group_idx + 1}"
                rows.append(["Sponsored Products", "Ad Group", "Create", campaign_id, ad_group_id, "", "", "", "", "",
                              ad_group_id, "", "", "", "enabled", "", "", 0.75, "", "", "", "", "", "", "", "", ""])
                total_ad_groups += 1

                for sku in config["sku_list"]:
                    rows.append(["Sponsored Products", "Product Ad", "Create", campaign_id, ad_group_id, "", "", "", "", "",
                                  "", "", "", "", "enabled", "", sku, "", "", "", "", "", "", "", "", "", ""])
                    total_product_ads += 1

                for neg_kw in config.get("keywords_negative", []):
                    rows.append(["Sponsored Products", "Negative Keyword", "Create", campaign_id, ad_group_id, "", "", "", "", "",
                                  ad_group_id, "", "", "", "enabled", "", "", "", "", neg_kw, "", "", "", "negativePhrase", "", "", ""])

                pt_config = config["base_pt_expression"]
                if isinstance(pt_config, list) and pt_config and isinstance(pt_config[0], str) and pt_config[0].startswith("B0"):
                    for asin in pt_config:
                        if asin.startswith("B0"):
                            for expr in [f'asin="{asin}"', f'asin-expanded="{asin}"']:
                                rows.append(["Sponsored Products", "Product Targeting", "Create", campaign_id, ad_group_id, "", "", "", "", "",
                                              "", "", "", "", "enabled", "", "", "", config["product_targeting_bid"], "", "", "", "", "", "", "", expr])
                                total_pt_rows += 2
                elif isinstance(pt_config, list) and pt_config and isinstance(pt_config[0], str) and "category" in pt_config[0]:
                    for single_category_expr in pt_config:
                        if "category" in single_category_expr:
                            start_price = config["price_start"]
                            while start_price < config["price_end_max"]:
                                end_price = start_price + config["price_step"]
                                full_expr = f"{single_category_expr} price= {start_price}-{end_price}"
                                rows.append(["Sponsored Products", "Product Targeting", "Create", campaign_id, ad_group_id, "", "", "", "", "",
                                              "", "", "", "", "enabled", "", "", "", config["product_targeting_bid"], "", "", "", "", "", "", "", full_expr])
                                start_price += config["price_step"]
                                total_pt_rows += 1
                else:
                    exprs = pt_config if isinstance(pt_config, list) else [pt_config]
                    for expr in exprs:
                        rows.append(["Sponsored Products", "Product Targeting", "Create", campaign_id, ad_group_id, "", "", "", "", "",
                                      "", "", "", "", "enabled", "", "", "", config["product_targeting_bid"], "", "", "", "", "", "", "", expr])
                        total_pt_rows += 1

        df = pd.DataFrame(rows, columns=header)
        df.to_csv(config["output_file"], index=False, encoding='utf-8-sig', quoting=csv.QUOTE_ALL)
        return config["output_file"], df, total_ad_groups, total_product_ads, total_pt_rows

    # ===================== SP_自动核心生成逻辑 =====================
    def generate_sp_auto_bulk_table(self, config):
        rows = []
        header = ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID",
                   "Portfolio ID", "Ad ID", "Keyword ID", "Product Targeting ID",
                   "Campaign Name", "Ad Group Name", "Start Date", "End Date",
                   "Targeting Type", "State", "Daily Budget", "SKU(注意更新SKU)",
                   "Ad Group Default Bid", "Bid", "Keyword Text",
                   "Native Language Keyword", "Native Language Locale", "Match Type",
                   "Bidding Strategy", "Placement", "Percentage", "Product Targeting Expression"]

        daily_budget = 5.0
        start_date = datetime.today().strftime("%Y%m%d")
        total_ad_groups = 0
        total_product_ads = 0
        total_pt_rows = 0

        for campaign_idx in range(config["campaign_loop_count"]):
            campaign_id = f"{config['campaign_name']}_{campaign_idx + 1}"
            campaign_name = campaign_id

            rows.append(["Sponsored Products", "Campaign", "Create", campaign_id, "", "", "", "", "", campaign_name,
                          "", start_date, "", "AUTO", "enabled", daily_budget, "", "", "", "", "", "", "", "Fixed bid", "", "", ""])

            for placement, percentage in zip(["placementTop", "placementProductPage", "placementRestOfSearch"], [0, 0, 0]):
                rows.append(["Sponsored Products", "Bidding Adjustment", "Create", campaign_id, "", "", "", "", "", "",
                              "", "", "", "", "", "", "", "", "", "", "", "", "", "", placement, percentage, ""])

            for ad_group_idx in range(config["ad_group_per_campaign"]):
                ad_group_id = f"{campaign_id}-{ad_group_idx + 1}"
                rows.append(["Sponsored Products", "Ad Group", "Create", campaign_id, ad_group_id, "", "", "", "", "",
                              ad_group_id, "", "", "", "enabled", "", "", 0.75, "", "", "", "", "", "", "", "", ""])
                total_ad_groups += 1

                for sku in config["sku_list"]:
                    rows.append(["Sponsored Products", "Product Ad", "Create", campaign_id, ad_group_id, "", "", "", "", "",
                                  "", "", "", "", "enabled", "", sku, "", "", "", "", "", "", "", "", "", ""])
                    total_product_ads += 1

                for neg_kw in config.get("keywords_negative", []):
                    rows.append(["Sponsored Products", "Negative Keyword", "Create", campaign_id, ad_group_id, "", "", "", "", "",
                                  ad_group_id, "", "", "", "enabled", "", "", "", "", neg_kw, "", "", "", "negativePhrase", "", "", ""])

                for match_type in ["close-match", "loose-match", "substitutes", "complements"]:
                    rows.append(["Sponsored Products", "Product Targeting", "Create", campaign_id, ad_group_id, "", "", "", "", "",
                                  "", "", "", "", "enabled", "", "", "", config["product_targeting_bid"], "", "", "", "", "", "", "", match_type])
                    total_pt_rows += 1

        df = pd.DataFrame(rows, columns=header)
        df.to_csv(config["output_file"], index=False, encoding='utf-8-sig', quoting=csv.QUOTE_ALL)
        return config["output_file"], df, total_ad_groups, total_product_ads, total_pt_rows

    # ===================== SP_KW：关键词投放核心生成逻辑 =====================
    def generate_sp_kw_bulk_table(self, config):
        rows = []
        header = ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID",
                   "Portfolio ID", "Ad ID", "Keyword ID", "Product Targeting ID",
                   "Campaign Name", "Ad Group Name", "Start Date", "End Date",
                   "Targeting Type", "State", "Daily Budget", "SKU",
                   "Ad Group Default Bid", "Bid", "Keyword Text",
                   "Native Language Keyword", "Native Language Locale", "Match Type",
                   "Bidding Strategy", "Placement", "Percentage", "Product Targeting Expression"]

        total_ad_groups = 0
        total_product_ads = 0
        total_keyword_rows = 0

        for campaign_idx in range(config["campaign_loop_count"]):
            campaign_id = f"{config['campaign_name']}_{campaign_idx + 1}"
            campaign_name = campaign_id

            rows.append(["Sponsored Products", "Campaign", "", campaign_id, "", "", "", "", "", campaign_name,
                          "", config["start_date"], "", "Manual", "enabled", config["daily_budget"], "", "", "", "", "", "", "", config["bidding_strategy"], "", "", ""])

            for placement, percentage in zip(
                ["Placement Top", "Placement Product Page", "Placement Rest Of Search", "Placement Amazon Business"],
                [config["placement_top"], config["placement_product_page"], config["placement_rest_of_search"], config["placement_amazon_business"]]
            ):
                rows.append(["Sponsored Products", "Bidding Adjustment", "", campaign_id, "", "", "", "", "", "",
                              "", "", "", "", "", "", "", "", "", "", "", "", "", config["bidding_strategy"], placement, percentage, ""])

            for ad_group_idx in range(config["ad_group_per_campaign"]):
                ad_group_id = f"{campaign_id}-{ad_group_idx + 1}"
                rows.append(["Sponsored Products", "Ad Group", "", campaign_id, ad_group_id, "", "", "", "", "",
                              ad_group_id, "", "", "", "enabled", "", "", config["ad_group_default_bid"], "", "", "", "", "", "", "", "", ""])
                total_ad_groups += 1

                for sku in config["sku_list"]:
                    rows.append(["Sponsored Products", "Product Ad", "", campaign_id, ad_group_id, "", "", "", "", "",
                                  "", "", "", "", "enabled", "", sku, "", "", "", "", "", "", "", "", "", ""])
                    total_product_ads += 1

                for keyword_text in config["keyword_text_list"]:
                    rows.append(["Sponsored Products", "Keyword", "", campaign_id, ad_group_id, "", "", "", "", "",
                                  "", "", "", "", "enabled", "", "", "", config["bid_amount"], keyword_text, "", "", config["match_type"], "", "", "", ""])
                    total_keyword_rows += 1

        df = pd.DataFrame(rows, columns=header)
        df.to_csv(config["output_file"], index=False, encoding='utf-8-sig', quoting=csv.QUOTE_ALL)
        return config["output_file"], df, total_ad_groups, total_product_ads, total_keyword_rows

    # ===================== SB_KW：多Campaign生成核心逻辑 =====================
    def _create_sbkw_multi_campaign_dataframe(self, config):
        columns = ["Product", "Entity", "Operation", "Campaign ID", "Portfolio ID",
                    "Ad Group ID", "Ad ID", "Keyword ID", "Product Targeting ID",
                    "Campaign Name", "Ad Group Name", "Ad Name", "Start Date", "End Date",
                    "State", "Brand Entity ID", "Budget Type", "Budget", "Bid Optimization",
                    "Product Location", "Bid", "Placement", "Percentage", "Keyword Text",
                    "Match Type", "Native Language Keyword", "Native Language Locale",
                    "Product Targeting Expression", "Landing Page URL", "Landing Page ASINs",
                    "Landing Page Type", "Brand Name", "Consent To Translate",
                    "Brand Logo Asset ID", "Brand Logo Crop", "Custom Images",
                    "Creative Headline", "Creative ASINs", "Video Asset IDs", "Subpages"]

        all_rows = []
        for campaign_idx in range(config["campaign_loop_count"]):
            campaign_id = f"{config['campaign_name_prefix']}_{campaign_idx + 1}"
            campaign_row = dict.fromkeys(columns, "")
            campaign_row.update({"Product": "Sponsored Brands", "Entity": "Campaign", "Operation": "Create",
                                  "Campaign ID": campaign_id, "Campaign Name": campaign_id, "Start Date": config["start_date"],
                                  "State": "enabled", "Brand Entity ID": config["brand_entity_id"],
                                  "Budget Type": "Daily", "Budget": config["budget"], "Bid Optimization": "False"})
            all_rows.append(campaign_row)

            for placement in ["Home", "Other", "Detail Page"]:
                adjustment_row = dict.fromkeys(columns, "")
                adjustment_row.update({"Product": "Sponsored Brands", "Entity": "Bidding Adjustment by Placement",
                                        "Operation": "Create", "Campaign ID": campaign_id, "Placement": placement, "Percentage": 0.0})
                all_rows.append(adjustment_row)

            for ad_group_idx in range(config["ad_group_per_campaign"]):
                ad_group_id = f"广告组-{campaign_idx + 1}-{ad_group_idx + 1}"
                ad_group_row = dict.fromkeys(columns, "")
                ad_group_row.update({"Product": "Sponsored Brands", "Entity": "Ad group", "Operation": "Create",
                                      "Campaign ID": campaign_id, "Ad Group ID": ad_group_id, "Ad Group Name": ad_group_id, "State": "enabled"})
                all_rows.append(ad_group_row)

                product_row = dict.fromkeys(columns, "")
                product_row.update({"Product": "Sponsored Brands", "Entity": "Product Collection Ad", "Operation": "Create",
                                     "Campaign ID": campaign_id, "Ad Group ID": ad_group_id, "Ad Name": ad_group_id, "State": "enabled",
                                     "Landing Page ASINs": config["landing_page_asins_str"], "Brand Name": config["brand_name"],
                                     "Consent To Translate": "False", "Brand Logo Asset ID": config["brand_logo_asset_id"],
                                     "Custom Images": config["custom_images"], "Creative Headline": config["creative_headline"],
                                     "Creative ASINs": config["creative_asins_str"]})
                all_rows.append(product_row)

                for keyword_text in config["keyword_text_list"]:
                    keyword_row = dict.fromkeys(columns, "")
                    keyword_row.update({"Product": "Sponsored Brands", "Entity": "Keyword", "Operation": "Create",
                                         "Campaign ID": campaign_id, "Ad Group ID": ad_group_id, "Ad Name": ad_group_id,
                                         "State": "enabled", "Bid": config["bid_amount"], "Keyword Text": keyword_text, "Match Type": config["match_type"]})
                    all_rows.append(keyword_row)

                for negative_keyword in config["negative_keywords"]:
                    negative_row = dict.fromkeys(columns, "")
                    negative_row.update({"Product": "Sponsored Brands", "Entity": "Negative Keyword", "Operation": "Create",
                                          "Campaign ID": campaign_id, "Ad Group ID": ad_group_id, "Ad Name": ad_group_id,
                                          "State": "enabled", "Keyword Text": negative_keyword, "Match Type": "negativePhrase"})
                    all_rows.append(negative_row)

        return pd.DataFrame(all_rows, columns=columns)

    # ===================== 否定词根：SP模板生成 =====================
    def _generate_sp_negative_keywords(self, config):
        """生成SP否定关键词（27列SP模板）"""
        header = ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID",
                   "Portfolio ID", "Ad ID", "Keyword ID", "Product Targeting ID",
                   "Campaign Name", "Ad Group Name", "Start Date", "End Date",
                   "Targeting Type", "State", "Daily Budget", "SKU(注意更新SKU)",
                   "Ad Group Default Bid", "Bid", "Keyword Text",
                   "Native Language Keyword", "Native Language Locale", "Match Type",
                   "Bidding Strategy", "Placement", "Percentage", "Product Targeting Expression"]

        rows = []
        match_type = config["neg_match_type"]

        for row_data in config["rows"]:
            campaign_id = row_data["campaign"]
            for adgroup in row_data["adgroups"]:
                for keyword in row_data["keywords"]:
                    rows.append(["Sponsored Products", "Negative Keyword", "Create", campaign_id, adgroup, "", "", "", "", "",
                                  adgroup, "", "", "", "enabled", "", "", "", "", keyword, "", "", "", match_type, "", "", ""])

        return pd.DataFrame(rows, columns=header)

    # ===================== 否定词根：SB模板生成 =====================
    def _generate_sb_negative_keywords(self, config):
        """生成SB否定关键词（40列SB模板）"""
        columns = ["Product", "Entity", "Operation", "Campaign ID", "Portfolio ID",
                    "Ad Group ID", "Ad ID", "Keyword ID", "Product Targeting ID",
                    "Campaign Name", "Ad Group Name", "Ad Name", "Start Date", "End Date",
                    "State", "Brand Entity ID", "Budget Type", "Budget", "Bid Optimization",
                    "Product Location", "Bid", "Placement", "Percentage", "Keyword Text",
                    "Match Type", "Native Language Keyword", "Native Language Locale",
                    "Product Targeting Expression", "Landing Page URL", "Landing Page ASINs",
                    "Landing Page Type", "Brand Name", "Consent To Translate",
                    "Brand Logo Asset ID", "Brand Logo Crop", "Custom Images",
                    "Creative Headline", "Creative ASINs", "Video Asset IDs", "Subpages"]

        all_rows = []
        match_type = config["neg_match_type"]

        for row_data in config["rows"]:
            campaign_id = row_data["campaign"]
            for adgroup in row_data["adgroups"]:
                for keyword in row_data["keywords"]:
                    row = dict.fromkeys(columns, "")
                    row.update({
                        "Product": "Sponsored Brands",
                        "Entity": "Negative Keyword",
                        "Operation": "Create",
                        "Campaign ID": campaign_id,
                        "Ad Group ID": adgroup,
                        "Ad Name": adgroup,
                        "State": "enabled",
                        "Keyword Text": keyword,
                        "Match Type": match_type
                    })
                    all_rows.append(row)

        return pd.DataFrame(all_rows, columns=columns)


if __name__ == "__main__":
    root = ctk.CTk()
    app = AmazonAdBulkGenerator(root)
    root.mainloop()
