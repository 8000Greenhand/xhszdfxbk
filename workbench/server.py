import csv
import json
import mimetypes
import os
import re
import subprocess
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
DB_PATH = DATA_ROOT / "workbench.json"
TASK_ROOT = DATA_ROOT / "tasks"


DEFAULT_DB = {
    "cases": [],
    "insights": [],
    "products": [],
    "keywords": [],
    "briefs": [],
    "reviews": [],
    "settings": {
        "project": "小羊森林",
        "scope": "母婴 / 儿童食养",
        "risk_terms": ["积食", "消积食", "上火", "降火", "脾胃", "健脾", "调理", "改善便秘", "增强免疫力"],
        "safe_terms": ["配料简单", "甜度适中", "口感温和", "日常加餐", "饭后小食", "出门方便", "妈妈选品参考"],
    },
}


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_dirs():
    DATA_ROOT.mkdir(exist_ok=True)
    TASK_ROOT.mkdir(exist_ok=True)
    if not DB_PATH.exists():
        save_db(DEFAULT_DB)


def load_db():
    ensure_dirs()
    try:
        data = json.loads(DB_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = DEFAULT_DB.copy()
    for key, value in DEFAULT_DB.items():
        data.setdefault(key, value if not isinstance(value, list) else [])
    return data


def save_db(data):
    DATA_ROOT.mkdir(exist_ok=True)
    DB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def note_id_from_url(url):
    match = re.search(r"/(?:explore|discovery/item)/([0-9a-fA-F]+)", url or "")
    if match:
        return match.group(1)
    match = re.search(r"([0-9a-fA-F]{20,})", url or "")
    return match.group(1) if match else datetime.now().strftime("%Y%m%d-%H%M%S")


def read_json(path, fallback=None):
    if fallback is None:
        fallback = []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def rows_to_dict(rows):
    result = {}
    for row in rows or []:
        if isinstance(row, dict) and "field" in row:
            result[str(row.get("field", ""))] = row.get("value", "")
    return result


def int_value(value):
    text = str(value or "0").replace(",", "").strip()
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else 0


def ratio(part, whole):
    return round(part / whole, 2) if whole else 0


def list_output_cases():
    cases = []
    if not OUTPUT_ROOT.exists():
        return cases
    for folder in sorted(OUTPUT_ROOT.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not folder.is_dir():
            continue
        note = rows_to_dict(read_json(folder / "raw" / "note.json", []))
        comments = read_json(folder / "raw" / "comments.json", [])
        case = build_case_from_output(folder.name, folder, note, comments)
        cases.append(case)
    return cases


def build_case_from_output(case_id, folder, note, comments):
    likes = int_value(note.get("likes"))
    collects = int_value(note.get("collects"))
    comment_count = int_value(note.get("comments")) or len(comments or [])
    save_ratio = ratio(collects, likes)
    comment_ratio = ratio(comment_count, likes)
    title = note.get("title") or case_id
    content = note.get("content") or ""
    tags = note.get("tags") or ""
    output_files = {
        "folder": str(folder),
        "contactSheet": str(folder / "关键帧总览.jpg") if (folder / "关键帧总览.jpg").exists() else "",
        "materialReport": str(folder / "拆解素材包.md") if (folder / "拆解素材包.md").exists() else "",
        "finalReport": str(folder / "爆款拆解报告.md") if (folder / "爆款拆解报告.md").exists() else "",
    }
    analysis = analyze_case(title, content, tags, likes, collects, comment_count, comments)
    return {
        "id": case_id,
        "url": "",
        "source": "市场样本",
        "project": "小羊森林",
        "title": title,
        "author": note.get("author", ""),
        "type": "视频" if list((folder / "assets").glob("*.mp4")) else "图文/未知",
        "status": "已完成",
        "createdAt": datetime.fromtimestamp(folder.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "metrics": {
            "likes": likes,
            "collects": collects,
            "comments": comment_count,
            "saveRatio": save_ratio,
            "commentRatio": comment_ratio,
        },
        "raw": {
            "content": content,
            "tags": tags,
            "comments": comments[:30],
        },
        "analysis": analysis,
        "files": output_files,
    }


def analyze_case(title, content, tags, likes, collects, comments_count, comments):
    save_ratio = ratio(collects, likes)
    comment_ratio = ratio(comments_count, likes)
    joined_comments = "\n".join(str(c.get("text", "")) for c in comments or [] if isinstance(c, dict))
    all_text = "\n".join([title or "", content or "", tags or "", joined_comments])

    demand_hits = keyword_hits(all_text, ["链接", "品牌", "牌子", "哪家", "怎么买", "想买", "求", "价格", "几岁", "多大"])
    safety_hits = keyword_hits(all_text, ["无添加", "低糖", "配料", "健康", "宝宝", "孩子", "零食", "加餐"])
    risk_hits = keyword_hits(all_text, DEFAULT_DB["settings"]["risk_terms"])

    if save_ratio >= 0.45 or demand_hits >= 4:
        grade = "A 完整拆解"
    elif save_ratio >= 0.25 or comment_ratio >= 0.08:
        grade = "B 轻量拆解"
    elif likes > 0:
        grade = "C 记录观察"
    else:
        grade = "D 暂不建议"

    if any(word in all_text for word in ["清单", "推荐", "分享", "合集"]) or content.count("#") >= 5:
        viral_type = "清单型 / 选品型"
    elif any(word in all_text for word in ["测评", "试吃", "横评"]):
        viral_type = "测评型"
    elif any(word in all_text for word in ["避坑", "别买", "踩雷"]):
        viral_type = "避坑型"
    else:
        viral_type = "种草型 / 经验分享型"

    if save_ratio >= 0.4:
        value_type = "收藏型 / 购买决策型"
    elif comment_ratio >= 0.1:
        value_type = "讨论型 / 问询型"
    else:
        value_type = "普通种草型"

    fit = "高" if safety_hits >= 4 and grade.startswith(("A", "B")) else "中" if safety_hits >= 2 else "低"
    risk = "高" if risk_hits >= 2 else "中" if risk_hits == 1 else "低"
    strategy = account_strategy(all_text)
    reproducibility = reproducibility_score(save_ratio, comment_ratio, demand_hits, safety_hits, risk_hits, all_text)
    evidence = evidence_score(all_text, comments or [])
    production = production_difficulty(all_text)
    priority = replicate_priority(grade, fit, risk, reproducibility, evidence, production)
    replicate = priority["decision"]

    user_questions = extract_user_questions(joined_comments)
    return {
        "grade": grade,
        "viralType": viral_type,
        "valueType": value_type,
        "accountStrategy": strategy,
        "reproducibilityScore": reproducibility,
        "evidenceScore": evidence,
        "productionDifficulty": production,
        "priorityScore": priority["score"],
        "priorityLevel": priority["level"],
        "targetUser": "关注宝宝零食、儿童食养和日常加餐选择的妈妈",
        "surfaceNeed": "想快速知道哪些儿童零食/食养产品值得看、怎么买、适合什么场景",
        "deepAnxiety": "怕配料复杂、怕太甜、怕不适合年龄、怕买错后孩子不接受",
        "hookTitle": title or "标题信息不足",
        "hookCover": "需要结合封面图判断；优先看是否出现产品清单、配料表、孩子试吃或强人群词",
        "hookFirstSeconds": "需要结合视频关键帧判断；优先看前 3 秒是否直接给人群、标准或结果",
        "trustMechanism": pick_trust_mechanism(all_text),
        "saveReason": "清单密度高、可回头对照购买，且评论区有品牌/链接/年龄等决策问题",
        "commentReason": "用户想追问品牌、链接、适用年龄、甜度、配料和购买方式",
        "conversionSignal": "高" if demand_hits >= 4 else "中" if demand_hits >= 2 else "低",
        "xiaoyangFit": fit,
        "riskLevel": risk,
        "replicateDecision": replicate,
        "replicableParts": ["选题角度", "清单结构", "配料表证据", "评论区承接"],
        "notToCopy": ["夸大功效", "逐字照抄原文", "没有证据的健康承诺", "只堆产品名"],
        "copyRisk": copy_risk(all_text, risk_hits),
        "negativeSignals": negative_signals(all_text, save_ratio, comment_ratio, comments or []),
        "productDirection": infer_product_direction(all_text),
        "userQuestions": user_questions,
        "evidenceNeeded": ["产品包装", "配料表", "适用年龄说明", "真实试吃反馈", "日常场景画面"],
        "safeExpression": ["配料简单", "甜度适中", "口感温和", "日常加餐", "出门携带方便"],
        "riskWarnings": build_risk_warnings(risk_hits),
        "replicatePlan": replicate_plan(strategy, viral_type, all_text),
        "nextAction": next_action(grade, fit, risk),
    }


def keyword_hits(text, words):
    return sum(text.count(word) for word in words)


def pick_trust_mechanism(text):
    parts = []
    if "配料" in text or "无添加" in text:
        parts.append("配料表证据")
    if "宝宝" in text or "孩子" in text:
        parts.append("真实妈妈/孩子使用场景")
    if any(word in text for word in ["链接", "品牌", "牌子", "哪家"]):
        parts.append("评论区购买问询")
    return " / ".join(parts) if parts else "人设信任 + 经验分享"


def account_strategy(text):
    if any(word in text for word in ["清单", "合集", "推荐", "分享"]) or text.count("#") >= 5:
        return {
            "type": "清单型妈妈选品账号",
            "why": "用多款产品和筛选标准降低妈妈决策成本，天然适合收藏和评论追问。",
            "bestFor": "小羊森林可以借这个打法做产品矩阵、场景清单和配料表选品标准。",
        }
    if any(word in text for word in ["避坑", "别买", "踩雷"]):
        return {
            "type": "避坑型妈妈账号",
            "why": "通过风险提醒获得信任，但对品牌自有账号更容易显得攻击性强。",
            "bestFor": "适合改成温和选品标准，不建议直接做强避坑口吻。",
        }
    if any(word in text for word in ["测评", "试吃", "横评"]):
        return {
            "type": "测评型妈妈账号",
            "why": "靠对比和真实体验建立信任，适合沉淀长期栏目。",
            "bestFor": "小羊森林可以做产品证据和试吃反馈，但要避免假客观测评。",
        }
    return {
        "type": "经验种草型妈妈账号",
        "why": "靠真实经验和生活场景带来信任，爆发力取决于人设可信度。",
        "bestFor": "适合作为品牌日常内容，但需要补足证据画面降低广告感。",
    }


def reproducibility_score(save_ratio, comment_ratio, demand_hits, safety_hits, risk_hits, text):
    score = 45
    score += min(20, int(save_ratio * 25))
    score += min(15, int(comment_ratio * 80))
    score += min(15, demand_hits * 2)
    score += min(10, safety_hits)
    if any(word in text for word in ["配料", "无添加", "低糖", "怎么选"]):
        score += 8
    if any(word in text for word in ["孩子出镜", "女儿", "儿子", "宝宝试吃"]):
        score -= 5
    score -= min(18, risk_hits * 7)
    return max(0, min(100, score))


def evidence_score(text, comments):
    score = 30
    evidence_words = ["配料", "包装", "试吃", "清单", "链接", "品牌", "牌子", "年龄", "几岁", "口感"]
    for word in evidence_words:
        if word in text:
            score += 6
    if len(comments) >= 8:
        score += 8
    if any(str(c.get("text", "")).find("链接") >= 0 for c in comments if isinstance(c, dict)):
        score += 10
    return max(0, min(100, score))


def production_difficulty(text):
    hard_signals = ["孩子出镜", "宝宝试吃", "户外", "探店", "大量产品", "测评"]
    count = sum(1 for word in hard_signals if word in text)
    if count >= 3:
        return "高"
    if count >= 1 or text.count("#") >= 8:
        return "中"
    return "低"


def replicate_priority(grade, fit, risk, reproducibility, evidence, production):
    score = 0
    score += 30 if grade.startswith("A") else 22 if grade.startswith("B") else 10 if grade.startswith("C") else 0
    score += {"高": 25, "中": 15, "低": 4}.get(fit, 0)
    score += int(reproducibility * 0.22)
    score += int(evidence * 0.16)
    score -= {"高": 18, "中": 8, "低": 0}.get(risk, 0)
    score -= {"高": 10, "中": 4, "低": 0}.get(production, 0)
    score = max(0, min(100, score))
    if score >= 78:
        level = "S 立即进入创作"
        decision = "立刻复刻"
    elif score >= 62:
        level = "A 补证据后复刻"
        decision = "先补资料"
    elif score >= 42:
        level = "B 只学习结构"
        decision = "只学习"
    else:
        level = "C 只记录"
        decision = "只记录"
    return {"score": score, "level": level, "decision": decision}


def copy_risk(text, risk_hits):
    risks = []
    if risk_hits:
        risks.append("出现食养高风险词，不能按原话对外写功效。")
    if any(word in text for word in ["链接", "品牌", "牌子"]):
        risks.append("评论区有购买问询，复刻时需要提前准备产品信息和客服承接。")
    if not any(word in text for word in ["配料", "无添加", "低糖", "怎么选"]):
        risks.append("证据标准不够明显，直接复刻容易变成普通广告。")
    if not risks:
        risks.append("主要风险是不要照抄原文和镜头顺序，要复刻结构与证据逻辑。")
    return risks


def negative_signals(text, save_ratio, comment_ratio, comments):
    signals = []
    if save_ratio < 0.2:
        signals.append("收藏比偏低，说明内容可能没有形成清单或决策价值。")
    if comment_ratio < 0.04:
        signals.append("评论比偏低，说明用户没有明显追问或互动动机。")
    if any(word in text for word in ["太贵", "骗人", "广告", "智商税"]):
        signals.append("评论或正文出现质疑信号，需要避免广告感。")
    if len(comments) < 5:
        signals.append("评论样本较少，用户需求判断可信度有限。")
    return signals or ["暂未看到明显反面信号，但仍需结合更多同类案例验证。"]


def replicate_plan(strategy, viral_type, text):
    if "清单" in viral_type or "选品" in viral_type:
        return [
            "先确定一个妈妈问题：怕太甜、怕配料复杂、出门加餐、饭后小食等。",
            "用 3 到 5 个产品做清单，不追求多，追求每个都有证据。",
            "每个产品固定拍 4 个镜头：包装、配料表、口感/质地、真实场景。",
            "结尾不要强卖，评论区承接年龄、甜度、配料和购买方式。",
        ]
    if "测评" in viral_type:
        return [
            "先声明筛选标准，不做空泛好吃不好吃。",
            "每个产品用同一套维度比较：配料、甜度、口感、场景、孩子接受度。",
            "避免伪客观，品牌自有内容要用真实记录口吻。",
        ]
    return [
        "保留妈妈真实经验口吻，但必须补足配料表和场景证据。",
        "把卖点改成选品标准，不直接夸产品。",
        "评论区准备安全表达版回复。"
    ]


def infer_product_direction(text):
    mapping = [
        ("奶酪", "奶酪/乳制零食"),
        ("苹果", "果干/水果零食"),
        ("山楂", "山楂类小食"),
        ("饼", "饼干/米饼类"),
        ("饮", "饮品/冲调类"),
        ("零食", "儿童零食/日常加餐"),
    ]
    return [label for key, label in mapping if key in text] or ["儿童食养 / 日常加餐"]


def extract_user_questions(text):
    rows = []
    for line in text.splitlines():
        if any(word in line for word in ["链接", "品牌", "牌子", "哪家", "怎么买", "几岁", "多大", "甜"]):
            rows.append(line.strip())
    return rows[:8]


def build_risk_warnings(risk_hits):
    warnings = ["不要宣称治疗、调理、改善疾病或替代医生建议"]
    if risk_hits:
        warnings.append("内部可记录积食/上火/脾胃等用户原话，对外要转译成配料、甜度、场景和适量表达")
    return warnings


def next_action(grade, fit, risk):
    if grade.startswith("A") and fit == "高" and risk != "高":
        return "进入复刻创作，先生成 3 个小羊森林安全表达选题"
    if fit in ["高", "中"]:
        return "先补产品证据，再进入复刻创作"
    return "只入库观察，不作为近期复刻优先项"


def merge_cases(db_cases, output_cases):
    merged = {case["id"]: case for case in output_cases}
    for case in db_cases:
        case_id = case.get("id")
        if not case_id:
            continue
        if case_id not in merged:
            merged[case_id] = case
            continue
        for key in ["url", "source", "project", "manualNote"]:
            if case.get(key) not in ("", None, []):
                merged[case_id][key] = case[key]
        if case.get("status") == "失败":
            merged[case_id]["status"] = "失败"
            merged[case_id]["error"] = case.get("error", "")
    return sorted(merged.values(), key=lambda x: x.get("createdAt", ""), reverse=True)


def create_brief(case, product=None, insight=None):
    product_name = product.get("name") if product else "待选择产品"
    question = insight.get("text") if insight else "妈妈想知道宝宝零食怎么选才放心"
    analysis = case.get("analysis", {})
    brief = {
        "id": uuid.uuid4().hex[:12],
        "createdAt": now_text(),
        "sourceCaseId": case.get("id"),
        "sourceTitle": case.get("title"),
        "product": product_name,
        "userQuestion": question,
        "goal": "收藏 + 信任 + 评论问询",
        "topic": f"{product_name}怎么做成一条妈妈愿意收藏的儿童食养选品笔记",
        "titles": [
            f"给宝宝选零食，我现在先看这 4 个细节",
            f"不是所有宝宝零食都适合囤，先看配料和场景",
            f"这类宝宝加餐，我会优先看甜度和配料表",
        ],
        "coverText": ["宝宝零食怎么选", "先看配料表", "日常加餐清单"],
        "opening": "最近很多妈妈问宝宝日常加餐怎么选，我不会只看好不好吃，会先看配料、甜度、年龄和孩子接不接受。",
        "structure": [
            "先说人群：适合正在给孩子选日常加餐的妈妈",
            "给出筛选标准：配料、甜度、口感、场景",
            "逐个展示产品证据：包装、配料表、试吃反馈",
            "结尾引导评论区：需要清单或年龄参考可以留言",
        ],
        "shots": ["产品合照", "包装近景", "配料表近景", "孩子试吃/日常场景", "评论区问题承接"],
        "safeWords": analysis.get("safeExpression", []),
        "riskWarnings": analysis.get("riskWarnings", []),
        "status": "待写",
    }
    return brief


class WorkbenchHandler(SimpleHTTPRequestHandler):
    server_version = "XiaoYangWorkbench/1.0"

    def translate_path(self, path):
        clean = urlparse(path).path
        if clean == "/":
            clean = "/index.html"
        return str(STATIC_ROOT / clean.lstrip("/"))

    def log_message(self, format, *args):
        return

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        text = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(text)
        except Exception:
            return parse_qs(text)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/bootstrap":
            db = load_db()
            cases = merge_cases(db.get("cases", []), list_output_cases())
            self.send_json({
                "cases": cases,
                "insights": db.get("insights", []),
                "products": db.get("products", []),
                "keywords": db.get("keywords", []),
                "briefs": db.get("briefs", []),
                "reviews": db.get("reviews", []),
                "settings": db.get("settings", DEFAULT_DB["settings"]),
            })
            return
        if parsed.path == "/api/task":
            task_id = parse_qs(parsed.query).get("id", [""])[0]
            self.send_json(read_json(TASK_ROOT / f"{task_id}.json", {"status": "missing"}))
            return
        if parsed.path == "/local-image":
            image_path = parse_qs(parsed.query).get("path", [""])[0]
            self.send_local_file(image_path)
            return
        if parsed.path == "/open-file":
            file_path = parse_qs(parsed.query).get("path", [""])[0]
            if file_path and Path(file_path).exists():
                os.startfile(file_path)
            body = "<html><body>已尝试打开本地文件，可以关闭这个页面。</body></html>".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        data = self.read_body()
        if parsed.path == "/api/analyze":
            self.send_json(start_analysis(data))
            return
        if parsed.path == "/api/insight":
            self.send_json(add_insight(data))
            return
        if parsed.path == "/api/product":
            self.send_json(add_product(data))
            return
        if parsed.path == "/api/keywords":
            self.send_json(add_keywords(data))
            return
        if parsed.path == "/api/brief":
            self.send_json(add_brief(data))
            return
        if parsed.path == "/api/review":
            self.send_json(add_review(data))
            return
        self.send_json({"error": "unknown endpoint"}, 404)

    def send_local_file(self, file_path):
        path = Path(file_path)
        try:
            resolved = path.resolve()
            if not str(resolved).startswith(str(ROOT.resolve())):
                raise ValueError("outside workspace")
            if not resolved.exists():
                raise FileNotFoundError(str(resolved))
            data = resolved.read_bytes()
            mime = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_response(404)
            self.end_headers()


def start_analysis(data):
    url = str(data.get("url", "")).strip()
    source = str(data.get("source", "市场样本")).strip() or "市场样本"
    if not url:
        return {"ok": False, "error": "请先粘贴小红书链接"}
    note_id = note_id_from_url(url)
    task_id = uuid.uuid4().hex[:12]
    task = {
        "id": task_id,
        "noteId": note_id,
        "url": url,
        "source": source,
        "status": "排队中",
        "createdAt": now_text(),
        "updatedAt": now_text(),
        "log": ["任务已创建，准备读取小红书内容"],
    }
    write_task(task)
    db = load_db()
    if not any(case.get("id") == note_id for case in db["cases"]):
        db["cases"].append({
            "id": note_id,
            "url": url,
            "source": source,
            "project": "小羊森林",
            "title": "等待抓取",
            "type": "未知",
            "status": "分析中",
            "createdAt": now_text(),
            "manualNote": "",
        })
        save_db(db)
    thread = threading.Thread(target=run_analysis_task, args=(task_id, url, note_id), daemon=True)
    thread.start()
    return {"ok": True, "task": task}


def write_task(task):
    task["updatedAt"] = now_text()
    TASK_ROOT.mkdir(exist_ok=True)
    (TASK_ROOT / f"{task['id']}.json").write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")


def run_analysis_task(task_id, url, note_id):
    task = read_json(TASK_ROOT / f"{task_id}.json", {})
    try:
        task["status"] = "运行中"
        task["log"].append("正在调用本地拆解工具，这一步可能需要几分钟")
        write_task(task)
        python = ROOT / ".venv" / "Scripts" / "python.exe"
        script = ROOT / "tools" / "xhs_analyzer.py"
        if not python.exists():
            task["log"].append("正在准备本地环境")
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "run_xhs_analysis.ps1"), "-Url", url], cwd=str(ROOT), timeout=1800)
        else:
            proc = subprocess.run([str(python), str(script), "--url", url], cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800)
            output = proc.stdout.decode("utf-8", errors="replace")
            task["log"].extend(output.splitlines()[-12:])
            if proc.returncode != 0:
                raise RuntimeError(output[-1200:])
        task["status"] = "已完成"
        task["log"].append("拆解完成，已进入案例库")
        update_case_after_task(note_id, url)
    except Exception as exc:
        task["status"] = "失败"
        task["error"] = str(exc)
        task["log"].append(f"失败：{exc}")
        mark_case_failed(note_id, str(exc))
    write_task(task)


