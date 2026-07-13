#region Imports
from dataclasses import dataclass
from datetime import datetime

#endregion


#region Data Classes


@dataclass(frozen=True)
class TokenUsage:
    """
    Represents token usage for a single API call.

    Attributes:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cache_creation_tokens: Number of tokens written to cache
        cache_read_tokens: Number of tokens read from cache
    """

    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    cache_creation_1h_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens across all categories."""
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_tokens
            + self.cache_read_tokens
        )


@dataclass(frozen=True)
class UsageRecord:
    """
    Represents a single usage event from Claude Code.

    Attributes:
        timestamp: When the event occurred
        session_id: UUID of the conversation session
        message_uuid: UUID of the specific message
        message_type: Type of message ('user' or 'assistant')
        model: Model name (e.g., 'claude-sonnet-4-5-20250929')
        folder: Project folder path
        git_branch: Current git branch (if available)
        version: Claude Code version
        token_usage: Token usage details (None for user messages)
        content: Message content text (for analysis)
        char_count: Character count of message content
    """

    timestamp: datetime
    session_id: str
    message_uuid: str
    message_type: str
    model: str | None
    folder: str
    git_branch: str | None
    version: str
    token_usage: TokenUsage | None
    content: str | None = None
    char_count: int = 0

    @property
    def date_key(self) -> str:
        """
        Get date string in YYYY-MM-DD format for grouping.

        Converts UTC timestamp to local timezone before extracting date.
        This ensures activity is grouped by the user's local calendar day,
        not UTC days. For example, activity at 23:30 local time will be
        grouped into the correct local day, even though it may be a different
        UTC day.

        Returns:
            Date string in YYYY-MM-DD format (local timezone)
        """
        local_timestamp = self.timestamp.astimezone()  # Convert to local timezone
        return local_timestamp.strftime("%Y-%m-%d")

    @property
    def is_user_prompt(self) -> bool:
        """Check if this is a user prompt message."""
        return self.message_type == "user"

    @property
    def is_assistant_response(self) -> bool:
        """Check if this is an assistant response message."""
        return self.message_type == "assistant"
#endregion
