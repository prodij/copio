import pytest
from pydantic import ValidationError

from copio_api.schemas.reaction import ReactionIn


def test_valid_emoji_accepted() -> None:
    body = ReactionIn(message_id="abc", emoji="👍")
    assert body.emoji == "👍"


def test_invalid_emoji_rejected() -> None:
    with pytest.raises(ValidationError):
        ReactionIn(message_id="abc", emoji="🥳")


def test_all_five_spec_emojis_accepted() -> None:
    for emoji in ("👍", "👎", "🎯", "❓", "🔁"):
        ReactionIn(message_id="abc", emoji=emoji)
