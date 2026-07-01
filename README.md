# CC Sessions

Claude Code 会话管理工具 —— 在 Web UI 中浏览、搜索、管理所有 Claude Code 对话会话。

## 功能

- **会话浏览**：左侧列表 + 右侧详情，展示完整对话流（用户消息 / Claude 回复 / 工具调用）
- **实时搜索**：搜索标题、首条消息、项目路径、自定义名称，300ms 防抖
- **智能排序**：按活跃度 / 按消息数 / 按时间，三种模式切换，置顶会话始终靠前
- **会话置顶**：列表项右侧 📍 图标一键置顶常用会话
- **恢复会话**：一键复制 `cd "原始目录"; cl -r <session-id>` 命令，兼容 Git Bash / PowerShell / CMD
- **重命名**：自定义会话名称，持久化存储
- **删除会话**：输入 `y` 确认删除，同时清理本机 JSONL 文件和子目录
- **会话摘要**：生成 Markdown 摘要文件，包含用户问题与 Claude 回复要点，弹窗渲染查看

## 安装

### 前置要求

- Python 3.6+（无外部依赖，仅用标准库）
- Claude Code 已安装并产生过会话

### 文件部署

将 `cc.py` 和 `cc.html` 放到同一目录（如 `~/bin/`）：

```bash
# 示例：放到 ~/bin/
mkdir -p ~/bin
cp cc.py cc.html ~/bin/
```

### 注册命令

**Git Bash（推荐）：**

```bash
# 编辑 ~/.bashrc，添加：
alias cc='python ~/bin/cc.py'
```

**CMD / PowerShell（Windows）：**

在 PATH 可达的目录（如 `%LOCALAPPDATA%\Microsoft\WindowsApps\`）创建 `cc.bat`：

```batch
@echo off
python "C:\Users\<你的用户名>\bin\cc.py" %*
```

**macOS / Linux：**

```bash
# 编辑 ~/.zshrc 或 ~/.bashrc，添加：
alias cc='python3 ~/bin/cc.py'
```

### 配置生效

```bash
source ~/.bashrc   # Git Bash
source ~/.zshrc    # macOS zsh
```

## 使用

### 启动 Web UI

```bash
cc              # 启动服务，浏览器打开 http://127.0.0.1
Ctrl+C          # 关闭服务
```

### CLI 命令

| 命令 | 作用 |
|------|------|
| `cc` | 启动 Web UI（默认端口 80） |
| `cc serve [端口]` | 指定端口启动 |
| `cc list [-n N] [-p 项目] [--id]` | 列出会话 |
| `cc search <关键词>` | 搜索会话 |
| `cc show <session-id前缀>` | 查看会话详情 |
| `cc resume <session-id前缀>` | 输出恢复命令 |
| `cc index` | 生成 Markdown 索引到聊天记录目录 |

### 恢复会话

Web UI 中点击恢复按钮，或在 CLI 中：

```bash
cc resume <session-id前缀>
# 输出：cd "D:\项目路径"; cl -r <full-session-id>
# 复制粘贴到终端即可
```

> **注意**：Claude Code 2.1.195+ 的 `--resume` 需要在会话原始工作目录下执行，因此恢复命令包含 `cd` 步骤。命令分隔符使用 `;` 兼容 Git Bash / PowerShell / CMD。

## 跨平台兼容性

| 平台 | 状态 | 说明 |
|------|------|------|
| Windows + Git Bash | ✅ 完全支持 | 主开发环境，alias 注册 |
| Windows + PowerShell | ✅ 完全支持 | 通过 .bat 注册，`;` 分隔符兼容 |
| Windows + CMD | ✅ 完全支持 | 通过 .bat 注册 |
| macOS | ✅ 兼容 | Python3 自带，`~/.claude/projects/` 路径一致 |
| Linux | ✅ 兼容 | 路径结构与 macOS 相同 |

### macOS / Linux 注意事项

- 使用 `python3` 而非 `python`
- 端口 80 需要 root 权限，建议用 `cc serve 8080` 等非特权端口
- Claude Code 的会话目录 `~/.claude/projects/` 结构跨平台一致，无需修改

## 数据存储

| 文件 | 作用 |
|------|------|
| `~/.claude/cc-session-names.json` | 自定义会话名称 |
| `~/.claude/cc-pinned.json` | 置顶会话 ID 列表 |

## 技术细节

- 解析 `~/.claude/projects/` 下的 JSONL 会话文件
- 提取 `ai-title`、`user`、`assistant`、`tool_use` 消息
- 项目路径从 JSONL 的 `cwd` 字段获取，自动缩写 `~/`
- Web 服务用 Python 内置 `http.server`，零外部依赖
- 前端单页 `cc.html`，暗色主题，前后端分离

## License

MIT
