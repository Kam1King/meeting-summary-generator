import { useEffect, useState } from "react";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  Eraser,
  FileText,
  HelpCircle,
  History,
  RefreshCw,
  Save,
  Sparkles,
  Upload,
} from "lucide-react";
import {
  createMeeting,
  extractErrorMessage,
  getHealth,
  getMeeting,
  listMeetings,
  regenerateSection,
  updateMeeting,
} from "./api.js";
import "./App.css";

const PLACEHOLDER = `Example:

Weekly product meeting.
Priya said the onboarding flow is still confusing for new users.
We decided to ship the simplified checkout this Friday.
Alex will update the release notes by Thursday.
Open question: should we hire a contractor for design support?`;
const MAX_TRANSCRIPT_FILE_SIZE = 10 * 1024 * 1024;
const TRANSCRIPT_FILE_EXTENSIONS = new Set(["txt", "md", "csv", "srt", "vtt", "json"]);

const emptySummary = {
  overview: { text: "", evidence: null, needs_review: false, review_reasons: [] },
  topics: [],
  decisions: [],
  action_items: [],
  pending_discussions: [],
  insufficient_information: false,
};

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function ReviewBadge({ item }) {
  if (!item?.needs_review) return null;
  return (
    <span className="badge" title={(item.review_reasons || []).join(" ")}>
      <AlertTriangle size={12} /> Needs review
    </span>
  );
}

function Evidence({ text }) {
  if (!text) return null;
  return <blockquote className="evidence">“{text}”</blockquote>;
}

function SectionActions({ onRegenerate, regenerating, onToggleEdit, editing, canSave, onSave, saving }) {
  return (
    <div className="actions" style={{ marginTop: 0 }}>
      <button className="ghost-btn" onClick={onToggleEdit} type="button">
        {editing ? "Cancel edit" : "Edit"}
      </button>
      {editing && (
        <button className="primary-btn" onClick={onSave} disabled={!canSave || saving} type="button">
          {saving ? <span className="spinner" /> : <Save size={16} />}
          Save
        </button>
      )}
      <button className="ghost-btn" onClick={onRegenerate} disabled={regenerating || editing} type="button">
        {regenerating ? <span className="spinner dark" /> : <RefreshCw size={16} />}
        Regenerate
      </button>
    </div>
  );
}