def update_case_after_task(note_id, url):
    output_case = next((case for case in list_output_cases() if case["id"] == note_id), None)
    db = load_db()
    db["cases"] = [case for case in db["cases"] if case.get("id") != note_id]
    if output_case:
        output_case["url"] = url
        db["cases"].append(output_case)
    save_db(db)


def mark_case_failed(note_id, error):
    db = load_db()
    for case in db["cases"]:
        if case.get("id") == note_id:
            case["status"] = "失败"
            case["error"] = error
    save_db(db)


def add_insight(data):
    text = str(data.get("text", "")).strip()
    if not text:
        return {"ok": False, "error": "请先输入用户原话"}
    db = load_db()
    item = {
        "id": uuid.uuid4().hex[:10],
        "createdAt": now_text(),
        "text": text,
        "source": data.get("source", "评论区/私信"),
        "product": data.get("product", ""),
        "user": data.get("user", "不确定"),
        "age": data.get("age", ""),
        "emotion": classify_emotion(text),
        "needType": classify_need(text),
        "deepInsight": explain_insight(text),
        "value": "高" if any(w in text for w in ["怕", "几岁", "太甜", "配料", "链接", "怎么买"]) else "中",
        "risk": "高" if any(w in text for w in DEFAULT_DB["settings"]["risk_terms"]) else "低",
        "topicSeed": build_topic_seed(text),
    }
    db["insights"].insert(0, item)
    save_db(db)
    return {"ok": True, "item": item}


