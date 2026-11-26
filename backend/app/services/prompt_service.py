from backend.app.models.meeting_schema import SectionName

SYSTEM_INSTRUCTION = """You are a careful meeting-notes extractor.

Extract only information that is explicitly supported by the provided transcript.
Never invent people, decisions, tasks, owners, deadlines, or topics.
If a field is not explicitly stated, return null or an empty list.
Do not treat suggestions, proposals, opinions, or hypotheticals as confirmed decisions.
A confirmed decision requires language that the group actually agreed, approved, decided, or committed to.
Every extracted item must include a supporting evidence quotation copied verbatim from the transcript.
Do not paraphrase evidence. Copy a contiguous snippet from the transcript.
If the transcript does not contain enough information for a section, return an empty list or empty text for that section.
Do not use knowledge from outside the transcript.
"""

EXTRACTION_RULES = """
Extraction rules:
- Main topics: important subjects that were discussed, with a brief explanation and verbatim evidence.
- Key decisions: only confirmed decisions. Exclude suggestions, ideas, and unresolved proposals.
- Action items: concrete tasks. Set owner to null unless a person is explicitly assigned. Set due_date to null unless a deadline is explicitly stated.
- Pending discussions: unresolved topics or questions that still need discussion.
- Meeting overview: a short factual summary. Do not add details that are not in the transcript.
"""

SECTION_FOCUS = {
    SectionName.overview: "Return only the meeting overview. Keep it concise and factual.",
    SectionName.topics: "Return only main topics discussed. Do not include decisions or action items.",
    SectionName.decisions: (
        "Return only confirmed decisions. Do not include suggestions, proposals, or unresolved ideas."
    ),
    SectionName.action_items: (
        "Return only action items. Use null for owner or due_date when they are not explicitly stated."
    ),
    SectionName.pending_discussions: (
        "Return only unresolved topics and open questions that require further discussion."
    ),
}


def build_summary_prompt(transcript: str) -> str:
    return (
        "Extract a structured meeting summary from the transcript below.\n"
        f"{EXTRACTION_RULES}\n"
        "Transcript:\n"
        f"{transcript.strip()}\n"
    )


def build_section_prompt(transcript: str, section: SectionName) -> str:
    focus = SECTION_FOCUS[section]
    return (
        f"Extract only the requested meeting section from the transcript below.\n"
        f"{focus}\n"
        f"{EXTRACTION_RULES}\n"
        "Do not invent missing information. If nothing is supported, return empty values.\n"
        "Transcript:\n"
        f"{transcript.strip()}\n"
    )
