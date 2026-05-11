"""
Payment 数据处理脚本 - 单元测试与集成测试
验证数据变更验证机制、异常捕获与告警、影响评估等核心功能
"""

import sys
import json
import tempfile
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from payment import DataSchemaValidator, ifs, PaymentProcessor


def test_ifs_basic():
    """测试ifs函数基本功能"""
    df = pd.DataFrame({
        'type': ['Order', 'Refund', 'Adjustment', 'Order'],
        'amount': [100, 50, 30, 200],
    })
    
    result = ifs(df, df['type'] == 'Order', df['amount'], default=0)
    assert list(result) == [100, 0, 0, 200], f"ifs基本功能失败: {list(result)}"
    print("  ✅ ifs基本功能")


def test_ifs_multi_condition():
    """测试ifs多条件功能"""
    df = pd.DataFrame({
        'type': ['Order', 'Refund', 'Adjustment'],
        'amount': [100, 50, 30],
    })
    
    result = ifs(df, 
        (df['type'] == 'Order') | (df['type'] == 'Refund'), df['amount'],
        default=0
    )
    assert list(result) == [100, 50, 0], f"ifs多条件失败: {list(result)}"
    print("  ✅ ifs多条件功能")


def test_validator_columns():
    """测试列存在性验证"""
    validator = DataSchemaValidator()
    
    # 完整列
    df_ok = pd.DataFrame(columns=['type', 'quantity', 'product sales', 'total',
                                   'promotional rebates', 'selling fees', 'fba fees',
                                   'description', 'date/time', 'sku'])
    passed, missing, new = validator.validate_columns(df_ok)
    assert passed, f"完整列验证应通过，但缺失: {missing}"
    print("  ✅ 列存在性验证 - 完整列通过")
    
    # 缺少必需列
    validator2 = DataSchemaValidator()
    df_missing = pd.DataFrame(columns=['type', 'quantity'])
    passed, missing, new = validator2.validate_columns(df_missing)
    assert not passed, "缺少必需列时验证应失败"
    assert 'total' in missing, f"应检测到缺失total列: {missing}"
    print("  ✅ 列存在性验证 - 缺失列检测")


def test_validator_cols_mapping():
    """测试映射完整性验证"""
    validator = DataSchemaValidator()
    
    df_ok = pd.DataFrame(columns=['type', 'quantity', 'product sales', 'total',
                                   'promotional rebates', 'selling fees', 'fba fees',
                                   'description', 'FBA storage fee', 
                                   'FBA Long-Term Storage Fee',
                                   'FBA Customer Return Fee',
                                   'Cost of Advertising',
                                   'FBA Inbound Placement Service Fee',
                                   'FBA Removal Order: Disposal Fee',
                                   'Liquidations'])
    passed, missing = validator.validate_cols_mapping(df_ok)
    assert passed, f"映射完整性验证应通过，但缺失: {missing}"
    print("  ✅ 映射完整性验证 - 通过")
    
    validator2 = DataSchemaValidator()
    df_missing_col = pd.DataFrame(columns=['type', 'quantity', 'total'])
    passed, missing = validator2.validate_cols_mapping(df_missing_col)
    assert not passed, "映射缺失时应失败"
    print("  ✅ 映射完整性验证 - 缺失检测")


def test_validator_type_values():
    """测试type值域验证"""
    validator = DataSchemaValidator()
    
    df_ok = pd.DataFrame({'type': ['Order', 'Refund', 'Adjustment', '']})
    passed, unknown = validator.validate_type_values(df_ok)
    assert passed, f"已知type值应通过，但发现未知: {unknown}"
    print("  ✅ type值域验证 - 已知值通过")
    
    validator2 = DataSchemaValidator()
    df_new_type = pd.DataFrame({'type': ['Order', 'NewType']})
    passed, unknown = validator2.validate_type_values(df_new_type)
    assert not passed, "未知type值应触发警告"
    assert 'NewType' in unknown, f"应检测到NewType: {unknown}"
    print("  ✅ type值域验证 - 未知值检测")


