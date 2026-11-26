from backend.app.models.meeting_schema import MeetingSummaryExtraction, OverviewExtraction
from backend.app.services.llm_errors import LLMResponseError


SAMPLE_TRANSCRIPT = (
    "Weekly product meeting.\n"
    "Priya said the onboarding flow is still confusing for new users.\n"
    "We decided to ship the simplified checkout this Friday.\n"
    "Alex will update the release notes by Thursday.\n"
    "Open question: should we hire a contractor for design support?"
)

VALID_EXTRACTION = MeetingSummaryExtraction(
    overview=OverviewExtraction(
        text="The team discussed onboarding issues and confirmed shipping simplified checkout.",
        evidence="We decided to ship the simplified checkout this Friday.",
    ),
    topics=[
        {
            "title": "Onboarding",
            "explanation": "New users still find onboarding confusing.",
            "evidence": "Priya said the onboarding flow is still confusing for new users.",
        }
    ],
    decisions=[
        {
            "statement": "Ship the simplified checkout this Friday",
            "evidence": "We decided to ship the simplified checkout this Friday.",
        }
    ],
    action_items=[
        {
            "task": "Update the release notes",
            "owner": "Alex",
            "due_date": "Thursday",
            "evidence": "Alex will update the release notes by Thursday.",
        }
    ],
    pending_discussions=[
        {
            "item": "Whether to hire a contractor for design support",
            "evidence": "Open question: should we hire a contractor for design support?",
        }
    ],
)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "gemini_configured" in body


def test_empty_transcript_rejected(client):
    response = client.post("/api/meetings", json={"transcript": "   "})
    assert response.status_code == 422


def test_invalid_short_transcript_rejected(client):
    response = client.post("/api/meetings", json={"transcript": "too short"})
    assert response.status_code == 422


def test_successful_summary_generation_with_mocked_gemini(client, monkeypatch):
    def fake_generate_summary(_self, _transcript):
        return VALID_EXTRACTION

    monkeypatch.setattr(
        "app.services.meeting_service.LLMService.generate_summary",
        fake_generate_summary,
    )
    response = client.post("/api/meetings", json={"transcript": SAMPLE_TRANSCRIPT})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] >= 1
    assert body["summary"]["decisions"][0]["statement"].startswith("Ship the simplified")
    assert body["summary"]["action_items"][0]["owner"] == "Alex"
    assert body["summary"]["insufficient_information"] is False


def test_retrieve_previously_saved_meeting(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.meeting_service.LLMService.generate_summary",
        lambda _self, _transcript: VALID_EXTRACTION,
    )
    created = client.post("/api/meetings", json={"transcript": SAMPLE_TRANSCRIPT}).json()
    listed = client.get("/api/meetings")
    assert listed.status_code == 200
    assert any(item["id"] == created["id"] for item in listed.json())

    fetched = client.get(f"/api/meetings/{created['id']}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["transcript"] == SAMPLE_TRANSCRIPT
    assert body["summary"]["topics"][0]["title"] == "Onboarding"


def test_invalid_gemini_response_handling(client, monkeypatch):
    def boom(_self, _transcript):
        raise LLMResponseError("Gemini returned invalid JSON for the meeting summary.")

    monkeypatch.setattr("app.services.meeting_service.LLMService.generate_summary", boom)
    response = client.post("/api/meetings", json={"transcript": SAMPLE_TRANSCRIPT})
    assert response.status_code == 502
    assert "invalid JSON" in response.json()["detail"]


def test_missing_gemini_key_returns_setup_message(client):
    response = client.post("/api/meetings", json={"transcript": SAMPLE_TRANSCRIPT})
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_update_meeting_summary(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.meeting_service.LLMService.generate_summary",
        lambda _self, _transcript: VALID_EXTRACTION,
    )
    created = client.post("/api/meetings", json={"transcript": SAMPLE_TRANSCRIPT}).json()
    edited = created["summary"]
    edited["overview"]["text"] = "Edited overview for the product meeting."
    response = client.put(
        f"/api/meetings/{created['id']}",
        json={"title": "Product weekly", "summary": edited},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Product weekly"
    assert response.json()["summary"]["overview"]["text"].startswith("Edited overview")


def test_regenerate_one_section_does_not_change_others(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.meeting_service.LLMService.generate_summary",
        lambda _self, _transcript: VALID_EXTRACTION,
    )

    def fake_section(_self, _transcript, section):
        assert section.value == "action_items"
        return {
            "action_items": [
                {
                    "task": "Send the recap email",
                    "owner": "Priya",
                    "due_date": None,
                    "evidence": "Priya said the onboarding flow is still confusing for new users.",
                }
            ]
        }

    monkeypatch.setattr("app.services.meeting_service.LLMService.generate_section", fake_section)
    created = client.post("/api/meetings", json={"transcript": SAMPLE_TRANSCRIPT}).json()
    original_decisions = created["summary"]["decisions"]
    original_topics = created["summary"]["topics"]
    original_overview = created["summary"]["overview"]["text"]

    regenerated = client.post(
        f"/api/meetings/{created['id']}/regenerate",
        json={"section": "action_items"},
    )
    assert regenerated.status_code == 200
    body = regenerated.json()["summary"]
    assert body["action_items"][0]["task"] == "Send the recap email"
    assert body["action_items"][0]["due_date"] is None
    assert body["decisions"] == original_decisions
    assert body["topics"] == original_topics
    assert body["overview"]["text"] == original_overview
