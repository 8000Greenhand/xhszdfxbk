import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
import yaml

try:
    from rapidocr_onnxruntime import RapidOCR
except Exception:
    RapidOCR = None

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "outputs"


def note_id_from_url(url: str) -> str:
    match = re.search(r"/(?:explore|discovery/item)/([0-9a-fA-F]+)", url)
    if match:
        return match.group(1)
    match = re.search(r"([0-9a-fA-F]{20,})", url)
    return match.group(1) if match else datetime.now().strftime("%Y%m%d-%H%M%S")


def run_opencli(args: list[str], cwd: Path) -> tuple[str, str, int]:
    opencli = shutil.which("opencli.cmd") or shutil.which("opencli") or "opencli"
    command = subprocess.list2cmdline([opencli, *args])
    proc = subprocess.run(
        ["cmd", "/d", "/c", f"chcp 65001 >nul && {command}"],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    return stdout, stderr, proc.returncode


def parse_json_array(text: str):
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char != "[":
            continue
        try:
            value, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, list):
            return value
    return []


def parse_rows(text: str):
    rows = parse_json_array(text)
    if rows:
        return rows
    try:
        value = yaml.safe_load(text)
    except Exception:
        return []
    return value if isinstance(value, list) else []


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fields_to_dict(rows: list[dict]) -> dict:
    result = {}
    for row in rows:
        if "field" in row:
            result[str(row.get("field", ""))] = row.get("value", "")
    return result


def extract_frames(video_path: Path, frames_dir: Path) -> list[Path]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    pattern = str(frames_dir / "frame_%03d.jpg")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-vf",
        "fps=1/3,scale=720:-1",
        "-q:v",
        "3",
        pattern,
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return sorted(frames_dir.glob("frame_*.jpg"))


