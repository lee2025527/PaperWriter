#!/usr/bin/env bash
# PaperWriter 技能安装器:把 skill/ 安装到本机终端智能体的技能目录。
# 用法:
#   ./install.sh                 # 自动检测已安装的智能体并安装
#   ./install.sh --target <目录>  # 安装到指定目录
#   ./install.sh --all           # 安装到所有已知位置
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/skill"
NAME="paper-writer"
TARGET=""

say() { printf '%s\n' "$*"; }

install_to() {
  local dest="$1"
  mkdir -p "$dest"
  rm -rf "$dest/$NAME"
  cp -R "$SRC" "$dest/$NAME"
  say "✅ 已安装到: $dest/$NAME"
}

# 解析参数
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --all) TARGET="all"; shift ;;
    *) say "未知参数: $1"; exit 1 ;;
  esac
done

say "PaperWriter 安装器"
say "技能本体: $SRC"
say ""

if [[ -n "$TARGET" && "$TARGET" != "all" ]]; then
  install_to "$TARGET"
else
  installed=0
  # Claude Code
  if [[ -d "$HOME/.claude" || "$TARGET" == "all" ]]; then
    install_to "$HOME/.claude/skills"; installed=1
  fi
  # ZCode 及通用 agents 目录
  if [[ -d "$HOME/.agents" || "$TARGET" == "all" ]]; then
    install_to "$HOME/.agents/skills"; installed=1
  fi
  if [[ "$installed" -eq 0 ]]; then
    say "未检测到已安装的终端智能体。两种方式任选:"
    say "  1) 手动指定目录: ./install.sh --target ~/.claude/skills"
    say "  2) 直接在项目里使用: 不安装,把本仓库 clone 到任意位置,"
    say "     在对话中让智能体读取 <仓库>/skill/SKILL.md 即可。"
    exit 1
  fi
fi

say ""
say "下一步:"
say "  1) pip install -r \"$HERE/requirements.txt\""
say "  2) cp \"$HERE/.env.example\" <你的项目目录>/.env 并填入 SERPAPI_KEY"
say "  3) cd <你的项目目录> && claude   # 或你使用的终端智能体"
say "  4) 对智能体说: 写论文"
