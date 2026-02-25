"""
Unit Tests for LLM Provider Failover System

Tests the UnifiedLLMClient, provider adapters, circuit breaker integration,
and failover behavior.
"""

import os
import sys
import time
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.circuit_breaker import CircuitBreaker, CircuitOpenError
from services.llm_provider import (
    ClaudeProvider,
    LLMResponse,
    Message,
    OllamaProvider,
    OpenAIProvider,
    ProviderConfig,
    ProviderType,
    UnifiedLLMClient,
    Usage,
)


class TestProviderConfig(unittest.TestCase):
    """Test provider configuration."""

    def test_default_config(self):
        """Test default provider configuration."""
        config = ProviderConfig()
        self.assertTrue(config.enabled)
        self.assertEqual(config.timeout, 120.0)
        self.assertEqual(config.max_retries, 3)
        self.assertIsNotNone(config.circuit_breaker)

    def test_cost_tracking(self):
        """Test cost tracking fields."""
        config = ProviderConfig(cost_per_1k_prompt=0.003, cost_per_1k_completion=0.015)
        self.assertEqual(config.cost_per_1k_prompt, 0.003)
        self.assertEqual(config.cost_per_1k_completion, 0.015)


class TestLLMResponse(unittest.TestCase):
    """Test LLM response normalization."""

    def test_response_creation(self):
        """Test creating LLM response."""
        usage = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        response = LLMResponse(
            id="test-123",
            content=[{"type": "text", "text": "Hello!"}],
            model="test-model",
            usage=usage,
            provider="claude",
            cost=0.002,
            latency=1.5,
        )

        self.assertEqual(response.id, "test-123")
        self.assertEqual(response.provider, "claude")
        self.assertEqual(response.cost, 0.002)
        self.assertEqual(response.latency, 1.5)

    def test_response_to_dict(self):
        """Test converting response to dictionary."""
        usage = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        response = LLMResponse(id="test-123", usage=usage, provider="openai")

        data = response.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["id"], "test-123")
        self.assertEqual(data["provider"], "openai")
        self.assertIn("usage", data)


