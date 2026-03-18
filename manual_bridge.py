"""
Karpathy Manual Bridge — file-based prompt/response handoff.

When KARPATHY_MANUAL_MODE=1, proposer/critic calls save prompts to
manual_prompts/ and wait for response files. The orchestrator (Claude Code)
reads prompts, shows them to the user, user pastes into their LLM
subscription, and Claude Code writes the response file.

No timeout. $0 API cost.
"""

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("karpathy.manual_bridge")

_PROJECT_ROOT = Path(__file__).resolve().parent
MANUAL_PROMPTS_DIR = _PROJECT_ROOT / "manual_prompts"

_call_seq = 0


def _next_seq() -> int:
    global _call_seq
    _call_seq += 1
    return _call_seq


def reset_seq() -> None:
    global _call_seq
    _call_seq = 0


@dataclass
class ManualCall:
    seq: int
    role: str
    model_hint: str
    prompt_file: str
    response_file: str


def save_prompt(
    role: str,
    system_prompt: str,
    user_prompt: str,
    model_hint: str = "",
    *,
    messages: Optional[list] = None,
) -> ManualCall:
    """Save prompt to disk, return paths for response."""
    MANUAL_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

    seq = _next_seq()
    safe_role = role.replace("/", "_").replace("\\", "_")

    prompt_fname = f"{seq:03d}_{safe_role}_prompt.txt"
    response_fname = f"{seq:03d}_{safe_role}_response.txt"

    prompt_path = MANUAL_PROMPTS_DIR / prompt_fname
    response_path = MANUAL_PROMPTS_DIR / response_fname

    lines = []
    lines.append("=" * 72)
    lines.append(f"KARPATHY MANUAL LLM CALL — #{seq}")
    lines.append(f"Role: {role}")
    lines.append(f"Model hint: {model_hint or 'Claude Sonnet 4.6'}")
    lines.append(f"Timestamp: {datetime.now().isoformat()}")
    lines.append("=" * 72)
    lines.append("")
    lines.append("--- SYSTEM PROMPT ---")
    lines.append(system_prompt or "(none)")
    lines.append("")
    lines.append("--- USER PROMPT ---")
    lines.append(user_prompt or "(none)")
    lines.append("")
    lines.append("=" * 72)
    lines.append("PASTE THE LLM RESPONSE INTO THE CORRESPONDING _response.txt FILE")
    lines.append(f"Response file: {response_path.name}")
    lines.append("IMPORTANT: Return ONLY valid JSON starting with {{")
    lines.append("=" * 72)

    prompt_path.write_text("\n".join(lines), encoding="utf-8")

    print()
    print("=" * 60)
    print(f"  MANUAL LLM CALL #{seq} — {role}")
    print(f"  Model hint: {model_hint or 'Claude Sonnet 4.6'}")
    print(f"  Prompt: {prompt_path}")
    print(f"  Response: {response_path}")
    print("  >>> Waiting for response file to be written <<<")
    print("=" * 60)
    print()

    return ManualCall(
        seq=seq,
        role=role,
        model_hint=model_hint,
        prompt_file=str(prompt_path),
        response_file=str(response_path),
    )


def wait_for_response(
    response_file: str,
    poll_interval: float = 2.0,
    timeout: Optional[float] = None,
) -> str:
    """Poll for response file. No timeout by default."""
    path = Path(response_file)
    start = time.time()
    check_count = 0

    while True:
        if path.exists():
            content = path.read_text(encoding="utf-8").strip()
            if content:
                elapsed = time.time() - start
                logger.info(f"[MANUAL] Response: {path.name} ({len(content)} chars, {elapsed:.1f}s)")
                return content

        check_count += 1
        if check_count % 15 == 0:
            elapsed = time.time() - start
            logger.info(f"[MANUAL] Waiting for {path.name} ({elapsed:.0f}s)")

        if timeout and (time.time() - start) > timeout:
            raise TimeoutError(f"No response within {timeout}s: {response_file}")

        time.sleep(poll_interval)


def manual_llm_call(
    role: str,
    system_prompt: str,
    user_prompt: str,
    model_hint: str = "",
    **kwargs,
) -> str:
    """All-in-one: save prompt, wait for response, return text."""
    call = save_prompt(role, system_prompt, user_prompt, model_hint)
    return wait_for_response(call.response_file)


def clean_prompts_dir() -> int:
    """Remove all files in manual_prompts/."""
    if not MANUAL_PROMPTS_DIR.exists():
        return 0
    count = 0
    for f in MANUAL_PROMPTS_DIR.iterdir():
        if f.is_file() and f.name != ".gitkeep":
            f.unlink()
            count += 1
    return count
