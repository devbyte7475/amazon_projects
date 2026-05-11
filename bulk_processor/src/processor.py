"""
数据处理核心模块
"""
import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional, Callable


class BulkDataProcessor:
    """亚马逊广告数据处理器"""
    
    def __init__(self, folder_path: str, config: Dict = None):
        """
        初始化处理器
        
        Args:
            folder_path: 包含 bulk Excel 文件的文件夹路径
            config: 配置参数
        """
        self.folder_path = Path(folder_path)
        self.config = config or {}
        
        self.sheet_map = {
            "Sponsored Products Campaigns": "sp",
            "SB Multi Ad Group Campaigns": "sb",
            "Sponsored Display Campaigns": "sd"
        }
        
        self.join_cols_map = {
            "sp": ["Entity", "Campaign ID", "Ad Group ID", "Ad ID", "Keyword ID", "Product Targeting ID", "Placement"],
            "sb": ["Entity", "Campaign ID", "Ad Group ID", "Ad ID", "Keyword ID", "Placement"],
            "sd": ["Entity", "Campaign ID", "Ad Group ID", "Ad ID", "Targeting ID"]
        }
        
        self.target_cols = [
            "Impressions", "Clicks", "Click-through Rate", "Spend", "Sales",
            "Orders", "Units", "Conversion Rate", "ACOS", "CPC", "ROAS"
        ]
        
        self.thresholds = self.config.get("thresholds", {
            "impressions": 4200,
            "ctr": 0.0045,
            "cvr": 0.1,
            "acos": 0.3
        })
        
        self.entity_numeric_map = {
            "Product Targeting": 4,
            "Product Ad": 5,
            "Negative Product Targeting": 8,
            "Negative Keyword": 7,
            "Keyword": 4,
            "Campaign Negative Keyword": 6,
            "Campaign": 1,
            "Bidding Adjustment": 2,
            "Ad Group": 3
        }
    
    def extract_start_date(self, file_path: str) -> datetime:
        """提取文件名中的起始日期"""
        filename = os.path.basename(file_path)
        parts = filename.split("-")
        if len(parts) >= 3 and len(parts[2]) == 8:
            return datetime.strptime(parts[2], "%Y%m%d")
        raise ValueError(f"文件名格式错误，无法提取日期：{filename}")
    
    def create_unique_key_vectorized(self, df: pd.DataFrame, cols: List[str], sep: str = "|") -> pd.DataFrame:
        """向量化生成唯一键"""
        key_parts = []
        for col in cols:
            col_values = df[col].astype(str).values
            col_values = np.where(col_values == 'nan', '', col_values)
            key_parts.append(col_values)
        
        unique_keys = np.full(len(df), '', dtype=object)
        for i, part in enumerate(key_parts):
            if i == 0:
                unique_keys = part.copy()
            else:
                unique_keys = unique_keys + sep + part
        
        df['unique_key'] = unique_keys
        return df
    
    def find_excel_files(self) -> Tuple[str, str]:
        """查找并识别新旧Excel文件"""
        file_pattern = str(self.folder_path / "bulk-*.xlsx")
        files = glob.glob(file_pattern)
        
        if len(files) != 2:
            raise ValueError(f"目标文件夹下需且仅需放2个bulk工作簿，当前找到{len(files)}个！")
        
        files_sorted = sorted(files, key=self.extract_start_date)
        old_file, new_file = files_sorted[0], files_sorted[1]
        
        return old_file, new_file
    
    def load_single_sheet(self, file_path: str, sheet_fullname: str, sheet_abbr: str, prefix: str, join_cols: List[str]) -> Tuple[str, pd.DataFrame]:
        """加载单个sheet"""
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_fullname)
            df = self.create_unique_key_vectorized(df, join_cols)
            return f"{prefix}_{sheet_abbr}", df
        except Exception as e:
            return f"{prefix}_{sheet_abbr}", pd.DataFrame()
    
    def load_sheets_parallel(self, file_path: str, prefix: str, progress_callback: Callable = None) -> Dict[str, pd.DataFrame]:
        """并行加载Excel文件的所有sheet"""
        result = {}
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for sheet_fullname, sheet_abbr in self.sheet_map.items():
                future = executor.submit(
                    self.load_single_sheet,
                    file_path, sheet_fullname, sheet_abbr, prefix, self.join_cols_map[sheet_abbr]
                )
                futures.append(future)
            
            for future in as_completed(futures):
                key, df = future.result()
                result[key] = df
                if progress_callback and not df.empty:
                    progress_callback(f"加载 {key}: {len(df)} 行")
        
        return result
    
    def merge_old_new_data(self, df_new: pd.DataFrame, df_old: pd.DataFrame) -> pd.DataFrame:
        """合并新旧数据"""
        old_match_cols = ["unique_key"] + [col for col in self.target_cols if col in df_old.columns]
        df_old_filtered = df_old[old_match_cols].copy()
        
        rename_map = {col: f"{col}_old" for col in old_match_cols if col != "unique_key"}
        df_old_filtered.rename(columns=rename_map, inplace=True)
        
        df_merged = pd.merge(df_new, df_old_filtered, on="unique_key", how="left")
        
        return df_merged
    
    def calculate_growth_vectorized(self, df: pd.DataFrame, target_cols: List[str], old_suffix: str = "_old", growth_suffix: str = "_环比") -> pd.DataFrame:
        """向量化计算环比"""
        growth_cols = []
        
        for col in target_cols:
            old_col = f"{col}{old_suffix}"
            if old_col not in df.columns:
                continue
            
            new_vals = pd.to_numeric(df[col], errors="coerce").values
            old_vals = pd.to_numeric(df[old_col], errors="coerce").values
            
            old_vals_safe = np.where(old_vals == 0, np.nan, old_vals)
            
            growth_col = f"{col}{growth_suffix}"
            growth_vals = (new_vals / old_vals_safe) - 1
            growth_vals = np.where(np.isinf(growth_vals), np.nan, growth_vals)
            
            df[growth_col] = growth_vals
            growth_cols.append(growth_col)
        
        non_growth_cols = [c for c in df.columns if not c.endswith(growth_suffix)]
        df = df[non_growth_cols + growth_cols]
        
        for col in growth_cols:
            vals = pd.to_numeric(df[col], errors='coerce')
            mask = pd.notna(vals)
            result = pd.Series(index=df.index, dtype=object)
            result[~mask] = np.nan
            result[mask] = (vals[mask] * 100).round(0).astype(int).astype(str) + '%'
            df[col] = result
        
        return df
    
    def add_entity_columns_vectorized(self, df: pd.DataFrame, ad_type: str) -> pd.DataFrame:
        """向量化添加实体列"""
        if ad_type == "sp":
            expr_col = "Product Targeting Expression"
            if expr_col in df.columns:
                df["asintarget"] = df[expr_col].astype(str).str.split("=", n=1).str[0].str.title()
            col_list1 = ['SKU', 'Targeting Type', 'Match Type', 'Placement', 'asintarget']
            col_list2 = ['ASIN (Informational only)', 'Keyword Text', 
                        'Percentage', 'Resolved Product Targeting Expression (Informational only)']
        elif ad_type == "sb":
            expr_col = "Resolved Product Targeting Expression (Informational only)"
            if expr_col in df.columns:
                df["asintarget_sb"] = df[expr_col].astype(str).str.split("=", n=1).str[0].str.title()
            col_list1 = ['Placement', 'Match Type', 'asintarget_sb']
            col_list2 = ['Keyword Text', 'Resolved Product Targeting Expression (Informational only)']
        else:
            expr_col = "Resolved Targeting Expression (Informational only)"
            if expr_col in df.columns:
                df["asintarget_sd"] = df[expr_col].astype(str).str.split("=", n=1).str[0].str.title()
            col_list1 = ['SKU', 'Bid Optimization', 'asintarget_sd', 'Cost Type']
            col_list2 = ['ASIN (Informational only)', 'Resolved Targeting Expression (Informational only)']
        
        col_list1_valid = [col for col in col_list1 if col in df.columns]
        col_list2_valid = [col for col in col_list2 if col in df.columns]
        
        if col_list1_valid:
            df["Entity2"] = self._concat_columns_vectorized(df, col_list1_valid)
        else:
            df["Entity2"] = ""
        
        if col_list2_valid:
            df["Entity3"] = self._concat_columns_vectorized(df, col_list2_valid)
        else:
            df["Entity3"] = ""
        
        temp_cols = ["asintarget", "asintarget_sb", "asintarget_sd"]
        df.drop(columns=[col for col in temp_cols if col in df.columns], errors="ignore", inplace=True)
        
        return df
    
    def _concat_columns_vectorized(self, df: pd.DataFrame, cols: List[str]) -> np.ndarray:
        """向量化拼接多列"""
        result = np.full(len(df), '', dtype=object)
        for col in cols:
            col_vals = df[col].astype(str).values
            col_vals = np.where(col_vals == 'nan', '', col_vals)
            result = result + col_vals
        return result
    
    def add_entity_numeric_column_vectorized(self, df: pd.DataFrame) -> pd.DataFrame:
        """向量化添加 Entity 数值列"""
        if 'Entity' not in df.columns:
            return df
        
        entity_values = df['Entity'].values
        result = np.full(len(df), np.nan, dtype=float)
        
        for entity_name, numeric_value in self.entity_numeric_map.items():
            mask = entity_values == entity_name
            result[mask] = numeric_value
        
        df['Entity数值'] = result
        return df
    
    def filter_negative_entities_vectorized(self, df: pd.DataFrame) -> pd.DataFrame:
        """向量化过滤包含 "Negative" 的 Entity 行"""
        if 'Entity' not in df.columns:
            return df
        
        entity_values = df['Entity'].astype(str).fillna('').values
        mask_negative = np.char.find(entity_values.astype(str), 'Negative') != -1
        df_filtered = df[~mask_negative].copy()
        
        return df_filtered
    
    def add_classification_columns_vectorized(self, df: pd.DataFrame) -> pd.DataFrame:
        """向量化添加分类列"""
        impressions = df['Impressions'].values
        df['曝光量'] = np.where(
            pd.isna(impressions), '低曝光',
            np.where(impressions > self.thresholds["impressions"], '高曝光', '低曝光')
        )
        
        ctr = df['Click-through Rate'].values
        df['点击率'] = np.where(
            pd.isna(ctr), '低点击',
            np.where(ctr > self.thresholds["ctr"], '高点击', '低点击')
        )
        
        cvr = df['Conversion Rate'].values
        df['转化率'] = np.where(
            pd.isna(cvr), '低转化',
            np.where(cvr == 0, '0',
                np.where(cvr > self.thresholds["cvr"], '高转化', '低转化'))
        )
        
        acos = df['ACOS'].values
        df['A_Cos'] = np.where(
            pd.isna(acos), '低ACOS',
            np.where(acos == 0, '0',
                np.where(acos > self.thresholds["acos"], '高ACOS', '低ACOS'))
        )
        
        return df
    
    def classify_change_vectorized(self, values: np.ndarray) -> np.ndarray:
        """向量化判断变化情况"""
        result = np.full(len(values), '', dtype=object)
        
        values_numeric = pd.to_numeric(
            pd.Series(values).astype(str).str.replace('%', ''),
            errors='coerce'
        ).values / 100
        
        mask_notna = pd.notna(values_numeric)
        abs_values = np.abs(values_numeric)
        
        result = np.where(
            ~mask_notna, '',
            np.where(abs_values > 0.3, '变化过大', '平稳')
        )
        
        return result
    
    def add_change_indicators_vectorized(self, df: pd.DataFrame, growth_suffix: str = "_环比") -> pd.DataFrame:
        """向量化添加变化指标列"""
        df['曝光量变化'] = self.classify_change_vectorized(df[f'Impressions{growth_suffix}'].values)
        df['CTR变化'] = self.classify_change_vectorized(df[f'Click-through Rate{growth_suffix}'].values)
        df['CVR变化'] = self.classify_change_vectorized(df[f'Conversion Rate{growth_suffix}'].values)
        df['CPC变化'] = self.classify_change_vectorized(df[f'CPC{growth_suffix}'].values)
        
        return df
    
    def add_result_column_vectorized(self, df: pd.DataFrame) -> pd.DataFrame:
        """向量化添加结果列"""
        df['结果列'] = (
            df['曝光量'].fillna('').astype(str).replace('nan', '') + 
            df['点击率'].fillna('').astype(str).replace('nan', '') + 
            df['转化率'].fillna('').astype(str).replace('nan', '') + 
            df['A_Cos'].fillna('').astype(str).replace('nan', '')
        )
        return df
    
    def process(self, progress_callback: Callable = None) -> Dict[str, pd.DataFrame]:
        """执行完整的数据处理流程"""
        try:
            if progress_callback:
                progress_callback("正在识别文件...")
            
            old_file, new_file = self.find_excel_files()
            
            if progress_callback:
                progress_callback("正在读取旧表数据...")
            
            old_data = self.load_sheets_parallel(old_file, "old", progress_callback)
            
            if progress_callback:
                progress_callback("正在读取新表数据...")
            
            new_data = self.load_sheets_parallel(new_file, "new", progress_callback)
            
            results = {}
            
            for ad_type in ["sp", "sb", "sd"]:
                if progress_callback:
                    progress_callback(f"正在处理 {ad_type.upper()} 数据...")
                
                df_old = old_data.get(f"old_{ad_type}", pd.DataFrame())
                df_new = new_data.get(f"new_{ad_type}", pd.DataFrame())
                
                if df_old.empty or df_new.empty:
                    continue
                
                df_merged = self.merge_old_new_data(df_new, df_old)
                df_merged = self.filter_negative_entities_vectorized(df_merged)
                
                growth_suffix = f"_{ad_type}环比" if ad_type == "sb" else "_环比"
                df_merged = self.calculate_growth_vectorized(df_merged, self.target_cols, growth_suffix=growth_suffix)
                df_merged = self.add_entity_columns_vectorized(df_merged, ad_type)
                
                if ad_type == "sp":
                    df_merged = self.add_entity_numeric_column_vectorized(df_merged)
                
                df_merged = self.add_classification_columns_vectorized(df_merged)
                df_merged = self.add_change_indicators_vectorized(df_merged, growth_suffix)
                df_merged = self.add_result_column_vectorized(df_merged)
                
                results[ad_type] = df_merged
                
                old_data[f"old_{ad_type}"] = None
                new_data[f"new_{ad_type}"] = None
            
            if progress_callback:
                progress_callback("正在导出结果...")
            
            output_files = []
            for ad_type, df in results.items():
                output_file = self.folder_path / f"bulk_{ad_type}_数据源表格.csv"
                df.to_csv(output_file, index=False, encoding='utf-8-sig', na_rep='')
                output_files.append(output_file)
            
            if progress_callback:
                progress_callback("处理完成!")
            
            return results
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"处理失败: {str(e)}")
            raise