def test_validator_description_values():
    """测试description值域验证"""
    validator = DataSchemaValidator()
    
    df_ok = pd.DataFrame({'description': ['FBA storage fee', 'Cost of Advertising']})
    passed, unknown = validator.validate_description_values(df_ok)
    assert passed, f"已知description值应通过，但发现未知: {unknown}"
    print("  ✅ description值域验证 - 已知值通过")
    
    validator2 = DataSchemaValidator()
    df_new_desc = pd.DataFrame({'description': ['FBA storage fee', 'New Fee Type']})
    passed, unknown = validator2.validate_description_values(df_new_desc)
    assert not passed, "未知description值应触发警告"
    assert 'New Fee Type' in unknown, f"应检测到New Fee Type: {unknown}"
    print("  ✅ description值域验证 - 未知值检测")


def test_validator_numeric_columns():
    """测试数值类型验证"""
    validator = DataSchemaValidator()
    
    df_ok = pd.DataFrame({
        'quantity': [1, 2],
        'total': [100.0, 200.0],
    })
    passed, non_numeric = validator.validate_numeric_columns(df_ok)
    assert passed, f"数值列验证应通过，但发现非数值: {non_numeric}"
    print("  ✅ 数值类型验证 - 数值列通过")
    
    validator2 = DataSchemaValidator()
    df_str_num = pd.DataFrame({
        'quantity': ['1', '2'],
        'total': ['100', '200'],
    })
    passed, non_numeric = validator2.validate_numeric_columns(df_str_num)
    assert not passed, "非数值列应触发警告"
    print("  ✅ 数值类型验证 - 非数值检测")


def test_snapshot_save_and_compare():
    """测试快照保存与对比"""
    validator = DataSchemaValidator()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshot_path = Path(tmpdir) / 'snapshot.json'
        
        df_v1 = pd.DataFrame({
            'type': ['Order', 'Refund'],
            'total': [100, 50],
            'description': ['FBA storage fee', 'Cost of Advertising'],
        })
        
        validator.save_schema_snapshot(df_v1, snapshot_path)
        assert snapshot_path.exists(), "快照文件应存在"
        
        with open(snapshot_path, 'r') as f:
            snapshot = json.load(f)
        assert 'columns' in snapshot, "快照应包含columns"
        assert 'type_values' in snapshot, "快照应包含type_values"
        print("  ✅ 快照保存功能")
        
        # 对比：无变更
        comparison = validator.compare_with_snapshot(df_v1, snapshot_path)
        assert comparison['status'] == 'compared', "对比状态应为compared"
        assert len(comparison['changes']) == 0, f"无变更时changes应为空: {comparison['changes']}"
        print("  ✅ 快照对比 - 无变更")
        
        # 对比：有变更
        df_v2 = pd.DataFrame({
            'type': ['Order', 'Refund', 'NewType'],
            'total': [100, 50, 30],
            'description': ['FBA storage fee', 'New Fee', 'Cost of Advertising'],
            'new_column': [1, 2, 3],
        })
        
        comparison = validator.compare_with_snapshot(df_v2, snapshot_path)
        assert len(comparison['changes']) > 0, "有变更时changes不应为空"
        change_types = [c['type'] for c in comparison['changes']]
        assert 'type_value_added' in change_types, "应检测到type新增值"
        assert 'description_value_added' in change_types, "应检测到description新增值"
        assert 'column_added' in change_types, "应检测到新增列"
        print("  ✅ 快照对比 - 变更检测")


def test_impact_assessment():
    """测试影响评估"""
    validator = DataSchemaValidator()
    
    changes_critical = {
        'changes': [{'type': 'column_removed', 'detail': '删除列: total'}]
    }
    impact = validator.assess_impact(changes_critical)
    assert impact['level'] == 'critical', f"列删除应为critical级别: {impact['level']}"
    print("  ✅ 影响评估 - critical级别")
    
    changes_high = {
        'changes': [{'type': 'type_value_added', 'detail': 'type新增值: NewType'}]
    }
    impact = validator.assess_impact(changes_high)
    assert impact['level'] == 'high', f"type新增值应为high级别: {impact['level']}"
    print("  ✅ 影响评估 - high级别")
    
    changes_medium = {
        'changes': [{'type': 'column_added', 'detail': '新增列: new_col'}]
    }
    impact = validator.assess_impact(changes_medium)
    assert impact['level'] == 'medium', f"新增列应为medium级别: {impact['level']}"
    print("  ✅ 影响评估 - medium级别")


