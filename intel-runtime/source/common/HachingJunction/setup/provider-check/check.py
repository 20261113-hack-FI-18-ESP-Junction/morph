#!/usr/bin/env python3
"""Credential-safe provider access checks. These checks never control a robot."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime
import getpass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / "station/.env.providers"
OUTPUT = ROOT / "station/verification/provider-checks"
KEYS = {
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "gemma": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "decisions": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "nemotron": ("NVIDIA_API_KEY", "NIM_API_KEY"),
    "elevenlabs": ("ELEVENLABS_API_KEY",),
    "jev": ("TYPESAFE_API_KEY",),
    "verda": ("VERDA_INFERENCE_KEY",),
}
DEFAULT_SERVICES = ["gemini", "decisions", "nemotron", "elevenlabs"]
MODELS = {"decisions": "gemini-decision-1", "gemma": "gemma-4-26b-a4b-it", "nemotron": "nvidia/nemotron-3.5-super-vl-120b-a12b", "jev": "jev-1.14.0", "verda": "nemotron-3.5-super-vl"}


def now():
    return datetime.now(ZoneInfo("Europe/Ljubljana")).isoformat()


def load_config(path=ENV_FILE):
    """Read literal assignments only; never execute or expand configuration."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Credential file must not be a symlink")
    if not path.exists():
        return {}
    if not path.is_file():
        raise ValueError("Credential path is not a regular file")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("Credential file must have owner-only permissions: chmod 600 station/.env.providers")
    result = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
        if not match:
            continue
        key, value = match.groups()
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise ValueError("Invalid quoted value in credential file") from None
        elif len(value) >= 2 and value[0] == value[-1] == "'":
            value = value[1:-1]
        if isinstance(value, str):
            result[key] = value
    return result


def credential(service, config):
    for key in KEYS[service]:
        if os.environ.get(key):
            return os.environ[key], key, "process_environment"
    for key in KEYS[service]:
        if config.get(key):
            return config[key], key, str(ENV_FILE)
    return None, KEYS[service][0], None


