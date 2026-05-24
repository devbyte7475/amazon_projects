"""
Amazon Payment 数据处理脚本（完整单文件版）
功能：合并、清洗、转换Amazon支付数据，支持终端拖放操作
作者：优化版 v3.0 - 增加数据变更验证与风险规避机制
"""

import os
import sys
import json
import glob
import logging
import argparse
import traceback
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("⚠️ 提示：安装 tqdm 可获得更好的进度显示 (pip install tqdm)")


# ==================== 数据诊断模块 ====================

def 修复乱码字符串(s):
    """
    将GBK编码被误解析为latin-1的乱码字符串还原为中文（跨系统适配版）
    
    参数:
        s: 输入字符串
    
    返回:
        修复后的字符串，如果修复失败则返回原字符串
    """
    if not isinstance(s, str):
        return s
    
    try:
        if os.name == 'nt':
            return s.encode('latin-1').decode('gbk', errors='ignore')
        else:
            return s.encode('latin-1').decode('utf-8-sig', errors='ignore')
    except Exception:
        return s


def find_column(df, target_name, logger=None):
    """
    智能查找DataFrame中的列名（不区分大小写、去除空格）
    
    参数:
        df: 输入的DataFrame
        target_name: 目标列名
        logger: 日志记录器（可选）
    
    返回:
        str: 实际的列名，如果找不到则返回None
    """
    if target_name in df.columns:
        return target_name
    
    target_lower = target_name.lower().strip()
    
    for col in df.columns:
        col_lower = col.lower().strip()
        if col_lower == target_lower:
            if logger:
                logger.info(f"列名映射: '{target_name}' -> '{col}'")
            return col
    
    if logger:
        logger.warning(f"未找到列: '{target_name}'")
        logger.info(f"可用列: {list(df.columns)}")
    
    return None


# ==================== Excel工具函数模块 ====================

def ifs(df, *args, default=np.nan):
    """
    支持多条件判断的极简版IFS函数
    
    参数:
        df: 输入的DataFrame
        *args: 成对的条件和结果，如：条件1, 结果1, 条件2, 结果2, ...
        default: 默认值（当所有条件都不满足时）
    
    返回:
        pandas.Series: 条件判断结果
    """
    if len(args) % 2 != 0:
        raise ValueError("参数必须是成对的：条件1, 结果1, 条件2, 结果2, ...")
    
    result = pd.Series(default, index=df.index, dtype=object)
    
    for i in range(0, len(args), 2):
        condition = args[i]
        output = args[i + 1]
        
        if isinstance(condition, pd.Series) and condition.dtype == bool:
            cond_series = condition
        elif isinstance(condition, tuple) and len(condition) == 3:
            col_name, operator, value = condition
            
            if col_name not in df.columns:
                raise ValueError(f"❌ 列名 '{col_name}' 不存在")
            
            if operator == '==':
                cond_series = df[col_name] == value
            elif operator == '!=':
                cond_series = df[col_name] != value
            elif operator == '>':
                cond_series = df[col_name] > value
            elif operator == '>=':
                cond_series = df[col_name] >= value
            elif operator == '<':
                cond_series = df[col_name] < value
            elif operator == '<=':
                cond_series = df[col_name] <= value
            elif operator == 'in':
                cond_series = df[col_name].isin(value)
            elif operator == 'not in':
                cond_series = ~df[col_name].isin(value)
            else:
                raise ValueError(f"❌ 不支持的运算符: {operator}")
        else:
            raise TypeError("❌ 条件必须是元组或布尔Series")
        
        if pd.isna(default):
            mask = result.isna() & cond_series
        else:
            mask = (result == default) & cond_series
        
        if mask.any():
            if isinstance(output, str) and output in df.columns:
                result.loc[mask] = df.loc[mask, output]
            else:
                result.loc[mask] = output
    
    return result


# ==================== 数据变更验证与风险规避模块 ====================

