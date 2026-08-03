"""Context-aware compression for large tool results."""

import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CompressionStrategy(Enum):
    """Compression strategies supported by this example agent."""

    CONTEXT_AWARE = "context_aware_summary"


@dataclass
class CompressedContent:
    """The result of compressing a tool response."""

    original_length: int
    compressed_length: int
    content: str
    strategy: CompressionStrategy = CompressionStrategy.CONTEXT_AWARE
    used_fallback: bool = False
    error: Optional[str] = None


class ContextCompressor:
    """Create query-focused summaries of ``fetch_webpage`` results."""

    def __init__(self, client, model: str):
        self.client = client
        self.model = model
        self.max_input_chars = int(os.getenv("COMPRESSION_MAX_INPUT_CHARS", "5000"))
        self.max_summary_tokens = int(os.getenv("SUMMARY_MAX_TOKENS", "500"))

    def compress_fetch_webpage_result(
        self,
        raw_result: str,
        query: str,
        current_context: Optional[str] = None,
    ) -> CompressedContent:
        """Apply the CONTEXT_AWARE strategy to one webpage tool result.

        Invalid results and failed fetches are returned unchanged. If the
        summarization request fails, returning the original tool result keeps
        the agent useful and makes the failure visible to the caller.
        """
        try:
            webpage = json.loads(raw_result)
        except (json.JSONDecodeError, TypeError) as error:
            return self._fallback(raw_result, f"invalid fetch_webpage result: {error}")

        if not isinstance(webpage, dict):
            return self._fallback(raw_result, "fetch_webpage result is not a JSON object")

        original_content = webpage.get("content", "")
        if (
            not webpage.get("success")
            or not isinstance(original_content, str)
            or not original_content.strip()
        ):
            return self._fallback(raw_result)

        title = webpage.get("title", "N/A")
        url = webpage.get("url", "N/A")
        limited_content = original_content[:self.max_input_chars]
        context_line = (
            f"Current context: {current_context[:1000]}"
            if current_context
            else ""
        )
        prompt = f"""Given the user's query: "{query}"
{context_line}

Analyze the following webpage and provide a focused summary that directly helps answer the query.
Focus on extracting information most relevant to: {query}

Title: {title}
URL: {url}
Content:
{limited_content}

Requirements:
1. Focus only on information relevant to the query
2. Prioritize current/recent information when the page contains dates
3. Preserve specific names, dates, numbers, and affiliations
4. Do not invent facts that are absent from the webpage
5. Maximum length: {self.max_summary_tokens} tokens
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You create concise, context-aware webpage summaries. "
                            "Retain factual details needed to answer the user's query."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_summary_tokens,
            )
            summary = response.choices[0].message.content
            if not isinstance(summary, str) or not summary.strip():
                raise ValueError("compression model returned an empty summary")

            compressed = json.dumps(
                {
                    "url": url,
                    "title": title,
                    "content": summary.strip(),
                    # "content_length": len(summary.strip()),
                    # "original_content_length": len(original_content),
                    # "compression_strategy": CompressionStrategy.CONTEXT_AWARE.value,
                    "success": True,
                },
                ensure_ascii=False,
            )
            return CompressedContent(
                original_length=len(raw_result),
                compressed_length=len(compressed),
                content=compressed,
            )
        except Exception as error:
            return self._fallback(raw_result, f"context-aware compression failed: {error}")

    @staticmethod
    def _fallback(raw_result: str, error: Optional[str] = None) -> CompressedContent:
        content = raw_result if isinstance(raw_result, str) else str(raw_result)
        return CompressedContent(
            original_length=len(content),
            compressed_length=len(content),
            content=content,
            used_fallback=True,
            error=error,
        )


def latest_user_query(messages) -> str:
    """Return the user request that led to the current tool call."""
    for message in reversed(messages):
        if message.get("role") == "user" and message.get("content"):
            return str(message["content"])
    return ""


def recent_conversation_context(messages, max_chars: int = 1000) -> str:
    """Build compact context without copying previous large tool results."""
    parts = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant"} or not content:
            continue
        label = "User" if role == "user" else "Assistant"
        parts.append(f"{label}: {content}")
    return "\n".join(parts)[-max_chars:]
