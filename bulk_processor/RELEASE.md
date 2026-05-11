# 亚马逊广告数据处理器 - 发布说明

## 项目概述

这是一个独立的桌面GUI应用,用于处理亚马逊广告bulk文件并生成优化策略表格。

## 项目结构

```
bulk_processor_app/
├── src/
│   ├── __init__.py          # 包初始化
│   ├── main.py              # 应用入口
│   ├── gui.py               # GUI界面
│   ├── processor.py         # 数据处理核心
│   └── utils.py             # 工具函数
├── assets/
│   └── icon.ico             # 应用图标
├── .github/
│   └── workflows/
│       └── build.yml        # GitHub Actions配置
├── build.spec               # PyInstaller配置
├── requirements.txt         # 依赖列表
├── README.md                # 使用说明
└── .gitignore               # Git忽略文件
```

## 功能特性

✅ 自动识别和处理bulk文件
✅ 计算环比数据
✅ 实时进度显示
✅ 参数配置
✅ 跨平台支持(Windows/macOS/Linux)

## 如何发布应用

### 方法1: 使用GitHub Actions自动打包(推荐)

1. **创建GitHub仓库**
   ```bash
   cd /Users/tank/Downloads/TRAE/bulk_version/bulk_processor_app
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. **推送到GitHub**
   ```bash
   # 在GitHub上创建新仓库
   git remote add origin https://github.com/你的用户名/bulk_processor.git
   git branch -M main
   git push -u origin main
   ```

3. **创建发布标签**
   ```bash
   git tag -a v1.0.0 -m "Release version 1.0.0"
   git push origin v1.0.0
   ```

4. **等待自动打包**
   - GitHub Actions会自动在Windows/macOS/Linux上打包
   - 打包完成后会自动创建Release
   - 在GitHub仓库的Releases页面下载对应平台的可执行文件

### 方法2: 本地打包

**macOS:**
```bash
cd /Users/tank/Downloads/TRAE/bulk_version/bulk_processor_app
pip install -r requirements.txt
pyinstaller build.spec
```

**Windows:**
```cmd
cd C:\path\to\bulk_processor_app
pip install -r requirements.txt
pyinstaller build.spec
```

**Linux:**
```bash
cd /path/to/bulk_processor_app
pip install -r requirements.txt
pyinstaller build.spec
```

## 使用方法

### 开发模式

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **运行应用**
   ```bash
   python src/main.py
   ```

### 生产模式

1. **下载可执行文件**
   - Windows: `bulk_processor.exe`
   - macOS: `bulk_processor.app`
   - Linux: `bulk_processor`

2. **运行应用**
   - 双击可执行文件即可运行
   - 无需安装Python或任何依赖

## 技术栈

- **GUI框架:** Tkinter (Python内置)
- **数据处理:** Pandas + NumPy
- **打包工具:** PyInstaller
- **自动化:** GitHub Actions

## 打包体积

- Windows: 约30-50MB
- macOS: 约30-50MB
- Linux: 约30-50MB

## 注意事项

1. **图标文件**
   - 当前使用占位图标
   - 建议替换为自定义图标(assets/icon.ico)

2. **代码签名**
   - Windows: 需要代码签名证书
   - macOS: 需要Apple开发者证书
   - Linux: 无需签名

3. **权限问题**
   - macOS可能需要允许运行未签名应用
   - Windows可能需要允许运行未知发布者的应用

## 后续优化

1. 添加自定义图标
2. 实现代码签名
3. 添加自动更新功能
4. 支持批量处理
5. 添加数据可视化

## 许可证

MIT License

## 联系方式

如有问题,请在GitHub上提交Issue。