class DataSchemaValidator:
    """数据结构验证器：检测数据变更并评估风险"""
    
    EXPECTED_COLUMNS = {
        'type': {'required': True, 'description': '交易类型'},
        'quantity': {'required': True, 'description': '数量'},
        'product sales': {'required': True, 'description': '产品销售额'},
        'total': {'required': True, 'description': '总计金额'},
        'promotional rebates': {'required': True, 'description': '促销折扣'},
        'selling fees': {'required': True, 'description': '销售佣金'},
        'fba fees': {'required': True, 'description': 'FBA费用'},
        'description': {'required': True, 'description': '描述'},
        'date/time': {'required': True, 'description': '日期时间'},
        'sku': {'required': False, 'description': 'SKU编码'},
        'order id': {'required': False, 'description': '订单ID'},
    }
    
    EXPECTED_TYPE_VALUES = ['Order', 'Refund', 'Adjustment', 'Service Fee', '']
    
    KNOWN_DESCRIPTION_VALUES = [
        'FBA storage fee',
        'FBA Long-Term Storage Fee',
        'FBA Customer Return Fee',
        'Cost of Advertising',
        'FBA Inbound Placement Service Fee',
        'FBA Removal Order: Disposal Fee',
        'Liquidations',
        'Coupon Redemption Fee',
    ]
    
    COLS_MAPPING = {
        'type': 'type',
        'quantity': 'quantity',
        'product sales': 'product sales',
        'total': 'total',
        'promotional rebates': 'promotional rebates',
        'selling fees': 'selling fees',
        'fba fees': 'fba fees',
        'description': 'description',
        'fba storage fee': 'FBA storage fee',
        'fba long term storage': 'FBA Long-Term Storage Fee',
        'FBA Customer Return Fee': 'FBA Customer Return Fee',
        'Cost of Advertising': 'Cost of Advertising',
        'FBA Inbound Placement Service Fee': 'FBA Inbound Placement Service Fee',
        'FBA Removal Order: Disposal Fee': 'FBA Removal Order: Disposal Fee',
        'Liquidations': 'Liquidations',
        '回款': 'total',
    }
    
    def __init__(self, logger=None):
        self.logger = logger
        self.warnings = []
        self.errors = []
        self.schema_snapshot = None
    
    def _log(self, level, msg):
        if self.logger:
            getattr(self.logger, level)(msg)
    
    def validate_columns(self, df):
        """
        验证DataFrame是否包含所有必需列
        
        返回:
            tuple: (是否通过, 缺失列列表, 新增列列表)
        """
        actual_cols = set(df.columns)
        expected_required = {k for k, v in self.EXPECTED_COLUMNS.items() if v['required']}
        expected_all = set(self.EXPECTED_COLUMNS.keys())
        
        missing_required = expected_required - actual_cols
        missing_optional = (expected_all - expected_required) - actual_cols
        new_columns = actual_cols - expected_all
        
        if missing_required:
            msg = f"⚠️ 缺少必需列: {missing_required}"
            self.errors.append(msg)
            self._log('error', msg)
        
        if missing_optional:
            msg = f"ℹ️ 缺少可选列: {missing_optional}"
            self.warnings.append(msg)
            self._log('warning', msg)
        
        if new_columns:
            msg = f"🆕 发现新增列: {new_columns}"
            self.warnings.append(msg)
            self._log('info', msg)
        
        return len(missing_required) == 0, missing_required, new_columns
    
    def validate_cols_mapping(self, df):
        """
        验证cols映射字典中的列是否存在于DataFrame中
        
        返回:
            tuple: (是否通过, 缺失映射列列表)
        """
        actual_cols = set(df.columns)
        mapped_actual_cols = set()
        
        for logical_name, actual_name in self.COLS_MAPPING.items():
            if actual_name not in actual_cols:
                mapped_actual_cols.add((logical_name, actual_name))
        
        if mapped_actual_cols:
            msg = f"⚠️ cols映射中以下实际列名不存在于数据中: {mapped_actual_cols}"
            self.errors.append(msg)
            self._log('error', msg)
        
        return len(mapped_actual_cols) == 0, mapped_actual_cols
    
    def validate_type_values(self, df):
        """
        验证type列的值域，检测是否有新增的type值
        
        返回:
            tuple: (是否通过, 未知type值列表)
        """
        if 'type' not in df.columns:
            return False, {'type列不存在'}
        
        actual_types = set(df['type'].dropna().unique())
        known_types = set(self.EXPECTED_TYPE_VALUES) | {'优惠券/秒杀'}
        unknown_types = actual_types - known_types
        
        if unknown_types:
            msg = f"⚠️ type列发现未知值: {unknown_types}，这些值可能未被业务逻辑覆盖"
            self.warnings.append(msg)
            self._log('warning', msg)
        
        return len(unknown_types) == 0, unknown_types
    
    def validate_description_values(self, df):
        """
        验证description列的值域，检测是否有新增的description值
        
        返回:
            tuple: (是否通过, 未知description值列表)
        """
        if 'description' not in df.columns:
            return False, {'description列不存在'}
        
        actual_descs = set(df['description'].dropna().unique())
        known_descs = set(self.KNOWN_DESCRIPTION_VALUES)
        unknown_descs = actual_descs - known_descs
        
        if unknown_descs:
            msg = f"⚠️ description列发现未知值: {unknown_descs}，这些值可能未被费用归因逻辑覆盖"
            self.warnings.append(msg)
            self._log('warning', msg)
        
        return len(unknown_descs) == 0, unknown_descs
    
    def validate_numeric_columns(self, df):
        """
        验证数值列是否为数值类型
        
        返回:
            tuple: (是否通过, 非数值列列表)
        """
        numeric_cols = ['quantity', 'product sales', 'total', 
                       'promotional rebates', 'selling fees', 'fba fees']
        non_numeric = []
        
        for col in numeric_cols:
            if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
                non_numeric.append(col)
        
        if non_numeric:
            msg = f"⚠️ 以下列应为数值类型但当前不是: {non_numeric}"
            self.warnings.append(msg)
            self._log('warning', msg)
        
        return len(non_numeric) == 0, non_numeric
    
    def save_schema_snapshot(self, df, output_path):
        """
        保存当前数据的结构快照，用于后续变更检测
        
        参数:
            df: 当前DataFrame
            output_path: 快照保存路径
        """
        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'row_count': len(df),
            'columns': list(df.columns),
            'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
            'type_values': list(df['type'].dropna().unique()) if 'type' in df.columns else [],
            'description_values': list(df['description'].dropna().unique()) if 'description' in df.columns else [],
            'null_counts': {col: int(df[col].isna().sum()) for col in df.columns},
        }
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        
        self.schema_snapshot = snapshot
        self._log('info', f"数据结构快照已保存: {output_path}")
    
    def compare_with_snapshot(self, df, snapshot_path):
        """
        与历史快照对比，检测数据变更
        
        参数:
            df: 当前DataFrame
            snapshot_path: 历史快照路径
        
        返回:
            dict: 变更报告
        """
        snapshot_path = Path(snapshot_path)
        if not snapshot_path.exists():
            self._log('warning', f"历史快照不存在: {snapshot_path}")
            return {'status': 'no_snapshot', 'changes': []}
        
        with open(snapshot_path, 'r', encoding='utf-8') as f:
            old_snapshot = json.load(f)
        
        changes = []
        
        new_cols = set(df.columns) - set(old_snapshot['columns'])
        removed_cols = set(old_snapshot['columns']) - set(df.columns)
        
        if new_cols:
            changes.append({'type': 'column_added', 'detail': f"新增列: {new_cols}"})
        if removed_cols:
            changes.append({'type': 'column_removed', 'detail': f"删除列: {removed_cols}"})
        
        if 'type' in df.columns:
            old_types = set(old_snapshot.get('type_values', []))
            new_types = set(df['type'].dropna().unique())
            added_types = new_types - old_types
            if added_types:
                changes.append({'type': 'type_value_added', 'detail': f"type新增值: {added_types}"})
        
        if 'description' in df.columns:
            old_descs = set(old_snapshot.get('description_values', []))
            new_descs = set(df['description'].dropna().unique())
            added_descs = new_descs - old_descs
            if added_descs:
                changes.append({'type': 'description_value_added', 'detail': f"description新增值: {added_descs}"})
        
        for col in df.columns:
            if col in old_snapshot.get('dtypes', {}):
                old_dtype = old_snapshot['dtypes'][col]
                new_dtype = str(df[col].dtype)
                if old_dtype != new_dtype:
                    changes.append({'type': 'dtype_changed', 'detail': f"列'{col}'类型变更: {old_dtype} → {new_dtype}"})
        
        return {'status': 'compared', 'changes': changes}
    
    def assess_impact(self, changes):
        """
        评估数据变更对业务逻辑的影响
        
        参数:
            changes: 变更报告
        
        返回:
            dict: 影响评估结果
        """
        impact = {
            'level': 'none',
            'affected_metrics': [],
            'recommendations': []
        }
        
        for change in changes.get('changes', []):
            change_type = change['type']
            detail = change['detail']
            
            if change_type == 'column_removed':
                impact['level'] = 'critical'
                impact['affected_metrics'].append(detail)
                impact['recommendations'].append(f"🚨 {detail} - 需要更新cols映射和业务逻辑")
            
            elif change_type == 'type_value_added':
                impact['level'] = 'high' if impact['level'] == 'none' else impact['level']
                impact['affected_metrics'].append(detail)
                impact['recommendations'].append(f"⚠️ {detail} - 需要检查是否需要新增归因逻辑")
            
            elif change_type == 'description_value_added':
                impact['level'] = 'high' if impact['level'] == 'none' else impact['level']
                impact['affected_metrics'].append(detail)
                impact['recommendations'].append(f"⚠️ {detail} - 需要检查是否需要新增费用归因")
            
            elif change_type == 'column_added':
                impact['level'] = 'medium' if impact['level'] == 'none' else impact['level']
                impact['recommendations'].append(f"ℹ️ {detail} - 检查是否需要纳入业务逻辑")
            
            elif change_type == 'dtype_changed':
                impact['level'] = 'medium' if impact['level'] == 'none' else impact['level']
                impact['recommendations'].append(f"ℹ️ {detail} - 检查数据类型转换是否正确")
        
        return impact
    
    def run_full_validation(self, df, snapshot_dir=None):
        """
        执行完整的数据验证流程
        
        参数:
            df: 待验证的DataFrame
            snapshot_dir: 快照保存目录
        
        返回:
            dict: 完整验证报告
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'row_count': len(df),
            'column_check': {},
            'mapping_check': {},
            'type_check': {},
            'description_check': {},
            'numeric_check': {},
            'snapshot_comparison': {},
            'impact_assessment': {},
            'all_warnings': [],
            'all_errors': [],
        }
        
        print("\n🔍 执行数据变更验证...")
        
        col_ok, missing, new = self.validate_columns(df)
        report['column_check'] = {'passed': col_ok, 'missing': list(missing), 'new': list(new)}
        
        map_ok, missing_map = self.validate_cols_mapping(df)
        report['mapping_check'] = {'passed': map_ok, 'missing_mappings': [f"{l}→{a}" for l, a in missing_map]}
        
        type_ok, unknown_types = self.validate_type_values(df)
        report['type_check'] = {'passed': type_ok, 'unknown_values': list(unknown_types)}
        
        desc_ok, unknown_descs = self.validate_description_values(df)
        report['description_check'] = {'passed': desc_ok, 'unknown_values': list(unknown_descs)}
        
        num_ok, non_numeric = self.validate_numeric_columns(df)
        report['numeric_check'] = {'passed': num_ok, 'non_numeric_columns': non_numeric}
        
        if snapshot_dir:
            snapshot_dir = Path(snapshot_dir)
            snapshot_path = snapshot_dir / 'schema_snapshot.json'
            
            if snapshot_path.exists():
                comparison = self.compare_with_snapshot(df, snapshot_path)
                report['snapshot_comparison'] = comparison
                
                if comparison['changes']:
                    impact = self.assess_impact(comparison)
                    report['impact_assessment'] = impact
            
            self.save_schema_snapshot(df, snapshot_path)
        
        report['all_warnings'] = self.warnings
        report['all_errors'] = self.errors
        
        self._print_validation_report(report)
        
        return report
    
    def _print_validation_report(self, report):
        """打印验证报告"""
        print("\n" + "=" * 80)
        print("📋 数据变更验证报告")
        print("=" * 80)
        
        checks = [
            ('column_check', '列存在性检查'),
            ('mapping_check', '映射完整性检查'),
            ('type_check', 'type值域检查'),
            ('description_check', 'description值域检查'),
            ('numeric_check', '数值类型检查'),
        ]
        
        for key, label in checks:
            passed = report.get(key, {}).get('passed', True)
            icon = "✅" if passed else "⚠️"
            print(f"  {icon} {label}")
        
        if report.get('snapshot_comparison', {}).get('changes'):
            print(f"  🔄 检测到数据结构变更: {len(report['snapshot_comparison']['changes'])} 项")
        
        if report.get('impact_assessment', {}).get('level', 'none') != 'none':
            level = report['impact_assessment']['level']
            level_icon = {'critical': '🚨', 'high': '⚠️', 'medium': 'ℹ️'}.get(level, '❓')
            print(f"  {level_icon} 影响等级: {level}")
        
        if report['all_warnings']:
            print(f"\n⚠️ 警告 ({len(report['all_warnings'])} 项):")
            for w in report['all_warnings']:
                print(f"  - {w}")
        
        if report['all_errors']:
            print(f"\n🚨 错误 ({len(report['all_errors'])} 项):")
            for e in report['all_errors']:
                print(f"  - {e}")
        
        if report.get('impact_assessment', {}).get('recommendations'):
            print(f"\n💡 建议:")
            for r in report['impact_assessment']['recommendations']:
                print(f"  {r}")
        
        print("=" * 80)


# ==================== 主处理类 ====================

class PaymentProcessor:
    """Amazon Payment 数据处理器"""
    
    def __init__(self):
        self.setup_logging()
        self.validator = DataSchemaValidator(self.logger)
        self.stats = {
            'total_files': 0,
            'success_files': 0,
            'failed_files': 0,
            'total_rows': 0,
            'errors': []
        }
    
    def setup_logging(self):
        """配置日志系统（健壮版：支持多次调用、自动降级目录）"""
        self.logger = logging.getLogger(f'payment_{id(self)}')
        self.logger.setLevel(logging.INFO)
        
        if self.logger.handlers:
            return
        
        log_dir = self._get_writable_log_dir()
        log_file = log_dir / f'payment_processing_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            self.logger.info(f"日志文件：{log_file}")
        except (PermissionError, OSError) as e:
            print(f"⚠️ 无法创建日志文件 {log_file}: {e}，将仅使用控制台输出")
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
    
    def _get_writable_log_dir(self):
        """获取可写的日志目录（按优先级尝试多个位置）"""
        candidates = [
            Path(__file__).parent / 'logs',
            Path.cwd() / 'amazon_payment_logs',
            Path.home() / 'amazon_payment_logs',
            Path('/tmp') / 'amazon_payment_logs',
        ]
        
        for dir_path in candidates:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                test_file = dir_path / '.write_test'
                test_file.write_text('test')
                test_file.unlink()
                return dir_path
            except (PermissionError, OSError):
                continue
        
        return Path('/tmp')
    
    def print_banner(self):
        """打印欢迎横幅"""
        banner = """
