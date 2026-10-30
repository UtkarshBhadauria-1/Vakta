import { useEffect, useRef, useState } from "react";
import { getBackendHealth, sendChat, submitFeedback } from "./api.js";

const TELEMETRY_PREFERENCE_KEY = "vakta.telemetry.enabled.v1";

function loadTelemetryPreference() {
  try {
    return window.localStorage.getItem(TELEMETRY_PREFERENCE_KEY) !== "false";
  } catch {
    return true;
  }
}

const SUGGESTIONS = [
  "How do I add or drop a course?",
  "Where can I find scholarship deadlines?",
  "When is the library open on weekends?",
  "What should I bring to advising?",
];

const SUPPORT_SECTIONS = {
  "student-support": {
    id: "student-support",
    title: "Student Support",
    description: "Ask a question about university life. Vakta searches the indexed information and includes source references when available.",
    suggestions: SUGGESTIONS,
  },
  academics: {
    id: "academics",
    title: "Academics",
    description: "Ask about courses, advising, faculty, and academic resources. Answers rely on the university information currently indexed.",
    suggestions: [
      "How do I add or drop a course?",
      "What should I bring to advising?",
      "Where can I find information about courses and faculty?",
    ],
  },
  examinations: {
    id: "examinations",
    title: "Examinations",
    description: "Ask about exam schedules, attendance, results, or revaluation information available to Vakta.",
    suggestions: [
      "Where can I find information about exam schedules?",
      "How can I ask about attendance requirements?",
      "Where can I find revaluation information?",
    ],
  },
  fees: {
    id: "fees",
    title: "Fees & Scholarships",
    description: "Ask about fee and scholarship information found in the indexed university documents.",
    suggestions: [
      "Where can I find scholarship deadlines?",
      "Where can I find information about tuition fees?",
      "How can I ask about fee payment options?",
    ],
  },
  campus: {
    id: "campus",
    title: "Campus Services",
    description: "Ask about campus services and facilities. Vakta will show its sources when the indexed documents provide evidence.",
    suggestions: [
      "When is the library open on weekends?",
      "Where can I find campus service information?",
      "Where can I find hostel information?",
    ],
  },
};

const TOPICS = [
  { id: "student-support", label: "Student Support", icon: "home" },
  { id: "academics", label: "Academics", icon: "book" },
  { id: "examinations", label: "Examinations", icon: "calendar" },
  { id: "fees", label: "Fees & Scholarships", icon: "coins" },
  { id: "campus", label: "Campus Services", icon: "building" },
];

const UTILITIES = [
  { id: "faqs", label: "FAQs", icon: "help" },
  { id: "settings", label: "Settings", icon: "settings" },
  { id: "help-support", label: "Help & Support", icon: "message" },
];