def classify_emotion(text):
    if any(w in text for w in ["怕", "担心", "不敢", "焦虑"]):
        return "焦虑"
    if any(w in text for w in ["链接", "怎么买", "哪里买", "求"]):
        return "求推荐/求链接"
    if any(w in text for w in ["真的吗", "确定", "会不会"]):
        return "质疑"
    return "观察/需求"


def classify_need(text):
    checks = [
        (["配料", "添加", "成分"], "成分安全"),
        (["甜", "糖"], "甜度/口味"),
        (["几岁", "多大", "年龄"], "年龄适配"),
        (["链接", "怎么买", "哪里买"], "购买转化"),
        (["出门", "幼儿园", "加餐", "饭后"], "使用场景"),
        (["上火", "积食", "脾胃"], "内部食养关注"),
    ]
    for words, label in checks:
        if any(w in text for w in words):
            return label
    return "未分类需求"


def explain_insight(text):
    if "甜" in text or "糖" in text:
        return "表层在问甜度，深层是担心孩子摄入负担和日常食用频率。"
    if "几岁" in text or "多大" in text:
        return "表层在问年龄，深层是怕买错、怕不适合孩子当前阶段。"
    if "配料" in text or "添加" in text:
        return "表层在看成分，深层是需要一个能快速判断安全感的选品标准。"
    if "链接" in text or "怎么买" in text:
        return "用户已经进入购买决策，需要评论区承接和产品信息清晰。"
    if any(w in text for w in ["上火", "积食", "脾胃"]):
        return "这是高价值原话，但对外表达要转译成配料简单、口感温和、适量加餐等安全说法。"
    return "这条原话可以先入库，后续和相似问题合并判断选题价值。"


