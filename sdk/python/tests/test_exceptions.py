"""Tests for openclawa2a.exceptions"""

import pytest

from openclawa2a.exceptions import (
    APIKeyError,
    AuditError,
    AuthError,
    ConnectionError,
    InvalidRequestError,
    OpenClawA2AError,
    ServerError,
    StreamingError,
    TaskCanceledError,
    TaskNotFoundError,
    TaskStateError,
    TimeoutError,
    TraceError,
)


class TestOpenClawA2AError:
    def test_basic_error(self):
        err = OpenClawA2AError("Something went wrong")
        assert err.message == "Something went wrong"
        assert err.code == "A2A_ERROR"
        assert err.details == {}

    def test_with_code_and_details(self):
        err = OpenClawA2AError("Boom", code="BOOM", details={"key": "val"})
        assert err.code == "BOOM"
        assert err.details == {"key": "val"}

    def test_with_cause(self):
        cause = ValueError("original")
        err = OpenClawA2AError("wrapper", cause=cause)
        assert err.cause is cause

    def test_to_dict(self):
        err = OpenClawA2AError("test", code="TEST", details={"a": 1})
        d = err.to_dict()
        assert d["code"] == "TEST"
        assert d["message"] == "test"
        assert d["details"] == {"a": 1}
        assert d["type"] == "OpenClawA2AError"

    def test_repr(self):
        err = OpenClawA2AError("msg", code="C")
        assert repr(err) == "OpenClawA2AError(code='C', message='msg')"

    def test_is_exception(self):
        assert isinstance(OpenClawA2AError("x"), Exception)


class TestTransportErrors:
    def test_connection_error(self):
        err = ConnectionError("can't connect")
        assert err.code == "CONNECTION_ERROR"
        assert "can't connect" in str(err)

    def test_timeout_error(self):
        err = TimeoutError("timed out")
        assert err.code == "TIMEOUT"

    def test_streaming_error(self):
        err = StreamingError("stream broke")
        assert err.code == "STREAMING_ERROR"


class TestAuthErrors:
    def test_auth_error(self):
        err = AuthError("bad token")
        assert err.code == "AUTH_ERROR"

    def test_api_key_error(self):
        err = APIKeyError("missing key")
        assert err.code == "API_KEY_ERROR"


class TestTaskErrors:
    def test_task_not_found(self):
        err = TaskNotFoundError("task-abc")
        assert err.task_id == "task-abc"
        assert "task-abc" in str(err)
        assert err.code == "TASK_NOT_FOUND"
        assert err.details["task_id"] == "task-abc"

    def test_task_canceled(self):
        err = TaskCanceledError("task-123")
        assert err.task_id == "task-123"
        assert err.code == "TASK_CANCELED"


class TestServerErrors:
    def test_server_error(self):
        err = ServerError(500, "Internal error")
        assert err.status_code == 500
        assert err.code == "SERVER_ERROR"

    def test_invalid_request_error(self):
        err = InvalidRequestError("missing field", details={"field": "name"})
        assert err.status_code == 400
        assert err.code == "INVALID_REQUEST"
        assert err.details["field"] == "name"
