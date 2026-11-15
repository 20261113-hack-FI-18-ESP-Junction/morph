"""Context boundary and MCP interoperability checks using temporary projects only."""
from __future__ import annotations

import asyncio
import ast
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from starlette.testclient import TestClient
from server import create_server, http_app
from store import ContextStore, MAX_TEXT_BYTES


class ProjectFixture:
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="morph-context-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "project"
        self.root.mkdir()
        self.write("AGENTS.md", "# Fixture project rules\nEnglish documentation.\n")
        self.write("context/START_HERE.md", "# Fixture overview\nGemini task selection is unverified.\n")
        self.write("context/CHAT_CONTEXT.md", "# Fixture chat summary\nOperator selected bounded recovery.\n")
        self.write("context/CONTEXT_MANIFEST.json", '{"coverage":"fixture only"}\n')
        self.store = ContextStore(self.root)

    def write(self, name: str, content: str):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def note(self, **changes):
        return {"note_id": str(uuid4()), "title": "Fixture handoff", "content": "Software test only; physical verification remains pending.", "author": "Test fixture", "evidence": "Temporary test data; no hardware was used.", "status": "handoff", **changes}


class ContextBoundaryTests(ProjectFixture, unittest.TestCase):
    def test_catalog_excludes_private_runtime_and_unapproved_paths(self):
        denied = [".env", ".junction-setup/private.md", "context/.env", "context/.hidden/note.md", "context/credentials.json", "context/private-key.txt", "context/connection.toml", "context/client.key", "context/server.pem", "station/runtime.db", "station/__pycache__/test.py", "station/node_modules/package/index.js", "unrelated/notes.md"]
        for path in denied:
            self.write(path, "private fixture")
        self.write("station/src/main.py", "print('source fixture')\n")
        included = {entry["path"] for entry in self.store.catalog(limit=200)["files"]}
        self.assertIn("station/src/main.py", included)
        for name in denied:
            with self.subTest(path=name):
                self.assertNotIn(name, included)
                with self.assertRaises(ValueError):
                    self.store.read(name)

    def test_traversal_absolute_and_noncanonical_paths_fail(self):
        for path in ["../AGENTS.md", str(self.root / "AGENTS.md"), "context/../AGENTS.md", "context\\START_HERE.md", "context//START_HERE.md", "./AGENTS.md", "context/./START_HERE.md", "context/START_HERE.md\x00", "", "context"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.store.read(path)

    def test_symlinks_are_excluded_and_cannot_be_read(self):
        outside = Path(self.temporary.name) / "outside.md"
        outside.write_text("private outside fixture", encoding="utf-8")
        (self.root / "context" / "linked.md").symlink_to(outside)
        (self.root / "context" / "linked-dir").symlink_to(outside.parent, target_is_directory=True)
        for name in ["context/linked.md", "context/linked-dir/outside.md"]:
            with self.assertRaises(ValueError):
                self.store.read(name)
        self.assertFalse(any("linked" in name for name, _ in self.store.paths()))

    def test_reads_are_fresh_and_character_pages_reconstruct_unicode(self):
        original = "Inspect č and å. " * 21
        path = self.write("context/read.md", original)
        parts, offset = [], 0
        while True:
            page = self.store.read("context/read.md", offset, 11)
            parts.append(page["content"])
            offset = page["next_offset"]
            if offset is None:
                break
        self.assertEqual("".join(parts), original)
        previous_hash = page["sha256"]
        path.write_text("Updated after server construction.", encoding="utf-8")
        current = self.store.read("context/read.md")
        self.assertNotEqual(current["sha256"], previous_hash)
        self.assertEqual(current["content"], "Updated after server construction.")
        self.assertTrue(current["read_at"].endswith("+00:00"))

    def test_catalog_pagination_has_no_duplicates(self):
        for index in range(9):
            self.write(f"context/page-{index}.md", "fixture")
        pages, offset = [], 0
        while True:
            result = self.store.catalog(offset=offset, limit=3)
            pages.extend(file["path"] for file in result["files"])
            offset = result["next_offset"]
            if offset is None:
                break
        self.assertEqual(len(pages), result["total"])
        self.assertEqual(len(pages), len(set(pages)))

    def test_binary_and_oversized_inputs_are_explicit(self):
        self.write("context/large.md", "x" * (MAX_TEXT_BYTES + 1))
        asset = self.root / "context" / "camera.png"
        asset.write_bytes(b"\x89PNG\r\n\x1a\n")
        for name in ["context/large.md", "context/camera.png"]:
            with self.assertRaises(ValueError):
                self.store.read(name)
        result = self.store.search("fixture")
        self.assertIn("context/large.md", result["skipped"])
        for call in [lambda: self.store.read("AGENTS.md", -1), lambda: self.store.read("AGENTS.md", limit=48001), lambda: self.store.catalog(limit=201), lambda: self.store.search(""), lambda: self.store.search("fixture", limit=0)]:
            with self.assertRaises(ValueError):
                call()

    def test_search_is_literal_bounded_case_insensitive_and_fresh(self):
        self.write("context/search.md", "Choice: GEMINI [task].\nChoice: Gemini [task].\n")
        first = self.store.search("gemini [task]", limit=1, prefix="context/search")
        self.assertEqual(len(first["matches"]), 1)
        self.assertTrue(first["more_matches"])
        self.assertEqual(first["matches"][0]["line"], 1)
        self.write("context/search.md", "Choice: Nemotron [task].\n")
        self.assertEqual(self.store.search("gemini [task]", prefix="context/search")["matches"], [])

    def test_common_key_formats_are_redacted_from_reads_search_and_notes(self):
        fake_key = "sk-proj-" + "a" * 32
        fake_bearer = "fixture-bearer-value-with-enough-characters"
        fake_password = "not-a-real-password-value"
        source = f'API_KEY="{fake_key}"\nAuthorization: Bearer {fake_bearer}\npassword = "{fake_password}"\n'
        self.write("context/provider.md", source)
        result = self.store.read("context/provider.md")
        self.assertTrue(result["redacted"])
        for value in (fake_key, fake_bearer, fake_password):
            self.assertNotIn(value, result["content"])
            self.assertEqual(self.store.search(value)["matches"], [])
        saved = self.store.save_note(**self.note(content=source))
        raw = (self.root / saved["path"]).read_text(encoding="utf-8")
        for value in (fake_key, fake_bearer, fake_password):
            self.assertNotIn(value, raw)

    def test_unquoted_opaque_keys_are_redacted_and_quoted_source_stays_valid(self):
        fake_key = "0123456789abcdef0123456789abcdef"
        self.write("context/pasted.md", f"ELEVENLABS_API_KEY={fake_key}\nMORPH_CONTEXT_TOKEN={fake_key}\npassword: {fake_key}\n")
        result = self.store.read("context/pasted.md")
        self.assertTrue(result["redacted"])
        self.assertNotIn(fake_key, result["content"])
        self.write("station/fixture.py", 'settings = {"password": "example-placeholder-password"}\n')
        source = self.store.read("station/fixture.py")["content"]
        ast.parse(source)
        self.assertEqual(ast.literal_eval(source.split("=", 1)[1]), {"password": "[REDACTED]"})
        self.write("context/fixture.json", '{"password":"example-placeholder-password"}')
        self.assertEqual(json.loads(self.store.read("context/fixture.json")["content"]), {"password": "[REDACTED]"})

    def test_notes_are_idempotent_and_conflicts_preserve_the_original(self):
        note = self.note()
        first = self.store.save_note(**note)
        repeat = self.store.save_note(**note)
        self.assertTrue(first["created"])
        self.assertFalse(repeat["created"])
        self.assertEqual(first["note"], repeat["note"])
        with self.assertRaises(ValueError):
            self.store.save_note(**{**note, "content": "Changed content must use a new UUID."})
        self.assertEqual(json.loads((self.root / first["path"]).read_text()), first["note"])

    def test_concurrent_retries_produce_one_complete_note(self):
        note = self.note()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.store.save_note(**note), range(16)))
        self.assertEqual(sum(result["created"] for result in results), 1)
        self.assertEqual(len(list((self.root / "context" / "notes").glob("*.json"))), 1)
        self.assertEqual(len({result["note"]["saved_at"] for result in results}), 1)
        self.assertFalse(list((self.root / "context" / "notes").glob(".note-*")))

    def test_notes_cannot_follow_directory_or_destination_symlinks(self):
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        notes = self.root / "context" / "notes"
        notes.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.store.save_note(**self.note())
        notes.unlink()
        notes.mkdir()
        note = self.note()
        victim = outside / "victim.json"
        victim.write_text('{"fixture":"unchanged"}')
        (notes / (note["note_id"] + ".json")).symlink_to(victim)
        with self.assertRaises(ValueError):
            self.store.save_note(**note)
        self.assertEqual(victim.read_text(), '{"fixture":"unchanged"}')


