"""Xiaohongshu analyzer v3.

Builds on xhs_analyzer_v2 and adds a focused durability fix for comments:
- comments default timeout is extended to 180s;
- TIMEOUT/exitCode 75 retries once with 240s;
- other analyzer behavior remains unchanged.
"""

from pathlib import Path

import xhs_analyzer as base
import xhs_analyzer_v2 as v2  # noqa: F401  # importing applies v2 patches


ORIGINAL_V2_RUN_OPENCLI = v2.patched_run_opencli


def has_arg(args: list[str], name: str) -> bool:
    return any(str(item) == name or str(item).startswith(f"{name}=") for item in args)


def is_comments_command(args: list[str]) -> bool:
    return len(args) >= 2 and args[0] == "xiaohongshu" and args[1] == "comments"


def with_timeout(args: list[str], seconds: int) -> list[str]:
    result = list(args)
    if is_comments_command(result) and not has_arg(result, "--timeout"):
        result.extend(["--timeout", str(seconds)])
    return result


def is_timeout_failure(stderr: str, code: int) -> bool:
    text = str(stderr or "").lower()
    return code == 75 or "timeout" in text or "timed out" in text


def patched_run_opencli_v3(args: list[str], cwd: Path):
    command_args = with_timeout(args, 180)
    stdout, stderr, code = ORIGINAL_V2_RUN_OPENCLI(command_args, cwd)

    if is_comments_command(args) and is_timeout_failure(stderr, code):
        retry_args = with_timeout(args, 240)
        stdout2, stderr2, code2 = ORIGINAL_V2_RUN_OPENCLI(retry_args, cwd)
        if code2 == 0 or code != 0:
            return stdout2, stderr2, code2

    return stdout, stderr, code


base.run_opencli = patched_run_opencli_v3


if __name__ == "__main__":
    base.main()
