#!/usr/bin/env python3
"""cc - Claude Code session manager"""
import json, os, sys, glob, re, shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
import unicodedata
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

PROJECTS_DIR = Path.home() / ".claude" / "projects"
CHAT_LOG_DIR = Path.home() / "Desktop" / "提示词系列" / "聊天记录"
NAMES_FILE = Path.home() / ".claude" / "cc-session-names.json"
PINNED_FILE = Path.home() / ".claude" / "cc-pinned.json"
BACKUP_DIR = Path("D:/cc-sessions-backup")
TZ = timezone(timedelta(hours=8))

def load_names():
    try:
        return json.loads(NAMES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_names(names):
    NAMES_FILE.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")

def load_pinned():
    try:
        return json.loads(PINNED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_pinned(pinned):
    PINNED_FILE.write_text(json.dumps(pinned, ensure_ascii=False, indent=2), encoding="utf-8")

def _w(s):
    """Display width accounting for CJK characters."""
    w = 0
    for c in s:
        w += 2 if unicodedata.east_asian_width(c) in "WF" else 1
    return w

def _pad(s, width):
    """Pad string to exact display width."""
    return s + " " * max(0, width - _w(s))

def _trunc(s, max_w):
    """Truncate string to max display width."""
    w, out = 0, ""
    for c in s:
        cw = 2 if unicodedata.east_asian_width(c) in "WF" else 1
        if w + cw > max_w - 1:
            return out + "…"
        out += c
        w += cw
    return out

def pretty_project(dir_name, cwd=""):
    # Use real cwd if available for accurate path
    if cwd:
        p = cwd.replace("\\", "/")
        home = str(Path.home()).replace("\\", "/")
        if p.startswith(home):
            rest = p[len(home):]
            return "~/" + rest.lstrip("/") if rest else "~"
        if len(p) >= 2 and p[1] == ":":
            return "/" + p[0].lower() + "/" + p[3:]
        return p
    # Fallback: decode from directory name
    p = dir_name
    p = p.replace("C--Users-zcy-", "~/")
    p = p.replace("C--Users-zcy", "~")
    while '--' in p:
        p = p.replace('--', '-')
    parts = [x for x in p.split('-') if x]
    path = '/'.join(parts)
    if len(path) >= 2 and path[0].isupper() and path[1] == '/':
        path = '/' + path[0].lower() + path[1:]
    return path

def extract_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                return item.get("text", "")
    return ""

def parse_session(jsonl_path):
    s = {
        "id": Path(jsonl_path).stem,
        "project_dir": Path(jsonl_path).parent.name,
        "cwd": "",
        "title": "",
        "first_msg": "",
        "timestamp": None,
        "msg_count": 0,
    }
    first_real_user_msg = None
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = entry.get("type")
                if t == "ai-title":
                    s["title"] = entry.get("aiTitle", "")
                elif t == "user":
                    if not s["cwd"]:
                        s["cwd"] = entry.get("cwd", "")
                    if not entry.get("isMeta"):
                        s["msg_count"] += 1
                    if first_real_user_msg is None and not entry.get("isMeta"):
                        msg = entry.get("message", {})
                        content = extract_content(msg.get("content", ""))
                        if content and not content.startswith("<"):
                            first_real_user_msg = content
                            ts = entry.get("timestamp")
                            if ts:
                                s["timestamp"] = ts
    except Exception:
        pass
    s["first_msg"] = (first_real_user_msg or "")[:200].replace("\n", " ").strip()
    return s

def load_all_sessions(project_filter=None):
    pattern = str(PROJECTS_DIR / "**" / "*.jsonl")
    sessions = []
    for f in glob.glob(pattern, recursive=True):
        if "subagents" in f:
            continue
        if project_filter and project_filter.lower() not in f.lower():
            continue
        sessions.append(parse_session(f))
    sessions.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    return sessions

def fmt_time(ts_str):
    if not ts_str:
        return "-"
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(TZ)
        return dt.strftime("%m-%d %H:%M")
    except Exception:
        return "-"

def cmd_list(args):
    limit, pf, show_id = 30, None, False
    i = 0
    while i < len(args):
        if args[i] in ("-n", "--limit") and i + 1 < len(args):
            limit = int(args[i + 1]); i += 2
        elif args[i] in ("-p", "--project") and i + 1 < len(args):
            pf = args[i + 1]; i += 2
        elif args[i] == "--id":
            show_id = True; i += 1
        else:
            i += 1
    sessions = load_all_sessions(pf)
    shown = sessions[:limit]
    hdr = f" {'#':>3}  {_pad('时间', 12)}  {_pad('项目', 22)}  {_pad('标题', 32)}  消息"
    if show_id:
        hdr += "  Session ID"
    print(hdr)
    print(" " + "-" * (_w(hdr) - 1))
    for i, s in enumerate(shown, 1):
        proj = _trunc(pretty_project(s["project_dir"], s.get("cwd", "")), 22)
        title = _trunc(s["title"] or s["first_msg"][:40], 32)
        line = f" {i:>3}  {_pad(fmt_time(s['timestamp']), 12)}  {_pad(proj, 22)}  {_pad(title, 32)}  {s['msg_count']}"
        if show_id:
            line += f"  {s['id'][:12]}…"
        print(line)
    total = len(sessions)
    if total > limit:
        print(f"\n 显示 {limit}/{total}，加 -n {total} 查看全部")

def cmd_search(args):
    if not args:
        print("用法: cc search <关键词>")
        return
    kw = " ".join(args).lower()
    sessions = [s for s in load_all_sessions()
                if kw in (s["title"] + " " + s["first_msg"]).lower()]
    if not sessions:
        print(f"未找到: {kw}")
        return
    print(f" 找到 {len(sessions)} 个会话:\n")
    for i, s in enumerate(sessions, 1):
        proj = _trunc(pretty_project(s["project_dir"], s.get("cwd", "")), 20)
        title = s["title"] or s["first_msg"][:60]
        print(f" {i}. [{fmt_time(s['timestamp'])}] {proj}")
        print(f"    {title}")
        print(f"    ID: {s['id']}\n")

def cmd_show(args):
    if not args:
        print("用法: cc show <session-id前缀>")
        return
    prefix = args[0]
    sessions = [s for s in load_all_sessions() if s["id"].startswith(prefix)]
    if not sessions:
        print(f"未找到 ID 前缀: {prefix}")
        return
    s = sessions[0]
    print(f"会话: {s['id']}")
    print(f"标题: {s['title'] or '(无)'}")
    print(f"项目: {pretty_project(s['project_dir'], s.get('cwd', ''))}")
    print(f"时间: {fmt_time(s['timestamp'])}")
    print(f"消息: {s['msg_count']} 条用户消息")
    if s["first_msg"]:
        print(f"首问: {s['first_msg'][:120]}")
    # Extract all user messages for summary
    pattern = str(PROJECTS_DIR / s["project_dir"] / f"{s['id']}.jsonl")
    files = glob.glob(pattern)
    if files:
        print("\n用户消息:")
        with open(files[0], "r", encoding="utf-8") as f:
            idx = 0
            for line in f:
                try:
                    entry = json.loads(line.strip())
                except Exception:
                    continue
                if entry.get("type") == "user" and not entry.get("isMeta"):
                    content = extract_content(entry.get("message", {}).get("content", ""))
                    if content and not content.startswith("<"):
                        idx += 1
                        t = fmt_time(entry.get("timestamp", ""))
                        print(f"  {idx}. [{t}] {content[:100]}")

def cmd_index(args):
    sessions = load_all_sessions()
    by_proj = {}
    for s in sessions:
        by_proj.setdefault(s["project_dir"], []).append(s)
    lines = [
        "# Claude Code 会话索引",
        f"\n生成时间: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M')}",
        f"会话总数: {len(sessions)}\n",
    ]
    for proj, ss in sorted(by_proj.items()):
        pp = pretty_project(proj, ss[0].get("cwd", ""))
        lines.append(f"\n## {pp}\n")
        lines.append("| 时间 | 标题 | 首问 | 消息 |")
        lines.append("|------|------|------|------|")
        for s in ss:
            t = fmt_time(s["timestamp"])
            title = (s["title"] or "-")[:40]
            msg = (s["first_msg"][:40] or "-").replace("|", "\\|")
            lines.append(f"| {t} | {title} | {msg} | {s['msg_count']} |")
    out = CHAT_LOG_DIR / "claude-code-sessions-index.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"已生成: {out}")
    print(f"共 {len(sessions)} 个会话，{len(by_proj)} 个项目")

def cmd_resume(args):
    if not args:
        print("用法: cc resume <session-id前缀>")
        print("  根据前缀匹配会话，输出可直接粘贴的恢复命令")
        return
    prefix = args[0]
    sessions = [s for s in load_all_sessions() if s["id"].startswith(prefix)]
    if not sessions:
        print(f"未找到 ID 前缀: {prefix}")
        return
    if len(sessions) > 1:
        print(f"匹配到 {len(sessions)} 个会话，请提供更长前缀:\n")
        for s in sessions[:5]:
            proj = pretty_project(s["project_dir"], s.get("cwd", ""))
            title = s["title"] or s["first_msg"][:50]
            print(f"  {s['id'][:16]}…  {fmt_time(s['timestamp'])}  {title}")
        return
    s = sessions[0]
    title = s["title"] or s["first_msg"][:60]
    cwd = s.get("cwd", "")
    print(f"会话: {title}")
    print(f"时间: {fmt_time(s['timestamp'])}  消息: {s['msg_count']} 条")
    if cwd:
        print(f"目录: {cwd}")
    print(f"\n恢复命令:")
    if cwd:
        print(f'  cd "{cwd}"; cl -r {s["id"]}')
    else:
        print(f"  cl -r {s['id']}")

def get_session_messages(project_dir, session_id):
    """Extract user and assistant messages from a session."""
    pattern = str(PROJECTS_DIR / project_dir / f"{session_id}.jsonl")
    files = glob.glob(pattern)
    messages = []
    if not files:
        return messages
    with open(files[0], "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
            except Exception:
                continue
            t = entry.get("type")
            ts = fmt_time(entry.get("timestamp", ""))
            if t == "user" and not entry.get("isMeta"):
                content = extract_content(entry.get("message", {}).get("content", ""))
                if content and not content.startswith("<"):
                    messages.append({"role": "user", "time": ts, "content": content[:800]})
            elif t == "assistant":
                msg = entry.get("message", {})
                content_list = msg.get("content", [])
                if isinstance(content_list, list):
                    for item in content_list:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text = item.get("text", "").strip()
                            if text:
                                messages.append({"role": "assistant", "time": ts, "content": text[:800]})
                        elif isinstance(item, dict) and item.get("type") == "tool_use":
                            name = item.get("name", "")
                            inp = item.get("input", {})
                            # Show a brief summary of tool calls
                            if name == "Bash":
                                cmd = inp.get("command", "")[:120]
                                messages.append({"role": "tool", "time": ts, "content": f"$ {cmd}"})
                            elif name in ("Read", "Write", "Edit"):
                                fp = inp.get("file_path", "")
                                messages.append({"role": "tool", "time": ts, "content": f"{name}: {fp}"})
                            else:
                                messages.append({"role": "tool", "time": ts, "content": f"{name}()"})
    return messages

def session_to_dict(s):
    names = load_names()
    pinned = load_pinned()
    custom = names.get(s["id"], "")
    title = custom or s["title"] or s["first_msg"][:80] or "(空)"
    jsonl = PROJECTS_DIR / s["project_dir"] / f"{s['id']}.jsonl"
    fsize = round(jsonl.stat().st_size / 1024 / 1024, 2) if jsonl.exists() else 0
    return {
        "id": s["id"],
        "title": title,
        "original_title": s["title"] or s["first_msg"][:80] or "(空)",
        "custom": bool(custom),
        "pinned": s["id"] in pinned,
        "project": pretty_project(s["project_dir"], s.get("cwd", "")),
        "cwd": s.get("cwd", ""),
        "time": fmt_time(s["timestamp"]),
        "timestamp": s["timestamp"] or "",
        "msg_count": s["msg_count"],
        "first_msg": s["first_msg"],
        "file_size": fsize,
    }

def generate_summary(jsonl_path):
    """Generate a concise markdown summary of a session and save to BACKUP_DIR."""
    jsonl_path = Path(jsonl_path)
    sid = jsonl_path.stem
    title, first_ts, user_msgs, pairs = "", "", [], []
    current_user = None
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = entry.get("type")
                ts = entry.get("timestamp", "")
                if t == "ai-title":
                    title = entry.get("aiTitle", "")
                elif t == "user" and not entry.get("isMeta"):
                    content = extract_content(entry.get("message", {}).get("content", ""))
                    if content and not content.startswith("<"):
                        if not first_ts:
                            first_ts = ts
                        current_user = content
                        user_msgs.append(content)
                elif t == "assistant" and current_user:
                    msg = entry.get("message", {})
                    for block in msg.get("content", []):
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "").strip()
                            if text:
                                pairs.append((current_user, text[:300]))
                                current_user = None
                                break
    except Exception as e:
        return None, str(e)

    project_dir = jsonl_path.parent.name
    cwd = ""
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line.strip())
                if entry.get("type") == "user":
                    cwd = entry.get("cwd", "")
                    break
    except Exception:
        pass

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BACKUP_DIR / f"{sid}.md"
    lines = [
        f"# {title or sid[:12]}",
        f"",
        f"- **项目**: {pretty_project(project_dir, cwd)}",
        f"- **时间**: {fmt_time(first_ts)}",
        f"- **消息数**: {len(user_msgs)}",
        f"",
    ]
    for i, (q, a) in enumerate(pairs, 1):
        lines.append(f"**{i}. {q[:120]}**")
        lines.append(f"")
        lines.append(f"> {a}")
        lines.append(f"")
    # Questions without assistant response
    for q in user_msgs[len(pairs):]:
        lines.append(f"- {q[:120]}")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path, None

def _load_html():
    html_path = Path(__file__).parent / "cc.html"
    return html_path.read_text(encoding="utf-8")

def cmd_serve(args):
    port = 80
    if args and args[0].isdigit():
        port = int(args[0])
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            path, qs = parsed.path, parse_qs(parsed.query)
            if path == "/":
                self._resp(200, "text/html", _load_html().encode())
            elif path == "/api/sessions":
                names = load_names()
                data = [session_to_dict(s) for s in load_all_sessions()]
                self._json(data)
            elif path == "/api/search":
                q = qs.get("q", [""])[0].lower()
                names = load_names()
                data = [session_to_dict(s) for s in load_all_sessions()
                        if q in (s["title"] + " " + s["first_msg"] + " " +
                                 names.get(s["id"], "") + " " +
                                 pretty_project(s["project_dir"], s.get("cwd", ""))).lower()]
                self._json(data)
            elif path.startswith("/api/session/"):
                sid = path.split("/")[-1]
                found = [s for s in load_all_sessions() if s["id"] == sid]
                if found:
                    s = found[0]
                    msgs = get_session_messages(s["project_dir"], s["id"])
                    backup = BACKUP_DIR / f"{s['id']}.jsonl"
                    summary = BACKUP_DIR / f"{s['id']}.md"
                    jsonl = PROJECTS_DIR / s["project_dir"] / f"{s['id']}.jsonl"
                    self._json({**session_to_dict(s), "messages": msgs,
                                "has_backup": backup.exists(),
                                "has_summary": summary.exists()})
                else:
                    self._json({"error": "not found"}, 404)
            elif path.startswith("/api/summary-content/"):
                sid = path.split("/")[-1]
                summary = BACKUP_DIR / f"{sid}.md"
                if summary.exists():
                    content = summary.read_text(encoding="utf-8")
                    self._json({"ok": True, "content": content})
                else:
                    self._json({"error": "no summary"}, 404)
            else:
                self._resp(404, "text/plain", b"Not Found")
        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/rename":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8", errors="replace"))
                sid, name = body.get("id", ""), body.get("name", "").strip()
                if not sid:
                    self._json({"error": "missing id"}, 400)
                    return
                names = load_names()
                if name:
                    names[sid] = name
                else:
                    names.pop(sid, None)
                save_names(names)
                self._json({"ok": True, "name": name or names.get(sid, "")})
            elif parsed.path == "/api/delete":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8", errors="replace"))
                sid = body.get("id", "")
                if not sid:
                    self._json({"error": "missing id"}, 400)
                    return
                deleted = False
                for f in glob.glob(str(PROJECTS_DIR / "**" / f"{sid}.jsonl"), recursive=True):
                    if "subagents" in f:
                        continue
                    # Delete subagent dir
                    sub_dir = Path(f).parent / sid
                    if sub_dir.is_dir():
                        shutil.rmtree(sub_dir, ignore_errors=True)
                    os.remove(f)
                    deleted = True
                # Clean custom name
                names = load_names()
                names.pop(sid, None)
                save_names(names)
                # Clean pinned
                pinned = load_pinned()
                pinned = [p for p in pinned if p != sid]
                save_pinned(pinned)
                # Clean empty project dirs
                for proj_dir in PROJECTS_DIR.iterdir():
                    if proj_dir.is_dir() and not list(proj_dir.glob("*.jsonl")):
                        shutil.rmtree(proj_dir, ignore_errors=True)
                self._json({"ok": deleted})
            elif parsed.path == "/api/pin":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8", errors="replace"))
                sid = body.get("id", "")
                if not sid:
                    self._json({"error": "missing id"}, 400)
                    return
                pinned = load_pinned()
                if sid in pinned:
                    pinned.remove(sid)
                else:
                    pinned.append(sid)
                save_pinned(pinned)
                self._json({"ok": True, "pinned": sid in pinned})
            elif parsed.path == "/api/summary":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8", errors="replace"))
                sid = body.get("id", "")
                if not sid:
                    self._json({"error": "missing id"}, 400)
                    return
                files = [f for f in glob.glob(str(PROJECTS_DIR / "**" / f"{sid}.jsonl"), recursive=True)
                         if "subagents" not in f]
                if not files:
                    self._json({"error": "session not found"}, 404)
                    return
                try:
                    out_path, err = generate_summary(files[0])
                    if err:
                        self._json({"error": err}, 500)
                    else:
                        fsize = round(out_path.stat().st_size / 1024, 1)
                        self._json({"ok": True, "path": str(out_path), "size": fsize})
                except Exception as e:
                    self._json({"error": str(e)}, 500)
            else:
                self._resp(404, "text/plain", b"Not Found")
        def _json(self, data, code=200):
            self._resp(code, "application/json", json.dumps(data, ensure_ascii=False).encode())
        def _resp(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", f"{ctype}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, fmt, *a):
            pass  # suppress request logs
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"CC Sessions: http://127.0.0.1:{port}")
    print(f"会话目录: {PROJECTS_DIR}")
    print("Ctrl+C 退出\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()

def main():
    if len(sys.argv) < 2:
        cmd_serve([])
        return
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    {"list": cmd_list, "search": cmd_search, "show": cmd_show,
     "resume": cmd_resume, "index": cmd_index, "serve": cmd_serve}.get(
        cmd, lambda _: print(f"未知命令: {cmd}")
    )(rest)

if __name__ == "__main__":
    main()