def build_topic_seed(text):
    if "甜" in text or "糖" in text:
        return "宝宝零食怎么判断甜度是否适合日常加餐"
    if "几岁" in text or "多大" in text:
        return "不同年龄段宝宝零食选择时先看哪些信息"
    if "配料" in text:
        return "妈妈看配料表选宝宝零食的 4 个重点"
    if any(w in text for w in ["上火", "积食", "脾胃"]):
        return "孩子日常加餐怎么选得更轻负担"
    return "从用户原话延展一个妈妈选品问题"


def add_product(data):
    name = str(data.get("name", "")).strip()
    if not name:
        return {"ok": False, "error": "请先填写产品名称"}
    db = load_db()
    raw = str(data.get("raw", "")).strip()
    item = {
        "id": uuid.uuid4().hex[:10],
        "createdAt": now_text(),
        "name": name,
        "series": data.get("series", ""),
        "foodType": data.get("foodType", "普通食品/待确认"),
        "form": data.get("form", infer_form(name + raw)),
        "internalDirections": infer_internal_directions(name + raw),
        "safeExpressions": infer_safe_expressions(name + raw),
        "age": data.get("age", ""),
        "scenes": infer_scenes(name + raw),
        "ingredients": data.get("ingredients", ""),
        "sellingPoints": data.get("sellingPoints", ""),
        "riskTerms": [term for term in DEFAULT_DB["settings"]["risk_terms"] if term in raw],
        "proofs": data.get("proofs", ""),
        "missing": infer_missing(data),
        "confidence": "中" if raw or data.get("ingredients") else "低",
        "unclassified": raw,
        "status": "需要确认",
    }
    db["products"].insert(0, item)
    save_db(db)
    return {"ok": True, "item": item}