class MCPIntegrationTests(ProjectFixture, unittest.TestCase):
    def test_wifi_cli_refuses_plaintext_before_reading_credentials(self):
        result = subprocess.run([sys.executable, str(SOURCE / "server.py"), "--root", str(self.root), "--transport", "http", "--host", "192.0.2.10", "--token-file", str(self.root / "nonexistent-token")], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Wi-Fi sharing requires TLS", result.stderr)
        self.assertNotIn("FileNotFoundError", result.stderr)

    def test_real_stdio_client_can_discover_read_search_and_save(self):
        async def exercise():
            params = StdioServerParameters(command=sys.executable, args=[str(SOURCE / "server.py"), "--root", str(self.root)])
            async with Client(params, read_timeout_seconds=15) as client:
                tools = {tool.name: tool for tool in (await client.list_tools()).tools}
                self.assertEqual(set(tools), {"get_project_context", "list_context", "read_context", "search_context", "save_handoff"})
                self.assertTrue(tools["read_context"].annotations.read_only_hint)
                self.assertFalse(tools["save_handoff"].annotations.read_only_hint)
                context = await client.call_tool("get_project_context")
                self.assertFalse(context.is_error)
                self.assertIn("Fixture overview", context.structured_content["overview"]["content"])
                read = await client.call_tool("read_context", {"path": "AGENTS.md"})
                self.assertIn("Fixture project rules", read.structured_content["content"])
                blocked = await client.call_tool("read_context", {"path": "../AGENTS.md"})
                self.assertTrue(blocked.is_error)
                search = await client.call_tool("search_context", {"query": "Gemini"})
                self.assertEqual(search.structured_content["matches"][0]["path"], "context/START_HERE.md")
                resources = await client.list_resources()
                self.assertEqual({str(resource.uri) for resource in resources.resources}, {"morph://context/start", "morph://context/chats"})
                resource = await client.read_resource("morph://context/chats")
                self.assertIn("bounded recovery", resource.contents[0].text)
                prompt = await client.get_prompt("resume_morph")
                self.assertIn("AGENTS.md", prompt.messages[0].content.text)
                note = self.note()
                first = await client.call_tool("save_handoff", note)
                second = await client.call_tool("save_handoff", note)
                self.assertTrue(first.structured_content["created"])
                self.assertFalse(second.structured_content["created"])
                saved = await client.call_tool("read_context", {"path": first.structured_content["path"]})
                self.assertIn("physical verification remains pending", saved.structured_content["content"])
        asyncio.run(exercise())

    def test_http_auth_host_origin_and_real_rpc(self):
        token = "fixture-only-" + "x" * 40
        app = http_app(create_server(self.root), token, "127.0.0.1", 8765)
        message = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "fixture", "version": "1"}}}
        headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
        with TestClient(app, base_url="http://127.0.0.1:8765") as client:
            for supplied in ({}, {"Authorization": "Bearer wrong-fixture-token"}):
                result = client.post("/mcp", json=message, headers=supplied)
                self.assertEqual(result.status_code, 401)
                self.assertNotIn(token, result.text)
            wrong_host = client.post("/mcp", json=message, headers={**headers, "Host": "attacker.invalid:8765"})
            self.assertEqual(wrong_host.status_code, 421)
            wrong_origin = client.post("/mcp", json=message, headers={**headers, "Origin": "https://attacker.invalid"})
            self.assertEqual(wrong_origin.status_code, 403)
            initialized = client.post("/mcp", json=message, headers=headers)
            self.assertEqual(initialized.status_code, 200)
            self.assertEqual(initialized.json()["result"]["serverInfo"]["name"], "morph-context")
            listed = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=headers)
            self.assertEqual(listed.status_code, 200)
            self.assertIn("read_context", {tool["name"] for tool in listed.json()["result"]["tools"]})
            read = client.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "read_context", "arguments": {"path": "AGENTS.md"}}}, headers=headers)
            self.assertEqual(read.status_code, 200)
            self.assertIn("Fixture project rules", read.json()["result"]["structuredContent"]["content"])
            oversized = client.post("/mcp", content="x" * 128_001, headers={**headers, "Content-Type": "application/json"})
            self.assertEqual(oversized.status_code, 413)


if __name__ == "__main__":
    unittest.main()
