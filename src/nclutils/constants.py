"""Constants for script utilities."""

import random

from questionary import Style as QuestionaryStyle

CHOICE_STYLE = QuestionaryStyle(
    [
        ("highlighted", ""),  # hover state
        ("selected", "bold noreverse"),
        ("instruction", "fg:#c5c5c5"),
        ("text", "fg:#c5c5c5"),
    ]
)


RANDOM = random.SystemRandom()
RANDOM.seed()
