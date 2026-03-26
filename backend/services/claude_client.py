"""Anthropic Claude API wrapper with retry, cost tracking, and tool_use support."""

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic package not installed")


class ClaudeClient:
    """Single wrapper for all Anthropic API calls."""

    # Cost per 1M tokens (March 2026)
    COSTS = {
        "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
        "claude-sonnet-4-5-20250514": {"input": 3.00, "output": 15.00},
    }

    def __init__(self, api_key: str, haiku_model: str, sonnet_model: str):
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError("anthropic package required. pip install anthropic")
        self.client = anthropic.Anthropic(api_key=api_key, timeout=120)
        self.haiku_model = haiku_model
        self.sonnet_model = sonnet_model
        self.total_tokens = {"input": 0, "output": 0}
        self.total_cost_usd = 0.0

    def call_haiku(
        self,
        prompt: str,
        system: str = "You are a document classifier. Return only valid JSON.",
        max_tokens: int = 500,
    ) -> Dict[str, Any]:
        """Quick classification call using Haiku."""
        return self._call(self.haiku_model, prompt, system, max_tokens=max_tokens)

    def call_sonnet(
        self,
        prompt: str,
        system: str = "You are a financial document extraction assistant.",
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Quality extraction call using Sonnet, optionally with tool_use."""
        return self._call(
            self.sonnet_model, prompt, system, tools=tools, max_tokens=max_tokens
        )

    def _call(
        self,
        model: str,
        prompt: str,
        system: str,
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        retries: int = 3,
    ) -> Dict[str, Any]:
        """Make an API call with retry logic."""
        last_error = None
        for attempt in range(retries):
            try:
                start = time.monotonic()

                kwargs: Dict[str, Any] = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": 0.1,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = {"type": "any"}

                response = self.client.messages.create(**kwargs)
                elapsed_ms = int((time.monotonic() - start) * 1000)

                # Track usage
                usage = {
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens,
                }
                self.total_tokens["input"] += usage["input"]
                self.total_tokens["output"] += usage["output"]
                self._track_cost(model, usage)

                # Extract response content
                text = ""
                tool_input = None
                for block in response.content:
                    if block.type == "text":
                        text += block.text
                    elif block.type == "tool_use":
                        tool_input = block.input

                if elapsed_ms > (2000 if "haiku" in model else 8000):
                    logger.warning(
                        "%s call slow: %dms, %d tokens",
                        model, elapsed_ms, usage["input"] + usage["output"],
                    )

                return {
                    "text": text,
                    "tool_input": tool_input,
                    "model": response.model,
                    "usage": usage,
                    "duration_ms": elapsed_ms,
                    "success": True,
                }

            except Exception as e:
                last_error = e
                wait = (2 ** attempt)
                logger.warning(
                    "API call failed (attempt %d/%d): %s. Retrying in %ds...",
                    attempt + 1, retries, e, wait,
                )
                time.sleep(wait)

        return {
            "text": "",
            "tool_input": None,
            "model": model,
            "usage": {"input": 0, "output": 0},
            "duration_ms": 0,
            "success": False,
            "error": str(last_error),
        }

    def _track_cost(self, model: str, usage: Dict[str, int]):
        costs = self.COSTS.get(model, {"input": 3.0, "output": 15.0})
        cost = (usage["input"] * costs["input"] + usage["output"] * costs["output"]) / 1_000_000
        self.total_cost_usd += cost

    def health_check(self) -> bool:
        """Verify API key works."""
        try:
            response = self.client.messages.create(
                model=self.haiku_model,
                max_tokens=5,
                messages=[{"role": "user", "content": "ping"}],
            )
            return bool(response.content)
        except Exception as e:
            logger.warning("Claude health check failed: %s", e)
            return False
