"""
Gateway-agnostic LLM layer.

Everything in the demo that needs an LLM (file extraction, column mapping, the
agent) calls llm.complete(prompt, system) -> {text, cost_usd, ...}. The backend
is swappable:

  - Magica gateway (default): POST a run to a Claude node, poll until COMPLETED,
    read output.output. Async by design; cost surfaced per call.
  - Direct Anthropic SDK (optional): if ANTHROPIC_API_KEY is set and Magica is
    not, use the SDK directly.

Because a gateway only does prompt-in / text-out (no tools, no structured-output
API), callers that need structure ask for JSON in the response and use
extract_json() to parse it. That keeps the whole thing portable.
"""
import json
import os
import re
import time
import urllib.request
import urllib.error

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env():
    """Minimal .env loader (no dependency on python-dotenv)."""
    path = os.path.join(_ROOT, ".env")
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and not os.environ.get(k):
            os.environ[k] = v


load_env()

MAGICA_BASE = os.environ.get("MAGICA_BASE", "https://api.magica.com/api/v1")
MAGICA_KEY = os.environ.get("MAGICA_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Sonnet for high-volume extraction/mapping (cheap), Opus for the agent (sharp).
EXTRACT_MODEL = os.environ.get("EXTRACT_MODEL", "claude_sonnet_4_6")
AGENT_MODEL = os.environ.get("AGENT_MODEL", "claude_opus_4_8")
# direct-Anthropic equivalents (only used if running without Magica)
_ANTHROPIC_MAP = {
    "claude_sonnet_4_6": "claude-sonnet-4-6",
    "claude_opus_4_6": "claude-opus-4-6",
    "claude_opus_4_7": "claude-opus-4-7",
    "claude_opus_4_8": "claude-opus-4-8",
}


def backend():
    if MAGICA_KEY:
        return "magica"
    if ANTHROPIC_KEY:
        return "anthropic"
    return "none"


def available():
    return backend() != "none"


def status():
    return {"backend": backend(), "available": available(),
            "extract_model": EXTRACT_MODEL, "agent_model": AGENT_MODEL}


class LLMError(Exception):
    pass


# --------------------------------------------------------------------------
# Magica backend
# --------------------------------------------------------------------------
def _magica(prompt, system, model, max_tokens, timeout):
    headers = {"Authorization": "Bearer " + MAGICA_KEY, "Content-Type": "application/json"}
    body = {"input": {"prompt": prompt, "system_prompt": system or "",
                      "max_tokens": min(int(max_tokens), 8192), "temperature": 0}}
    req = urllib.request.Request(MAGICA_BASE + "/nodes/" + model + "/run",
                                 json.dumps(body).encode(), headers, method="POST")
    try:
        run = json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        raise LLMError("Magica run failed: HTTP %s %s" % (e.code, e.read().decode()[:200]))
    run_id = run.get("runId") or run.get("id")
    if not run_id:
        raise LLMError("Magica: no runId in response: %s" % run)

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1.5)
        g = urllib.request.Request(MAGICA_BASE + "/nodes/runs/" + run_id, headers=headers)
        s = json.load(urllib.request.urlopen(g, timeout=60))
        st = str(s.get("status", "")).upper()
        if st in ("COMPLETED", "SUCCEEDED", "SUCCESS", "DONE"):
            out = s.get("output") or {}
            text = out.get("output") if isinstance(out, dict) else out
            return {"text": text or "", "cost_usd": float(out.get("cost_usd") or 0),
                    "model": out.get("model", model), "credits": s.get("creditUsed", 0)}
        if st in ("FAILED", "ERROR"):
            raise LLMError("Magica run %s: %s" % (st, s.get("error")))
    raise LLMError("Magica run timed out after %ss" % timeout)


# --------------------------------------------------------------------------
# Direct Anthropic backend (fallback)
# --------------------------------------------------------------------------
def _anthropic(prompt, system, model, max_tokens, timeout):
    import anthropic
    client = anthropic.Anthropic()
    mid = _ANTHROPIC_MAP.get(model, "claude-sonnet-4-6")
    resp = client.messages.create(model=mid, max_tokens=min(int(max_tokens), 8192),
                                  system=system or "", messages=[{"role": "user", "content": prompt}])
    text = " ".join(b.text for b in resp.content if b.type == "text")
    return {"text": text, "cost_usd": 0.0, "model": mid, "credits": 0}


def complete(prompt, system="", model=None, max_tokens=2000, timeout=120):
    model = model or EXTRACT_MODEL
    b = backend()
    if b == "magica":
        return _magica(prompt, system, model, max_tokens, timeout)
    if b == "anthropic":
        return _anthropic(prompt, system, model, max_tokens, timeout)
    raise LLMError("No LLM backend configured (set MAGICA_API_KEY or ANTHROPIC_API_KEY in .env)")


# --------------------------------------------------------------------------
# JSON extraction from free-form model text
# --------------------------------------------------------------------------
def extract_json(text):
    """Pull the first JSON object/array out of a model response."""
    if not text:
        raise LLMError("empty model response")
    t = text.strip()
    # strip ```json fences
    m = re.search(r"```(?:json)?\s*(.+?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    # find the outermost { } or [ ]
    for open_c, close_c in (("{", "}"), ("[", "]")):
        i, j = t.find(open_c), t.rfind(close_c)
        if i != -1 and j != -1 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except Exception:
                continue
    raise LLMError("could not parse JSON from model response: " + t[:200])