def configure(services, path=ENV_FILE):
    if not sys.stdin.isatty():
        raise ValueError("Run configure yourself in an interactive terminal; never paste keys into chat")
    path = Path(path)
    config = load_config(path)
    original = path.read_text() if path.exists() else "# Local server-side provider credentials. Never commit or share.\n"
    additions = []
    seen = set()
    for service in services:
        key = KEYS[service][0]
        if key in seen:
            continue
        seen.add(key)
        existing, _, _ = credential(service, config)
        if existing:
            print(f"{key}: already configured; preserved")
            continue
        value = getpass.getpass(f"{key} (hidden; Enter skips): ").strip()
        if not value:
            print(f"{key}: skipped")
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.\-]+", value):
            raise ValueError(f"{key}: unexpected characters; no changes were saved")
        additions.append(f"{key}={json.dumps(value)}\n")
    if not additions:
        print("No credential changes")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Credential file must not be a symlink")
    fd, temp_name = tempfile.mkstemp(prefix=".provider-credentials-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(original.rstrip("\n") + "\n" + "".join(additions))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    print(f"Saved {len(additions)} credential(s) to {path}, permissions 0600. Values are hidden.")


def redact(value, secrets):
    """Redact credentials and token-bearing fields before any log or output."""
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if re.search(r"authorization|api[_-]?key|^(?:access_|refresh_)?token$", str(k), re.I)
                    else redact(v, secrets)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in sorted(filter(None, secrets), key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9_.-]+", r"\1[REDACTED]", value)
        return value
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Redirect rejected; credentials were not forwarded", headers, fp)


def request(url, method, headers, payload, timeout):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={**headers, "Accept": "application/json", "Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as response:
            status = response.status
            raw = response.read(1_000_001)
    except urllib.error.HTTPError as error:
        status = error.code
        raw = error.read(1_000_001) if error.fp else b""
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        is_timeout = isinstance(error, TimeoutError) or isinstance(getattr(error, "reason", None), TimeoutError)
        return {"http_status": None, "latency_ms": round((time.perf_counter()-started)*1000, 2),
                "timeout_seconds": timeout, "error_category": "timeout" if is_timeout else "transport_error", "transport_error": str(error)}
    elapsed = round((time.perf_counter()-started)*1000, 2)
    if len(raw) > 1_000_000:
        return {"http_status": status, "latency_ms": elapsed, "timeout_seconds": timeout, "error_category": "response_too_large", "error": "Response exceeded the one-megabyte limit"}
    try:
        body = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        body = {"non_json_response": raw.decode(errors="replace")[:2000]}
    return {"http_status": status, "latency_ms": elapsed, "timeout_seconds": timeout,
            "error_category": "http_error" if status >= 400 else "redirect_rejected" if 300 <= status < 400 else None, "response": body}


def choice_payload(field, model):
    return {"model": model, field: "The operator requests pause after the current cycle.",
            "questions": {"goal": {"type": "choice", "instructions": "What does the operator request?",
                "criteria": {"pause": "Pause after the current cycle", "continue": "Continue sorting", "hold": "Unsupported request or hold"}}}}


def build_request(service, key, image_path=None, gemini_model=None):
    if service == "decisions":
        body = choice_payload("input", MODELS[service])
        return "https://generativelanguage.googleapis.com/v1beta/decisions", "POST", {"x-goog-api-key": key}, body, body
    if service == "jev":
        body = choice_payload("state", MODELS[service])
        return "https://api.typesafe.ai/v1/systemone", "POST", {"Authorization": f"Bearer {key}"}, body, body
    if service == "gemini":
        if not gemini_model or not re.fullmatch(r"gemini-[a-z0-9.-]+", gemini_model):
            raise ValueError("Provide an exact currently available model using --gemini-model")
        body = {"model": gemini_model, "input": "Reply with only the word READY.", "generation_config": {"max_output_tokens": 64, "thinking_level": "minimal"}}
        return "https://generativelanguage.googleapis.com/v1beta/interactions", "POST", {"x-goog-api-key": key, "Api-Revision": "2026-05-20"}, body, body
    if service == "gemma":
        body = {"contents": [{"parts": [{"text": "Reply with exactly READY"}]}],
                "generationConfig": {"maxOutputTokens": 32, "thinkingConfig": {"thinkingLevel": "minimal"}}}
        evidence = {"model": MODELS[service], **body}
        return f"https://generativelanguage.googleapis.com/v1beta/models/{MODELS[service]}:generateContent", "POST", {"x-goog-api-key": key}, body, evidence
    if service == "elevenlabs":
        return "https://api.elevenlabs.io/v1/models", "GET", {"xi-api-key": key}, None, {"purpose": "Model catalogue and credential access only; no microphone or streaming test"}
    if service in ("nemotron", "verda"):
        if not image_path:
            raise ValueError("Nemotron requires --image pointing to a consented task image or a clearly labeled synthetic fixture")
        path = Path(image_path)
        raw = path.read_bytes()
        if len(raw) > 4_000_000:
            raise ValueError("Use an image smaller than four megabytes for this minimal test")
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif raw.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        else:
            raise ValueError("Only PNG or JPEG image content is accepted")
        prompt = "Describe the visible object and its color in one short sentence. Do not infer a defect or physical outcome."
        content = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(raw).decode()}"}}]
        max_tokens = 1024 if service == "verda" else 256
        body = {"model": MODELS[service], "messages": [{"role": "user", "content": content}], "max_tokens": max_tokens, "temperature": 0, "stream": False}
        evidence = {"model": MODELS[service], "prompt": prompt, "image": {"file": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "mime": mime}, "max_tokens": max_tokens, "temperature": 0, "stream": False}
        if service == "nemotron":
            body["reasoning_effort"] = evidence["reasoning_effort"] = "none"
            url = "https://integrate.api.nvidia.com/v1/chat/completions"
        else:
            url = "https://containers.datacrunch.io/nemotron-3-5-super-vl-b300/v1/chat/completions"
        return url, "POST", {"Authorization": f"Bearer {key}"}, body, evidence
    raise ValueError("Unknown service")


def validate(service, result):
    if result.get("http_status") != 200:
        return False, "HTTP request did not succeed"
    body = result.get("response")
    if service == "elevenlabs":
        ok = isinstance(body, list) and bool(body) and all(isinstance(m, dict) and isinstance(m.get("model_id"), str) for m in body)
        return ok, "Model catalogue only; Scribe v3 Live session and real microphone remain unverified"
    if not isinstance(body, dict):
        return False, "Expected a JSON object"
    if service in ("decisions", "jev"):
        goal = body.get("answers", {}).get("goal", {})
        probabilities = goal.get("probabilities", {})
        ok = goal.get("choice") == "pause" and isinstance(probabilities, dict) and set(probabilities) == {"pause", "continue", "hold"}
        ok = ok and all(isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 1 for v in probabilities.values())
        ok = ok and abs(sum(probabilities.values()) - 1) <= 0.01
        if service == "decisions":
            ok = ok and body.get("usage", {}).get("total_output_tokens") == 0
        else:
            ok = ok and body.get("model") == MODELS["jev"]
        return ok, "Fixed-choice schema, pause selection and probabilities checked; no robot dispatch"
    if service == "gemini":
        texts = [p.get("text", "") for step in body.get("steps", []) if step.get("type") == "model_output"
                 for p in step.get("content", []) if p.get("type") == "text"]
        return any(t.strip() == "READY" for t in texts), "Expected the exact short response READY"
    if service == "gemma":
        texts = [part.get("text", "") for candidate in body.get("candidates", [])
                 for part in candidate.get("content", {}).get("parts", []) if not part.get("thought")]
        returned = body.get("modelVersion")
        if returned is not None and returned != MODELS[service]:
            return False, "Returned modelVersion differs from the requested Gemma model; inspect deployment identity"
        return any(text.strip() == "READY" for text in texts), "Expected READY from the pinned Gemma model; returned modelVersion checked when present"
    if service == "nemotron":
        choices = body.get("choices", [])
        content = choices[0].get("message", {}).get("content") if choices else None
        return body.get("model") == MODELS[service] and isinstance(content, str) and bool(content.strip()), "Exact returned model and nonempty visual response required; quality remains unmeasured"
    if service == "verda":
        choices = body.get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            has_reasoning = isinstance(message.get("reasoning_content"), str) and bool(message["reasoning_content"].strip())
            return False, "Model returned reasoning only; no usable final visual response" if has_reasoning else "No usable final visual response"
        return isinstance(body.get("model"), str) and bool(body["model"].strip()), "Sponsor deployment returned a model identifier and final visual response; compare recorded identity with deployment metadata"
    return False, "Unknown service"


def check(args):
    config = load_config()
    secrets = [v for service in KEYS for v, _, _ in [credential(service, config)] if v]
    report = {"schema_version": 1, "check_id": str(uuid.uuid4()), "started_at": now(), "timezone": "Europe/Ljubljana", "mode": args.command,
              "scope": "Provider access only. No station requests, robot commands, production integration or physical verification.",
              "credential_file": str(ENV_FILE), "services": []}
    for service in args.services:
        key, variable, source = credential(service, config)
        record = {"service": service, "credential_configured": bool(key), "variable": variable, "credential_source": source,
                  "status": "configured_not_tested" if key else "blocked_missing_credential"}
        if args.command == "live" and key:
            try:
                url, method, headers, body, evidence = build_request(service, key, args.image, args.gemini_model)
                record.update({"endpoint": url, "method": method, "requested_model": MODELS.get(service, args.gemini_model if service == "gemini" else None),
                               "input": evidence, "image_kind": args.image_kind if service in ("nemotron", "verda") else None, "started_at": now()})
                result = request(url, method, headers, body, args.timeout)
                record.update(result)
                response_body = result.get("response")
                record["returned_model"] = response_body.get("model", response_body.get("modelVersion")) if isinstance(response_body, dict) else None
                if service == "decisions" and record["returned_model"] is None:
                    record["model_identity_note"] = "The documented Decisions response does not include a model identifier; the request pins gemini-decision-1."
                if service == "gemini":
                    record["api_revision"] = "2026-05-20"
                if service == "verda":
                    record["model_identity_note"] = "Sponsor-supplied deployment alias. Requested and returned identifiers are recorded separately; NVIDIA catalog-name equality is not assumed."
                passed, detail = validate(service, result)
                record.update({"status": "passed_catalogue_only" if passed and service == "elevenlabs" else "passed_minimal_request" if passed else "failed", "validation": detail, "finished_at": now()})
            except (ValueError, OSError, TypeError, KeyError, IndexError, AttributeError) as error:
                record.update({"status": "blocked_or_invalid_response", "error": str(error)})
        report["services"].append(redact(record, secrets))
        print(f"{service}: {report['services'][-1]['status']}")
    report["finished_at"] = now()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    output = OUTPUT / f"{report['check_id']}.json"
    output.write_text(json.dumps(redact(report, secrets), indent=2) + "\n")
    print(f"Evidence: {output}")
    eligible = (lambda r: r["credential_configured"]) if args.command == "preflight" else (lambda r: r["status"].startswith("passed_"))
    return 0 if all(eligible(r) for r in report["services"]) else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["configure", "preflight", "live"])
    parser.add_argument("--services", nargs="+", choices=KEYS, default=DEFAULT_SERVICES,
                        help="Jev is opt-in; it does not replace Gemini Decision 1")
    parser.add_argument("--gemini-model", help="Exact verified Gemini generative model ID")
    parser.add_argument("--image", help="PNG/JPEG file explicitly selected for the Nemotron request")
    parser.add_argument("--image-kind", choices=["synthetic_fixture", "camera_frame", "reference_image"], help="Required with --image; record the actual source of the image")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 60:
        parser.error("--timeout must be between 1 and 60 seconds")
    if args.image and not args.image_kind:
        parser.error("--image-kind is required with --image")
    try:
        if args.command == "configure":
            configure(args.services)
            return 0
        return check(args)
    except (ValueError, OSError) as error:
        print(f"Setup error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
