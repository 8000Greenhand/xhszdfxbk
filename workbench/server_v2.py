"""Patched launcher for the Xiaoyang Forest content learning workbench.

This module keeps the original server.py as the stable base, then patches only the
content-learning / GPT-analysis behavior. The goal is to avoid rewriting the full
server while moving the workflow from a simple analysis package to a sample
screening + product-fit + creative-translation system.
"""

import re
import threading
import uuid
from urllib.parse import urlparse

import server as base


ANALYSIS_PROCESS_MODES = [
    "只登记",
    "先判断价值",
    "只拆结构",
    "分析产品承接",
    "生成创作大纲",
    "生成官号图文",
    "生成博主文字脚本",
    "完整分析",
    "等数据后分析",
]

ANALYSIS_TRIGGER_MODES = {
    "先判断价值",
    "只拆结构",
    "分析产品承接",
    "生成创作大纲",
    "生成官号图文",
    "生成博主文字脚本",
    "完整分析",
}

SYSTEM_CHECK_KEYWORDS = [
    "样本初筛",
    "样本池分类",
    "产品承接",
    "创作出口",
    "不要默认这条样本有价值",
    "博主文字脚本",
]

ORIGINAL_BUILD_ANALYSIS_INPUT = base.build_analysis_input
ORIGINAL_END_HEADERS = base.Handler.end_headers
ORIGINAL_DO_GET = base.Handler.do_GET


base.DEFAULT_DB["settings"]["name"] = "小羊森林内容样本学习与创作转译系统"
base.DEFAULT_DB["settings"]["process_modes"] = ANALYSIS_PROCESS_MODES

base.SAMPLE_TYPE_META.update({
    "市场参考": {
        "table": "市场参考样本",
        "goal": "输入市场爆文、普通笔记、竞品或跨领域参考，先判断样本价值，再决定是否只拆结构、看产品承接或进入创作转译。",
        "analysisFocus": ["样本初筛", "样本池分类", "标题封面结构", "评论需求", "产品承接", "可迁移点", "不可照搬点", "创作出口"],
    },
    "达人合作": {
        "table": "达人合作笔记",
        "goal": "把合作笔记当成真实产品内容实验样本，判断内容角度、产品讲法、评论信号和可迁移创作价值，而不是只看达人复投。",
        "analysisFocus": ["产品内容实验", "产品讲法", "评论购买信号", "可迁移结构", "官号图文可能", "博主文字脚本可能", "反面避坑"],
    },
    "官号发布": {
        "table": "官号发布笔记",
        "goal": "沉淀自有内容实验，判断哪些标题封面、结构、产品承接和转化链路值得继续复用或避坑。",
        "analysisFocus": ["自有内容实验", "封面标题", "第一页承接", "商品点击", "订单/GMV", "评论反馈", "下一步优化"],
    },
})


PRODUCT_CARD_KEYWORDS = {
    "painPoints": ["积食", "脾胃", "胃口", "食欲", "鼻炎", "喷嚏", "清水鼻涕", "鼻塞", "上火", "口干", "睡不踏实", "一头汗", "冷饮", "肚肚", "便便"],
    "fitContent": ["清单", "科普", "食谱", "加餐", "早餐", "换季", "发作期", "发作后", "场景", "误区", "对比", "判断标准"],
    "banned": ["治疗", "根治", "治愈", "药", "药效", "立刻", "马上", "保证", "替代", "鼻窦炎", "发烧", "黄浓鼻涕"],
    "officialWriting": ["原理", "食材", "配方", "适用", "禁忌", "注意", "吃法", "详情页", "科普"],
    "bloggerScript": ["孩子", "妈妈", "日常", "出门", "上学", "幼儿园", "真实", "口感", "方便", "开袋"],
}


def no_cache_end_headers(self):
    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    self.send_header("Pragma", "no-cache")
    self.send_header("Expires", "0")
    ORIGINAL_END_HEADERS(self)


base.Handler.end_headers = no_cache_end_headers


def keyword_hits(text, words):
    return [word for word in words if word and word in text]


def compact_lines(text, limit=5):
    lines = [re.sub(r"\s+", " ", line).strip(" -：:;") for line in str(text or "").splitlines()]
    lines = [line for line in lines if len(line) >= 4]
    return "；".join(lines[:limit])


