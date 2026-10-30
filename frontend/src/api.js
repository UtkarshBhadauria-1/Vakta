const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

function requestHeaders(telemetryEnabled) {
  const headers = { "Content-Type": "application/json" };
  if (!telemetryEnabled) headers["X-Telemetry-Opt-Out"] = "1";
  return headers;
}

export async function getBackendHealth() {
  const response = await fetch(`${API_BASE_URL}/api/health`);
  if (!response.ok) throw new Error("Backend health check failed");
  return response.json();
}

export async function sendChat(question, conversation = [], sessionId = null, telemetryEnabled = true) {
  let response;
  const body = { question, conversation };
  if (sessionId) body.session_id = sessionId;

  try {
    response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: requestHeaders(telemetryEnabled),
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("We couldn't reach Vakta. Please check the backend and try again.");
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : "Please try again in a moment.";
    throw new Error(detail);
  }
  if (typeof payload.answer !== "string" || !payload.answer.trim()) {
    throw new Error("The assistant returned an empty answer. Please try again.");
  }
  return { ...payload, answer: payload.answer.trim() };
}

export async function submitFeedback(sessionId, rating, telemetryEnabled = true) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/feedback`, {
      method: "POST",
      headers: requestHeaders(telemetryEnabled),
      body: JSON.stringify({ session_id: sessionId, user_rating: rating }),
    });
  } catch {
    throw new Error("Could not submit feedback.");
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : "Feedback submission failed.";
    throw new Error(detail);
  }
  return payload;
}