def infer_form(text):
    for key, label in [("饮", "饮品"), ("奶酪", "奶酪脆"), ("苹果", "果干"), ("山楂", "山楂类"), ("饼", "饼干/米饼")]:
        if key in text:
            return label
    return "待识别"


def infer_internal_directions(text):
    directions = []
    for key, label in [("上火", "上火关注"), ("脾胃", "脾胃关注"), ("积食", "积食关注"), ("低糖", "低糖零食"), ("出门", "出门携带"), ("加餐", "日常加餐")]:
        if key in text:
            directions.append(label)
    return directions or ["日常加餐"]


def infer_safe_expressions(text):
    words = []
    for key in ["配料简单", "甜度适中", "口感温和", "出门方便", "日常加餐"]:
        if key in text:
            words.append(key)
    if "低糖" in text:
        words.append("甜度适中")
    if "配料" in text:
        words.append("配料表清晰")
    return sorted(set(words or ["配料简单", "日常加餐"]))


def infer_scenes(text):
    scenes = []
    for key, label in [("早餐", "早餐"), ("饭后", "饭后小食"), ("出门", "出门携带"), ("幼儿园", "幼儿园"), ("加餐", "下午加餐")]:
        if key in text:
            scenes.append(label)
    return scenes or ["日常加餐"]


