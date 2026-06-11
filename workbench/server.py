import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = Path(__file__).resolve().parent / "static"
OUTPUT_ROOT = ROOT / "outputs"
DATA_ROOT = ROOT / "data"
TASK_ROOT = DATA_ROOT / "tasks"
DB_PATH = DATA_ROOT / "workbench_v2.json"
ANALYSIS_INBOX_ROOT = ROOT / "analysis_inbox"
ANALYSIS_RESULTS_ROOT = ROOT / "analysis_results"

DEFAULT_DB = {
    "samples": [],
    "products": [],
    "voices": [],
    "settings": {
        "name": "小红书内容样本与合作复盘工作台",
        "sample_types": ["市场参考", "达人合作", "官号发布"],
        "process_modes": ["只登记", "完整分析", "等数据后分析"],
    },
}

SAMPLE_TYPE_META = {
    "市场参考": {
        "table": "市场参考样本",
        "goal": "学习外部爆款、竞品、跨领域内容，判断什么值得借鉴。",
        "analysisFocus": ["点击吸引", "收藏理由", "评论需求", "结构借鉴", "产品承接", "风险边界", "转译方向"],
    },
    "达人合作": {
        "table": "达人合作笔记",
        "goal": "登记所有合作达人笔记，判断种草质量、合作价值和复投建议。",
        "analysisFocus": ["人群匹配", "种草自然度", "评论需求", "数据追踪完整度", "花费性价比", "复投建议", "下次 brief"],
    },
    "官号发布": {
        "table": "官号发布笔记",
        "goal": "复盘官号图文/视频，判断封面标题、页内承接、商品点击和成交链路。",
        "analysisFocus": ["封面标题", "第一页承接", "产品出现位置", "商品点击", "订单/GMV", "系列化价值", "下一篇改法"],
    },
}

PRODUCT_TAGS = {
    "forms": ["直饮", "膏方", "零食", "冲泡", "食材包", "饮品"],
    "needs": ["脾胃", "积食后养护", "鼻敏", "清润", "上火", "日常加餐", "出门携带"],
    "timing": ["日常", "饭后", "换季", "发作期辅助", "发作后养护", "关键几天"],
    "content": ["搜索内容", "场景内容", "清单内容", "科普内容", "达人种草", "官号转化"],
}

COMMENT_KEYWORDS = ["链接", "怎么买", "哪里买", "哪家", "品牌", "牌子", "想买", "求", "价格", "几岁", "多大", "宝宝", "孩子", "适合", "配料", "甜", "糖", "安全", "添加", "健康", "怕", "有没有", "是什么"]


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_dirs():
    DATA_ROOT.mkdir(exist_ok=True)
    TASK_ROOT.mkdir(exist_ok=True)
    ANALYSIS_INBOX_ROOT.mkdir(exist_ok=True)
    ANALYSIS_RESULTS_ROOT.mkdir(exist_ok=True)
    if not DB_PATH.exists():
        write_json(DB_PATH, DEFAULT_DB)


