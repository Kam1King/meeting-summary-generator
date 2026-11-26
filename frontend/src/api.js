import axios from "axios";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8001",
  headers: { "Content-Type": "application/json" },
  timeout: 120000,
});

export function extractErrorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail) && detail[0]?.msg) {
    return detail.map((item) => item.msg).join(" ");
  }
  if (error?.message) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

export async function getHealth() {
  const { data } = await client.get("/health");
  return data;
}

export async function listMeetings() {
  const { data } = await client.get("/api/meetings");
  return data;
}

export async function createMeeting(transcript, title) {
  const { data } = await client.post("/api/meetings", { transcript, title });
  return data;
}

export async function getMeeting(meetingId) {
  const { data } = await client.get(`/api/meetings/${meetingId}`);
  return data;
}

export async function updateMeeting(meetingId, payload) {
  const { data } = await client.put(`/api/meetings/${meetingId}`, payload);
  return data;
}

export async function regenerateSection(meetingId, section) {
  const { data } = await client.post(`/api/meetings/${meetingId}/regenerate`, { section });
  return data;
}
