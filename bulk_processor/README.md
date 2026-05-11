# 亚马逊广告数据处理器

一个独立的桌面应用,用于处理亚马逊广告bulk文件并生成优化策略表格。

## 功能特性

- ✅ 自动识别和处理bulk文件
- ✅ 计算环比数据
- ✅ 实时进度显示
- ✅ 参数配置
- ✅ 跨平台支持(Windows/macOS/Linux)

## 使用方法

1. 下载对应平台的可执行文件
2. 双击运行应用
3. 选择包含bulk文件的文件夹
4. 点击"开始处理"
5. 查看处理结果

## 开发

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行应用

```bash
python src/main.py
```

### 打包应用

```bash
pyinstaller build.spec
```

## 许可证

MIT License
