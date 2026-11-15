"""Scoped project reads and append-only, idempotent handoff notes."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from datetime import datetime, timezone
from uuid import UUID

ROOT_FILES = {
    "AGENTS.md", "JUNCTION.md", "IGNITE_INTEL_PHYSICAL_AI.md",
    "PHYSICAL_AI_WORKFLOW.md", "PHYSICAL_AI_ORCHESTRATION.md",
    "PHYSICAL_AI_EXTENSIONS.md", "PHYSICAL_AI_CHALLENGE_COMBINATIONS.md",
    "PHYSICAL_AI_TASK_PLAN.md", "PHYSICAL_AI_SETUP.md", "NOTION_SYNC.md",
    "CONTEXT_SHARING.md", "Intel_Physical AI Hackathon.pdf", ".gitignore",
}
DIRECTORIES = ("context", "context_mcp", "setup", "station", "design/morph-handoff")
TEXT_SUFFIXES = {".md", ".txt", ".py", ".sh", ".ps1", ".toml", ".json", ".yaml", ".yml", ".sql", ".js", ".cjs", ".ts", ".tsx", ".jsx", ".css", ".html", ".svg", ".in", ".lock", ".csv", ".xml"}
BINARY_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".ttf", ".woff", ".woff2"}
DENIED_PARTS = {"node_modules", "__pycache__", "dist", "build", "tmp", "logs"}
MAX_TEXT_BYTES = 2_000_000
MAX_ASSET_BYTES = 32_000_000
MAX_NOTE_CHARS = 24_000
SECRET_PATTERNS = [
    re.compile(r"(?i)\b(?:sk-(?:proj-)?[a-z0-9_-]{16,}|nvapi-[a-z0-9_-]{16,}|gh[pousr]_[a-z0-9_]{20,}|github_pat_[a-z0-9_]{20,}|AIza[a-z0-9_-]{30,})"),
    re.compile(r"(?i)(\bBearer\s+)[a-z0-9._~+/-]{16,}"),
    re.compile(r"(?im)([\"']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|client[_-]?secret|authorization|MORPH_CONTEXT_TOKEN)[\"']?\s*[:=]\s*)(?P<quote>[\"'])[^\"'\r\n]{8,}(?P=quote)"),
    re.compile(r"(?im)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|client[_-]?secret|authorization|MORPH_CONTEXT_TOKEN)\s*[:=]\s*)(?P<unquoted>[a-z0-9][a-z0-9_+/=-]{15,})(?=[ \t]*(?:[#;]|$))"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact(text: str) -> str:
    def replacement(match: re.Match) -> str:
        prefix = match.group(1) if match.lastindex else ""
        # Keep quoted strings valid in Python, JSON and shell source exports.
        quote = match.groupdict().get("quote")
        if quote:
            return prefix + quote + "[REDACTED]" + quote
        if match.groupdict().get("unquoted"):
            return prefix + '"[REDACTED]"'
        return prefix + "[REDACTED]"

    for pattern in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class ContextStore:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        if not (self.root / "AGENTS.md").is_file():
            raise ValueError("The project root must contain AGENTS.md")

    def path(self, relative: str) -> Path:
        p = PurePosixPath(relative)
        if not relative or "\\" in relative or "\x00" in relative or p.is_absolute() or ".." in p.parts or p.as_posix() != relative:
            raise ValueError("Use an exact project-relative path from list_context")
        if relative not in ROOT_FILES:
            if not any(relative.startswith(prefix + "/") for prefix in DIRECTORIES):
                raise ValueError("Path is outside the shared context")
            if any(part.startswith(".") or part in DENIED_PARTS for part in p.parts):
                raise ValueError("Hidden files, caches and runtime data are not shared")
            if p.suffix.lower() not in TEXT_SUFFIXES | BINARY_SUFFIXES:
                raise ValueError("This file type is not shared")
            if p.name.lower() in {"connection.json", "connection.toml", "connection.yaml", "connection.yml"} or any(word in p.name.lower() for word in ("credential", "private-key", "token-file", "secret")):
                raise ValueError("Credential and connection files are not shared")
        full = self.root.joinpath(*p.parts)
        current = self.root
        for part in p.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("Symbolic links are not shared")
        if not full.resolve().is_relative_to(self.root):
            raise ValueError("Path escapes the project")
        if not full.is_file():
            raise ValueError("Shared file not found")
        return full

    def paths(self):
        candidates = [self.root / name for name in ROOT_FILES]
        for prefix in DIRECTORIES:
            base = self.root / prefix
            if base.is_symlink() or not base.is_dir():
                continue
            for directory, dirs, files in os.walk(base, followlinks=False):
                dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in DENIED_PARTS and not (Path(directory) / d).is_symlink())
                candidates.extend(Path(directory) / name for name in files)
        for candidate in sorted(set(candidates)):
            relative = candidate.relative_to(self.root).as_posix()
            try:
                yield relative, self.path(relative)
            except ValueError:
                continue

    def is_text(self, path: Path) -> bool:
        return path.suffix.lower() in TEXT_SUFFIXES or path.name == ".gitignore"

    def text(self, relative: str) -> tuple[str, bool]:
        path = self.path(relative)
        if not self.is_text(path):
            raise ValueError("Binary asset: use the portable bundle to view this file")
        with path.open("rb") as handle:
            raw = handle.read(MAX_TEXT_BYTES + 1)
        if len(raw) > MAX_TEXT_BYTES:
            raise ValueError("File exceeds the 2 MB text limit")
        try:
            original = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("File is not UTF-8 text") from error
        cleaned = redact(original)
        return cleaned, cleaned != original

    def catalog(self, prefix: str = "", offset: int = 0, limit: int = 100) -> dict:
        if not 1 <= limit <= 200 or offset < 0:
            raise ValueError("limit must be 1–200 and offset nonnegative")
        entries = []
        for relative, path in self.paths():
            if not relative.startswith(prefix):
                continue
            stat = path.stat()
            entries.append({"path": relative, "bytes": stat.st_size, "kind": "text" if self.is_text(path) else "asset", "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()})
        return {"files": entries[offset:offset + limit], "total": len(entries), "next_offset": offset + limit if offset + limit < len(entries) else None, "checked_at": now()}

    def read(self, relative: str, offset: int = 0, limit: int = 24_000) -> dict:
        if offset < 0 or not 1 <= limit <= 48_000:
            raise ValueError("offset must be nonnegative and limit must be 1–48000 characters")
        text, redacted = self.text(relative)
        return {"path": relative, "content": text[offset:offset + limit], "offset": offset, "next_offset": offset + limit if offset + limit < len(text) else None, "total_characters": len(text), "sha256": hashlib.sha256(text.encode()).hexdigest(), "redacted": redacted, "read_at": now()}

    def search(self, query: str, limit: int = 30, prefix: str = "") -> dict:
        if not 1 <= len(query.strip()) <= 200 or not 1 <= limit <= 100:
            raise ValueError("query must be 1–200 characters and limit must be 1–100")
        matches, skipped = [], []
        query = query.casefold()
        for relative, path in self.paths():
            if not relative.startswith(prefix) or not self.is_text(path):
                continue
            try:
                text, _ = self.text(relative)
            except ValueError:
                skipped.append(relative)
                continue
            for number, line in enumerate(text.splitlines(), 1):
                index = line.casefold().find(query)
                if index < 0:
                    continue
                if len(matches) == limit:
                    return {"matches": matches, "more_matches": True, "skipped": skipped}
                matches.append({"path": relative, "line": number, "snippet": line[max(0, index - 120):index + 380]})
        return {"matches": matches, "more_matches": False, "skipped": skipped}

    def save_note(self, note_id: str, title: str, content: str, author: str, evidence: str, status: str) -> dict:
        note_id = str(UUID(note_id))
        if status not in {"proposed", "implemented", "verified", "blocked", "handoff"}:
            raise ValueError("Use proposed, implemented, verified, blocked, or handoff")
        fields = {"note_id": note_id, "title": title, "content": content, "author": author, "evidence": evidence, "status": status}
        if any(not isinstance(v, str) or not v.strip() for v in fields.values()):
            raise ValueError("All note fields must be nonempty")
        if len(title) > 200 or len(author) > 200 or len(evidence) > 4000 or len(content) > MAX_NOTE_CHARS:
            raise ValueError("Note field exceeds its size limit")
        fields = {key: redact(value) for key, value in fields.items()}
        directory = self.root / "context" / "notes"
        for parent in (directory.parent, directory):
            if parent.is_symlink():
                raise ValueError("Notes directory cannot be a symbolic link")
            parent.mkdir(exist_ok=True)
        destination = directory / (note_id + ".json")
        if destination.is_symlink():
            raise ValueError("Note cannot be a symbolic link")
        record = {**fields, "saved_at": now(), "verification_notice": "Status and author are caller-provided claims; check linked evidence independently."}
        descriptor, temporary = tempfile.mkstemp(prefix=".note-", dir=directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(record, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, destination)
                created = True
            except FileExistsError:
                previous = json.loads(destination.read_text(encoding="utf-8"))
                if any(previous.get(key) != value for key, value in fields.items()):
                    raise ValueError("This note_id already exists with different content; use a new UUID")
                record, created = previous, False
        finally:
            os.unlink(temporary)
        return {"path": destination.relative_to(self.root).as_posix(), "created": created, "note": record}
