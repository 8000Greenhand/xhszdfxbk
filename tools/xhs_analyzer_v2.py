"""Improved Xiaohongshu analyzer wrapper.

Keeps the original xhs_analyzer implementation, but patches metadata parsing so
note title/author/engagement fields are not lost when opencli returns nested JSON
objects instead of the older [{field, value}] rows. Also appends a diagnostics
block to the material package so we can see why note/comments failed.
"""

import json
import re
import sys
from pathlib import Path

import yaml

# Allow importing sibling module when this file is executed directly.
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import xhs_analyzer as base  # noqa: E402


TITLE_KEYS = {
    "title", "displaytitle", "display_title", "notetitle", "note_title",
}
CONTENT_KEYS = {
    "desc", "description", "content", "text", "notecontent", "note_content",
}
AUTHOR_KEYS = {
    "author", "nickname", "nick_name", "username", "user_name",
    "name", "usernickname", "user_nickname",
}
LIKE_KEYS = {"likes", "like", "liked", "likedcount", "liked_count", "likecount", "like_count"}
COLLECT_KEYS = {"collects", "collect", "collected", "collectedcount", "collected_count", "collectcount", "collect_count", "favoritecount", "favorite_count"}
COMMENT_KEYS = {"comments", "comment", "commentcount", "comment_count", "commentscount", "comments_count"}
TAG_KEYS = {"tags", "taglist", "hash_tags", "hashtags"}
LIST_KEYS = {"comments", "commentlist", "items", "list", "notes", "result", "results", "data"}

ORIGINAL_GENERATE_REPORT = base.generate_report
ORIGINAL_GENERATE_FINAL_REPORT = base.generate_final_report


def normalize_key(key: object) -> str:
    return re.sub(r"[^a-z0-9_]+", "", str(key or "").strip().lower())


def clean_text(value: object) -> str:
    text = str(value or "").strip()
    if text in {"None", "null", "undefined"}:
        return ""
    return text


def parse_json_value(text: str):
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text or ""):
        if char not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[idx:])
            return value
        except json.JSONDecodeError:
            continue
    try:
        return yaml.safe_load(text)
    except Exception:
        return None


def first_list_value(value):
    if isinstance(value, list):
        return value
    if not isinstance(value, dict):
        return None
    for key, item in value.items():
        if normalize_key(key) in LIST_KEYS and isinstance(item, list):
            return item
    for item in value.values():
        found = first_list_value(item)
        if found:
            return found
    return None


