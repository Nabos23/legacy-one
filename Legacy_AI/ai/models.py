from enum import Enum


class Model(str, Enum):
    # OpenAI
    GPT_4_1          = "gpt-4.1"
    GPT_4_1_MINI     = "gpt-4.1-mini"
    GPT_5_4_MINI     = "gpt-5.4-mini"
    GPT_5_4_NANO     = "gpt-5.4-nano-2026-03-17"
    GPT_IMAGE_2      = "gpt-image-2"

    # Anthropic (via LiteLLM prefix)
    # CLAUDE_SONNET    = "anthropic/claude-sonnet-4-6"
    # CLAUDE_HAIKU     = "anthropic/claude-haiku-4-5-20251001"
    # CLAUDE_OPUS      = "anthropic/claude-opus-4-8"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def default(cls) -> "Model":
        """Returns the default model used across the system."""
        return cls.GPT_5_4_MINI
