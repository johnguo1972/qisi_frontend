"""Exceptions shared by AI configuration, prompts, and response handling."""


class AIConfigError(Exception):
    """Raised when AI runtime configuration is missing or invalid."""


class AIPromptError(Exception):
    """Raised when an AI prompt cannot be rendered safely."""


class AIResponseError(Exception):
    """Raised when an AI response cannot be validated or normalized."""