function Icon({ name, className = "" }) {
  const paths = {
    home: <><path d="m3 10 9-7 9 7" /><path d="M5 9v11h14V9M9 20v-6h6v6" /></>,
    book: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" /><path d="M8 6h8M8 10h7" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18M8 14h3M8 17h6" /></>,
    coins: <><ellipse cx="12" cy="6" rx="8" ry="3" /><path d="M4 6v5c0 1.7 3.6 3 8 3 1.3 0 2.5-.1 3.6-.4M20 6v3" /><path d="M4 11v5c0 1.7 3.6 3 8 3 .7 0 1.4 0 2.1-.1" /><circle cx="18" cy="16" r="4" /><path d="M18 14v4M19.2 14.8c-.3-.4-.7-.6-1.3-.6-.7 0-1.2.4-1.2.9 0 1.4 2.5.6 2.5 2 0 .5-.5.9-1.2.9-.6 0-1.1-.2-1.4-.6" /></>,
    building: <><path d="M4 21h16M6 21V5l6-2 6 2v16M9 8h1m4 0h1M9 12h1m4 0h1M10 21v-5h4v5" /></>,
    plus: <><path d="M12 5v14M5 12h14" /></>,
    menu: <><path d="M4 6h16M4 12h16M4 18h16" /></>,
    close: <><path d="m18 6-12 12M6 6l12 12" /></>,
    send: <><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></>,
    arrow: <><path d="M7 17 17 7M7 7h10v10" /></>,
    help: <><circle cx="12" cy="12" r="9" /><path d="M9.8 9a2.3 2.3 0 1 1 3.8 1.7c-.9.8-1.6 1.2-1.6 2.8M12 17h.01" /></>,
    settings: <><path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z" /><path d="m19.4 15 .1.1a1.8 1.8 0 0 1-2.5 2.5l-.1-.1a1.8 1.8 0 0 0-3 .9v.2a1.8 1.8 0 0 1-3.6 0v-.2a1.8 1.8 0 0 0-3-.9l-.1.1a1.8 1.8 0 0 1-2.5-2.5l.1-.1a1.8 1.8 0 0 0-.9-3h-.2a1.8 1.8 0 0 1 0-3.6h.2a1.8 1.8 0 0 0 .9-3l-.1-.1a1.8 1.8 0 0 1 2.5-2.5l.1.1a1.8 1.8 0 0 0 3-.9v-.2a1.8 1.8 0 0 1 3.6 0v.2a1.8 1.8 0 0 0 3 .9l.1-.1a1.8 1.8 0 0 1 2.5 2.5l-.1.1a1.8 1.8 0 0 0 .9 3h.2a1.8 1.8 0 0 1 0 3.6h-.2a1.8 1.8 0 0 0-.9 3Z" /></>,
    message: <><path d="M20 11.5a7.5 7.5 0 0 1-8 7.5 8.8 8.8 0 0 1-3.2-.6L4 20l1.5-4A7.2 7.2 0 0 1 4 11.5 7.5 7.5 0 0 1 12 4a7.5 7.5 0 0 1 8 7.5Z" /><path d="M8 12h.01M12 12h.01M16 12h.01" /></>,
    compass: <><circle cx="12" cy="12" r="9" /><path d="m15.7 8.3-2.1 5.3-5.3 2.1 2.1-5.3 5.3-2.1Z" /></>,
    shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" /><path d="m9 12 2 2 4-4" /></>,
    sparkle: <><path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Z" /><path d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z" /></>,
    star: <><path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.9L12 18l-6.2 3.1 1.2-6.9-5-4.9 6.9-1L12 2Z" /></>,
    alert: <><path d="M10.3 3.3 1.5 18a2 2 0 0 0 1.7 3h17.6a2 2 0 0 0 1.7-3L13.7 3.3a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/></>,
    check: <><path d="M20 6 9 17l-5-5"/></>,
    toggle: <><rect x="1" y="5" width="22" height="14" rx="7"/><circle cx="16" cy="12" r="3"/></>,
  };

  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.sparkle}
    </svg>
  );
}

function BrandMark({ small = false }) {
  return (
    <svg
      className={`brand-mark ${small ? "brand-mark-small" : ""}`}
      viewBox="0 0 40 40"
      fill="none"
      aria-hidden="true"
    >
      <path className="brand-bubble" d="M9 9.5A4.5 4.5 0 0 1 13.5 5h13A4.5 4.5 0 0 1 31 9.5v12a4.5 4.5 0 0 1-4.5 4.5h-6l-6 5v-5h-1A4.5 4.5 0 0 1 9 21.5v-12Z" />
      <path className="brand-wave" d="M15 16v3m5-7v11m5-8v5" />
    </svg>
  );
}

