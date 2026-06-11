"""Launcher v3: content-learning workbench + robust Xiaohongshu metadata parser.

server_v2 already patches the workbench workflow. This file keeps all of that and
only swaps the local analyzer from tools/xhs_analyzer.py to tools/xhs_analyzer_v2.py,
which can parse nested/object JSON metadata for title/author/engagement fields.
"""

import subprocess
import sys

import server_v2  # noqa: F401  # importing applies all v2 patches
import server as base


def patched_run_analysis_task_v3(task_id, sample_id, url, sample_meta):
    task_path = base.TASK_ROOT / f"{task_id}.json"
    db = base.load_db()
    sample = next((x for x in db.get("samples", []) if x.get("id") == sample_id), None)
    try:
        base.write_json(task_path, {"id": task_id, "status": "正在抓取小红书内容", "updatedAt": base.now_text()})
        analyzer = base.ROOT / "tools" / "xhs_analyzer_v2.py"
        subprocess.run([sys.executable, str(analyzer), "--url", url], cwd=base.ROOT, check=True)
        note_id = base.note_id_from_url(url)
        base.write_json(task_path, {"id": task_id, "status": "正在生成 GPT 分析包", "updatedAt": base.now_text()})
        package_id = base.create_analysis_package(note_id, url, sample_meta)
        package_dir = base.ANALYSIS_INBOX_ROOT / package_id
        ok, msg = base.git_upload(package_dir)
        db = base.load_db()
        sample = next((x for x in db.get("samples", []) if x.get("id") == sample_id), None)
        if sample:
            sample["noteId"] = note_id
            sample["analysisPackageId"] = package_id
            sample["status"] = "待 GPT 分析" if ok else "分析包生成成功，GitHub 上传失败"
            sample["updatedAt"] = base.now_text()
            base.save_db(db)
        base.write_json(task_path, {"id": task_id, "status": sample.get("status") if sample else "完成", "message": msg, "packageId": package_id, "updatedAt": base.now_text()})
    except Exception as exc:
        db = base.load_db()
        sample = next((x for x in db.get("samples", []) if x.get("id") == sample_id), None)
        if sample:
            sample["status"] = "抓取/分析包生成失败"
            sample["error"] = str(exc)
            sample["updatedAt"] = base.now_text()
            base.save_db(db)
        base.write_json(task_path, {"id": task_id, "status": "失败", "error": str(exc), "updatedAt": base.now_text()})


base.run_analysis_task = patched_run_analysis_task_v3


if __name__ == "__main__":
    base.run()
