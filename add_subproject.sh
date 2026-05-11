#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

usage() {
    cat <<EOF
用法: ./add_subproject.sh <子项目名称> <源仓库URL> [源分支]

将新项目作为独立子文件夹合并到 amazon_projects 仓库，
自动保留完整提交历史并纳入统一打包流程。

参数:
  子项目名称    新子文件夹名称（如 new_tool）
  源仓库URL     源仓库的 Git URL（如 https://github.com/user/repo.git）
  源分支        可选，默认为 main

示例:
  ./add_subproject.sh new_tool https://github.com/devbyte7475/new_tool.git
  ./add_subproject.sh new_tool https://github.com/devbyte7475/new_tool.git master

说明:
  - 统一打包工作流 (.github/workflows/build.yml) 会自动检测所有
    包含 requirements.txt 的子目录，无需手动修改任何配置文件。
  - 新子项目只需确保包含 requirements.txt 和入口文件
    (.spec / main.py / <项目名>.py) 即可被自动纳入打包。
EOF
}

if [ $# -lt 2 ]; then
    usage
    exit 1
fi

PROJECT_NAME="$1"
SOURCE_URL="$2"
SOURCE_BRANCH="${3:-main}"

if [ -d "$REPO_DIR/$PROJECT_NAME" ]; then
    echo "错误: 子项目 '$PROJECT_NAME' 已存在"
    exit 1
fi

echo "=========================================="
echo "  添加子项目: $PROJECT_NAME"
echo "  源仓库: $SOURCE_URL"
echo "  源分支: $SOURCE_BRANCH"
echo "=========================================="

cd "$REPO_DIR"

echo ""
echo "[1/4] 添加远程仓库..."
REMOTE_NAME="${PROJECT_NAME}_remote"
if git remote | grep -q "^${REMOTE_NAME}$"; then
    echo "远程 '$REMOTE_NAME' 已存在，跳过"
else
    git remote add "$REMOTE_NAME" "$SOURCE_URL"
fi

echo ""
echo "[2/4] 拉取源仓库数据..."
git fetch "$REMOTE_NAME" || {
    echo "错误: 无法拉取源仓库，请检查 URL 和网络"
    exit 1
}

echo ""
echo "[3/4] 合并子项目（保留完整提交历史）..."
git subtree add --prefix="$PROJECT_NAME" "$REMOTE_NAME/$SOURCE_BRANCH" || {
    echo "错误: subtree 合并失败"
    exit 1
}

echo ""
echo "[4/4] 移除子项目自带的 GitHub Actions（由统一工作流管理）..."
if [ -d "$REPO_DIR/$PROJECT_NAME/.github" ]; then
    rm -rf "$REPO_DIR/$PROJECT_NAME/.github"
    git add -A
    git commit -m "移除 $PROJECT_NAME 自带的 GitHub Actions 工作流" || true
fi

echo ""
echo "=========================================="
echo "  子项目 '$PROJECT_NAME' 添加成功！"
echo "=========================================="
echo ""
echo "统一打包工作流会自动检测到新子项目，条件："
echo "  - 子目录包含 requirements.txt"
echo "  - 子目录包含入口文件 (.spec / main.py / <项目名>.py)"
echo ""
echo "如需推送到远程仓库，请执行："
echo "  git push origin main"
echo ""
echo "如需触发打包，请执行："
echo "  git tag v1.0.0 && git push origin v1.0.0"
echo "  或在 GitHub Actions 页面手动触发"
