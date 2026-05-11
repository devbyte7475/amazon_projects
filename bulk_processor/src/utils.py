"""
工具函数模块
"""
import json
from pathlib import Path
from typing import Dict, Any


class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.config_file = self._get_config_path()
        self.default_config = {
            "thresholds": {
                "impressions": 4200,
                "ctr": 0.0045,
                "cvr": 0.1,
                "acos": 0.3
            }
        }
    
    def _get_config_path(self) -> Path:
        """获取配置文件路径"""
        config_dir = Path.home() / ".bulk_processor"
        config_dir.mkdir(exist_ok=True)
        return config_dir / "config.json"
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置"""
        if not self.config_file.exists():
            return self.default_config.copy()
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return self.default_config.copy()
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def reset_config(self) -> Dict[str, Any]:
        """重置配置"""
        self.save_config(self.default_config.copy())
        return self.default_config.copy()
