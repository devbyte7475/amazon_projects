"""
亚马逊广告数据处理器 - 终端版
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.processor import BulkDataProcessor
from src.utils import ConfigManager


def log(message: str, level: str = "info"):
    """终端日志输出"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = {
        "info": "ℹ",
        "success": "✓",
        "warning": "⚠",
        "error": "✗",
    }.get(level, " ")
    print(f"  [{timestamp}] {prefix} {message}")


def progress_callback(message: str):
    """处理进度回调"""
    if "处理完成" in message:
        log(message, "success")
    elif "失败" in message:
        log(message, "error")
    else:
        log(message, "info")


def auto_search_folder() -> str:
    """自动搜索包含 bulk 文件的文件夹"""
    search_paths = [
        Path.cwd(),
        Path.home() / "Downloads",
        Path.home() / "Desktop",
    ]

    for search_path in search_paths:
        if not search_path.exists():
            continue
        files = list(search_path.glob("bulk-*.xlsx"))
        if len(files) == 2:
            return str(search_path)

    return ""


def show_config(config: dict):
    """显示当前配置"""
    thresholds = config.get("thresholds", {})
    print("\n  当前处理参数:")
    print(f"    曝光量阈值: {thresholds.get('impressions', 4200):,}")
    print(f"    点击率阈值: {thresholds.get('ctr', 0.0045) * 100:.2f}%")
    print(f"    转化率阈值: {thresholds.get('cvr', 0.1) * 100:.0f}%")
    print(f"    ACOS阈值:   {thresholds.get('acos', 0.3) * 100:.0f}%")
    print()


def show_results(results: dict, folder_path: str):
    """显示处理结果"""
    total_rows = sum(len(df) for df in results.values())

    print("\n" + "=" * 50)
    print("  处理结果")
    print("=" * 50)
    print(f"  处理文件: 2 个")
    print(f"  总数据行: {total_rows:,} 行")
    print(f"  输出文件: {len(results)} 个")
    print(f"  输出目录: {folder_path}")
    for ad_type in results:
        print(f"    - bulk_{ad_type}_数据源表格.csv")
    print("=" * 50)


def cmd_process(args):
    """执行数据处理"""
    config_manager = ConfigManager()
    config = config_manager.load_config()

    folder_path = args.folder

    if not folder_path:
        folder_path = auto_search_folder()
        if not folder_path:
            log("未找到包含 bulk 文件的文件夹，请通过 -f 参数指定路径", "error")
            sys.exit(1)
        log(f"自动发现文件夹: {folder_path}", "success")

    folder = Path(folder_path)
    if not folder.exists():
        log(f"文件夹不存在: {folder_path}", "error")
        sys.exit(1)

    if args.show_config or args.config:
        show_config(config)

    if args.config:
        thresholds = config.get("thresholds", {})
        for key in ["impressions", "ctr", "cvr", "acos"]:
            val = getattr(args, f"set_{key}", None)
            if val is not None:
                if key == "impressions":
                    thresholds[key] = int(val)
                else:
                    thresholds[key] = float(val)
        config_manager.save_config(config)
        log("配置已更新", "success")
        show_config(config)
        if not args.folder:
            return

    print("\n  亚马逊广告数据处理器")
    print("  " + "-" * 30)

    try:
        processor = BulkDataProcessor(str(folder), config)

        log("正在识别文件...")
        old_file, new_file = processor.find_excel_files()
        log(f"旧表: {Path(old_file).name}", "success")
        log(f"新表: {Path(new_file).name}", "success")

        results = processor.process(progress_callback=progress_callback)

        show_results(results, str(folder))
        log("数据处理完成!", "success")

    except Exception as e:
        log(f"处理失败: {str(e)}", "error")
        sys.exit(1)


def cmd_config(args):
    """管理配置"""
    config_manager = ConfigManager()
    config = config_manager.load_config()

    if args.reset:
        config = config_manager.reset_config()
        log("配置已重置为默认值", "success")

    thresholds = config.get("thresholds", {})
    for key in ["impressions", "ctr", "cvr", "acos"]:
        val = getattr(args, f"set_{key}", None)
        if val is not None:
            if key == "impressions":
                thresholds[key] = int(val)
            else:
                thresholds[key] = float(val)

    config_manager.save_config(config)
    show_config(config)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="亚马逊广告数据处理器 - 终端版",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m src.main                        # 自动搜索 bulk 文件
  python -m src.main -f /path/to/folder     # 指定文件夹
  python -m src.main config --show          # 查看配置
  python -m src.main config --reset         # 重置配置
  python -m src.main config --set-impressions 5000  # 修改阈值
        """
    )
    subparsers = parser.add_subparsers(dest="command")

    # process 子命令（默认）
    process_parser = subparsers.add_parser("process", help="处理广告数据")
    process_parser.add_argument("-f", "--folder", default="", help="包含 bulk 文件的文件夹路径")
    process_parser.add_argument("--show-config", action="store_true", help="显示当前配置")
    process_parser.set_defaults(func=cmd_process)

    # config 子命令
    config_parser = subparsers.add_parser("config", help="管理处理参数配置")
    config_parser.add_argument("--show", action="store_true", help="显示当前配置")
    config_parser.add_argument("--reset", action="store_true", help="重置为默认配置")
    config_parser.add_argument("--set-impressions", dest="set_impressions", type=float, help="设置曝光量阈值")
    config_parser.add_argument("--set-ctr", dest="set_ctr", type=float, help="设置点击率阈值")
    config_parser.add_argument("--set-cvr", dest="set_cvr", type=float, help="设置转化率阈值")
    config_parser.add_argument("--set-acos", dest="set_acos", type=float, help="设置ACOS阈值")
    config_parser.set_defaults(func=cmd_config)

    # 兼容无子命令时直接处理
    if len(sys.argv) == 1 or (len(sys.argv) > 1 and not sys.argv[1].startswith("-") and sys.argv[1] not in ("process", "config")):
        args = parser.parse_args(["process"] + sys.argv[1:])
    else:
        args = parser.parse_args()

    if not hasattr(args, "func"):
        # 默认执行 process
        args = parser.parse_args(["process"] + sys.argv[1:])

    # 支持 config --show 时同时更新参数
    if args.command == "config":
        args.func(args)
    elif args.command == "process" or args.command is None:
        # 如果指定了 config 参数，也执行配置更新
        if any(getattr(args, f"set_{k}", None) is not None for k in ["impressions", "ctr", "cvr", "acos"]):
            args.config = True
        else:
            args.config = False
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