def test_metric_validation():
    """测试归因结果校验"""
    processor = PaymentProcessor()
    
    df = pd.DataFrame({
        'type': ['Order', 'Refund'],
        'quantity': [10, 5],
        'product sales': [1000, 500],
        'total': [800, -50],
        'promotional rebates': [50, 25],
        'selling fees': [150, 75],
        'fba fees': [30, 0],
        'description': ['', ''],
        '销量': [10, 0],
        '退货量': [0, 5],
        '销售额': [1000, 0],
        '退款额': [0, 500],
        '仓库赔偿': [0, 0],
        '折扣金额': [50, 25],
        '佣金': [150, 75],
        'fba运费': [30, 0],
        '退货处理费': [0, 0],
        '优惠券/秒杀': [0, 0],
        '广告费': [0, 0],
        '仓储费': [0, 0],
        '入库配置费': [0, 0],
        '移除费': [0, 0],
        '批清收益': [0, 0],
    })
    
    # 此测试验证_validate_metric_results不会抛出异常
    processor._validate_metric_results(df)
    print("  ✅ 归因结果校验 - 正常执行")


def test_full_validation():
    """测试完整验证流程"""
    validator = DataSchemaValidator()
    
    df = pd.DataFrame({
        'type': ['Order', 'Refund', 'Adjustment'],
        'quantity': [10, 5, 0],
        'product sales': [1000.0, 500.0, 0.0],
        'total': [800.0, -50.0, 30.0],
        'promotional rebates': [50.0, 25.0, 0.0],
        'selling fees': [150.0, 75.0, 0.0],
        'fba fees': [30.0, 0.0, 0.0],
        'description': ['FBA storage fee', 'Cost of Advertising', ''],
        'date/time': ['Jan 01, 2024', 'Jan 02, 2024', 'Jan 03, 2024'],
        'sku': ['SKU001', 'SKU002', np.nan],
    })
    
    report = validator.run_full_validation(df)
    
    assert 'column_check' in report, "报告应包含column_check"
    assert 'mapping_check' in report, "报告应包含mapping_check"
    assert 'type_check' in report, "报告应包含type_check"
    assert 'description_check' in report, "报告应包含description_check"
    assert 'numeric_check' in report, "报告应包含numeric_check"
    print("  ✅ 完整验证流程 - 报告结构正确")


def run_all_tests():
    """运行所有测试"""
    print("=" * 80)
    print("🧪 Payment 数据处理脚本 - 单元测试与集成测试")
    print("=" * 80)
    
    tests = [
        ("ifs函数", [
            test_ifs_basic,
            test_ifs_multi_condition,
        ]),
        ("数据变更验证", [
            test_validator_columns,
            test_validator_cols_mapping,
            test_validator_type_values,
            test_validator_description_values,
            test_validator_numeric_columns,
        ]),
        ("快照与对比", [
            test_snapshot_save_and_compare,
        ]),
        ("影响评估", [
            test_impact_assessment,
        ]),
        ("归因校验", [
            test_metric_validation,
        ]),
        ("集成测试", [
            test_full_validation,
        ]),
    ]
    
    total = 0
    passed = 0
    failed = 0
    
    for category, test_funcs in tests:
        print(f"\n📋 {category}")
        print("-" * 40)
        for func in test_funcs:
            total += 1
            try:
                func()
                passed += 1
            except Exception as e:
                failed += 1
                print(f"  ❌ {func.__name__} 失败: {e}")
    
    print("\n" + "=" * 80)
    print(f"📊 测试结果: 总计 {total} | 通过 {passed} | 失败 {failed}")
    print("=" * 80)
    
    if failed == 0:
        print("✅ 所有测试通过！")
    else:
        print(f"❌ 有 {failed} 个测试失败")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
