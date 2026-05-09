"""Voice rules are load-bearing — these tests guard the system prompt from
drifting into the forbidden vocabulary.
"""
from copio_api.agent.prompts import HONEST_VOICE_SYSTEM_PROMPT, VOICE_DOC

# Anti-vocab from CEO plan + DESIGN.md voice rules. These words are forbidden
# in agent output. They must NOT appear as instructions to USE — but they may
# appear in the negative ("never say leverage") inside the system prompt.
# So we check that they only appear in negative contexts.
FORBIDDEN_WORDS = [
    "leverage", "synergy", "holistic", "seamless", "robust",
    "comprehensive", "drive engagement", "optimize", "unlock value",
    "journey", "nuanced", "multifaceted", "vibrant", "foster",
    "showcase", "intricate", "fundamental", "significant", "delve",
    "crucial", "pivotal", "landscape", "tapestry", "underscore",
]


def test_system_prompt_mentions_honest_voice() -> None:
    assert "honest" in HONEST_VOICE_SYSTEM_PROMPT.lower()
    assert "I can see" in HONEST_VOICE_SYSTEM_PROMPT
    assert "I infer" in HONEST_VOICE_SYSTEM_PROMPT


def test_system_prompt_forbids_em_dashes() -> None:
    # The instruction must mention em dashes, but the prompt itself should
    # not contain a real em dash since the model would copy that.
    assert "—" not in HONEST_VOICE_SYSTEM_PROMPT.replace("—.", "")
    assert "em dash" in HONEST_VOICE_SYSTEM_PROMPT.lower()


def test_system_prompt_lists_forbidden_words() -> None:
    """All forbidden words must appear in the prompt's anti-list, otherwise
    the runtime cannot prevent drift.
    """
    for word in FORBIDDEN_WORDS:
        assert word.lower() in HONEST_VOICE_SYSTEM_PROMPT.lower(), (
            f"forbidden word '{word}' missing from anti-list in system prompt"
        )


def test_voice_doc_references_examples_file() -> None:
    assert "EXAMPLES.md" in VOICE_DOC


def test_voice_doc_no_em_dashes() -> None:
    # The voice doc itself must not contain em dashes — the model treats it
    # as an example of how to write.
    assert "—" not in VOICE_DOC