def read_json(path, fallback=None):
    if fallback is None:
        fallback = {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_text(path, fallback=""):
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return fallback


def load_db():
    ensure_dirs()
    data = read_json(DB_PATH, {})
    for key, value in DEFAULT_DB.items():
        data.setdefault(key, [] if isinstance(value, list) else value)
    return data


def save_db(data):
    write_json(DB_PATH, data)


def note_id_from_url(url):
    match = re.search(r"/(?:explore|discovery/item)/([0-9a-fA-F]+)", url or "")
    if match:
        return match.group(1)
    match = re.search(r"([0-9a-fA-F]{20,})", url or "")
    return match.group(1) if match else ""


def safe_name(value):
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", str(value or "")).strip("_")
    return text[:80] or datetime.now().strftime("%Y%m%d-%H%M%S")


def int_value(value):
    text = str(value or "0").replace(",", "").strip()
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return 0
    number = float(match.group(0))
    if "万" in text:
        number *= 10000
    return int(number)


def rows_to_dict(rows):
    if isinstance(rows, dict):
        return rows
    result = {}
    for row in rows or []:
        if isinstance(row, dict) and "field" in row:
            result[str(row.get("field", ""))] = row.get("value", "")
    return result


def raw_path(folder, name):
    return folder / "raw" / name


def find_output_folder(note_id):
    if not OUTPUT_ROOT.exists():
        return None
    if note_id:
        direct = OUTPUT_ROOT / str(note_id)
        if direct.exists():
            return direct
    folders = [p for p in OUTPUT_ROOT.iterdir() if p.is_dir()]
    return sorted(folders, key=lambda p: p.stat().st_mtime, reverse=True)[0] if folders else None


def find_first_file(folder, patterns):
    for pattern in patterns:
        matches = list(folder.glob(pattern))
        if matches:
            return matches[0]
    return None


def digest_comments(comments, limit=50):
    rows = []
    for row in comments if isinstance(comments, list) else []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text", "")).strip()
        if not text:
            continue
        author = row.get("author") or row.get("nickname") or "未知"
        rows.append({"author": author, "text": text, "likes": row.get("likes", 0)})
    if not rows:
        return "未提取到。"
    priority = [r for r in rows if any(k in r["text"] for k in COMMENT_KEYWORDS)]
    final = (priority + [r for r in rows if r not in priority])[:limit]
    return "\n".join([f"{idx+1}. {r['author']}：{r['text']}" for idx, r in enumerate(final)])


def compact_ocr(folder):
    rows = read_json(raw_path(folder, "ocr.json"), [])
    lines, seen = [], set()
    for row in rows if isinstance(rows, list) else []:
        frame = row.get("frame", "") if isinstance(row, dict) else ""
        for item in row.get("texts", []) if isinstance(row, dict) else []:
            text = str(item.get("text", "")).strip()
            if len(text) < 2:
                continue
            key = re.sub(r"\s+", "", text)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- {frame}：{text}" if frame else f"- {text}")
            if len(lines) >= 120:
                break
        if len(lines) >= 120:
            break
    return "\n".join(lines) if lines else "未提取到。"


def compact_transcript(folder):
    rows = read_json(raw_path(folder, "transcript.json"), [])
    if isinstance(rows, list) and rows:
        lines = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            text = str(row.get("text", "")).strip()
            if not text:
                continue
            start = row.get("start", "")
            end = row.get("end", "")
            prefix = f"{start}-{end}" if start != "" and end != "" else str(start)
            lines.append(f"{prefix} {text}" if prefix else text)
        if lines:
            return "\n".join(lines)
    return read_text(raw_path(folder, "口播转写.txt"), "").strip() or "未提取到。"


def list_local_files(folder):
    rows = []
    for path in folder.rglob("*"):
        if path.is_file():
            rows.append("- " + str(path.relative_to(folder)).replace("\\", "/"))
        if len(rows) >= 220:
            rows.append("- ……")
            break
    return "\n".join(rows) if rows else "未提取到。"


def summarize_raw_text(path, limit=1200):
    text = read_text(path, "").strip()
    if not text:
        return "无"
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)
    return text[:limit] + ("..." if len(text) > limit else "")


def fallback_diagnostic(folder, step, parsed_data):
    stdout = summarize_raw_text(raw_path(folder, f"{step}.stdout.txt"))
    stderr = summarize_raw_text(raw_path(folder, f"{step}.stderr.txt"))
    if step == "note":
        fields = rows_to_dict(parsed_data)
        parsed_count = len([v for v in fields.values() if str(v or "").strip()])
        success = bool(fields.get("title") or fields.get("author") or fields.get("content"))
    elif step == "comments":
        parsed_count = len(parsed_data) if isinstance(parsed_data, list) else 0
        success = parsed_count > 0
    else:
        parsed_count = len(parsed_data) if isinstance(parsed_data, list) else (1 if parsed_data else 0)
        success = parsed_count > 0
    reason = "" if success else "未解析到有效数据。请检查 stdout/stderr：可能是 opencli 返回结构变化、登录态失效、验证码、权限、短链跳转或 xsec_token 问题。"
    return {
        "step": step,
        "success": success,
        "returncode": "未记录",
        "parsed_count": parsed_count,
        "failure_reason": reason,
        "stdout_summary": stdout,
        "stderr_summary": stderr,
    }


def load_fetch_diagnostics(folder, note_rows, comments_rows):
    download_rows = read_json(raw_path(folder, "download.json"), [])
    source = {"note": note_rows, "comments": comments_rows, "download": download_rows}
    diagnostics = {}
    for step in ["note", "comments", "download"]:
        saved = read_json(raw_path(folder, f"{step}.diagnostic.json"), None)
        diagnostics[step] = saved if isinstance(saved, dict) else fallback_diagnostic(folder, step, source.get(step))
    return diagnostics


