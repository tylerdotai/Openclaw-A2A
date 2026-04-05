"""Tests for openclawa2a.audit"""

import json
import tempfile
from pathlib import Path

import pytest

from openclawa2a.audit import (
    AuditLogger,
    AuditOperation,
    _AuditSpan,
    configure_audit_logger,
    get_audit_logger,
)
from openclawa2a.tracing import new_trace_id


class TestAuditLogger:
    def test_log_writes_to_stdout(self, capsys):
        logger = AuditLogger(output_path=None)
        trace_id = logger.log("test_op", status="success")
        assert len(trace_id) == 32
        captured = capsys.readouterr()
        assert "AUDIT" in captured.out

    def test_log_writes_to_file(self):
        with tempfile.NamedTemporaryFile(suffix=".ndjson", delete=False) as f:
            path = Path(f.name)

        try:
            logger = AuditLogger(output_path=path)
            trace_id = new_trace_id()
            logger.log("send_message", trace_id=trace_id, task_id="task-1", status="success")

            lines = path.read_text().splitlines()
            assert len(lines) == 1

            entry = json.loads(lines[0])
            assert entry["trace_id"] == trace_id
            assert entry["operation"] == "send_message"
            assert entry["task_id"] == "task-1"
            assert entry["status"] == "success"
            assert entry["version"] == "1"
            assert "_immutable" in entry
        finally:
            path.unlink(missing_ok=True)

    def test_redact(self):
        logger = AuditLogger(redact_keys=["api_key", "password"])
        result = logger._redact({"api_key": "secret", "password": "123", "name": "ok"})
        assert result["api_key"] == "[REDACTED]"
        assert result["password"] == "[REDACTED]"
        assert result["name"] == "ok"

    def test_log_error(self):
        with tempfile.NamedTemporaryFile(suffix=".ndjson", delete=False) as f:
            path = Path(f.name)
        try:
            logger = AuditLogger(output_path=path)
            logger.log("send_message", status="failure", error={"code": "TIMEOUT", "message": "took too long"})

            entry = json.loads(path.read_text().splitlines()[0])
            assert entry["status"] == "failure"
            assert entry["error"]["code"] == "TIMEOUT"
        finally:
            path.unlink(missing_ok=True)

    def test_global_logger(self):
        configure_audit_logger(output_path=None, service_name="test-global")
        gl = get_audit_logger()
        assert gl.service_name == "test-global"


class TestAuditSpan:
    def test_span_context_manager_success(self, capsys):
        logger = AuditLogger(output_path=None)
        with logger.trace("send_message", task_id="t1") as span:
            span.success(result_id="r1")

        captured = capsys.readouterr().out
        entries = [json.loads(l.split("AUDIT ", 1)[1]) for l in captured.splitlines() if "AUDIT" in l]
        assert len(entries) == 2
        assert entries[0]["status"] == "started"
        assert entries[1]["status"] == "success"
        assert entries[1]["metadata"]["result_id"] == "r1"

    def test_span_context_manager_failure(self, capsys):
        logger = AuditLogger(output_path=None)
        with logger.trace("send_message", task_id="t1") as span:
            span.failure(error_code="ERR", error_message="something broke")

        captured = capsys.readouterr().out
        entries = [json.loads(l.split("AUDIT ", 1)[1]) for l in captured.splitlines() if "AUDIT" in l]
        assert entries[1]["status"] == "failure"
        assert entries[1]["error"]["code"] == "ERR"

    def test_span_exit_with_exception(self, capsys):
        logger = AuditLogger(output_path=None)
        try:
            with logger.trace("send_message"):
                raise ValueError("boom")
        except ValueError:
            pass

        captured = capsys.readouterr().out
        entries = [json.loads(l.split("AUDIT ", 1)[1]) for l in captured.splitlines() if "AUDIT" in l]
        # Should have started + failure from __exit__
        statuses = [e["status"] for e in entries]
        assert "failure" in statuses


class TestAuditOperation:
    def test_operation_values(self):
        assert AuditOperation.SEND_MESSAGE.value == "send_message"
        assert AuditOperation.GET_TASK.value == "get_task"
        assert AuditOperation.TASK_COMPLETED.value == "task_completed"