def infer_missing(data):
    missing = []
    for key, label in [("age", "适用年龄"), ("ingredients", "配料表"), ("proofs", "证明素材"), ("sellingPoints", "可说卖点")]:
        if not data.get(key):
            missing.append(label)
    return missing


def add_keywords(data):
    text = str(data.get("text", "")).strip()
    if not text:
        return {"ok": False, "error": "请粘贴关键词或表格内容"}
    rows = parse_keyword_text(text)
    db = load_db()
    db["keywords"] = rows + db["keywords"]
    save_db(db)
    return {"ok": True, "items": rows}


def parse_keyword_text(text):
    rows = []
    sample = text.replace("\ufeff", "")
    try:
        dialect = csv.Sniffer().sniff(sample[:1000], delimiters=",\t;，")
        reader = csv.DictReader(sample.splitlines(), dialect=dialect)
        for row in reader:
            rows.append(normalize_keyword_row(row))
    except Exception:
        for line in sample.splitlines():
            parts = re.split(r"[\t,， ]+", line.strip())
            if parts and parts[0]:
                rows.append(normalize_keyword_row({"关键词": parts[0], "搜索热度": parts[1] if len(parts) > 1 else ""}))
    return [row for row in rows if row.get("keyword")][:200]


def normalize_keyword_row(row):
    keyword = first_value(row, ["关键词", "keyword", "词", "搜索词"])
    heat = first_value(row, ["搜索热度", "热度", "search", "heat"])
    notes = first_value(row, ["笔记数", "内容数", "竞争度", "notes"])
    item = {
        "id": uuid.uuid4().hex[:10],
        "createdAt": now_text(),
        "keyword": keyword,
        "type": classify_keyword(keyword),
        "heat": heat,
        "noteCount": notes,
        "competition": "待判断",
        "opportunity": keyword_opportunity(keyword, heat, notes),
        "product": "",
        "topic": keyword_topic(keyword),
        "risk": "高" if any(term in keyword for term in DEFAULT_DB["settings"]["risk_terms"]) else "低",
        "priority": "A" if any(w in keyword for w in ["宝宝", "儿童", "零食", "配料", "低糖"]) else "B",
    }
    return item


