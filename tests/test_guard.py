import json

from dlp_guard.audit import AuditLog
from dlp_guard.guard import Guard


class FakeDialog:
    def __init__(self, answer: bool):
        self.answer = answer
        self.calls = []

    def confirm(self, c):
        self.calls.append(c)
        return self.answer


def make_guard(tmp_path, answer=True):
    d = FakeDialog(answer)
    return Guard(d, AuditLog(tmp_path / "audit.jsonl")), d


def test_clean_prompt_no_dialog(tmp_path):
    g, d = make_guard(tmp_path)
    r = g.check_prompt("ChatGPT", "hello")
    assert (r.action, r.sensitive) == ("allow", False)
    assert d.calls == []


def test_sensitive_prompt_continue(tmp_path):
    g, d = make_guard(tmp_path, True)
    r = g.check_prompt("ChatGPT", "here is WALLED_SENSITIVE data")
    assert r.action == "allow" and r.reason == "user_continue"
    assert d.calls[0].kind == "prompt"


def test_sensitive_prompt_cancel(tmp_path):
    g, _ = make_guard(tmp_path, False)
    assert g.check_prompt("Perplexity", "WALLED_SENSITIVE").action == "block"


def test_sensitive_file_dialog_shows_name(tmp_path):
    g, d = make_guard(tmp_path, False)
    r = g.check_file("ChatGPT", "secret.txt", b"WALLED_SENSITIVE")
    assert r.action == "block"
    assert (d.calls[0].kind, d.calls[0].name) == ("file", "secret.txt")


def test_audit_has_no_content(tmp_path):
    g, _ = make_guard(tmp_path)
    g.check_prompt("ChatGPT", "WALLED_SENSITIVE super secret body")
    log = (tmp_path / "audit.jsonl").read_text()
    assert "super secret body" not in log
    entry = json.loads(log.splitlines()[0])
    assert set(entry) == {"ts", "site", "kind", "name", "sensitive", "decision"}