def patched_make_product_card(payload):
    raw = payload.get("raw", "") or ""
    name = payload.get("name", "").strip() or "未命名产品"
    text = f"{name}\n{raw}"

    pain_points = keyword_hits(text, PRODUCT_CARD_KEYWORDS["painPoints"])
    fit_content = keyword_hits(text, PRODUCT_CARD_KEYWORDS["fitContent"])
    banned_hits = keyword_hits(text, PRODUCT_CARD_KEYWORDS["banned"])
    official_hits = keyword_hits(text, PRODUCT_CARD_KEYWORDS["officialWriting"])
    blogger_hits = keyword_hits(text, PRODUCT_CARD_KEYWORDS["bloggerScript"])

    card = {
        "id": uuid.uuid4().hex[:10],
        "name": name,
        "category": payload.get("category", ""),
        "forms": keyword_hits(text, base.PRODUCT_TAGS["forms"]),
        "needs": keyword_hits(text, base.PRODUCT_TAGS["needs"]),
        "timing": keyword_hits(text, base.PRODUCT_TAGS["timing"]),
        "contentTags": keyword_hits(text, base.PRODUCT_TAGS["content"]),
        "positioning": payload.get("positioning", "") or compact_lines(raw, 2),
        "targetUser": payload.get("targetUser", ""),
        "scenes": payload.get("scenes", ""),
        "painPoints": payload.get("painPoints", "") or "、".join(pain_points),
        "sellingPoints": payload.get("sellingPoints", ""),
        "ingredients": payload.get("ingredients", ""),
        "taste": payload.get("taste", ""),
        "age": payload.get("age", ""),
        "usage": payload.get("usage", ""),
        "commonConcerns": payload.get("commonConcerns", ""),
        "fitContent": payload.get("fitContent", "") or "、".join(fit_content),
        "avoidContent": payload.get("avoidContent", ""),
        "compliance": payload.get("compliance", ""),
        "banned": payload.get("banned", "") or "、".join(banned_hits),
        "difference": payload.get("difference", ""),
        "officialWriting": payload.get("officialWriting", "") or "、".join(official_hits),
        "bloggerScript": payload.get("bloggerScript", "") or "、".join(blogger_hits),
        "faq": payload.get("faq", ""),
        "raw": raw,
        "createdAt": base.now_text(),
    }
    return card


base.make_product_card = patched_make_product_card


def product_context_text(limit=12):
    """Build a compact product/voice context block for GPT analysis packages."""
    db = base.load_db()
    products = db.get("products", [])[:limit]
    voices = db.get("voices", [])[:20]

    if products:
        product_lines = []
        for idx, item in enumerate(products, 1):
            raw = str(item.get("raw", "")).strip()
            raw_short = raw[:1000] + ("……" if len(raw) > 1000 else "")
            product_lines.append("\n".join([
                f"### 产品 {idx}：{item.get('name', '未命名产品')}",
                f"- 定位：{item.get('positioning', '') or '未填写'}",
                f"- 分类：{item.get('category', '') or '未填写'}",
                f"- 适用年龄：{item.get('age', '') or '未填写'}",
                f"- 核心场景：{item.get('scenes', '') or '未填写'}",
                f"- 用户痛点：{item.get('painPoints', '') or '未填写'}",
                f"- 主卖点：{item.get('sellingPoints', '') or '未填写'}",
                f"- 口味/便利性：{item.get('taste', '') or '未填写'}｜{item.get('usage', '') or '未填写'}",
                f"- 常见顾虑：{item.get('commonConcerns', '') or item.get('faq', '') or '未填写'}",
                f"- 可承接内容：{item.get('fitContent', '') or ', '.join(item.get('contentTags', []) or []) or '未填写'}",
                f"- 不适合硬蹭：{item.get('avoidContent', '') or '未填写'}",
                f"- 禁用/合规表达：{item.get('banned', '') or item.get('compliance', '') or '未填写'}",
                f"- 官号图文讲法：{item.get('officialWriting', '') or '未填写'}",
                f"- 博主文字脚本讲法：{item.get('bloggerScript', '') or '未填写'}",
                f"- 原始资料摘要：{raw_short or '未填写'}",
            ]))
        products_text = "\n\n".join(product_lines)
    else:
        products_text = "当前还没有结构化产品卡。若样本需要判断产品承接，请明确说明资料不足，不要硬猜。"

    if voices:
        voice_lines = []
        for idx, item in enumerate(voices, 1):
            voice_lines.append(f"{idx}. {item.get('source', '未标注来源')}｜{item.get('product', '未关联产品')}：{item.get('text', '')}")
        voices_text = "\n".join(voice_lines)
    else:
        voices_text = "当前还没有用户原声。"

    return f"""## 产品资料卡摘要\n\n{products_text}\n\n## 用户原声摘要\n\n{voices_text}"""


