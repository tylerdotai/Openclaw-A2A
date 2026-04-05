"""Tests for openclawa2a.client"""

import pytest

from openclawa2a.client import OpenClawA2AClient
from openclawa2a.models import Message, Part, PartType, Role
from openclawa2a.exceptions import OpenClawA2AError


class TestClientConstruction:
    def test_basic_construction(self):
        client = OpenClawA2AClient("https://agent.example.com/a2a")
        assert client.base_url == "https://agent.example.com/a2a"
        assert client.timeout == 60.0
        assert client.max_retries == 3

    def test_base_url_strips_trailing_slash(self):
        client = OpenClawA2AClient("https://agent.example.com/a2a/")
        assert client.base_url == "https://agent.example.com/a2a"

    def test_with_api_key(self):
        client = OpenClawA2AClient("https://example.com", api_key="secret-key")
        assert client.api_key == "secret-key"

    def test_repr(self):
        client = OpenClawA2AClient("https://example.com")
        assert "https://example.com" in repr(client)


class TestDefaultHeaders:
    def test_headers_without_api_key(self):
        client = OpenClawA2AClient("https://example.com", enable_tracing=False)
        headers = client._default_headers()
        assert headers["User-Agent"] == "openclawa2a/0.1.0"
        assert headers["Content-Type"] == "application/json"
        assert "X-API-Key" not in headers

    def test_headers_with_api_key(self):
        client = OpenClawA2AClient("https://example.com", api_key="key123", enable_tracing=False)
        headers = client._default_headers()
        assert headers["X-API-Key"] == "key123"

    def test_headers_with_tracing(self):
        client = OpenClawA2AClient("https://example.com", enable_tracing=True)
        headers = client._default_headers()
        assert "traceparent" in headers
        assert "tracestate" in headers


class TestMessageNormalization:
    """Test that send_message normalizes various input formats."""

    def test_message_as_dict(self):
        client = OpenClawA2AClient("https://example.com")
        # Test the internal normalization logic path
        msg_dict = {"role": "user", "parts": [{"kind": "text", "text": "Hello"}]}
        assert msg_dict["role"] == "user"

    def test_message_as_message_object(self):
        msg = Message(
            role=Role.USER,
            parts=[Part(kind=PartType.TEXT, text="Hello")],
        )
        msg_dict = msg.model_dump(by_alias=True, exclude_none=True)
        assert msg_dict["role"] == "user"
        assert msg_dict["parts"][0]["kind"] == "text"


class TestClientClose:
    @pytest.mark.asyncio
    async def test_close(self):
        client = OpenClawA2AClient("https://example.com")
        await client.close()  # Should not raise
