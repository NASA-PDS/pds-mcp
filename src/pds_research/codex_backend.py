from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .model_backends import ModelUsage, StructuredModelResult, strict_json_schema


class CodexCliBackend:
    """Development-only structured backend using local Codex authentication.

    It runs from an empty temporary directory so the model cannot inspect the
    benchmark or reference plans. It is intentionally capped and must not be
    used as a confirmatory experiment backend.
    """

    def __init__(self, *, model: str, max_requests: int = 3, timeout_seconds: int = 180) -> None:
        if not 1 <= max_requests <= 3:
            raise ValueError("Codex smoke runs are hard-capped at three requests")
        self.model = model
        self.max_requests = max_requests
        self.timeout_seconds = timeout_seconds
        self.requests_made = 0

    def generate_structured(
        self,
        *,
        instructions: str,
        input_text: str,
        schema_name: str,
        schema: dict[str, Any],
        max_output_tokens: int = 1200,
        seed: int | None = None,
    ) -> StructuredModelResult:
        del schema_name, max_output_tokens, seed
        if self.requests_made >= self.max_requests:
            raise RuntimeError("Codex smoke request ceiling reached")
        self.requests_made += 1
        with tempfile.TemporaryDirectory(prefix="pds-codex-smoke-") as directory:
            root = Path(directory)
            schema_path = root / "schema.json"
            output_path = root / "output.json"
            schema_path.write_text(json.dumps(strict_json_schema(schema)))
            prompt = (
                "You are a schema-constrained PDS query planner. Do not use tools, files, "
                "the web, or prior benchmark knowledge.\n\n"
                + instructions
                + "\n\nINPUT:\n"
                + input_text
            )
            command = [
                "codex", "exec", "--ephemeral", "--ignore-user-config",
                "--skip-git-repo-check", "--sandbox", "read-only",
                "--model", self.model, "--output-schema", str(schema_path),
                "--output-last-message", str(output_path), "-C", str(root), prompt,
            ]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            if completed.returncode:
                detail = "\n".join(completed.stderr.strip().splitlines()[-12:])
                raise RuntimeError(f"codex exec failed:\n{detail or 'unknown error'}")
            value = json.loads(output_path.read_text())
        return StructuredModelResult(
            value=value,
            response_id="codex-cli-development-smoke",
            model=self.model,
            # The CLI does not expose stable per-call token accounting through
            # output-last-message; formal cost metrics require the API backend.
            usage=ModelUsage(0, 0, 0.0),
            raw_status="completed",
        )
