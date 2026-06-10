import logging
import anthropic
from pydantic import BaseModel
from typing import Optional
import config

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """\
You are a rental post analyzer. The user will give you a Facebook post in any language.
Your job is to decide whether it matches the rental criteria below.

RENTAL CRITERIA:
{criteria}

Always call the analyze_rental_post tool with your findings.
If the post is not about renting an apartment (e.g. it's a question, a comment, or selling),
set matches=false and explain why in the reason field.
"""

ANALYZE_TOOL = {
    "name": "analyze_rental_post",
    "description": "Report whether a Facebook post matches the rental criteria",
    "input_schema": {
        "type": "object",
        "properties": {
            "matches": {
                "type": "boolean",
                "description": "True if the post matches ALL of the rental criteria",
            },
            "reason": {
                "type": "string",
                "description": "One or two sentences explaining the decision",
            },
            "price": {
                "type": "string",
                "description": "Rental price exactly as stated in the post, e.g. '4500 NIS/month'. Omit this field entirely if no price is mentioned — never write a placeholder like 'unknown'.",
            },
            "location": {
                "type": "string",
                "description": "Location or neighborhood mentioned in the post. Omit this field entirely if no location is mentioned — never write a placeholder like 'unknown'.",
            },
            "size": {
                "type": "string",
                "description": "Apartment size exactly as stated, e.g. '3 rooms, 65m²'. Omit this field entirely if no size is mentioned — never write a placeholder like 'unknown'.",
            },
        },
        "required": ["matches", "reason"],
    },
}


class AnalysisResult(BaseModel):
    matches: bool
    reason: str
    price: Optional[str] = None
    location: Optional[str] = None
    size: Optional[str] = None


def analyze_post(post_text: str) -> AnalysisResult:
    if not post_text.strip():
        return AnalysisResult(matches=False, reason="Post has no text content")

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            system=SYSTEM_PROMPT.format(criteria=config.RENTAL_CRITERIA),
            messages=[{"role": "user", "content": post_text[:4000]}],
            tools=[ANALYZE_TOOL],
            tool_choice={"type": "tool", "name": "analyze_rental_post"},
        )

        tool_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if tool_block is None:
            logger.warning("No tool_use block in response")
            return AnalysisResult(matches=False, reason="Analysis unavailable")

        return AnalysisResult(**tool_block.input)

    except Exception as exc:
        logger.error("Claude API error: %s", exc)
        return AnalysisResult(matches=False, reason=f"Analysis error: {exc}")