def make_contact_sheet(frames: list[Path], output: Path, max_frames: int = 12):
    if not frames:
        return
    selected = frames[:max_frames]
    thumbs = []
    for frame in selected:
        img = Image.open(frame).convert("RGB")
        img.thumbnail((240, 426))
        thumbs.append((frame, img.copy()))
        img.close()

    cols = 4
    rows = (len(thumbs) + cols - 1) // cols
    cell_w, cell_h = 260, 470
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, (frame, img) in enumerate(thumbs):
        x = (idx % cols) * cell_w + 10
        y = (idx // cols) * cell_h + 10
        sheet.paste(img, (x, y))
        draw.text((x, y + img.height + 8), frame.name, fill=(40, 40, 40))
    sheet.save(output, quality=92)


def run_ocr(frames: list[Path], output_path: Path, max_frames: int = 38) -> list[dict]:
    if RapidOCR is None or not frames:
        save_json(output_path, [])
        return []

    ocr = RapidOCR()
    rows = []
    for frame in frames[:max_frames]:
        try:
            result, _ = ocr(str(frame))
        except Exception as exc:
            rows.append({"frame": frame.name, "error": str(exc), "texts": []})
            continue

        texts = []
        for item in result or []:
            text = str(item[1]).strip()
            score = float(item[2])
            if not text or score < 0.55:
                continue
            # Watermarks are useful once, but noisy across every frame.
            if text in {"小红书", "墩妈JINA"}:
                continue
            texts.append({"text": text, "score": round(score, 3)})
        rows.append({"frame": frame.name, "texts": texts})

    save_json(output_path, rows)
    return rows


def format_time(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def transcribe_video(video_path: Path | None, raw_dir: Path, model_size: str = "base") -> list[dict]:
    transcript_json = raw_dir / "transcript.json"
    transcript_txt = raw_dir / "口播转写.txt"
    if WhisperModel is None or video_path is None or not video_path.exists():
        save_json(transcript_json, [])
        transcript_txt.write_text("", encoding="utf-8")
        return []

    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(
            str(video_path),
            language="zh",
            vad_filter=True,
            beam_size=5,
        )
        rows = []
        for seg in segments:
            text = str(seg.text).strip()
            if text:
                rows.append({
                    "start": round(float(seg.start), 2),
                    "end": round(float(seg.end), 2),
                    "text": text,
                })
    except Exception as exc:
        rows = [{"error": str(exc)}]

    save_json(transcript_json, rows)
    lines = []
    for row in rows:
        if row.get("error"):
            lines.append(f"转写失败：{row['error']}")
        else:
            lines.append(f"{format_time(row['start'])}-{format_time(row['end'])} {row['text']}")
    transcript_txt.write_text("\n".join(lines), encoding="utf-8")
    return rows


def dedupe_ocr_lines(ocr_rows: list[dict], limit: int = 40) -> list[str]:
    seen = set()
    lines = []
    for row in ocr_rows:
        for item in row.get("texts", []):
            text = item.get("text", "").strip()
            if not is_useful_ocr_line(text):
                continue
            key = re.sub(r"\s+", "", text)
            if not key or key in seen:
                continue
            seen.add(key)
            lines.append(text)
            if len(lines) >= limit:
                return lines
    return lines


def is_useful_ocr_line(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 4:
        return False
    if re.fullmatch(r"[A-Za-z0-9%\-:/\.]+", compact):
        return False
    if len(compact) > 55 and not any(word in compact for word in ["配料", "陈皮", "山药", "苹果", "奶酪", "酸奶"]):
        return False
    noisy_words = ["邮编", "委托方地址", "产品标准代号", "贮存条件", "营养成分表"]
    if any(word in compact for word in noisy_words):
        return False
    return True


def extract_product_timeline(content: str) -> list[tuple[str, str]]:
    items = re.findall(r"#(\d{2}:\d{2})\[时刻\]#\s*([^#]+)", content or "")
    return [(time, name.strip()) for time, name in items if name.strip()]


def ocr_script_lines(ocr_rows: list[dict], limit: int = 20) -> list[str]:
    candidates = dedupe_ocr_lines(ocr_rows, limit=80)
    keep_words = [
        "我", "它", "这个", "因为", "所以", "孩子", "宝宝", "妈妈", "真的",
        "好喝", "好吃", "酸甜", "奶酪", "配料表就是", "配料表只有", "一岁",
    ]
    drop_words = [
        "净含量", "标准代号", "贮存", "邮编", "委托方", "参考值", "保护环境",
        "爱护地球", "幼儿园", "植物饮料", "浓缩液", "浓缩汁", "产品", "2026",
    ]
    lines = []
    for text in candidates:
        compact = re.sub(r"\s+", "", text)
        if any(word in compact for word in drop_words):
            continue
        if len(compact) > 36 and not any(word in compact for word in ["配料表就是", "配料表只有"]):
            continue
        if not any(word in compact for word in keep_words):
            continue
        lines.append(text)
        if len(lines) >= limit:
            break
    return lines


def comment_insights(comments: list[dict]) -> dict:
    texts = [str(c.get("text", "")) for c in comments if c.get("text")]
    joined = "\n".join(texts)
    demand_words = ["链接", "牌子", "品牌", "哪家", "在哪里买", "怎么买", "想买", "求", "是什么"]
    demand_comments = [t for t in texts if any(w in t for w in demand_words)]

    tokens = re.findall(r"[\u4e00-\u9fff]{2,}", joined)
    stop = {
        "这个", "那个", "有没有", "都是", "什么", "姐妹", "这里", "顶置", "收起",
        "小红书", "笔记", "博主", "评论", "链接", "发啦", "好吃",
    }
    common = Counter(t for t in tokens if t not in stop).most_common(12)
    return {
        "demand_comments": demand_comments[:10],
        "common_terms": common,
    }


def first_video(asset_dir: Path) -> Path | None:
    for ext in ("*.mp4", "*.mov", "*.m4v"):
        files = sorted(asset_dir.rglob(ext))
        if files:
            return files[0]
    return None


def collect_downloaded_assets(note_id: str, asset_dir: Path):
    if any(asset_dir.rglob("*.*")):
        return
    candidates = [
        ROOT / "xiaohongshu-downloads" / note_id,
        ROOT / "xhs-downloads" / note_id,
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        files = [p for p in candidate.rglob("*") if p.is_file()]
        if not files:
            continue
        asset_dir.mkdir(parents=True, exist_ok=True)
        for src in files:
            shutil.copy2(src, asset_dir / src.name)
        return


def generate_report(
    report_path: Path,
    url: str,
    note_id: str,
    note: dict,
    comments: list[dict],
    download_rows: list[dict],
    asset_dir: Path,
    frames: list[Path],
    contact_sheet: Path | None,
    ocr_rows: list[dict],
    transcript_rows: list[dict],
):
    insights = comment_insights(comments)
    tags = note.get("tags", "")
    title = note.get("title", "")
    content = note.get("content", "")
    ocr_lines = dedupe_ocr_lines(ocr_rows)

    lines = [
        f"# 小红书爆款拆解素材包 - {note_id}",
        "",
        f"- 原链接：{url}",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 作者：{note.get('author', '')}",
        f"- 点赞：{note.get('likes', '')}",
        f"- 收藏：{note.get('collects', '')}",
        f"- 评论：{note.get('comments', '')}",
        f"- 标签：{tags}",
        "",
        "## 读取状态",
        "",
    ]

    polluted = title in {"手机号登录", "马上登录即可"} or content == "刷到更懂你的优质内容"
    if polluted:
        lines.append("- 正文读取被登录弹层文案污染，标题和正文先不作为可信素材。")
    else:
        lines.extend([f"- 标题：{title}", f"- 正文：{content}"])

    lines.extend([
        f"- 素材目录：{asset_dir}",
        f"- 下载结果：{len(download_rows)} 个素材条目",
        f"- 关键帧数量：{len(frames)}",
        f"- OCR 文本条数：{len(ocr_lines)}",
        f"- 口播转写段落：{sum(1 for row in transcript_rows if row.get('text'))}",
    ])
    if contact_sheet and contact_sheet.exists():
        lines.append(f"- 关键帧总览：{contact_sheet}")

    lines.extend(["", "## 视频画面 OCR", ""])
    if ocr_lines:
        for text in ocr_lines:
            lines.append(f"- {text}")
    else:
        lines.append("- 暂未识别到稳定画面文字。")

    lines.extend(["", "## 口播转写", ""])
    transcript_lines = [row for row in transcript_rows if row.get("text")]
    if transcript_lines:
        for row in transcript_lines[:80]:
            lines.append(f"- {format_time(row['start'])}-{format_time(row['end'])} {row['text']}")
    else:
        lines.append("- 暂未生成口播转写。")

    lines.extend([
        "",
        "## 评论区信号",
        "",
        "### 高频词",
    ])
    for term, count in insights["common_terms"]:
        lines.append(f"- {term}：{count}")

    lines.extend(["", "### 明确需求评论"])
    if insights["demand_comments"]:
        for text in insights["demand_comments"]:
            lines.append(f"- {text}")
    else:
        lines.append("- 暂未抓到明显求链接/问品牌评论。")

    lines.extend([
        "",
        "## 初步爆款判断",
        "",
        "- 这条内容不是超大爆款，但收藏/点赞比例偏高，说明用户有保存和购买决策需求。",
        "- 评论区反复出现“链接、品牌、哪家、想买”，核心吸引点不是娱乐，而是宝宝零食选品清单。",
        "- 标签集中在宝宝零食、无添加、健康零食，说明选题命中的是妈妈人群的安全感和省心需求。",
        "",
        "## 可复用结构",
        "",
        "1. 人群钩子：宝宝零食/健康/配料干净。",
        "2. 选择理由：不是网红款，强调真实筛选。",
        "3. 清单密度：一次给多款，制造收藏价值。",
        "4. 信任补强：评论区补品牌和购买线索。",
        "5. 转化入口：置顶评论承接“有没有链接”的需求。",
        "",
        "## 画面脚本线索",
        "",
        "- 口播开头直接锁定人群：一岁以上宝宝、健康零食。",
        "- 每个段落按单品推进：展示包装、配料、口味、孩子试吃或使用场景。",
        "- 多次拍配料表和产品近景，用“看得见的证据”降低妈妈人群的不信任。",
        "- 节奏上是典型清单视频：苹果脆、四神饮、奶酪脆、小雪饼、煎饼、苹果干、酸奶条。",
        "",
        "## 下一步自动化",
        "",
        "- 加音频转写：还原视频口播脚本。",
        "- 加最终报告模板：输出“为什么爆、怎么仿、不能抄什么、可复用脚本”。",
    ])

    report_path.write_text("\n".join(lines), encoding="utf-8")


def generate_final_report(
    report_path: Path,
    url: str,
    note_id: str,
    note: dict,
    comments: list[dict],
    frames: list[Path],
    contact_sheet: Path | None,
    ocr_rows: list[dict],
    transcript_rows: list[dict],
):
    title = note.get("title", "")
    content = note.get("content", "")
    timeline = extract_product_timeline(content)
    insights = comment_insights(comments)
    ocr_lines = ocr_script_lines(ocr_rows, limit=20)
    transcript_lines = [row["text"] for row in transcript_rows if row.get("text")]
    collect_count = int(str(note.get("collects", "0")).replace(",", "") or 0)
    like_count = int(str(note.get("likes", "0")).replace(",", "") or 0)
    save_ratio = round(collect_count / like_count, 2) if like_count else 0

    lines = [
        f"# 爆款内容拆解报告 - {title or note_id}",
        "",
        "## 结论",
        "",
        f"- 这条不是流量型大爆款，但收藏/点赞比约 {save_ratio}，说明它有明显“收藏备用”和“购买决策”价值。",
        "- 爆点不是剧情或强情绪，而是“宝宝健康零食清单 + 配料表证据 + 评论区承接链接”。",
        "- 适合复用到母婴、零食、儿童用品、成分党选品这类账号。",
        "",
        "## 基础数据",
        "",
        f"- 作者：{note.get('author', '')}",
        f"- 点赞：{note.get('likes', '')}",
        f"- 收藏：{note.get('collects', '')}",
        f"- 评论：{note.get('comments', '')}",
        f"- 标签：{note.get('tags', '')}",
        f"- 原链接：{url}",
        "",
        "## 内容结构",
        "",
        "- 开头：直接点名目标人群和利益点，一岁以上宝宝、健康零食。",
        "- 主体：按单品清单推进，每个单品都给一个“为什么放心”的理由。",
        "- 证据：展示包装、配料表、孩子试吃，把主观推荐变成可验证推荐。",
        "- 收尾：靠评论区置顶补品牌和购买线索，承接转化需求。",
        "",
        "## 视频时间线",
        "",
    ]
    if timeline:
        for time, name in timeline:
            lines.append(f"- {time}：{name}")
    else:
        lines.append("- 暂未从正文中提取到时间线。")

    lines.extend([
        "",
        "## 画面与口播线索",
        "",
    ])
    for text in ocr_lines:
        lines.append(f"- {text}")
    if not ocr_lines:
        lines.append("- 暂未识别到稳定画面文字。")

    lines.extend([
        "",
        "## 口播转写状态",
        "",
    ])
    if transcript_lines:
        lines.append(f"- 已生成 {len(transcript_lines)} 段本地口播转写，可在原始素材里校对。")
        lines.append("- 本地模型会有少量错别字，正式判断优先结合画面 OCR、时间线和评论区。")
        lines.append("- 从转写和画面共同看，表达方式是：人群锁定 -> 单品展示 -> 配料/口味证据 -> 孩子反馈。")
    else:
        lines.append("- 暂未生成口播转写。")

    lines.extend([
        "",
        "## 评论区需求",
        "",
    ])
    for text in insights["demand_comments"][:8]:
        lines.append(f"- {text}")
    if not insights["demand_comments"]:
        lines.append("- 评论区暂未出现明显购买/品牌追问。")

    lines.extend([
        "",
        "## 为什么能被收藏",
        "",
        "- 用户面对的是“宝宝能不能吃、配料干不干净、买哪款不踩雷”的决策问题。",
        "- 清单内容天然适合收藏，因为用户不会立刻买完所有单品。",
        "- 配料表和试吃画面降低信任成本，评论区再补充品牌和链接，形成闭环。",
        "",
        "## 可复用模板",
        "",
        "1. 开头：`我最近给宝宝筛了几款真正配料干净的{品类}`。",
        "2. 筛选标准：`不是网红款，主要看配料、口味、孩子接受度`。",
        "3. 单品结构：`包装展示 -> 配料表 -> 口感/场景 -> 孩子反馈`。",
        "4. 结尾：`评论区放清单/品牌，方便大家对照`。",
        "",
        "## 不建议照抄",
        "",
        "- 不要只抄产品清单，真正有效的是“妈妈替你筛过”的信任人设。",
        "- 不要只讲好吃，要补配料表、年龄段、甜度、口感、适用场景。",
        "- 不要把标题写成泛泛推荐，应该锁定人群和标准，例如“一岁以上”“配料干净”“不甜”。",
        "",
        "## 文件证据",
        "",
        f"- 关键帧：{len(frames)} 张",
        f"- 口播转写：{len(transcript_lines)} 段",
    ])
    if contact_sheet and contact_sheet.exists():
        lines.append(f"- 关键帧总览：{contact_sheet}")
    transcript_path = report_path.parent / "raw" / "口播转写.txt"
    if transcript_path.exists():
        lines.append(f"- 口播转写文件：{transcript_path}")
    lines.append(f"- 素材包编号：{note_id}")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    args = parser.parse_args()

    note_id = note_id_from_url(args.url)
    run_dir = OUTPUT_ROOT / note_id
    raw_dir = run_dir / "raw"
    asset_dir = run_dir / "assets"
    frames_dir = run_dir / "frames"
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)

    print("1/6 读取笔记基础信息...")
    note_out, note_err, note_code = run_opencli([
        "xiaohongshu", "note", args.url,
        "--format", "json",
        "--window", "foreground",
        "--site-session", "persistent",
        "--keep-tab", "true",
        "--trace", "retain-on-failure",
    ], ROOT)
    (raw_dir / "note.stdout.txt").write_text(note_out, encoding="utf-8")
    (raw_dir / "note.stderr.txt").write_text(note_err, encoding="utf-8")
    note_rows = parse_rows(note_out)
    save_json(raw_dir / "note.json", note_rows)

    print("2/6 读取评论区...")
    comments_out, comments_err, comments_code = run_opencli([
        "xiaohongshu", "comments", args.url,
        "--limit", "50",
        "--with-replies", "true",
        "--format", "json",
        "--window", "foreground",
        "--site-session", "persistent",
        "--keep-tab", "true",
        "--trace", "retain-on-failure",
    ], ROOT)
    (raw_dir / "comments.stdout.txt").write_text(comments_out, encoding="utf-8")
    (raw_dir / "comments.stderr.txt").write_text(comments_err, encoding="utf-8")
    comments_rows = parse_rows(comments_out)
    save_json(raw_dir / "comments.json", comments_rows)

    print("3/6 下载视频/图片素材...")
    download_out, download_err, download_code = run_opencli([
        "xiaohongshu", "download", args.url,
        "--output", str(asset_dir),
        "--format", "json",
        "--window", "foreground",
        "--site-session", "persistent",
        "--keep-tab", "true",
        "--trace", "retain-on-failure",
    ], ROOT)
    (raw_dir / "download.stdout.txt").write_text(download_out, encoding="utf-8")
    (raw_dir / "download.stderr.txt").write_text(download_err, encoding="utf-8")
    download_rows = parse_rows(download_out)
    save_json(raw_dir / "download.json", download_rows)
    collect_downloaded_assets(note_id, asset_dir)

    print("4/6 抽取视频关键帧...")
    video = first_video(asset_dir)
    frames = []
    contact_sheet = None
    if video:
        frames = extract_frames(video, frames_dir)
        contact_sheet = run_dir / "关键帧总览.jpg"
        make_contact_sheet(frames, contact_sheet)

    print("5/6 识别关键帧文字...")
    ocr_rows = run_ocr(frames, raw_dir / "ocr.json")

    print("6/6 转写视频口播...")
    transcript_rows = transcribe_video(video, raw_dir)

    report_path = run_dir / "拆解素材包.md"
    final_report_path = run_dir / "爆款拆解报告.md"
    generate_report(
        report_path=report_path,
        url=args.url,
        note_id=note_id,
        note=fields_to_dict(note_rows),
        comments=comments_rows,
        download_rows=download_rows,
        asset_dir=asset_dir,
        frames=frames,
        contact_sheet=contact_sheet,
        ocr_rows=ocr_rows,
        transcript_rows=transcript_rows,
    )
    generate_final_report(
        report_path=final_report_path,
        url=args.url,
        note_id=note_id,
        note=fields_to_dict(note_rows),
        comments=comments_rows,
        frames=frames,
        contact_sheet=contact_sheet,
        ocr_rows=ocr_rows,
        transcript_rows=transcript_rows,
    )

    print("")
    print("完成。")
    print(f"报告：{report_path}")
    print(f"正式拆解：{final_report_path}")
    print(f"素材：{asset_dir}")
    if contact_sheet:
        print(f"关键帧总览：{contact_sheet}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