def format_fetch_diagnostics(diagnostics):
    blocks = []
    labels = {"note": "基础信息 note", "comments": "评论 comments", "download": "下载 download"}
    for step in ["note", "comments", "download"]:
        item = diagnostics.get(step, {})
        status = "成功" if item.get("success") else "失败"
        blocks.append("\n".join([
            f"### {labels[step]}",
            "",
            f"- 状态：{status}",
            f"- 返回码：{item.get('returncode', '未记录')}",
            f"- 解析数量：{item.get('parsed_count', 0)}",
            f"- 失败原因：{item.get('failure_reason') or '无'}",
            "",
            "stdout 摘要：",
            "",
            "```text",
            str(item.get("stdout_summary") or "无"),
            "```",
            "",
            "stderr 摘要：",
            "",
            "```text",
            str(item.get("stderr_summary") or "无"),
            "```",
        ]))
    return "\n\n".join(blocks)


def infer_content_form(folder):
    if list((folder / "assets").glob("*.mp4")):
        return "视频"
    if list((folder / "assets").glob("*.jpg")) or list((folder / "assets").glob("*.png")):
        return "图文"
    return "不确定"


def build_analysis_input(package_id, note_id, url, sample_meta=None):
    folder = find_output_folder(note_id)
    if not folder:
        raise RuntimeError("未找到本地 outputs 输出文件夹。")
    note_rows = read_json(raw_path(folder, "note.json"), [])
    comments = read_json(raw_path(folder, "comments.json"), [])
    note = rows_to_dict(note_rows)
    diagnostics = load_fetch_diagnostics(folder, note_rows, comments)
    note_failure = diagnostics.get("note", {}).get("failure_reason") or "未提取到"
    comments_failure = diagnostics.get("comments", {}).get("failure_reason") or "未提取到。"
    sample_meta = sample_meta or {}
    metrics = {
        "likes": int_value(note.get("likes")),
        "collects": int_value(note.get("collects")),
        "comments": int_value(note.get("comments")) or len(comments if isinstance(comments, list) else []),
    }
    tags = note.get("tags", "") or note.get("topics", "") or note_failure
    content = note.get("content", "") or note.get("desc", "") or note_failure
    comments_text = digest_comments(comments, 50)
    if comments_text == "未提取到。":
        comments_text = comments_failure
    contact_sheet = find_first_file(folder, ["*关键帧总览*.jpg", "*总览*.jpg", "*.jpg"])
    local_files = list_local_files(folder)
    return f"""# GPT 分析输入包

## 1. 基础信息

- 分析包 ID：{package_id}
- 小红书笔记 ID：{note_id or folder.name}
- 原始链接：{url}
- 标题：{note.get('title', '') or sample_meta.get('title', '') or note_failure}
- 作者：{note.get('author', '') or sample_meta.get('creator', '') or note_failure}
- 内容形式：{sample_meta.get('contentForm') or infer_content_form(folder)}
- 样本类型：{sample_meta.get('sampleType', '未标注')}
- 处理方式：{sample_meta.get('processMode', '未标注')}
- 点赞：{metrics['likes']}
- 收藏：{metrics['collects']}
- 评论：{metrics['comments']}
- 创建时间：{now_text()}

## 2. 用户备注 / 分析背景

{sample_meta.get('note', '').strip() or '未填写。'}

## 3. 抓取诊断

{format_fetch_diagnostics(diagnostics)}

## 4. 合作 / 发布补充信息

- 达人名称：{sample_meta.get('creator', '') or '未填写'}
- 合作产品 / 发布产品：{sample_meta.get('product', '') or '未填写'}
- 合作花费：{sample_meta.get('cost', '') or '未填写'}
- 合作形式：{sample_meta.get('collabType', '') or '未填写'}
- 数据追踪方式：{sample_meta.get('tracking', '') or '未填写'}
- 初步判断：{sample_meta.get('initialJudgement', '') or '未填写'}
- 是否挂车：{sample_meta.get('hasCart', '') or '未填写'}
- 选题/合作目的：{sample_meta.get('objective', '') or '未填写'}

## 5. 笔记正文

{content}

## 6. 标签 / 话题

{tags}

## 7. 评论区原话

{comments_text}

## 8. 画面 OCR 文字

{compact_ocr(folder)}

## 9. 口播转写

{compact_transcript(folder)}

## 10. 关键帧 / 画面摘要

关键帧总览图本地路径：

{str(contact_sheet) if contact_sheet else '未提取到。'}

## 11. 本地素材文件说明

outputs/{folder.name}/ 下存在以下关键文件：

{local_files}

说明：视频、图片、frames、outputs 原始素材只保存在本机，不上传 GitHub。GPT 请只读取 analysis_inbox 中的文字材料。

## 12. 给 GPT 的分析任务

请根据样本类型输出有业务价值的分析：

- 市场参考：判断为什么值得记录、点击钩子、用户需求、评论信号、可借鉴结构、适合小羊森林哪个产品、能否转成官号内容、不能照抄什么、给出一版可执行转译方向。
- 达人合作：判断种草是否有效、人群是否匹配、内容是否讲清产品、评论区需求、数据追踪完整度、花费与性价比、是否值得复投、下次 brief 怎么改、哪些结构可复用到官号。
- 官号发布：判断封面标题、第一页承接、页内结构、产品出现位置、商品点击/成交链路、是否值得系列化、下一篇怎么改。

如果资料不足，请明确列出需要用户补充的字段，不要硬猜。
"""