def first_value(row, keys):
    for key in keys:
        if key in row and str(row[key]).strip():
            return str(row[key]).strip()
    return ""


def classify_keyword(keyword):
    if any(w in keyword for w in ["1岁", "2岁", "3岁", "一岁", "年龄"]):
        return "年龄词"
    if any(w in keyword for w in ["出门", "幼儿园", "加餐", "早餐", "饭后"]):
        return "场景词"
    if any(w in keyword for w in ["配料", "无添加", "低糖", "甜"]):
        return "成分焦虑词"
    if any(w in keyword for w in ["小羊森林", "小鹿蓝蓝", "秋田满满", "宝宝馋了"]):
        return "品牌/竞品词"
    return "品类词"


def keyword_opportunity(keyword, heat, notes):
    if any(w in keyword for w in ["配料", "怎么选", "低糖", "无添加", "几岁"]):
        return "可直接转成选题"
    return "先观察搜索趋势"


def keyword_topic(keyword):
    if "怎么选" in keyword:
        return f"围绕“{keyword}”做选品标准型笔记"
    if "低糖" in keyword or "配料" in keyword:
        return f"围绕“{keyword}”做配料表/甜度判断笔记"
    return f"围绕“{keyword}”做清单或测评笔记"


def add_brief(data):
    db = load_db()
    cases = merge_cases(db.get("cases", []), list_output_cases())
    case = next((c for c in cases if c.get("id") == data.get("caseId")), cases[0] if cases else None)
    if not case:
        return {"ok": False, "error": "还没有可用案例"}
    product = next((p for p in db["products"] if p.get("id") == data.get("productId")), None)
    insight = next((i for i in db["insights"] if i.get("id") == data.get("insightId")), None)
    brief = create_brief(case, product, insight)
    db["briefs"].insert(0, brief)
    save_db(db)
    return {"ok": True, "item": brief}