def analysis_mode_instruction(process_mode):
    mapping = {
        "先判断价值": "本次优先做样本初筛：判断是否值得保留、属于哪个样本池、值得学什么、不值得学什么、是否需要继续深拆或转译。不要直接强行生成稿子。",
        "只拆结构": "本次只拆结构：重点分析标题公式、封面信息组织、开头钩子、内容展开逻辑、收口方式和可迁移形式。产品承接只做轻判断，不要硬转译。",
        "分析产品承接": "本次重点判断产品承接：识别样本背后的用户需求，判断能否关联小羊森林某个产品，承接强度是强/中/弱/不建议，并说明不能硬说的点。",
        "生成创作大纲": "本次在完成初筛和产品承接判断后，如样本确有价值，请生成创作转译大纲。大纲优先于完整成稿。",
        "生成官号图文": "本次在完成初筛和产品承接判断后，如适合品牌官号，请生成官号挂车图文方案：标题、封面、第一页承接、内页结构、正文、话题、置顶评论。",
        "生成博主文字脚本": "本次在完成初筛和产品承接判断后，如适合达人/博主视频，请生成博主可直接理解的完整文字脚本。不要输出分镜，不要写导演式拍摄指导。",
        "完整分析": "本次做完整分析：先样本初筛，再深度拆解，再判断产品承接和创作出口；只有确实值得转译时才给出创作大纲/官号图文/博主文字脚本建议。",
        "等数据后分析": "本次信息可能不足，请先指出缺哪些数据，能判断的只做暂存观察，不要硬猜。",
        "只登记": "本次只登记，不需要深度分析。",
    }
    return mapping.get(process_mode or "", mapping["先判断价值"])


def patched_build_analysis_input(package_id, note_id, url, sample_meta=None):
    sample_meta = sample_meta or {}
    raw = ORIGINAL_BUILD_ANALYSIS_INPUT(package_id, note_id, url, sample_meta)
    prefix = raw.split("\n## 12. 给 GPT 的分析任务", 1)[0]
    if prefix == raw:
        prefix = raw.split("\n## 11. 给 GPT 的分析任务", 1)[0]
    brain_path = base.ROOT / "workbench" / "prompts" / "content_learning_system_v1.md"
    system_brain = base.read_text(brain_path, "未读取到系统大脑文件。")
    process_mode = sample_meta.get("processMode", "先判断价值")
    current_instruction = analysis_mode_instruction(process_mode)
    context = product_context_text()

    return f"""{prefix}

## 11. 小羊森林内容样本学习与创作转译系统 v1

以下规则是本项目的系统大脑。你必须按它工作，而不是按普通爆文库、达人复盘表或官号图文生成器工作。

{system_brain}

## 12. 当前产品资料与用户原声

{context}

## 13. 本次处理方式

- 处理方式：{process_mode}
- 分析目的：{current_instruction}

## 14. 给 GPT 的强制执行要求

1. 先做【样本初筛】，不要默认这条样本有价值，也不要默认它一定要复刻。
2. 必须判断样本应该进入哪个池：高价值复刻、结构参考、评论洞察、产品承接、反面避坑、暂存观察、低价值丢弃。
3. 必须判断产品承接强度：强 / 中 / 弱 / 不建议。能承接才说怎么承接；不能承接要明确说不能硬接。
4. 如果样本只适合结构参考，就只拆标题、封面、开头、内容逻辑，不要强行关联产品。
5. 如果样本缺评论、缺数据、缺产品资料，要明确列出缺什么，不要硬猜。
6. 如果结论是丢弃、仅归档、暂存观察或暂不转译，不要强行生成官号图文或博主脚本。
7. 如果需要输出给博主使用，请输出【博主文字脚本】，不要输出达人 brief 表格、分镜、镜头时长或导演式拍摄指导。
8. 食品/儿童食养内容必须注意合规：不写治疗、根治、替代药物、立刻见效、保证有效，不做医疗化和夸大承诺。
9. 输出要具体、可执行、能帮助后续创作，不要写空泛咨询报告。
"""