def create_analysis_package(note_id, url, sample_meta=None):
    created = now_text()
    package_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{safe_name(note_id or uuid.uuid4().hex[:8])}"
    package_dir = ANALYSIS_INBOX_ROOT / package_id
    package_dir.mkdir(parents=True, exist_ok=False)
    analysis_input = build_analysis_input(package_id, note_id, url, sample_meta)
    manifest = {
        "id": package_id,
        "note_id": note_id,
        "url": url,
        "created_at": created,
        "sample_type": (sample_meta or {}).get("sampleType", ""),
        "process_mode": (sample_meta or {}).get("processMode", ""),
        "status": "pending_gpt_analysis",
    }
    status = {"status": "已上传 GitHub，等待 GPT 分析", "created_at": created, "updated_at": created, "result_folder": ""}
    write_json(package_dir / "manifest.json", manifest)
    write_json(package_dir / "status.json", status)
    (package_dir / "analysis_input.md").write_text(analysis_input, encoding="utf-8")
    (package_dir / "source.md").write_text(analysis_input[:12000], encoding="utf-8")
    return package_id


def git_upload(path):
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    try:
        subprocess.run(["git", "add", rel], cwd=ROOT, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", f"Add GPT analysis package {path.name}"], cwd=ROOT, check=True, capture_output=True, text=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True, capture_output=True, text=True)
        return True, "已上传 GitHub"
    except subprocess.CalledProcessError as exc:
        return False, (exc.stderr or exc.stdout or str(exc)).strip()


def get_results():
    results = {}
    if not ANALYSIS_RESULTS_ROOT.exists():
        return results
    for folder in ANALYSIS_RESULTS_ROOT.iterdir():
        if not folder.is_dir():
            continue
        text = read_text(folder / "analysis_result.md") or read_text(folder / "gpt_analysis.md") or read_text(folder / "task_brief.md")
        status = read_json(folder / "result_status.json", {}) or read_json(folder / "gpt_analysis.json", {})
        results[folder.name] = {
            "id": folder.name,
            "relativePath": f"analysis_results/{folder.name}",
            "analysisText": text,
            "status": status,
        }
    return results


def get_inbox():
    inbox = {}
    if not ANALYSIS_INBOX_ROOT.exists():
        return inbox
    for folder in ANALYSIS_INBOX_ROOT.iterdir():
        if not folder.is_dir():
            continue
        manifest = read_json(folder / "manifest.json", {})
        status = read_json(folder / "status.json", {})
        item = {
            "id": manifest.get("id") or folder.name,
            "folder": folder.name,
            "noteId": manifest.get("note_id", ""),
            "url": manifest.get("url", ""),
            "sampleType": manifest.get("sample_type", ""),
            "processMode": manifest.get("process_mode", ""),
            "createdAt": manifest.get("created_at", ""),
            "status": status.get("status") or manifest.get("status", ""),
            "relativePath": f"analysis_inbox/{folder.name}",
            "hasInput": (folder / "analysis_input.md").exists(),
        }
        inbox[item["id"]] = item
        if item["noteId"]:
            inbox[item["noteId"]] = item
    return inbox


def derive_missing(sample):
    missing = []
    st = sample.get("sampleType")
    if st == "达人合作":
        for key, label in [("product", "合作产品"), ("tracking", "数据追踪方式")]:
            if not sample.get(key):
                missing.append(label)
        if sample.get("processMode") != "只登记" and not sample.get("cost"):
            missing.append("合作花费")
        if sample.get("tracking") in ["小红星可追踪", "平台可追踪"]:
            for key, label in [("impressions", "曝光/播放"), ("itemClicks", "商品点击"), ("orders", "订单")]:
                if not sample.get(key):
                    missing.append(label)
    elif st == "官号发布":
        for key, label in [("product", "发布产品"), ("hasCart", "是否挂车"), ("objective", "发布目的")]:
            if not sample.get(key):
                missing.append(label)
        if sample.get("hasCart") == "是":
            for key, label in [("impressions", "曝光"), ("reads", "阅读/播放"), ("itemClicks", "商品点击"), ("orders", "订单/GMV")]:
                if not sample.get(key):
                    missing.append(label)
    elif st == "市场参考":
        if not sample.get("recordReason"):
            missing.append("记录原因")
        if not sample.get("note"):
            missing.append("为什么想学它 / 想重点看什么")
    return missing


def attach_states(sample, inbox, results):
    sid = sample.get("id", "")
    note_id = sample.get("noteId", "")
    item = inbox.get(sample.get("analysisPackageId", "")) or inbox.get(note_id) or inbox.get(sid)
    result = None
    if item:
        result = results.get(item["id"]) or results.get(item["folder"])
    if not result:
        result = results.get(sample.get("analysisPackageId", "")) or results.get(sid)
    sample["missing"] = derive_missing(sample)
    sample["gpt"] = {"inbox": item, "result": result, "status": "已完成分析" if result else (item.get("status") if item else sample.get("status", "只登记"))}
    return sample


def run_analysis_task(task_id, sample_id, url, sample_meta):
    task_path = TASK_ROOT / f"{task_id}.json"
    db = load_db()
    sample = next((x for x in db.get("samples", []) if x.get("id") == sample_id), None)
    try:
        write_json(task_path, {"id": task_id, "status": "正在抓取小红书内容", "updatedAt": now_text()})
        analyzer = ROOT / "tools" / "xhs_analyzer.py"
        subprocess.run([sys.executable, str(analyzer), "--url", url], cwd=ROOT, check=True)
        note_id = note_id_from_url(url)
        write_json(task_path, {"id": task_id, "status": "正在生成 GPT 分析包", "updatedAt": now_text()})
        package_id = create_analysis_package(note_id, url, sample_meta)
        package_dir = ANALYSIS_INBOX_ROOT / package_id
        ok, msg = git_upload(package_dir)
        db = load_db()
        sample = next((x for x in db.get("samples", []) if x.get("id") == sample_id), None)
        if sample:
            sample["noteId"] = note_id
            sample["analysisPackageId"] = package_id
            sample["status"] = "待 GPT 分析" if ok else "分析包生成成功，GitHub 上传失败"
            sample["updatedAt"] = now_text()
            save_db(db)
        write_json(task_path, {"id": task_id, "status": sample.get("status") if sample else "完成", "message": msg, "packageId": package_id, "updatedAt": now_text()})
    except Exception as exc:
        db = load_db()
        sample = next((x for x in db.get("samples", []) if x.get("id") == sample_id), None)
        if sample:
            sample["status"] = "抓取/分析包生成失败"
            sample["error"] = str(exc)
            sample["updatedAt"] = now_text()
            save_db(db)
        write_json(task_path, {"id": task_id, "status": "失败", "error": str(exc), "updatedAt": now_text()})


def create_sample(payload):
    db = load_db()
    url = payload.get("url", "").strip()
    sample_type = payload.get("sampleType") or "市场参考"
    process_mode = payload.get("processMode") or "只登记"
    sample = {
        "id": uuid.uuid4().hex[:12],
        "url": url,
        "noteId": note_id_from_url(url),
        "title": payload.get("title", ""),
        "creator": payload.get("creator", ""),
        "sampleType": sample_type,
        "contentForm": payload.get("contentForm", "自动识别"),
        "processMode": process_mode,
        "recordReason": payload.get("recordReason", ""),
        "product": payload.get("product", ""),
        "collabType": payload.get("collabType", ""),
        "cost": payload.get("cost", ""),
        "tracking": payload.get("tracking", ""),
        "initialJudgement": payload.get("initialJudgement", "不确定"),
        "hasCart": payload.get("hasCart", ""),
        "objective": payload.get("objective", ""),
        "publishDate": payload.get("publishDate", ""),
        "note": payload.get("note", ""),
        "metrics": payload.get("metrics", {}),
        "status": "只登记" if process_mode == "只登记" else ("待补数据" if process_mode == "等数据后分析" else "待抓取"),
        "createdAt": now_text(),
        "updatedAt": now_text(),
    }
    db["samples"].insert(0, sample)
    save_db(db)
    task_id = None
    if process_mode == "完整分析" and url:
        task_id = uuid.uuid4().hex[:10]
        sample["taskId"] = task_id
        sample["status"] = "正在抓取"
        save_db(db)
        thread = threading.Thread(target=run_analysis_task, args=(task_id, sample["id"], url, sample), daemon=True)
        thread.start()
    return {"sample": sample, "taskId": task_id}


def make_product_card(payload):
    raw = payload.get("raw", "")
    name = payload.get("name", "").strip() or "未命名产品"
    text = f"{name}\n{raw}"
    def hits(words):
        return [w for w in words if w in text]
    card = {
        "id": uuid.uuid4().hex[:10],
        "name": name,
        "category": payload.get("category", ""),
        "forms": hits(PRODUCT_TAGS["forms"]),
        "needs": hits(PRODUCT_TAGS["needs"]),
        "timing": hits(PRODUCT_TAGS["timing"]),
        "contentTags": hits(PRODUCT_TAGS["content"]),
        "targetUser": payload.get("targetUser", ""),
        "scenes": payload.get("scenes", ""),
        "sellingPoints": payload.get("sellingPoints", ""),
        "ingredients": payload.get("ingredients", ""),
        "taste": payload.get("taste", ""),
        "age": payload.get("age", ""),
        "usage": payload.get("usage", ""),
        "compliance": payload.get("compliance", ""),
        "banned": payload.get("banned", ""),
        "raw": raw,
        "createdAt": now_text(),
    }
    return card


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        parsed = urlparse(path)
        clean = parsed.path.lstrip("/") or "index.html"
        return str(STATIC_ROOT / clean)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/bootstrap":
            db = load_db()
            inbox = get_inbox()
            results = get_results()
            samples = [attach_states(dict(x), inbox, results) for x in db.get("samples", [])]
            # Also surface GitHub analysis packages that are not yet registered as samples.
            registered_packages = {x.get("analysisPackageId") for x in samples if x.get("analysisPackageId")}
            for key, item in inbox.items():
                if key != item.get("id") or item.get("id") in registered_packages:
                    continue
                if any(s.get("noteId") == item.get("noteId") for s in samples):
                    continue
                samples.append(attach_states({
                    "id": item["id"],
                    "url": item.get("url", ""),
                    "noteId": item.get("noteId", ""),
                    "title": item.get("url", "") or item["id"],
                    "creator": "",
                    "sampleType": item.get("sampleType") or "市场参考",
                    "contentForm": "不确定",
                    "processMode": item.get("processMode") or "完整分析",
                    "status": item.get("status") or "待 GPT 分析",
                    "createdAt": item.get("createdAt", ""),
                    "updatedAt": item.get("createdAt", ""),
                    "analysisPackageId": item["id"],
                }, inbox, results))
            self.send_json({**db, "samples": samples, "typeMeta": SAMPLE_TYPE_META, "productTags": PRODUCT_TAGS, "analysisResults": results})
            return
        if parsed.path == "/api/task":
            task_id = parse_qs(parsed.query).get("id", [""])[0]
            self.send_json(read_json(TASK_ROOT / f"{task_id}.json", {"status": "未找到任务"}))
            return
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        payload = self.read_body()
        if parsed.path in ["/api/sample", "/api/analyze"]:
            self.send_json(create_sample(payload))
            return
        if parsed.path == "/api/product":
            db = load_db()
            card = make_product_card(payload)
            db["products"].insert(0, card)
            save_db(db)
            self.send_json({"product": card})
            return
        if parsed.path == "/api/voice":
            db = load_db()
            item = {"id": uuid.uuid4().hex[:10], "text": payload.get("text", ""), "source": payload.get("source", ""), "product": payload.get("product", ""), "type": payload.get("type", ""), "createdAt": now_text()}
            db["voices"].insert(0, item)
            save_db(db)
            self.send_json({"voice": item})
            return
        if parsed.path == "/api/sample/update":
            db = load_db()
            sample_id = payload.get("id")
            for item in db.get("samples", []):
                if item.get("id") == sample_id:
                    item.update({k: v for k, v in payload.items() if k != "id"})
                    item["updatedAt"] = now_text()
                    break
            save_db(db)
            self.send_json({"ok": True})
            return
        self.send_json({"error": "Not found"}, 404)


def run():
    ensure_dirs()
    port = int(os.environ.get("XIAOYANG_WORKBENCH_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"小红书内容样本与合作复盘工作台已启动：http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
