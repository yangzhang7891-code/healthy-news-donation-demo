"""Donor persona definitions for synthetic fixture generation.

A persona controls how much of a simulated donor's activity touches
news content, and how much activity they have in total. Three personas
bracket the range real donors are expected to fall in: someone whose
media diet is dominated by news, someone who avoids it almost
entirely, and someone in between. Extraction/canary code should be
correct across all three, not just tuned to whichever is easiest.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    name: str
    news_share: float  # probability a given watch/browse/like event is a news item
    activity_count: int  # number of history records to generate per platform


PERSONAS: dict[str, Persona] = {
    "news_heavy": Persona("news_heavy", news_share=0.75, activity_count=120),
    "news_avoider": Persona("news_avoider", news_share=0.03, activity_count=90),
    "mixed": Persona("mixed", news_share=0.30, activity_count=100),
}