class TestClaudeProvider(unittest.TestCase):
    """Test Claude provider adapter."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset circuit breaker
        CircuitBreaker.remove("llm-claude")

    @unittest.skipIf(
        not hasattr(sys.modules.get("anthropic", object()), "Anthropic"),
        "anthropic package not installed",
    )
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    @patch("anthropic.Anthropic")
    def test_claude_completion(self, mock_anthropic):
        """Test Claude completion."""
        # Mock Anthropic response
        mock_response = MagicMock()
        mock_response.id = "msg_123"
        mock_response.content = [{"type": "text", "text": "Hello, world!"}]
        mock_response.model = "claude-sonnet-4-5"
        mock_response.stop_reason = "end_turn"
        mock_response.stop_sequence = None
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        # Test provider
        config = ProviderConfig(
            api_key="test-key",
            model="claude-sonnet-4-5",
            cost_per_1k_prompt=0.003,
            cost_per_1k_completion=0.015,
        )
        provider = ClaudeProvider(config)

        messages = [{"role": "user", "content": "Hello!"}]
        response = provider.create_completion(messages)

        # Verify response
        self.assertEqual(response.id, "msg_123")
        self.assertEqual(response.provider, "claude")
        self.assertGreater(response.cost, 0)
        self.assertGreater(response.latency, 0)
        self.assertEqual(response.usage.prompt_tokens, 10)
        self.assertEqual(response.usage.completion_tokens, 5)

    def test_claude_circuit_breaker_open(self):
        """Test Claude provider with circuit breaker open."""
        config = ProviderConfig()
        provider = ClaudeProvider(config)

        # Force circuit open
        provider.circuit.force_open(duration=60)

        messages = [{"role": "user", "content": "Hello!"}]

        with self.assertRaises(CircuitOpenError):
            provider.create_completion(messages)


class TestOllamaProvider(unittest.TestCase):
    """Test Ollama provider adapter."""

    def setUp(self):
        """Set up test fixtures."""
        CircuitBreaker.remove("llm-ollama")

    @patch("requests.post")
    def test_ollama_completion(self, mock_post):
        """Test Ollama completion."""
        # Mock Ollama response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Hello from Ollama!"},
            "done_reason": "stop",
        }
        mock_post.return_value = mock_response

        # Test provider
        config = ProviderConfig(endpoint="http://localhost:11434", model="llama3.2")
        provider = OllamaProvider(config)

        messages = [{"role": "user", "content": "Hello!"}]
        response = provider.create_completion(messages)

        # Verify response
        self.assertEqual(response.provider, "ollama")
        self.assertEqual(response.cost, 0.0)  # Ollama is free
        self.assertGreater(response.latency, 0)
        self.assertIn("text", response.content[0])

    def test_ollama_token_counting(self):
        """Test Ollama token counting (approximate)."""
        config = ProviderConfig()
        provider = OllamaProvider(config)

        text = "This is a test message with several words."
        tokens = provider.count_tokens(text)

        # Approximate: ~4 chars per token
        expected_tokens = len(text) // 4
        self.assertAlmostEqual(tokens, expected_tokens, delta=2)


class TestOpenAIProvider(unittest.TestCase):
    """Test OpenAI provider adapter."""

    def setUp(self):
        """Set up test fixtures."""
        CircuitBreaker.remove("llm-openai")

    @unittest.skipIf(
        not hasattr(sys.modules.get("openai", object()), "OpenAI"), "openai package not installed"
    )
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("openai.OpenAI")
    def test_openai_completion(self, mock_openai_class):
        """Test OpenAI completion."""
        # Mock OpenAI response
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello from GPT-4!"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.id = "chatcmpl-123"
        mock_response.model = "gpt-4-turbo"
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # Test provider
        config = ProviderConfig(
            api_key="test-key",
            model="gpt-4-turbo",
            cost_per_1k_prompt=0.01,
            cost_per_1k_completion=0.03,
        )
        provider = OpenAIProvider(config)

        messages = [{"role": "user", "content": "Hello!"}]
        response = provider.create_completion(messages)

        # Verify response
        self.assertEqual(response.id, "chatcmpl-123")
        self.assertEqual(response.provider, "openai")
        self.assertGreater(response.cost, 0)
        self.assertEqual(response.usage.total_tokens, 15)


class TestUnifiedLLMClient(unittest.TestCase):
    """Test unified LLM client with failover."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset all circuit breakers
        CircuitBreaker.reset_all()

    @patch.dict(os.environ, {"LLM_FAILOVER_ENABLED": "true"})
    def test_client_initialization(self):
        """Test client initialization."""
        client = UnifiedLLMClient()

        self.assertTrue(client.failover_enabled)
        self.assertIn("claude", client.providers)
        self.assertIn("ollama", client.providers)
        self.assertIn("openai", client.providers)
        self.assertEqual(len(client.failover_order), 3)

    @patch.dict(os.environ, {"LLM_FAILOVER_ENABLED": "false"})
    def test_failover_disabled(self):
        """Test with failover disabled."""
        client = UnifiedLLMClient()
        self.assertFalse(client.failover_enabled)

    @patch("services.llm_provider.ClaudeProvider.create_completion")
    def test_successful_completion(self, mock_create):
        """Test successful completion with primary provider."""
        # Mock Claude response
        mock_response = LLMResponse(
            id="msg_123",
            content=[{"type": "text", "text": "Success!"}],
            model="claude-sonnet-4-5",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="claude",
            cost=0.001,
            latency=1.0,
        )
        mock_create.return_value = mock_response

        client = UnifiedLLMClient()
        messages = [{"role": "user", "content": "Hello!"}]

        response = client.create_completion(messages)

        self.assertEqual(response.provider, "claude")
        self.assertEqual(client.successful_requests, 1)
        self.assertEqual(client.failover_count, 0)

    @patch("services.llm_provider.ClaudeProvider.create_completion")
    @patch("services.llm_provider.OllamaProvider.create_completion")
    def test_failover_to_ollama(self, mock_ollama, mock_claude):
        """Test failover from Claude to Ollama."""
        # Claude fails
        mock_claude.side_effect = Exception("Claude API error")

        # Ollama succeeds
        mock_ollama.return_value = LLMResponse(
            id="ollama-123",
            content=[{"type": "text", "text": "Ollama response"}],
            model="llama3.2",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="ollama",
            cost=0.0,
            latency=0.5,
        )

        client = UnifiedLLMClient()
        messages = [{"role": "user", "content": "Hello!"}]

        response = client.create_completion(messages)

        self.assertEqual(response.provider, "ollama")
        self.assertEqual(client.failover_count, 1)
        self.assertEqual(client.successful_requests, 1)

    @patch("services.llm_provider.ClaudeProvider.create_completion")
    @patch("services.llm_provider.OllamaProvider.create_completion")
    @patch("services.llm_provider.OpenAIProvider.create_completion")
    def test_failover_to_openai(self, mock_openai, mock_ollama, mock_claude):
        """Test failover all the way to OpenAI."""
        # Claude and Ollama fail
        mock_claude.side_effect = Exception("Claude error")
        mock_ollama.side_effect = Exception("Ollama error")

        # OpenAI succeeds
        mock_openai.return_value = LLMResponse(
            id="gpt-123",
            content=[{"type": "text", "text": "GPT-4 response"}],
            model="gpt-4-turbo",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="openai",
            cost=0.0015,
            latency=2.0,
        )

        client = UnifiedLLMClient()
        messages = [{"role": "user", "content": "Hello!"}]

        response = client.create_completion(messages)

        self.assertEqual(response.provider, "openai")
        self.assertEqual(client.failover_count, 1)

    @patch("services.llm_provider.ClaudeProvider.create_completion")
    @patch("services.llm_provider.OllamaProvider.create_completion")
    @patch("services.llm_provider.OpenAIProvider.create_completion")
    def test_all_providers_fail(self, mock_openai, mock_ollama, mock_claude):
        """Test when all providers fail."""
        # All providers fail
        mock_claude.side_effect = Exception("Claude error")
        mock_ollama.side_effect = Exception("Ollama error")
        mock_openai.side_effect = Exception("OpenAI error")

        client = UnifiedLLMClient()
        messages = [{"role": "user", "content": "Hello!"}]

        with self.assertRaises(RuntimeError) as context:
            client.create_completion(messages)

        self.assertIn("All providers failed", str(context.exception))
        self.assertEqual(client.failed_requests, 1)

    def test_circuit_breaker_skip(self):
        """Test that open circuits are skipped during failover."""
        client = UnifiedLLMClient()

        # Open Claude circuit
        client.providers["claude"].circuit.force_open(duration=60)

        # Verify circuit is open
        self.assertTrue(client.providers["claude"].circuit.is_open)

    def test_messages_api_compatibility(self):
        """Test drop-in replacement for anthropic.messages.create()."""
        client = UnifiedLLMClient()

        # Verify messages API exists
        self.assertIsNotNone(client.messages)
        self.assertTrue(hasattr(client.messages, "create"))

    def test_metrics_tracking(self):
        """Test metrics collection."""
        client = UnifiedLLMClient()

        metrics = client.get_metrics()

        self.assertIn("total_requests", metrics)
        self.assertIn("successful_requests", metrics)
        self.assertIn("failed_requests", metrics)
        self.assertIn("failover_count", metrics)
        self.assertIn("total_cost", metrics)
        self.assertIn("providers", metrics)

    def test_circuit_status(self):
        """Test getting circuit breaker status."""
        client = UnifiedLLMClient()

        status = client.get_circuit_status()

        self.assertIn("claude", status)
        self.assertIn("ollama", status)
        self.assertIn("openai", status)

        for provider_status in status.values():
            self.assertIn("state", provider_status)
            self.assertIn("metrics", provider_status)


