"""Append-only per-run records, exclusive creation, and credential redaction."""
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4


def unique_id(prefix):
    return prefix + "_" + uuid4().hex


class Redactor:
    def __init__(self, secrets=()):
        self._secrets = tuple(sorted((s for s in secrets if isinstance(s, str) and s), key=len, reverse=True))

    def text(self, value):
        for secret in self._secrets:
            value = value.replace(secret, "[REDACTED]")
        return re.sub(r"(?i)bearer\s+[^\s\"',;]+", "Bearer [REDACTED]", value)

    def clean(self, value):
        if isinstance(value, dict):
            return {self.text(str(k)): ("[REDACTED]" if str(k).lower() in
                    ("token", "password", "secret", "credential", "authorization_header", "access_token")
                    else self.clean(v)) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.clean(v) for v in value]
        if isinstance(value, str):
            return self.text(value)
        return value


class MemoryEvidence:
    def __init__(self):
        self.events = []
        self.redactor = Redactor()

    def open(self, run_id, redactor):
        self.run_id = run_id
        self.redactor = redactor

    def emit(self, event):
        self.events.append(self.redactor.clean(event))

    def finish(self, manifest, report):
        self.manifest = self.redactor.clean(manifest)
        self.report = self.redactor.clean(report)


class JsonlEvidence:
    def __init__(self, root):
        self.root = Path(root)

    def open(self, run_id, redactor):
        self.redactor = redactor
        self.root.mkdir(parents=True, exist_ok=True)
        self.directory = self.root / run_id
        self.directory.mkdir()  # UUID collision fails safely, never reuses a run.
        self.events_path = self.directory / "events.jsonl"
        with self.events_path.open("x", encoding="utf-8"):
            pass

    def emit(self, event):
        with self.events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(self.redactor.clean(event), ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()

    def finish(self, manifest, report):
        events = self.events_path.read_bytes()
        manifest = dict(manifest, events_sha256=hashlib.sha256(events).hexdigest(),
                        events_bytes=len(events), hash_scope="first events_bytes bytes; later terminal rejections may append")
        # Manifest is the final materialization marker. A missing Manifest means
        # incomplete evidence, even if a report file was partially written.
        for name, value in (("report.json", report), ("manifest.json", manifest)):
            with (self.directory / name).open("x", encoding="utf-8") as stream:
                json.dump(self.redactor.clean(value), stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