def add_review(data):
    title = str(data.get("title", "")).strip()
    url = str(data.get("url", "")).strip()
    if not title and not url:
        return {"ok": False, "error": "请至少填写标题或链接"}
    likes = int_value(data.get("likes"))
    collects = int_value(data.get("collects"))
    comments = int_value(data.get("comments"))
    publish_date = str(data.get("publishDate", "")).strip()
    objective = str(data.get("objective", "")).strip() or "未填写"
    comment_text = str(data.get("commentText", "")).strip()
    review = build_review(
        title=title or note_id_from_url(url),
        url=url,
        publish_date=publish_date,
        objective=objective,
        likes=likes,
        collects=collects,
        comments=comments,
        comment_text=comment_text,
        manual_conclusion=str(data.get("manualConclusion", "")).strip(),
    )
    db = load_db()
    db["reviews"].insert(0, review)
    save_db(db)
    return {"ok": True, "item": review}


def build_review(title, url, publish_date, objective, likes, collects, comments, comment_text, manual_conclusion):
    save_ratio = ratio(collects, likes)
    comment_ratio = ratio(comments, likes)
    question_count = keyword_hits(comment_text, ["链接", "怎么买", "哪里", "几岁", "多大", "甜", "配料", "牌子", "品牌"])
    concern_count = keyword_hits(comment_text, DEFAULT_DB["settings"]["risk_terms"] + ["怕", "担心", "太甜", "添加"])
    if save_ratio >= 0.45 or question_count >= 4:
        result = "成功样本"
    elif save_ratio >= 0.25 or comment_ratio >= 0.08 or question_count >= 2:
        result = "观察样本"
    else:
        result = "待优化样本"
    if likes == 0 and collects == 0 and comments == 0:
        result = "数据待补"

    learning = []
    if save_ratio >= 0.45:
        learning.append("收藏比高，说明内容具备清单、标准或购买决策价值。")
    elif likes:
        learning.append("收藏比还不够高，下一条要加强清单密度、配料表证据或年龄/场景标准。")
    if question_count >= 2:
        learning.append("评论区出现购买/年龄/配料追问，说明内容已经触发决策需求。")
    if concern_count:
        learning.append("评论里有食养或安全焦虑，后续要用安全表达承接，不要写功效承诺。")
    if not learning:
        learning.append("先积累 24 小时、72 小时和 7 天数据，再判断真实表现。")

    next_action = "继续做同结构变体" if result == "成功样本" else "保留选题，重做标题/封面/证据" if result == "观察样本" else "暂不复刻，先找失败原因"
    return {
        "id": uuid.uuid4().hex[:10],
        "createdAt": now_text(),
        "title": title,
        "url": url,
        "publishDate": publish_date,
        "objective": objective,
        "metrics": {
            "likes": likes,
            "collects": collects,
            "comments": comments,
            "saveRatio": save_ratio,
            "commentRatio": comment_ratio,
        },
        "commentText": comment_text,
        "questionCount": question_count,
        "concernCount": concern_count,
        "result": result,
        "learning": learning,
        "nextAction": next_action,
        "manualConclusion": manual_conclusion,
    }


def main():
    ensure_dirs()
    port = int(os.environ.get("XIAOYANG_WORKBENCH_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), WorkbenchHandler)
    print(f"小羊森林内容工作台已启动：http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