function SourceList({ sources }) {
  if (!sources?.length) return null;
  return (
    <div className="source-list" aria-label="Answer sources">
      <div className="source-heading"><span className="source-rule" />Based on these sources</div>
      <div className="source-cards">
        {sources.map((source) => (
          <details className="source-card" key={source.id}>
            <summary>
              <span className="source-dot" />
              <span className="source-title">{source.title}</span>
              <Icon name="arrow" className="source-arrow" />
            </summary>
            <p>{source.excerpt}</p>
            <div className="source-meta">
              <span>{source.source}{source.page ? ` · page ${source.page}` : ""}</span>
              <span>Match {(source.score * 100).toFixed(0)}%</span>
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}

// ── Escalation notice banner ────────────────────────────────────────────────

function EscalationBanner({ reason, requiresClarification }) {
  if (!reason && !requiresClarification) return null;
  const isClarification = requiresClarification && !reason?.includes("escalated");

  if (isClarification) {
    return (
      <div className="escalation-banner escalation-clarify" role="status">
        <Icon name="alert" className="escalation-icon" />
        <span>Clarification needed — could you rephrase or specify the topic?</span>
      </div>
    );
  }

  const label =
    reason === "explicit_request"
      ? "Marked for possible staff follow-up in this chat only — staff were not notified."
      : reason === "grievance"
      ? "Grievance flagged locally — this prototype did not notify staff."
      : reason === "negative_sentiment"
      ? "Concern flagged locally — no support ticket or staff notification was sent."
      : reason === "low_confidence"
      ? "Low confidence — please clarify your question."
      : reason === "insufficient_evidence"
      ? "Limited information available in the knowledge base."
      : "Flagged locally for review — no staff notification was sent.";

  return (
    <div className="escalation-banner escalation-alert" role="alert">
      <Icon name="alert" className="escalation-icon" />
      <span>{label}</span>
    </div>
  );
}

// ── Star rating widget ──────────────────────────────────────────────────────

function StarRating({ sessionId, telemetryEnabled }) {
  const [hover, setHover] = useState(0);
  const [selected, setSelected] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  if (!sessionId || !telemetryEnabled) return null;
  if (submitted) {
    return (
      <div className="star-rating-done" aria-live="polite">
        <Icon name="check" className="star-check-icon" />
        <span>Thanks for your feedback!</span>
      </div>
    );
  }

  const handleRate = async (rating) => {
    setSelected(rating);
    setSubmitting(true);
    setError("");
    try {
      await submitFeedback(sessionId, rating, telemetryEnabled);
      setSubmitted(true);
    } catch {
      setError("Could not save rating. Please try again.");
      setSelected(0);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="star-rating" aria-label="Rate this response">
      <span className="star-label">Was this helpful?</span>
      <div className="star-buttons" role="group" aria-label="Rating: 1 to 5 stars">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            className={`star-btn ${n <= (hover || selected) ? "star-filled" : ""}`}
            aria-label={`Rate ${n} out of 5`}
            aria-pressed={selected === n}
            disabled={submitting}
            onMouseEnter={() => setHover(n)}
            onMouseLeave={() => setHover(0)}
            onClick={() => handleRate(n)}
          >
            <Icon name="star" />
          </button>
        ))}
      </div>
      {error && <span className="star-error" role="alert">{error}</span>}
    </div>
  );
}

// ── Intent badge ────────────────────────────────────────────────────────────

function IntentBadge({ intent }) {
  if (!intent) return null;
  const intentColors = {
    admissions: "#3d7fa8",
    schedule: "#4a8a6a",
    fees: "#8a6a3d",
    exams: "#7a4d8a",
    grievance: "#a84d4d",
    hostel: "#4d7a8a",
    library: "#6a7a4d",
  };
  const color = intentColors[intent] || "#647880";
  return (
    <span
      className="intent-badge"
      style={{ "--badge-color": color }}
      title={`Classified intent: ${intent}`}
    >
      {intent}
    </span>
  );
}

function TelemetryPreference({ enabled, onToggle, variant = "sidebar" }) {
  return (
    <div className={`telemetry-toggle-row telemetry-toggle-${variant}`} role="group" aria-label="Session analytics preference">
      <div className="telemetry-toggle-label">
        <span>Session analytics</span>
        <span className="telemetry-toggle-sub">No query or answer text is saved to telemetry</span>
      </div>
      <button
        type="button"
        className={`telemetry-btn ${enabled ? "telemetry-on" : "telemetry-off"}`}
        aria-pressed={enabled}
        aria-label={enabled ? "Disable session analytics" : "Enable session analytics"}
        onClick={onToggle}
        title={enabled ? "Analytics on — click to opt out" : "Analytics off — click to opt in"}
      >
        <span className="telemetry-thumb" />
      </button>
    </div>
  );
}

function Sidebar({ open, collapsed, activeItem, onClose, onNewChat, onSelect, telemetryEnabled, onToggleTelemetry }) {
  return (
    <>
      {open && <button className="sidebar-scrim" type="button" aria-label="Close navigation" onClick={onClose} />}
      <aside className={`sidebar ${open ? "sidebar-open" : ""} ${collapsed ? "sidebar-collapsed" : ""}`} aria-label="Vakta navigation">
        <div className="sidebar-top">
          <a className="wordmark" href="#top" onClick={onClose} aria-label="Vakta home">
            <BrandMark />
            <span>Vakta</span>
          </a>
          <button className="icon-button sidebar-close" type="button" onClick={onClose} aria-label="Close navigation">
            <Icon name="close" />
          </button>
        </div>
        <p className="brand-tagline">Your Campus Companion</p>

        <button className="new-chat-button" type="button" onClick={onNewChat}>
          <Icon name="plus" className="button-icon" />
          <span>New Conversation</span>
        </button>

        <nav className="sidebar-nav" aria-label="Main navigation">
          <span className="sidebar-section-label">STUDENT SPACE</span>
          {TOPICS.map((item) => (
            <button
              className={`nav-item ${activeItem === item.id ? "nav-item-active" : ""}`}
              type="button"
              key={item.id}
              onClick={() => { onSelect(item.id); onClose(); }}
              aria-current={activeItem === item.id ? "page" : undefined}
            >
              <Icon name={item.icon} className="nav-icon" />
              <span>{item.label}</span>
              {activeItem === item.id && <span className="nav-pip" />}
            </button>
          ))}
        </nav>

        <nav className="sidebar-utilities" aria-label="Resources and support">
          <span className="sidebar-section-label">MORE</span>
          {UTILITIES.map((item) => (
            <button
              className={`nav-item ${activeItem === item.id ? "nav-item-active" : ""}`}
              type="button"
              key={item.id}
              onClick={() => { onSelect(item.id); onClose(); }}
              aria-current={activeItem === item.id ? "page" : undefined}
            >
              <Icon name={item.icon} className="nav-icon" />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <TelemetryPreference enabled={telemetryEnabled} onToggle={onToggleTelemetry} />

        <div className="sidebar-footer-note">
          <span className="footer-status-dot" />
          <span>University information, made easier to find.</span>
        </div>
      </aside>
    </>
  );
}

function PromptList({ questions, onAsk, label = "SUGGESTED QUESTIONS" }) {
  return (
    <div className="prompt-list">
      <span className="suggestion-label">{label}</span>
      <div className="suggestion-grid">
        {questions.map((question) => (
          <button className="suggestion-card" type="button" key={question} onClick={() => onAsk(question)}>
            <span>{question}</span>
            <Icon name="arrow" className="suggestion-arrow" />
          </button>
        ))}
      </div>
    </div>
  );
}

function SupportLanding({ activeItem, onSuggest, onSelect }) {
  const section = SUPPORT_SECTIONS[activeItem] || SUPPORT_SECTIONS["student-support"];
  const isHome = activeItem === "student-support";

  return (
    <section className={`support-landing ${isHome ? "support-home" : ""}`} aria-labelledby="landing-title">
      <div className="landing-copy">
        <span className="welcome-eyebrow"><span className="eyebrow-mark" />{isHome ? "YOUR CAMPUS, A LITTLE CLOSER" : "VAKTA STUDENT SUPPORT"}</span>
        <h1 id="landing-title">{isHome ? <>Welcome to <span>Vakta</span></> : section.title}</h1>
        <p>{isHome
          ? "Your university companion for academic guidance, campus information, and student support. Ask a question and Vakta will search the information available to it."
          : section.description}</p>
      </div>

      {isHome && (
        <div className="quick-links" aria-label="Browse support topics">
          {["academics", "examinations", "fees", "campus"].map((id) => (
            <button className="quick-link" type="button" key={id} onClick={() => onSelect(id)}>
              <span>{SUPPORT_SECTIONS[id].title}</span>
              <Icon name="arrow" />
            </button>
          ))}
        </div>
      )}

      <PromptList questions={section.suggestions} onAsk={onSuggest} label={isHome ? "A FEW PLACES TO START" : "TRY A QUESTION"} />
    </section>
  );
}

function FaqPage({ onAsk, onBack }) {
  const [search, setSearch] = useState("");
  const faqStarters = [...new Set(SUGGESTIONS)];
  const filteredStarters = faqStarters.filter((question) => question.toLowerCase().includes(search.trim().toLowerCase()));

  return (
    <section className="utility-page" aria-labelledby="faq-title">
      <div className="utility-page-header">
        <span className="welcome-eyebrow"><span className="eyebrow-mark" />ANSWERS FROM VAKTA</span>
        <h1 id="faq-title">FAQs</h1>
        <p>Search common question starters, then ask Vakta to look for an answer in the indexed university information.</p>
      </div>
      <label className="search-field">
        <Icon name="help" />
        <span className="sr-only">Search question starters</span>
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search question starters" />
        {search && <button type="button" className="search-clear" onClick={() => setSearch("")}>Clear</button>}
      </label>
      {filteredStarters.length > 0 ? (
        <PromptList questions={filteredStarters} onAsk={onAsk} label="QUESTION STARTERS" />
      ) : (
        <p className="empty-search">No matching question starters. Try asking Vakta directly.</p>
      )}
      <div className="honest-note">
        <Icon name="shield" />
        <p>There is no separate FAQ answer set in this frontend. These are prompts, not prewritten university answers.</p>
      </div>
      <button className="text-action" type="button" onClick={onBack}>Ask a different question in chat <span aria-hidden="true">→</span></button>
    </section>
  );
}

function SettingsPage({ telemetryEnabled, onToggleTelemetry }) {
  return (
    <section className="utility-page" aria-labelledby="settings-title">
      <div className="utility-page-header">
        <span className="welcome-eyebrow"><span className="eyebrow-mark" />YOUR PREFERENCES</span>
        <h1 id="settings-title">Settings</h1>
        <p>Manage the session analytics preference used by this browser.</p>
      </div>
      <div className="settings-panel">
        <div>
          <h2>Session analytics</h2>
          <p>When disabled, Vakta sends the existing opt-out header with chat requests. This setting does not control other backend storage. The preference is kept in this browser when local storage is available.</p>
        </div>
        <TelemetryPreference enabled={telemetryEnabled} onToggle={onToggleTelemetry} variant="settings" />
        <span className="preference-status">Current setting: {telemetryEnabled ? "on" : "off"}</span>
      </div>
    </section>
  );
}

function HelpPage({ onBack, onSelect }) {
  return (
    <section className="utility-page" aria-labelledby="help-title">
      <div className="utility-page-header">
        <span className="welcome-eyebrow"><span className="eyebrow-mark" />USING YOUR CAMPUS COMPANION</span>
        <h1 id="help-title">Help &amp; Support</h1>
        <p>Ask a clear question about university life. Vakta searches its indexed information and may return source references with an answer.</p>
      </div>
      <div className="help-steps">
        <div><span>01</span><p><strong>Ask one question at a time.</strong> Include the course, service, or topic you mean when it helps.</p></div>
        <div><span>02</span><p><strong>Check the sources.</strong> Expand a source under an answer to read its excerpt and origin.</p></div>
        <div><span>03</span><p><strong>Confirm important details.</strong> Answers can be incomplete; use the university’s official information for decisions.</p></div>
      </div>
      <div className="help-actions">
        <button className="primary-action" type="button" onClick={() => onSelect("student-support")}>Ask Vakta a question</button>
        <button className="text-action" type="button" onClick={onBack}>Return to Student Support</button>
      </div>
    </section>
  );
}

function inlineText(text, keyPrefix) {
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g).filter(Boolean);
  return tokens.map((token, index) => {
    const key = `${keyPrefix}-${index}`;
    if (token.startsWith("**") && token.endsWith("**")) return <strong key={key}>{token.slice(2, -2)}</strong>;
    if (token.startsWith("*") && token.endsWith("*")) return <em key={key}>{token.slice(1, -1)}</em>;
    if (token.startsWith("`") && token.endsWith("`")) return <code key={key}>{token.slice(1, -1)}</code>;
    return token;
  });
}

function MessageBody({ content }) {
  const blocks = content.split(/\n\s*\n/).filter((block) => block.trim());
  return blocks.map((block, blockIndex) => {
    const lines = block.split("\n");
    const heading = lines.length === 1 && /^(#{1,3})\s+/.exec(lines[0]);
    if (heading) {
      const Heading = heading[1].length === 1 ? "h3" : "h4";
      return <Heading key={`block-${blockIndex}`}>{inlineText(lines[0].slice(heading[0].length), `h-${blockIndex}`)}</Heading>;
    }
    if (lines.every((line) => /^\s*[-*]\s+/.test(line))) {
      return <ul key={`block-${blockIndex}`}>{lines.map((line, index) => <li key={`li-${index}`}>{inlineText(line.replace(/^\s*[-*]\s+/, ""), `li-${blockIndex}-${index}`)}</li>)}</ul>;
    }
    if (lines.every((line) => /^\s*\d+[.)]\s+/.test(line))) {
      return <ol key={`block-${blockIndex}`}>{lines.map((line, index) => <li key={`li-${index}`}>{inlineText(line.replace(/^\s*\d+[.)]\s+/, ""), `ol-${blockIndex}-${index}`)}</li>)}</ol>;
    }
    return <p key={`block-${blockIndex}`}>{lines.map((line, index) => <span key={`line-${index}`}>{index > 0 && <br />}{inlineText(line, `p-${blockIndex}-${index}`)}</span>)}</p>;
  });
}

function Conversation({ messages, isLoading, scrollRef, telemetryEnabled, activeSection, onRetry }) {
  return (
    <div className="conversation" ref={scrollRef} aria-live="polite" aria-label="Conversation">
      <div className="conversation-width">
        {activeSection.id !== "student-support" && (
          <div className="conversation-context">
            <span>{activeSection.title}</span>
            <p>{activeSection.description}</p>
          </div>
        )}
        <div className="date-divider"><span /> CURRENT CONVERSATION <span /></div>
        {messages.map((message) => (
          <article className={`message-row ${message.role === "user" ? "message-user-row" : ""}`} key={message.id}>
            {message.role === "assistant" && <div className="assistant-avatar"><BrandMark small /></div>}
            <div className={`message-content ${message.role === "user" ? "user-content" : ""}`}>
              <div className="message-meta">
                <strong>{message.role === "user" ? "You" : "Vakta"}</strong>
                {message.isError && <span className="error-label">CONNECTION ISSUE</span>}
                {message.role === "assistant" && message.intent && (
                  <IntentBadge intent={message.intent} />
                )}
              </div>
              <div className={`message-bubble ${message.role === "user" ? "user-bubble" : "assistant-bubble"} ${message.isError ? "error-bubble" : ""}`}>
                <MessageBody content={message.content} />
              </div>
              {message.isError && message.retry && (
                <button className="retry-action" type="button" onClick={() => onRetry(message)} disabled={isLoading}>
                  <Icon name="arrow" /> Retry
                </button>
              )}
              {message.role === "assistant" && (message.escalated || message.requires_clarification) && (
                <EscalationBanner
                  reason={message.escalation_reason}
                  requiresClarification={message.requires_clarification}
                />
              )}
              {message.sources?.length > 0 && <SourceList sources={message.sources} />}
              {message.role === "assistant" && !message.isError && message.session_id && (
                <StarRating
                  sessionId={message.session_id}
                  telemetryEnabled={telemetryEnabled}
                />
              )}
            </div>
          </article>
        ))}
        {isLoading && (
          <div className="message-row" role="status" aria-label="Vakta is looking for an answer">
            <div className="assistant-avatar"><BrandMark small /></div>
            <div className="message-content">
              <div className="message-meta"><strong>Vakta</strong><span className="thinking-label">SEARCHING UNIVERSITY INFORMATION</span></div>
              <div className="typing-bubble"><span /><span /><span /></div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeItem, setActiveItem] = useState("student-support");
  const [backendStatus, setBackendStatus] = useState("checking");
  const [inputError, setInputError] = useState("");
  const [telemetryEnabled, setTelemetryEnabled] = useState(loadTelemetryPreference);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const scrollRef = useRef(null);
  const textareaRef = useRef(null);
  const conversationEpochRef = useRef(0);
  const pendingEpochRef = useRef(null);

  useEffect(() => {
    let active = true;
    getBackendHealth()
      .then((health) => {
        if (active) setBackendStatus(health.retrieval_ready ? "ready" : "degraded");
      })
      .catch(() => {
        if (active) setBackendStatus("offline");
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, isLoading]);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [menuOpen]);

  const startNewChat = () => {
    conversationEpochRef.current += 1;
    setMessages([]);
    setInput("");
    setInputError("");
    setActiveItem("student-support");
    setMenuOpen(false);
    setIsLoading(false);
    setCurrentSessionId(null);
    textareaRef.current?.focus();
  };

  const requestAnswer = async ({ question, previousTurns, sessionId, epoch, errorId }) => {
    if (pendingEpochRef.current === epoch) return;
    pendingEpochRef.current = epoch;
    setIsLoading(true);
    if (errorId) setMessages((current) => current.filter((message) => message.id !== errorId));

    try {
      const payload = await sendChat(question, previousTurns, sessionId, telemetryEnabled);
      if (epoch !== conversationEpochRef.current) return;
      if (payload.session_id) setCurrentSessionId(payload.session_id);
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: payload.answer,
          sources: payload.sources || [],
          session_id: payload.session_id || null,
          intent: payload.intent || null,
          confidence_score: payload.confidence_score || null,
          escalated: payload.escalated || false,
          escalation_reason: payload.escalation_reason || null,
          requires_clarification: payload.requires_clarification || false,
        },
      ]);
    } catch (error) {
      if (epoch !== conversationEpochRef.current) return;
      setMessages((current) => [
        ...current,
        {
          id: `error-${Date.now()}`,
          role: "assistant",
          content: error.message || "We couldn't reach Vakta. Please check the backend and try again.",
          sources: [],
          isError: true,
          retry: { question, previousTurns, sessionId, epoch },
        },
      ]);
    } finally {
      if (pendingEpochRef.current === epoch) pendingEpochRef.current = null;
      if (epoch === conversationEpochRef.current) {
        setIsLoading(false);
        textareaRef.current?.focus();
      }
    }
  };

  const sendMessage = (value = input) => {
    const question = value.trim();
    const epoch = conversationEpochRef.current;
    if (!question || pendingEpochRef.current === epoch) {
      if (!question) setInputError("Type a question to get started.");
      return;
    }
    setInputError("");
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "";
    const previousTurns = messages
      .filter((message) => ["user", "assistant"].includes(message.role) && !message.isError)
      .slice(-8)
      .map(({ role, content }) => ({ role, content }));
    setMessages((current) => [...current, { id: `user-${Date.now()}`, role: "user", content: question }]);
    void requestAnswer({ question, previousTurns, sessionId: currentSessionId, epoch });
  };

  const retryMessage = (message) => {
    if (!message.retry || message.retry.epoch !== conversationEpochRef.current) return;
    void requestAnswer({ ...message.retry, errorId: message.id });
  };

  const onSubmit = (event) => {
    event.preventDefault();
    sendMessage();
  };

  const onKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  const onToggleSidebar = () => {
    if (window.matchMedia("(max-width: 800px)").matches) {
      setMenuOpen((open) => !open);
    } else {
      setSidebarCollapsed((collapsed) => !collapsed);
    }
  };

  const handleNavSelect = (id) => {
    setActiveItem(id);
    setMenuOpen(false);
  };

  const statusText = {
    checking: "Checking knowledge base",
    ready: "Knowledge base ready",
    degraded: "Knowledge base unavailable",
    offline: "Backend unavailable",
  }[backendStatus];

  const handleInputChange = (event) => {
    setInput(event.target.value);
    if (inputError) setInputError("");
    event.target.style.height = "auto";
    event.target.style.height = `${Math.min(event.target.scrollHeight, 136)}px`;
  };

  const toggleTelemetry = () => {
    setTelemetryEnabled((enabled) => {
      const next = !enabled;
      try {
        window.localStorage.setItem(TELEMETRY_PREFERENCE_KEY, String(next));
      } catch {
        // The in-memory opt-out still applies if browser storage is unavailable.
      }
      return next;
    });
  };

  const activePage = [...TOPICS, ...UTILITIES].find((item) => item.id === activeItem) || TOPICS[0];
  const isSupportSection = Boolean(SUPPORT_SECTIONS[activeItem]);
  const returnToSupport = () => handleNavSelect("student-support");

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`} id="top">
      <Sidebar
        open={menuOpen}
        collapsed={sidebarCollapsed}
        activeItem={activeItem}
        onClose={() => setMenuOpen(false)}
        onNewChat={startNewChat}
        onSelect={handleNavSelect}
        telemetryEnabled={telemetryEnabled}
        onToggleTelemetry={toggleTelemetry}
      />

      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button sidebar-toggle" type="button" onClick={onToggleSidebar} aria-label="Toggle navigation" aria-expanded={window.matchMedia("(max-width: 800px)").matches ? menuOpen : !sidebarCollapsed}>
              <Icon name="menu" />
            </button>
            <span className="topbar-brand">Vakta</span>
            <span className="breadcrumb-slash">/</span>
            <span className="topbar-current">{activePage.label}</span>
          </div>
          <div className="topbar-actions">
            <div className={`system-status status-${backendStatus}`} title="Live document retrieval status" role="status">
              <span className="status-indicator" />
              <span>{statusText}</span>
            </div>
            <button className="topbar-new-chat" type="button" onClick={startNewChat}>
              <Icon name="plus" />
              <span>New Chat</span>
            </button>
          </div>
        </header>

        {activeItem === "faqs" ? (
          <FaqPage onAsk={(question) => { handleNavSelect("student-support"); sendMessage(question); }} onBack={returnToSupport} />
        ) : activeItem === "settings" ? (
          <SettingsPage telemetryEnabled={telemetryEnabled} onToggleTelemetry={toggleTelemetry} />
        ) : activeItem === "help-support" ? (
          <HelpPage onBack={returnToSupport} onSelect={handleNavSelect} />
        ) : (
          <section className="chat-workspace" aria-label={`${activePage.label} support`}>
            <div className={`chat-stage ${messages.length === 0 ? "chat-stage-welcome" : "chat-stage-conversation"}`}>
              {messages.length === 0
                ? <SupportLanding activeItem={activeItem} onSuggest={sendMessage} onSelect={handleNavSelect} />
                : <Conversation
                    messages={messages}
                    isLoading={isLoading}
                    scrollRef={scrollRef}
                    telemetryEnabled={telemetryEnabled}
                    activeSection={isSupportSection ? SUPPORT_SECTIONS[activeItem] : SUPPORT_SECTIONS["student-support"]}
                    onRetry={retryMessage}
                  />}
            </div>

            <div className="composer-area">
              <form className="composer" onSubmit={onSubmit}>
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={onKeyDown}
                  placeholder={`Ask Vakta about ${activeItem === "student-support" ? "university life" : activePage.label.toLowerCase()}…`}
                  aria-label="Ask Vakta a question"
                  maxLength={1200}
                  disabled={isLoading}
                />
                <button className="send-button" type="submit" disabled={isLoading || !input.trim()} aria-label={isLoading ? "Sending question" : "Send question"}>
                  <Icon name="send" />
                </button>
              </form>
              <div className="composer-footnote" aria-live="polite">
                <span className={inputError ? "composer-error" : "composer-grounding"}>
                  {inputError || <><Icon name="shield" />Answers are grounded in indexed university information.</>}
                </span>
                <span><kbd>Enter</kbd> sends <span className="footnote-separator">·</span> <kbd>Shift + Enter</kbd> adds a line</span>
              </div>
            </div>
            <p className="disclaimer">Vakta can make mistakes. Confirm important details with your university.</p>
          </section>
        )}
      </main>
    </div>
  );
}
