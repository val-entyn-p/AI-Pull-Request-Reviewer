import { useState } from "react"
import axios from "axios"
import "./App.css"

const API_URL = "http://127.0.0.1:8000"

const SEVERITY_COLORS = {
  low: "#4ade80",
  medium: "#facc15",
  high: "#f97316",
  critical: "#ef4444"
}

function SeverityBadge({ severity }) {
  return (
    <span style={{
      background: SEVERITY_COLORS[severity] + "22",
      color: SEVERITY_COLORS[severity],
      border: `1px solid ${SEVERITY_COLORS[severity]}44`,
      padding: "2px 10px",
      borderRadius: "4px",
      fontSize: "12px",
      fontFamily: "monospace",
      fontWeight: "600",
      textTransform: "uppercase",
      letterSpacing: "0.05em"
    }}>
      {severity}
    </span>
  )
}

function IssueCard({ issue, type }) {
  const icons = { bugs: "⚠", style_issues: "◈", suggestions: "→" }
  const colors = { bugs: "#ef4444", style_issues: "#facc15", suggestions: "#60a5fa" }

  return (
    <div style={{
      background: "#0d1117",
      border: `1px solid ${colors[type]}33`,
      borderLeft: `3px solid ${colors[type]}`,
      borderRadius: "6px",
      padding: "12px 16px",
      marginBottom: "8px"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
        <span style={{ color: colors[type], fontFamily: "monospace", fontSize: "13px" }}>
          {icons[type]} {issue.file}
          {issue.line && <span style={{ color: "#6e7681" }}>:{issue.line}</span>}
        </span>
        {issue.severity && <SeverityBadge severity={issue.severity} />}
      </div>
      <p style={{ color: "#8b949e", fontSize: "14px", margin: 0, lineHeight: "1.5" }}>
        {issue.description}
      </p>
    </div>
  )
}

function ReviewResult({ result, prUrl }) {
  const sections = [
    { key: "bugs", label: "Bugs", icon: "⚠" },
    { key: "style_issues", label: "Style Issues", icon: "◈" },
    { key: "suggestions", label: "Suggestions", icon: "→" }
  ]

  return (
    <div style={{ marginTop: "32px" }}>
      {/* Header */}
      <div style={{
        background: "#161b22",
        border: "1px solid #30363d",
        borderRadius: "10px",
        padding: "20px 24px",
        marginBottom: "16px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start"
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "10px" }}>
            <span style={{ color: "#6e7681", fontFamily: "monospace", fontSize: "13px" }}>
              {prUrl.replace("https://github.com/", "")}
            </span>
            <SeverityBadge severity={result.overall_severity} />
            <span style={{
              color: result.approve ? "#4ade80" : "#ef4444",
              fontFamily: "monospace",
              fontSize: "13px",
              fontWeight: "600"
            }}>
              {result.approve ? "✓ APPROVE" : "✗ REQUEST CHANGES"}
            </span>
          </div>
          <p style={{ color: "#c9d1d9", fontSize: "14px", margin: 0, lineHeight: "1.6" }}>
            {result.summary}
          </p>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px", marginBottom: "20px" }}>
        {[
          { label: "Bugs", count: result.bugs.length, color: "#ef4444" },
          { label: "Style Issues", count: result.style_issues.length, color: "#facc15" },
          { label: "Suggestions", count: result.suggestions.length, color: "#60a5fa" }
        ].map(stat => (
          <div key={stat.label} style={{
            background: "#161b22",
            border: "1px solid #30363d",
            borderRadius: "8px",
            padding: "16px",
            textAlign: "center"
          }}>
            <div style={{ color: stat.color, fontSize: "28px", fontWeight: "700", fontFamily: "monospace" }}>
              {stat.count}
            </div>
            <div style={{ color: "#6e7681", fontSize: "12px", marginTop: "4px" }}>{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Issue sections */}
      {sections.map(section => (
        result.review[section.key]?.length > 0 && (
          <div key={section.key} style={{ marginBottom: "24px" }}>
            <h3 style={{
              color: "#8b949e",
              fontSize: "12px",
              fontFamily: "monospace",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              marginBottom: "10px",
              paddingBottom: "8px",
              borderBottom: "1px solid #21262d"
            }}>
              {section.icon} {section.label} ({result[section.key].length})
            </h3>
            {result[section.key].map((issue, i) => (
              <IssueCard key={i} issue={issue} type={section.key} />
            ))}
          </div>
        )
      ))}
    </div>
  )
}

export default function App() {
  const [prUrl, setPrUrl] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])

  async function handleReview() {
    if (!prUrl.trim()) return
    // delete tomorrow
    const response = await axios.post(`${API_URL}/review-pr`, { pr_url: prUrl })
    console.log("FULL RESPONSE:", JSON.stringify(response.data))
    setResult(response.data)

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await axios.post(`${API_URL}/review-pr`, { pr_url: prUrl })
      setResult(response.data)
      setHistory(prev => [{ prUrl, result: response.data, time: new Date().toLocaleTimeString() }, ...prev.slice(0, 9)])
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong. Is your backend running?")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0d1117",
      color: "#c9d1d9",
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace"
    }}>
      <div style={{ maxWidth: "860px", margin: "0 auto", padding: "48px 24px" }}>

        {/* Header */}
        <div style={{ marginBottom: "40px" }}>
          <div style={{ color: "#6e7681", fontSize: "12px", fontFamily: "monospace", marginBottom: "8px" }}>
            // AI CODE REVIEWER v1.0
          </div>
          <h1 style={{
            fontSize: "32px",
            fontWeight: "700",
            color: "#e6edf3",
            margin: "0 0 8px 0",
            letterSpacing: "-0.5px"
          }}>
            Pull Request Analyzer
          </h1>
          <p style={{ color: "#6e7681", fontSize: "14px", margin: 0 }}>
            Paste any public GitHub PR URL to get an instant AI code review
          </p>
        </div>

        {/* Input */}
        <div style={{ display: "flex", gap: "10px", marginBottom: "8px" }}>
          <input
            value={prUrl}
            onChange={e => setPrUrl(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleReview()}
            placeholder="https://github.com/owner/repo/pull/123"
            style={{
              flex: 1,
              background: "#161b22",
              border: "1px solid #30363d",
              borderRadius: "8px",
              padding: "12px 16px",
              color: "#e6edf3",
              fontFamily: "monospace",
              fontSize: "14px",
              outline: "none"
            }}
          />
          <button
            onClick={handleReview}
            disabled={loading}
            style={{
              background: loading ? "#21262d" : "#238636",
              color: loading ? "#6e7681" : "#ffffff",
              border: "none",
              borderRadius: "8px",
              padding: "12px 24px",
              fontFamily: "monospace",
              fontSize: "14px",
              fontWeight: "600",
              cursor: loading ? "not-allowed" : "pointer",
              transition: "all 0.15s",
              whiteSpace: "nowrap"
            }}
          >
            {loading ? "Analyzing..." : "Review PR →"}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div style={{
            background: "#21262d",
            border: "1px solid #ef444433",
            borderLeft: "3px solid #ef4444",
            borderRadius: "6px",
            padding: "12px 16px",
            color: "#ef4444",
            fontSize: "14px",
            marginTop: "12px",
            fontFamily: "monospace"
          }}>
            ✗ {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div style={{
            textAlign: "center",
            padding: "48px",
            color: "#6e7681",
            fontFamily: "monospace",
            fontSize: "14px"
          }}>
            <div style={{ marginBottom: "12px", fontSize: "24px" }}>⟳</div>
            Fetching PR and analyzing code...
          </div>
        )}

        {/* Results */}
        {result && <ReviewResult result={result.review} prUrl={result.pr_url} />}

        {/* History */}
        {history.length > 0 && (
          <div style={{ marginTop: "48px", borderTop: "1px solid #21262d", paddingTop: "24px" }}>
            <h3 style={{
              color: "#6e7681",
              fontSize: "12px",
              fontFamily: "monospace",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              marginBottom: "12px"
            }}>
              // Recent Reviews
            </h3>
            {history.map((item, i) => (
              <div
                key={i}
                onClick={() => { setPrUrl(item.prUrl); setResult(item.result) }}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 14px",
                  background: "#161b22",
                  border: "1px solid #21262d",
                  borderRadius: "6px",
                  marginBottom: "6px",
                  cursor: "pointer",
                  fontSize: "13px",
                  fontFamily: "monospace"
                }}
              >
                <span style={{ color: "#8b949e" }}>
                  {item.prUrl.replace("https://github.com/", "")}
                </span>
                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  <SeverityBadge severity={item.result.review.overall_severity} />
                  <span style={{ color: "#6e7681", fontSize: "12px" }}>{item.time}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}