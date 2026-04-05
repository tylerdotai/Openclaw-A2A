"""Tests for openclawa2a.tracing"""

import pytest

from openclawa2a.tracing import (
    build_traceparent,
    clear_current_trace,
    extract_trace_headers,
    get_current_span_id,
    get_current_trace_id,
    inject_trace_headers,
    new_trace_id,
    parse_traceparent,
    set_current_trace,
    setup_tracing,
    get_tracer,
)


class TestTraceId:
    def test_new_trace_id_format(self):
        tid = new_trace_id()
        assert len(tid) == 32
        assert all(c in "0123456789abcdef" for c in tid)

    def test_new_trace_id_unique(self):
        ids = [new_trace_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestTraceparent:
    def test_build_traceparent(self):
        parent = build_traceparent("0af7651916cd43dd8448eb211c80319c", "b7ad6b7169203331")
        assert parent == "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

    def test_build_traceparent_invalid_trace_id(self):
        with pytest.raises(Exception):
            build_traceparent("short", "b7ad6b7169203331")

    def test_build_traceparent_invalid_span_id(self):
        with pytest.raises(Exception):
            build_traceparent("0af7651916cd43dd8448eb211c80319c", "short")

    def test_parse_traceparent(self):
        parsed = parse_traceparent("00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01")
        assert parsed["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
        assert parsed["span_id"] == "b7ad6b7169203331"
        assert parsed["flags"] == "01"

    def test_parse_traceparent_invalid(self):
        with pytest.raises(Exception):
            parse_traceparent("not-valid")


class TestInjectExtract:
    def test_inject_trace_headers(self):
        headers = inject_trace_headers()
        assert "traceparent" in headers
        assert headers["tracestate"] == "openclawa2a=1"

    def test_inject_with_provided_trace_id(self):
        headers = inject_trace_headers("0af7651916cd43dd8448eb211c80319c")
        assert "0af7651916cd43dd8448eb211c80319c" in headers["traceparent"]

    def test_extract_from_headers(self):
        headers = {
            "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
        }
        extracted = extract_trace_headers(headers)
        assert extracted["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
        assert extracted["span_id"] == "b7ad6b7169203331"

    def test_extract_missing(self):
        assert extract_trace_headers({}) == {}
        assert extract_trace_headers({"accept": "application/json"}) == {}


class TestContextVars:
    def test_set_and_get_trace_id(self):
        clear_current_trace()
        set_current_trace("abc123" + "0" * 25)
        assert get_current_trace_id() == "abc123" + "0" * 25
        clear_current_trace()

    def test_clear_trace(self):
        set_current_trace("test" + "0" * 28)
        clear_current_trace()
        assert get_current_trace_id() is None


class TestTracer:
    def test_get_tracer(self):
        tracer = get_tracer()
        assert tracer.name == "openclawa2a"

    def test_start_span(self):
        tracer = get_tracer()
        span = tracer.start_span("test-op", trace_id="abc" + "0" * 29)
        assert span.name == "test-op"
        assert span.trace_id == "abc" + "0" * 29
        assert len(span.span_id) == 16

    def test_span_lifecycle(self):
        tracer = get_tracer()
        span = tracer.start_span("test")
        span.set_tag("key", "value")
        span.set_tags({"a": 1, "b": 2})
        assert span.tags == {"key": "value", "a": 1, "b": 2}
        assert span.end_time is None
        span.end()
        assert span.end_time is not None

    def test_span_to_dict(self):
        tracer = get_tracer()
        span = tracer.start_span("my-op", trace_id="t" * 32)
        span.set_tag("env", "test")
        d = span.to_dict()
        assert d["name"] == "my-op"
        assert d["trace_id"] == "t" * 32
        assert d["service"] == "openclawa2a"
        assert d["tags"] == {"env": "test"}


class TestSetupTracing:
    def test_setup_tracing(self):
        setup_tracing(service_name="my-agent", enabled=True)
        tracer = get_tracer()
        assert tracer.name == "my-agent"