def latest_analysis_input_status():
    root = base.ANALYSIS_INBOX_ROOT
    if not root.exists():
        return {
            "exists": False,
            "ok": False,
            "message": "analysis_inbox 文件夹还不存在。生成一次分析包后会自动出现。",
            "requiredKeywords": SYSTEM_CHECK_KEYWORDS,
            "keywordHits": {},
        }
    folders = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
    for folder in folders:
        path = folder / "analysis_input.md"
        if not path.exists():
            continue
        text = base.read_text(path, "")
        hits = {keyword: (keyword in text) for keyword in SYSTEM_CHECK_KEYWORDS}
        return {
            "exists": True,
            "folder": folder.name,
            "relativePath": str(path.relative_to(base.ROOT)).replace("\\", "/"),
            "ok": all(hits.values()),
            "requiredKeywords": SYSTEM_CHECK_KEYWORDS,
            "keywordHits": hits,
            "message": "最新分析包已接入新逻辑。" if all(hits.values()) else "最新分析包存在，但关键词不完整，可能是旧分析包或生成时仍在跑旧服务。",
        }
    return {
        "exists": False,
        "ok": False,
        "message": "analysis_inbox 里还没有 analysis_input.md。保存一条需要分析的样本后再看。",
        "requiredKeywords": SYSTEM_CHECK_KEYWORDS,
        "keywordHits": {},
    }


def system_check_payload():
    brain_path = base.ROOT / "workbench" / "prompts" / "content_learning_system_v1.md"
    brain_text = base.read_text(brain_path, "")
    brain_hits = {keyword: (keyword in brain_text) for keyword in ["样本初筛", "样本池分类", "产品承接", "博主文字脚本"]}
    latest_input = latest_analysis_input_status()
    checks = {
        "serverV2Active": True,
        "promptFileExists": brain_path.exists(),
        "promptKeywordHits": brain_hits,
        "processModes": ANALYSIS_PROCESS_MODES,
        "processModesOk": all(mode in ANALYSIS_PROCESS_MODES for mode in ["先判断价值", "只拆结构", "分析产品承接", "生成创作大纲", "生成博主文字脚本"]),
        "latestAnalysisInput": latest_input,
    }
    checks["ok"] = bool(checks["serverV2Active"] and checks["promptFileExists"] and all(brain_hits.values()) and checks["processModesOk"])
    return checks


def patched_do_get(self):
    parsed = urlparse(self.path)
    if parsed.path == "/api/system_check":
        self.send_json(system_check_payload())
        return
    ORIGINAL_DO_GET(self)


def patched_create_sample(payload):
    db = base.load_db()
    url = payload.get("url", "").strip()
    sample_type = payload.get("sampleType") or "市场参考"
    process_mode = payload.get("processMode") or "只登记"
    sample = {
        "id": uuid.uuid4().hex[:12],
        "url": url,
        "noteId": base.note_id_from_url(url),
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
        "analysisPurpose": process_mode,
        "status": "只登记" if process_mode == "只登记" else ("待补数据" if process_mode == "等数据后分析" else "待抓取"),
        "createdAt": base.now_text(),
        "updatedAt": base.now_text(),
    }
    db["samples"].insert(0, sample)
    base.save_db(db)

    task_id = None
    if process_mode in ANALYSIS_TRIGGER_MODES and url:
        task_id = uuid.uuid4().hex[:10]
        sample["taskId"] = task_id
        sample["status"] = "正在抓取"
        base.save_db(db)
        thread = threading.Thread(
            target=base.run_analysis_task,
            args=(task_id, sample["id"], url, sample),
            daemon=True,
        )
        thread.start()
    return {"sample": sample, "taskId": task_id}


base.build_analysis_input = patched_build_analysis_input
base.create_sample = patched_create_sample
base.Handler.do_GET = patched_do_get


if __name__ == "__main__":
    base.run()