export default function App() {
  const [transcript, setTranscript] = useState("");
  const [transcriptFileName, setTranscriptFileName] = useState("");
  const [meetings, setMeetings] = useState([]);
  const [current, setCurrent] = useState(null);
  const [summary, setSummary] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState("");
  const [editingSection, setEditingSection] = useState("");

  async function refreshHistory() {
    try {
      const data = await listMeetings();
      setMeetings(data);
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }

  useEffect(() => {
    refreshHistory();
    getHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "unreachable", gemini_configured: false }));
  }, []);

  function applyMeeting(meeting) {
    setCurrent(meeting);
    setSummary(meeting.summary || emptySummary);
    setTranscript(meeting.transcript || "");
    setTranscriptFileName("");
    setEditingSection("");
  }

  async function handleTranscriptFile(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setError("");
    const extension = file.name.split(".").pop()?.toLowerCase();
    if (!TRANSCRIPT_FILE_EXTENSIONS.has(extension)) {
      setError("Choose a text transcript file: .txt, .md, .csv, .srt, .vtt, or .json.");
      return;
    }
    if (file.size > MAX_TRANSCRIPT_FILE_SIZE) {
      setError("Transcript files must be 10 MB or smaller.");
      return;
    }

    try {
      const contents = await file.text();
      if (!contents.trim()) {
        setError("The selected transcript file is empty.");
        return;
      }
      setTranscript(contents);
      setTranscriptFileName(file.name);
    } catch {
      setError("Could not read the selected file. Try saving it as UTF-8 text and upload it again.");
    }
  }

  async function handleGenerate() {
    setError("");
    setLoading(true);
    try {
      const meeting = await createMeeting(transcript);
      applyMeeting(meeting);
      await refreshHistory();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleOpen(id) {
    setError("");
    try {
      const meeting = await getMeeting(id);
      applyMeeting(meeting);
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }

  async function handleSave() {
    if (!current || !summary) return;
    setSaving(true);
    setError("");
    try {
      const meeting = await updateMeeting(current.id, { title: current.title, summary });
      applyMeeting(meeting);
      await refreshHistory();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleRegenerate(section) {
    if (!current) return;
    setRegenerating(section);
    setError("");
    try {
      const meeting = await regenerateSection(current.id, section);
      applyMeeting(meeting);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setRegenerating("");
    }
  }

  function updateOverview(text) {
    setSummary((prev) => ({ ...prev, overview: { ...prev.overview, text } }));
  }

  function updateListItem(section, index, field, value) {
    setSummary((prev) => {
      const next = [...prev[section]];
      next[index] = { ...next[index], [field]: value };
      return { ...prev, [section]: next };
    });
  }

  const geminiReady = health?.gemini_configured;

  return (
    <div className="app-shell">
      <header className="topbar">
        <h1>Smart Meeting Summary Generator</h1>
        <p>
          Paste meeting notes or upload a text transcript. Gemini Flash extracts topics, confirmed decisions,
          action items, and open questions — only when the transcript supports them.
        </p>
      </header>

      <div className="layout">
        <aside className="panel">
          <h2>
            <History size={16} /> Meeting history
          </h2>
          {meetings.length === 0 ? (
            <p className="empty">No saved meetings yet.</p>
          ) : (
            <div className="history-list">
              {meetings.map((item) => (
                <button
                  key={item.id}
                  className={`history-item ${current?.id === item.id ? "active" : ""}`}
                  onClick={() => handleOpen(item.id)}
                  type="button"
                >
                  <strong>{item.title}</strong>
                  <span>{formatDate(item.created_at)}</span>
                </button>
              ))}
            </div>
          )}
        </aside>

        <main className="workspace">
          {error && <div className="banner error">{error}</div>}
          {health && health.status === "unreachable" && (
            <div className="banner error">Backend is not reachable. Start the FastAPI server on port 8000.</div>
          )}
          {health && health.status === "ok" && !geminiReady && (
            <div className="banner warn">
              Gemini is not configured. Add GEMINI_API_KEY to backend/.env, then restart the API.
            </div>
          )}

          <section className="card">
            <div className="section-head">
              <h2>
                <ClipboardList size={18} /> Transcript
              </h2>
            </div>
            <textarea
              className="textarea"
              value={transcript}
              onChange={(event) => setTranscript(event.target.value)}
              placeholder={PLACEHOLDER}
            />
            <div className="transcript-import">
              <label className="ghost-btn file-upload-btn">
                <Upload size={16} /> Upload transcript
                <input
                  className="file-input"
                  type="file"
                  accept=".txt,.md,.csv,.srt,.vtt,.json,text/plain,text/csv,application/json"
                  onChange={handleTranscriptFile}
                  aria-label="Upload transcript file"
                />
              </label>
              <span className="file-hint">
                {transcriptFileName ? (
                  <><FileText size={14} /> {transcriptFileName}</>
                ) : (
                  "TXT, MD, CSV, SRT, VTT, or JSON · up to 10 MB"
                )}
              </span>
            </div>
            <div className="actions">
              <button className="primary-btn" onClick={handleGenerate} disabled={loading || !transcript.trim()} type="button">
                {loading ? <span className="spinner" /> : <Sparkles size={16} />}
                {loading ? "Generating summary..." : "Generate Summary"}
              </button>
              <button
                className="ghost-btn"
                onClick={() => {
                  setTranscript("");
                  setTranscriptFileName("");
                  setSummary(null);
                  setCurrent(null);
                  setError("");
                }}
                type="button"
              >
                <Eraser size={16} /> Clear
              </button>
            </div>
          </section>

          {summary && (
            <>
              {summary.insufficient_information && (
                <div className="banner warn">
                  The transcript does not contain enough information to build a reliable summary.
                  Add more meeting detail and generate again.
                </div>
              )}

              <section className="card">
                <div className="section-head">
                  <h2>
                    Meeting Overview <ReviewBadge item={summary.overview} />
                  </h2>
                  <SectionActions
                    editing={editingSection === "overview"}
                    onToggleEdit={() => setEditingSection((value) => (value === "overview" ? "" : "overview"))}
                    onSave={handleSave}
                    saving={saving}
                    canSave={Boolean(current)}
                    onRegenerate={() => handleRegenerate("overview")}
                    regenerating={regenerating === "overview"}
                  />
                </div>
                {editingSection === "overview" ? (
                  <textarea
                    className="edit-area"
                    value={summary.overview.text}
                    onChange={(event) => updateOverview(event.target.value)}
                  />
                ) : (
                  <p>{summary.overview.text || "No overview was extracted."}</p>
                )}
                <Evidence text={summary.overview.evidence} />
              </section>

              <section className="card">
                <div className="section-head">
                  <h2>
                    <CheckCircle2 size={18} /> Main Topics
                  </h2>
                  <SectionActions
                    editing={editingSection === "topics"}
                    onToggleEdit={() => setEditingSection((value) => (value === "topics" ? "" : "topics"))}
                    onSave={handleSave}
                    saving={saving}
                    canSave={Boolean(current)}
                    onRegenerate={() => handleRegenerate("topics")}
                    regenerating={regenerating === "topics"}
                  />
                </div>
                {summary.topics.length === 0 ? (
                  <p className="empty">No topics were supported by the transcript.</p>
                ) : (
                  summary.topics.map((topic, index) => (
                    <div className="item" key={`${topic.title}-${index}`}>
                      {editingSection === "topics" ? (
                        <>
                          <input
                            className="edit-input"
                            value={topic.title}
                            onChange={(event) => updateListItem("topics", index, "title", event.target.value)}
                          />
                          <textarea
                            className="edit-area"
                            value={topic.explanation}
                            onChange={(event) => updateListItem("topics", index, "explanation", event.target.value)}
                          />
                        </>
                      ) : (
                        <>
                          <strong>
                            {topic.title} <ReviewBadge item={topic} />
                          </strong>
                          <p>{topic.explanation}</p>
                        </>
                      )}
                      <Evidence text={topic.evidence} />
                    </div>
                  ))
                )}
              </section>

              <section className="card">
                <div className="section-head">
                  <h2>
                    <Sparkles size={18} /> Key Decisions
                  </h2>
                  <SectionActions
                    editing={editingSection === "decisions"}
                    onToggleEdit={() => setEditingSection((value) => (value === "decisions" ? "" : "decisions"))}
                    onSave={handleSave}
                    saving={saving}
                    canSave={Boolean(current)}
                    onRegenerate={() => handleRegenerate("decisions")}
                    regenerating={regenerating === "decisions"}
                  />
                </div>
                {summary.decisions.length === 0 ? (
                  <p className="empty">No confirmed decisions were found.</p>
                ) : (
                  summary.decisions.map((decision, index) => (
                    <div className="item" key={`${decision.statement}-${index}`}>
                      {editingSection === "decisions" ? (
                        <textarea
                          className="edit-area"
                          value={decision.statement}
                          onChange={(event) => updateListItem("decisions", index, "statement", event.target.value)}
                        />
                      ) : (
                        <p>
                          {decision.statement} <ReviewBadge item={decision} />
                        </p>
                      )}
                      <Evidence text={decision.evidence} />
                    </div>
                  ))
                )}
              </section>

              <section className="card">
                <div className="section-head">
                  <h2>
                    <CalendarClock size={18} /> Action Items
                  </h2>
                  <SectionActions
                    editing={editingSection === "action_items"}
                    onToggleEdit={() => setEditingSection((value) => (value === "action_items" ? "" : "action_items"))}
                    onSave={handleSave}
                    saving={saving}
                    canSave={Boolean(current)}
                    onRegenerate={() => handleRegenerate("action_items")}
                    regenerating={regenerating === "action_items"}
                  />
                </div>
                {summary.action_items.length === 0 ? (
                  <p className="empty">No action items were explicitly assigned.</p>
                ) : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Task</th>
                          <th>Owner</th>
                          <th>Due Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.action_items.map((item, index) => (
                          <tr key={`${item.task}-${index}`}>
                            <td>
                              {editingSection === "action_items" ? (
                                <input
                                  className="edit-input"
                                  value={item.task}
                                  onChange={(event) => updateListItem("action_items", index, "task", event.target.value)}
                                />
                              ) : (
                                <>
                                  {item.task} <ReviewBadge item={item} />
                                </>
                              )}
                              <Evidence text={item.evidence} />
                            </td>
                            <td>
                              {editingSection === "action_items" ? (
                                <input
                                  className="edit-input"
                                  value={item.owner || ""}
                                  onChange={(event) =>
                                    updateListItem("action_items", index, "owner", event.target.value || null)
                                  }
                                />
                              ) : (
                                item.owner || "—"
                              )}
                            </td>
                            <td>
                              {editingSection === "action_items" ? (
                                <input
                                  className="edit-input"
                                  value={item.due_date || ""}
                                  onChange={(event) =>
                                    updateListItem("action_items", index, "due_date", event.target.value || null)
                                  }
                                />
                              ) : (
                                item.due_date || "—"
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section className="card">
                <div className="section-head">
                  <h2>
                    <HelpCircle size={18} /> Pending Discussions
                  </h2>
                  <SectionActions
                    editing={editingSection === "pending_discussions"}
                    onToggleEdit={() =>
                      setEditingSection((value) => (value === "pending_discussions" ? "" : "pending_discussions"))
                    }
                    onSave={handleSave}
                    saving={saving}
                    canSave={Boolean(current)}
                    onRegenerate={() => handleRegenerate("pending_discussions")}
                    regenerating={regenerating === "pending_discussions"}
                  />
                </div>
                {summary.pending_discussions.length === 0 ? (
                  <p className="empty">No unresolved discussions were extracted.</p>
                ) : (
                  summary.pending_discussions.map((item, index) => (
                    <div className="item" key={`${item.item}-${index}`}>
                      {editingSection === "pending_discussions" ? (
                        <textarea
                          className="edit-area"
                          value={item.item}
                          onChange={(event) =>
                            updateListItem("pending_discussions", index, "item", event.target.value)
                          }
                        />
                      ) : (
                        <p>
                          {item.item} <ReviewBadge item={item} />
                        </p>
                      )}
                      <Evidence text={item.evidence} />
                    </div>
                  ))
                )}
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