class TestCostCalculation(unittest.TestCase):
    """Test cost calculation accuracy."""

    def test_claude_cost(self):
        """Test Claude cost calculation."""
        config = ProviderConfig(cost_per_1k_prompt=0.003, cost_per_1k_completion=0.015)
        provider = ClaudeProvider(config)

        usage = Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)

        cost = provider.calculate_cost(usage)

        # (1000/1000 * 0.003) + (500/1000 * 0.015) = 0.003 + 0.0075 = 0.0105
        self.assertAlmostEqual(cost, 0.0105, places=4)

    def test_ollama_cost_is_zero(self):
        """Test that Ollama cost is always zero."""
        config = ProviderConfig()
        provider = OllamaProvider(config)

        usage = Usage(prompt_tokens=10000, completion_tokens=5000, total_tokens=15000)

        cost = provider.calculate_cost(usage)
        self.assertEqual(cost, 0.0)


class TestFailoverScenarios(unittest.TestCase):
    """Test various failover scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        CircuitBreaker.reset_all()

    @patch("services.llm_provider.ClaudeProvider.create_completion")
    @patch("services.llm_provider.OllamaProvider.create_completion")
    @patch("services.llm_provider.OpenAIProvider.create_completion")
    def test_timeout_failover(self, mock_openai, mock_ollama, mock_claude):
        """Test failover on timeout."""
        # All providers timeout
        mock_claude.side_effect = TimeoutError("Request timed out")
        mock_ollama.side_effect = TimeoutError("Request timed out")
        mock_openai.side_effect = TimeoutError("Request timed out")

        client = UnifiedLLMClient()
        messages = [{"role": "user", "content": "Hello!"}]

        # Should fail when all providers timeout
        with self.assertRaises(RuntimeError):
            client.create_completion(messages)

    def test_circuit_breaker_integration(self):
        """Test circuit breaker integration."""
        config = ProviderConfig()
        provider = ClaudeProvider(config)

        # Record failures to open circuit
        for _ in range(5):
            provider.circuit.record_failure(Exception("Test error"))

        # Circuit should be open
        self.assertTrue(provider.circuit.is_open)

        # Request should be rejected
        messages = [{"role": "user", "content": "Hello!"}]
        with self.assertRaises(CircuitOpenError):
            provider.create_completion(messages)


class TestProviderPriority(unittest.TestCase):
    """Test provider priority and ordering."""

    @patch.dict(os.environ, {"LLM_DEFAULT_PROVIDER": "ollama"})
    def test_custom_failover_order(self):
        """Test custom failover order."""
        client = UnifiedLLMClient()

        # Ollama should be first
        self.assertEqual(client.failover_order[0], "ollama")

    @patch.dict(os.environ, {"LLM_DEFAULT_PROVIDER": "openai"})
    def test_openai_primary(self):
        """Test OpenAI as primary."""
        client = UnifiedLLMClient()

        self.assertEqual(client.failover_order[0], "openai")


if __name__ == "__main__":
    unittest.main()