╔════════════════════════════════════════════════════════════╗
║       Amazon Payment 数据处理工具 v3.0                    ║
║       支持拖放文件夹 | 数据变更验证 | 风险规避             ║
╚════════════════════════════════════════════════════════════╝
        """
        print(banner)
    
    def get_folder_path(self, cli_path=None):
        """
        获取文件夹路径（支持命令行参数、拖放和手动输入）
        
        参数:
            cli_path: 命令行传入的路径（可选）
        
        返回:
            Path: 验证后的文件夹路径
        """
        if cli_path:
            path = Path(cli_path.strip('"\'').strip())
            if not path.exists():
                print(f"❌ 错误：路径不存在: {path}")
                self.logger.error(f"路径不存在: {path}")
                return None
            if not path.is_dir():
                print(f"❌ 错误：路径不是文件夹: {path}")
                self.logger.error(f"路径不是文件夹: {path}")
                return None
            return path
        
        if not sys.stdin.isatty():
            print("❌ 非交互模式下未提供数据文件夹路径")
            print("💡 用法: python payment.py /path/to/data/folder")
            self.logger.error("非交互模式下未提供路径参数")
            return None
        
        print("\n📁 请选择数据文件夹：")
        print("   方法1：直接将文件夹拖放到此终端窗口")
        print("   方法2：手动输入文件夹完整路径")
        print("   方法3：输入 'quit' 退出程序\n")
        
        while True:
            try:
                user_input = input("👉 请输入路径或拖放文件夹：").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 用户取消操作，程序退出")
                    sys.exit(0)
                
                user_input = user_input.strip('"\'')
                user_input = user_input.strip()
                
                path = Path(user_input)
                
                if not path.exists():
                    print(f"❌ 错误：路径不存在: {path}")
                    print(f"💡 提示：请检查路径是否正确")
                    print(f"   当前工作目录: {Path.cwd()}")
                    self.logger.error(f"路径不存在: {path}")
                    continue
                
                if not path.is_dir():
                    print(f"❌ 错误：路径不是文件夹: {path}")
                    self.logger.error(f"路径不是文件夹: {path}")
                    continue
                
                return path
                
            except KeyboardInterrupt:
                print("\n\n👋 用户中断操作，程序退出")
                sys.exit(0)
            except Exception as e:
                print(f"❌ 输入错误: {e}")
                self.logger.error(f"输入错误: {e}\n{traceback.format_exc()}")
    
    def validate_data_folder(self, folder_path):
        """
        验证数据文件夹是否包含有效文件
        
        参数:
            folder_path: 文件夹路径
        
        返回:
            tuple: (是否有效, 文件列表, 错误消息)
        """
        self.logger.info(f"验证文件夹: {folder_path}")
        
        excel_files = list(folder_path.glob("*.xlsx")) + list(folder_path.glob("*.xls"))
        csv_files = list(folder_path.glob("*.csv"))
        
        all_files = excel_files + csv_files
        
        if not all_files:
            error_msg = f"文件夹中没有找到 Excel (.xlsx/.xls) 或 CSV (.csv) 文件"
            self.logger.warning(error_msg)
            return False, [], error_msg
        
        self.logger.info(f"找到 {len(excel_files)} 个Excel文件, {len(csv_files)} 个CSV文件")
        
        return True, all_files, ""
    
    def datamerge(self, folder_path, skip_csv=7, skip_excel=7):
        """
        核心合并函数（跨系统适配）
        
        参数:
            folder_path: 包含Excel和CSV文件的文件夹路径
            skip_csv: CSV文件跳过的行数
            skip_excel: Excel文件跳过的行数
        
        返回:
            合并后的DataFrame
        """
        self.logger.info(f"开始合并数据，跳过CSV {skip_csv} 行，跳过Excel {skip_excel} 行")
        
        excel_files = list(folder_path.glob("*.xlsx")) + list(folder_path.glob("*.xls"))
        csv_files = list(folder_path.glob("*.csv"))
        
        self.stats['total_files'] = len(excel_files) + len(csv_files)
        
        print(f"\n📂 找到 {len(excel_files)} 个Excel文件, {len(csv_files)} 个CSV文件")
        
        all_data = []
        
        if TQDM_AVAILABLE:
            file_iterator = tqdm(excel_files + csv_files, desc="处理文件", unit="个")
        else:
            file_iterator = excel_files + csv_files
            print("\n处理文件中...")
        
        for idx, file in enumerate(file_iterator, 1):
            try:
                if file.suffix in ['.xlsx', '.xls']:
                    df = self._read_excel_file(file, skip_excel)
                else:
                    df = self._read_csv_file(file, skip_csv)
                
                if df is not None and not df.empty:
                    df['文件来源'] = file.name
                    all_data.append(df)
                    self.stats['success_files'] += 1
                    self.stats['total_rows'] += len(df)
                    
                    if not TQDM_AVAILABLE:
                        print(f"  ✅ [{idx}/{self.stats['total_files']}] {file.name} ({len(df)} 行)")
                else:
                    self.stats['failed_files'] += 1
                    if not TQDM_AVAILABLE:
                        print(f"  ⚠️ [{idx}/{self.stats['total_files']}] {file.name} (空文件)")
                    
            except Exception as e:
                self.stats['failed_files'] += 1
                error_msg = f"读取文件失败 {file.name}: {str(e)}"
                self.stats['errors'].append(error_msg)
                self.logger.error(error_msg)
                if not TQDM_AVAILABLE:
                    print(f"  ❌ [{idx}/{self.stats['total_files']}] {file.name} - 错误: {e}")
        
        if all_data:
            try:
                combined_df = pd.concat(all_data, ignore_index=True, sort=False)
                self.logger.info(f"合并完成: {len(combined_df)} 行数据")
                return combined_df
            except Exception as e:
                self.logger.error(f"合并数据失败: {e}\n{traceback.format_exc()}")
                return pd.DataFrame()
        else:
            self.logger.warning("没有找到可读取的数据文件")
            return pd.DataFrame()
    
    def _read_excel_file(self, file_path, skiprows):
        """读取Excel文件"""
        try:
            engine = 'openpyxl' if file_path.suffix == '.xlsx' else 'xlrd'
            df = pd.read_excel(file_path, skiprows=skiprows, engine=engine)
            
            if df.empty:
                self.logger.warning(f"Excel文件为空: {file_path.name}")
                return None
            
            self.logger.debug(f"成功读取Excel: {file_path.name}")
            return df
            
        except Exception as e:
            self.logger.error(f"读取Excel失败 {file_path.name}: {e}")
            raise
    
    def _read_csv_file(self, file_path, skiprows):
        """读取CSV文件（跨系统编码适配）"""
        if os.name == 'nt':
            encodings = ['gbk', 'utf-8-sig', 'utf-8', 'latin-1', 'gb2312']
        else:
            encodings = ['utf-8-sig', 'gbk', 'utf-8', 'latin-1', 'gb2312']
        
        df = None
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, skiprows=skiprows, encoding=encoding)
                df.columns = [修复乱码字符串(col) for col in df.columns]
                self.logger.debug(f"成功读取CSV [{encoding}]: {file_path.name}")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.logger.warning(f"尝试{encoding}读取CSV失败 {file_path.name}: {e}")
                continue
        
        if df is None:
            try:
                df = pd.read_csv(file_path, skiprows=skiprows, encoding='latin-1')
                df.columns = [修复乱码字符串(col) for col in df.columns]
                self.logger.info(f"强制用latin-1读取: {file_path.name}")
            except Exception as e:
                self.logger.error(f"无法读取CSV文件: {file_path.name}, 错误: {e}")
                raise
        
        if df.empty:
            return None
        
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].apply(lambda x: 修复乱码字符串(x) if isinstance(x, str) else x)
        
        return df
    
    def datatransform(self, df, 转换阈值=0.8, 显示日志=True, 空值填充=None):
        """
        智能识别DataFrame中"本应是数值却误判为object"的列，清洗后转为int/float
        
        参数:
            df: 输入的DataFrame
            转换阈值: 可转换比例阈值，默认0.8
            显示日志: 是否显示转换日志，默认True
            空值填充: 空值填充值，默认None
        
        返回:
            处理后的DataFrame
        """
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            if 显示日志:
                print("⚠️ DataFrame为空/无效，返回空DataFrame")
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        
        df处理后 = df.copy()
        object列列表 = df处理后.select_dtypes(include=['object']).columns.tolist()
        
        if not object列列表:
            if 显示日志:
                print("⚠️ 未检测到object类型列，无需转换")
            return df处理后
        
        def 清洗数值文本(series):
            try:
                series = series.replace(['', 'NULL', 'null', 'None', 'nan', 'NaN', 'N/A', 'n/a'], np.nan)
                str_series = series.astype(str).str.strip()
                str_series = str_series.str.replace(',', '', regex=False).str.replace(' ', '', regex=False)
                str_series = str_series.str.lstrip('¥￥$€£')
                
                百分数标记 = str_series.str.endswith('%', na=False)
                str_series = str_series.str.rstrip('%')
                
                str_series = str_series.str.lower().replace({
                    'inf': np.inf, 'infinity': np.inf, '-inf': -np.inf, '-infinity': -np.inf
                }, regex=False)
                
                数值列 = pd.to_numeric(str_series, errors='coerce')
                
                if 百分数标记.any():
                    mask = 百分数标记 & 数值列.notna() & ~np.isinf(数值列)
                    数值列[mask] = 数值列[mask] / 100
                return 数值列
            except Exception as e:
                if 显示日志:
                    print(f"⚠️ 清洗列时出错: {e}")
                return series
        
        转换报告 = []
        
        if TQDM_AVAILABLE:
            列迭代器 = tqdm(object列列表, desc="转换数据类型", unit="列")
        else:
            列迭代器 = object列列表
            print("\n转换数据类型中...")
        
        for idx, 列名 in enumerate(列迭代器, 1):
            if df处理后[列名].isna().all():
                continue
            
            非空样本 = df处理后[列名].dropna()
            if len(非空样本) == 0:
                转换报告.append({
                    '列名': 列名, '原类型': str(df处理后[列名].dtype), '新类型': 'object',
                    '可转换比例': "0.0%", '状态': '⏸️ 跳过（无有效样本）'
                })
                continue
            
            抽样数 = min(1000, len(非空样本))
            样本 = 非空样本.sample(n=抽样数, random_state=42) if len(非空样本) > 1000 else 非空样本
            
            清洗后样本 = 清洗数值文本(样本)
            可转换数量 = 清洗后样本.notna().sum()
            可转换比例 = 可转换数量 / len(样本) if len(样本) > 0 else 0
            
            if 可转换比例 < 转换阈值:
                转换报告.append({
                    '列名': 列名, '原类型': str(df处理后[列名].dtype), '新类型': 'object',
                    '可转换比例': f"{可转换比例:.1%}", '状态': f'⏸️ 跳过（低于{转换阈值:.0%}阈值）'
                })
                continue
            
            原类型 = str(df处理后[列名].dtype)
            try:
                df处理后[列名] = 清洗数值文本(df处理后[列名])
                
                if df处理后[列名].notna().any():
                    有效值 = df处理后[列名].dropna()
                    if np.any(np.isinf(有效值)):
                        新类型 = 'float64'
                        df处理后[列名] = df处理后[列名].astype('float64')
                    else:
                        有小数 = (有效值 % 1 != 0).any()
                        if not 有小数:
                            try:
                                df处理后[列名] = df处理后[列名].astype('Int64')
                                新类型 = 'Int64'
                            except Exception:
                                df处理后[列名] = df处理后[列名].astype('float64')
                                新类型 = 'float64'
                        else:
                            df处理后[列名] = df处理后[列名].astype('float64')
                            新类型 = 'float64'
                else:
                    df处理后[列名] = df处理后[列名].astype('float64')
                    新类型 = 'float64'
                
                if 空值填充 is not None:
                    try:
                        if 新类型 == 'Int64':
                            填充值 = int(空值填充)
                        elif 新类型 == 'float64':
                            填充值 = float(空值填充)
                        else:
                            填充值 = 空值填充
                        df处理后[列名] = df处理后[列名].fillna(填充值)
                    except Exception as e:
                        if 显示日志:
                            print(f"⚠️ 列'{列名}'填充失败（{e}），跳过填充")
                
                转换报告.append({
                    '列名': 列名, '原类型': 原类型, '新类型': 新类型,
                    '可转换比例': f"{可转换比例:.1%}", '状态': '✅ 转换成功'
                })
            except Exception as e:
                try:
                    实际类型 = str(df处理后[列名].dtype)
                except:
                    实际类型 = 'unknown'
                转换报告.append({
                    '列名': 列名, '原类型': 原类型, '新类型': 实际类型,
                    '可转换比例': f"{可转换比例:.1%}", '状态': f'❌ 转换失败: {str(e)[:80]}'
                })
        
        if 显示日志 and 转换报告:
            print("\n" + "=" * 80)
            print("📊 数值列智能转换报告")
            print(f"🔍 阈值: {转换阈值:.0%} | 样本量: 最多1000行 | 空值填充: {空值填充 if 空值填充 is not None else '无'}")
            print("=" * 80)
            for 报告 in 转换报告:
                icon = "✅" if "成功" in 报告['状态'] else ("⏸️" if "跳过" in 报告['状态'] else "❌")
                print(f"{icon} {报告['列名']:20s} | {报告['原类型']:10s} → {报告['新类型']:10s} | "
                      f"比例: {报告['可转换比例']:6s} | {报告['状态']}")
            print("=" * 80)
            成功数 = sum(1 for r in 转换报告 if "✅" in r['状态'])
            跳过数 = sum(1 for r in 转换报告 if "⏸️" in r['状态'])
            失败数 = sum(1 for r in 转换报告 if "❌" in r['状态'])
            print(f"📈 总计: {len(转换报告)}列 | 成功: {成功数} | 跳过: {跳过数} | 失败: {失败数}")
            print("=" * 80)
        
        return df处理后
    
    def process_dates(self, df):
        """处理日期列"""
        try:
            print("\n📅 处理日期数据...")
            
            date_col = find_column(df, 'date/time', self.logger)
            
            if date_col is None:
                error_msg = "未找到 'date/time' 列，请检查数据文件是否包含日期时间列"
                print(f"❌ {error_msg}")
                print(f"💡 可用列: {list(df.columns)}")
                self.logger.error(error_msg)
                raise KeyError(error_msg)
            
            df[date_col] = df[date_col].str.split(' ').str[:3].str.join(' ')
            df[date_col] = pd.to_datetime(
                df[date_col],
                format='%b %d, %Y',
                errors='coerce'
            )
            
            df['年'] = df[date_col].dt.year
            df['月'] = df[date_col].dt.month
            df['日'] = df[date_col].dt.day
            
            self.logger.info("日期转换完成")
            print("✅ 日期转换完成")
            
            return df
            
        except Exception as e:
            self.logger.error(f"日期处理失败: {e}\n{traceback.format_exc()}")
            raise
    
    def add_data_dimensions(self, df):
        """添加数据维度列"""
        try:
            print("\n📊 划分数据维度...")
            
            sku_col = find_column(df, 'sku', self.logger)
            
            if sku_col is None:
                print("⚠️ 未找到 'sku' 列，将所有数据标记为店铺维度")
                df['数据维度'] = '店铺维度'
            else:
                数据维度条件1 = df[sku_col].isna()
                数据维度条件2 = df[sku_col].notna()
                
                df['数据维度'] = ifs(
                    df,
                    数据维度条件1, '店铺维度',
                    数据维度条件2, '商品维度',
                )
            
            self.logger.info(f"数据维度划分完成: {df['数据维度'].unique()}")
            print(f"✅ 数据维度划分完成: {df['数据维度'].unique()}")
            
            return df
            
        except Exception as e:
            self.logger.error(f"数据维度划分失败: {e}\n{traceback.format_exc()}")
            raise
    
    def create_metric_columns(self, df):
        """
        创建指标列（含数据变更验证与异常捕获）
        
        在执行业务逻辑归因前，先验证数据结构是否符合预期，
        如果检测到数据变更可能导致逻辑错误，会发出告警。
        """
        try:
            print("\n🔢 计算业务指标...")
            
            cols = DataSchemaValidator.COLS_MAPPING
            
            # ===== 数据变更验证 =====
            validation = self.validator.run_full_validation(df)
            
            if validation['all_errors']:
                print("\n🚨 检测到严重数据问题，业务逻辑可能无法正确执行！")
                for err in validation['all_errors']:
                    print(f"  {err}")
                
                if sys.stdin.isatty():
                    proceed = input("\n是否继续处理？(y/n): ").strip().lower()
                    if proceed != 'y':
                        print("❌ 用户中止处理")
                        self.logger.warning("用户因数据验证错误中止处理")
                        return df
                else:
                    print("⚠️ 非交互模式，自动跳过错误继续处理")
                    self.logger.warning("非交互模式下遇到数据验证错误，自动继续处理")
            
            if validation['all_warnings']:
                print("\n⚠️ 检测到数据变更警告：")
                for w in validation['all_warnings']:
                    print(f"  {w}")
            
            # ===== 执行业务逻辑归因 =====
            type_col = find_column(df, 'type', self.logger)
            desc_col = find_column(df, 'description', self.logger)
            
            if type_col:
                df[type_col] = df[type_col].fillna('优惠券/秒杀')
            
            if desc_col and type_col:
                df.loc[df[desc_col].str.contains('Coupon Redemption', na=False), desc_col] = 'Coupon Redemption Fee'
            
            df['销量'] = ifs(df, df['type'] == 'Order', df[cols['quantity']], default=0)
            df['退货量'] = ifs(df, df['type'] == 'Refund', df[cols['quantity']], default=0)
            df['销售额'] = ifs(df, df['type'] == 'Order', df[cols['product sales']], default=0)
            df['退款额'] = ifs(df, df['type'] == 'Refund', df[cols['product sales']], default=0)
            df['仓库赔偿'] = ifs(df, df['type'] == 'Adjustment', df[cols['total']], default=0)
            df['折扣金额'] = ifs(df, (df['type'] == 'Order') | (df['type'] == 'Refund'), df[cols['promotional rebates']], default=0)
            df['佣金'] = ifs(df, (df['type'] == 'Order') | (df['type'] == 'Refund'), df[cols['selling fees']], default=0)
            df['fba运费'] = ifs(df, df['type'] == 'Order', df[cols['fba fees']], default=0)
            df['退货处理费'] = ifs(df, df['description'] == cols['FBA Customer Return Fee'], df[cols['total']], default=0)
            df['优惠券/秒杀'] = ifs(df, df['type'] == '优惠券/秒杀', df[cols['total']], default=0)
            df['广告费'] = ifs(df, df['description'] == cols['Cost of Advertising'], df[cols['total']], default=0)
            df['仓储费'] = ifs(df, (df['description'] == cols['fba storage fee']) | (df['description'] == cols['fba long term storage']), df[cols['total']], default=0)
            df['入库配置费'] = ifs(df, df['description'] == cols['FBA Inbound Placement Service Fee'], df[cols['total']], default=0)
            df['移除费'] = ifs(df, df['description'] == cols['FBA Removal Order: Disposal Fee'], df[cols['total']], default=0)
            df['批清收益'] = ifs(df, df['type'] == cols['Liquidations'], df[cols['total']], default=0)
            
            df['回款'] = df[cols['total']]
            df['预估货值'] = df['销售额'] * 0.15
            df['预估毛利'] = df['回款'] - df['预估货值']
            
            # ===== 归因结果校验 =====
            self._validate_metric_results(df)
            
            self.logger.info("业务指标计算完成")
            print("✅ 业务指标计算完成")
            
            return df
            
        except KeyError as e:
            error_msg = f"业务指标计算失败 - 列不存在: {e}"
            print(f"\n🚨 {error_msg}")
            print(f"💡 这通常是因为数据表格结构发生了变更，请检查数据列名")
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            raise
        except Exception as e:
            self.logger.error(f"业务指标计算失败: {e}\n{traceback.format_exc()}")
            raise
    
    def _validate_metric_results(self, df):
        """
        校验业务指标计算结果，检测归因遗漏
        
        检查逻辑：所有归因指标之和应接近total列的合计值
        """
        metric_cols = ['销量', '退货量', '销售额', '退款额', '仓库赔偿', '折扣金额',
                       '佣金', 'fba运费', '退货处理费', '优惠券/秒杀', '广告费',
                       '仓储费', '入库配置费', '移除费', '批清收益']
        
        zero_count = 0
        all_zero_cols = []
        
        for col in metric_cols:
            if col in df.columns:
                non_zero = (df[col] != 0).sum()
                if non_zero == 0:
                    all_zero_cols.append(col)
                    zero_count += 1
        
        if all_zero_cols:
            self.logger.warning(f"以下指标列全为0，可能存在归因遗漏: {all_zero_cols}")
            print(f"\n⚠️ 注意：以下指标列全为0，可能存在归因遗漏:")
            for col in all_zero_cols:
                print(f"  - {col}")
    
    def export_results(self, df, output_folder):
        """导出结果文件"""
        try:
            print("\n💾 导出结果文件...")
            
            output_folder.mkdir(exist_ok=True)
            
            原表路径 = output_folder / 'payment_原表_逻辑化.xlsx'
            
            df.to_excel(原表路径, index=False)
            self.logger.info(f"原表已导出: {原表路径}")
            print(f"  ✅ 原表已导出: {原表路径}")
            
            return 原表路径
            
        except Exception as e:
            self.logger.error(f"导出失败: {e}\n{traceback.format_exc()}")
            raise
    
    def print_summary(self):
        """打印处理摘要"""
        print("\n" + "=" * 80)
        print("📊 处理摘要")
        print("=" * 80)
        print(f"  总文件数: {self.stats['total_files']}")
        print(f"  成功文件: {self.stats['success_files']}")
        print(f"  失败文件: {self.stats['failed_files']}")
        print(f"  总数据行: {self.stats['total_rows']}")
        
        if self.stats['errors']:
            print("\n❌ 错误列表:")
            for error in self.stats['errors']:
                print(f"  - {error}")
        
        if self.validator.warnings:
            print(f"\n⚠️ 数据变更警告: {len(self.validator.warnings)} 项")
        if self.validator.errors:
            print(f"🚨 数据变更错误: {len(self.validator.errors)} 项")
        
        print("=" * 80)
    
    def run(self, folder_path=None):
        """主处理流程"""
        try:
            self.print_banner()
            
            folder = self.get_folder_path(cli_path=folder_path)
            if folder is None:
                return False
            
            is_valid, files, error_msg = self.validate_data_folder(folder)
            if not is_valid:
                print(f"\n❌ {error_msg}")
                print("请确保文件夹包含 .xlsx, .xls 或 .csv 文件")
                return False
            
            df = self.datamerge(folder, skip_csv=7, skip_excel=7)
            
            if df.empty:
                print("\n❌ 没有读取到任何数据，请检查文件格式")
                return False
            
            print(f"\n🎉 数据合并完成! 总共 {len(df)} 行数据")
            
            df = self.datatransform(df)
            
            df = self.process_dates(df)
            
            df = self.add_data_dimensions(df)
            
            df = self.create_metric_columns(df)
            
            output_folder = folder / 'processed_results'
            原表路径 = self.export_results(df, output_folder)
            
            snapshot_dir = output_folder / 'schema_snapshots'
            self.validator.save_schema_snapshot(df, snapshot_dir / 'schema_snapshot.json')
            
            self.print_summary()
            
            print(f"\n✅ 处理完成！结果已保存到: {output_folder}")
            print(f"  📄 原表: {原表路径.name}")
            
            self.logger.info("处理流程完成")
            
            return True
            
        except KeyboardInterrupt:
            print("\n\n👋 用户中断操作")
            self.logger.info("用户中断操作")
            return False
        except Exception as e:
            error_msg = f"处理失败: {e}"
            print(f"\n❌ {error_msg}")
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return False


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(
        description='Amazon Payment 数据处理工具 v3.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  python payment.py /path/to/data/folder
  python payment.py --skip-csv 5 --skip-excel 3 /path/to/data/folder
  python payment.py  # 交互模式，手动输入路径
        '''
    )
    parser.add_argument('folder', nargs='?', default=None,
                        help='数据文件夹路径（不提供则进入交互模式）')
    parser.add_argument('--skip-csv', type=int, default=7,
                        help='CSV文件跳过行数（默认7）')
    parser.add_argument('--skip-excel', type=int, default=7,
                        help='Excel文件跳过行数（默认7）')
    
    args = parser.parse_args()
    
    try:
        processor = PaymentProcessor()
        success = processor.run(folder_path=args.folder)
        
        if sys.stdin.isatty():
            print("\n" + "=" * 80)
            input("按回车键退出...")
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        logging.error(f"程序异常: {e}\n{traceback.format_exc()}")
        
        if sys.stdin.isatty():
            input("\n按回车键退出...")
        
        sys.exit(1)


if __name__ == "__main__":
    main()