def walk_dict(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk_dict(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_dict(item)


def set_if_empty(result: dict, key: str, value: object):
    text = clean_text(value)
    if text and not result.get(key):
        result[key] = text


def extract_note_fields(value) -> dict:
    """Extract a flat note dict from nested opencli output."""
    if isinstance(value, list):
        result = {}
        for row in value:
            if not isinstance(row, dict):
                continue
            if "field" in row:
                result[str(row.get("field", ""))] = row.get("value", "")
            else:
                nested = extract_note_fields(row)
                for key, item in nested.items():
                    result.setdefault(key, item)
        return normalize_note_dict(result)

    if not isinstance(value, dict):
        return {}

    result = {}
    for node in walk_dict(value):
        for key, item in node.items():
            k = normalize_key(key)
            if k in TITLE_KEYS:
                set_if_empty(result, "title", item)
            elif k in CONTENT_KEYS:
                set_if_empty(result, "content", item)
            elif k in AUTHOR_KEYS:
                set_if_empty(result, "author", item)
            elif k in LIKE_KEYS:
                set_if_empty(result, "likes", item)
            elif k in COLLECT_KEYS:
                set_if_empty(result, "collects", item)
            elif k in COMMENT_KEYS:
                set_if_empty(result, "comments", item)
            elif k in TAG_KEYS and not result.get("tags"):
                if isinstance(item, list):
                    tag_names = []
                    for tag in item:
                        if isinstance(tag, dict):
                            tag_names.append(clean_text(tag.get("name") or tag.get("tag") or tag.get("title")))
                        else:
                            tag_names.append(clean_text(tag))
                    result["tags"] = " ".join([x for x in tag_names if x])
                else:
                    set_if_empty(result, "tags", item)
    return result


def normalize_note_dict(value: dict) -> dict:
    if not isinstance(value, dict):
        return {}
    extracted = extract_note_fields(value) if not any(k in value for k in ["title", "author", "content"]) else {}
    result = dict(value)
    for key, item in extracted.items():
        result.setdefault(key, item)
    alias_map = {
        "desc": "content",
        "description": "content",
        "nickname": "author",
        "nickName": "author",
        "user_name": "author",
        "liked_count": "likes",
        "likedCount": "likes",
        "collect_count": "collects",
        "collected_count": "collects",
        "comment_count": "comments",
    }
    for old, new in alias_map.items():
        if not result.get(new) and result.get(old):
            result[new] = result.get(old)
    return result


def patched_parse_rows(text: str):
    value = parse_json_value(text)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        list_value = first_list_value(value)
        if list_value and not extract_note_fields(value).get("title"):
            return list_value
        note = extract_note_fields(value)
        return note if note else value
    return []


def patched_fields_to_dict(rows) -> dict:
    if isinstance(rows, dict):
        return normalize_note_dict(rows)
    if isinstance(rows, list):
        result = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            if "field" in row:
                result[str(row.get("field", ""))] = row.get("value", "")
            else:
                nested = extract_note_fields(row)
                for key, item in nested.items():
                    result.setdefault(key, item)
        if result:
            return normalize_note_dict(result)
    return {}


def normalize_comments(comments):
    if isinstance(comments, list):
        return [x for x in comments if isinstance(x, dict)]
    if isinstance(comments, dict):
        found = first_list_value(comments)
        if found:
            return [x for x in found if isinstance(x, dict)]
    return []


def patched_comment_insights(comments) -> dict:
    rows = normalize_comments(comments)
    texts = [str(c.get("text") or c.get("content") or c.get("comment") or "") for c in rows]
    texts = [t for t in texts if t]
    joined = "\n".join(texts)
    demand_words = ["链接", "牌子", "品牌", "哪家", "在哪里买", "怎么买", "想买", "求", "是什么"]
    demand_comments = [t for t in texts if any(w in t for w in demand_words)]

    tokens = re.findall(r"[\u4e00-\u9fff]{2,}", joined)
    stop = {
        "这个", "那个", "有没有", "都是", "什么", "姐妹", "这里", "顶置", "收起",
        "小红书", "笔记", "博主", "评论", "链接", "发啦", "好吃",
    }
    common = base.Counter(t for t in tokens if t not in stop).most_common(12)
    return {"demand_comments": demand_comments[:10], "common_terms": common}


def short_text(path: Path, limit: int = 1800) -> str:
    if not path.exists():
        return "文件不存在"
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return "空"
    return text[:limit] + ("\n……已截断……" if len(text) > limit else "")


def command_status(raw_dir: Path, name: str, parsed_count: int | None = None) -> dict:
    stdout_path = raw_dir / f"{name}.stdout.txt"
    stderr_path = raw_dir / f"{name}.stderr.txt"
    stdout = short_text(stdout_path, 1200)
    stderr = short_text(stderr_path, 1200)
    ok = bool(parsed_count and parsed_count > 0)
    if name == "note":
        value = parse_json_value(stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else "")
        ok = bool(extract_note_fields(value).get("title") or extract_note_fields(value).get("author"))
    return {"name": name, "ok": ok, "parsed_count": parsed_count, "stdout": stdout, "stderr": stderr}


def append_diagnostics(report_path: Path, raw_dir: Path, note_rows, comments_rows, download_rows):
    diagnostics = {
        "note": command_status(raw_dir, "note", 1 if patched_fields_to_dict(note_rows) else 0),
        "comments": command_status(raw_dir, "comments", len(normalize_comments(comments_rows))),
        "download": command_status(raw_dir, "download", len(download_rows) if isinstance(download_rows, list) else 0),
    }
    (raw_dir / "diagnostics.json").write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["", "## 抓取诊断", ""]
    for key in ["note", "comments", "download"]:
        item = diagnostics[key]
        lines.extend([
            f"### {key}",
            f"- 状态：{'成功' if item['ok'] else '未成功或未解析到有效数据'}",
            f"- 解析数量：{item['parsed_count']}",
            "- stderr 摘要：",
            "```txt",
            item["stderr"],
            "```",
            "- stdout 摘要：",
            "```txt",
            item["stdout"],
            "```",
            "",
        ])
    with report_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def patched_generate_report(*args, **kwargs):
    ORIGINAL_GENERATE_REPORT(*args, **kwargs)
    report_path = kwargs.get("report_path") if kwargs else None
    asset_dir = kwargs.get("asset_dir") if kwargs else None
    note = kwargs.get("note") if kwargs else None
    comments = kwargs.get("comments") if kwargs else None
    download_rows = kwargs.get("download_rows") if kwargs else None
    if report_path is None and len(args) >= 1:
        report_path = args[0]
    if asset_dir is None and len(args) >= 7:
        asset_dir = args[6]
    if note is None and len(args) >= 4:
        note = args[3]
    if comments is None and len(args) >= 5:
        comments = args[4]
    if download_rows is None and len(args) >= 6:
        download_rows = args[5]
    if report_path and asset_dir:
        raw_dir = Path(asset_dir).parent / "raw"
        append_diagnostics(Path(report_path), raw_dir, note or {}, comments or [], download_rows or [])


# Patch base module functions used by base.main().
base.parse_rows = patched_parse_rows
base.fields_to_dict = patched_fields_to_dict
base.comment_insights = patched_comment_insights
base.generate_report = patched_generate_report


if __name__ == "__main__":
    base.main()
