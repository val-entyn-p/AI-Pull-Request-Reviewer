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

const TRUST_COLORS = {
  "maintainer": "#a78bfa",
  "contributor": "#4ade80",
  "occasional": "#facc15",
  "first-timer": "#60a5fa"
}

const TRUST_LABELS = {
  "maintainer": "⚡ Maintainer",
  "contributor": "✓ Contributor",
  "occasional": "◎ Occasional",
  "first-timer": "★ First Timer"
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

function TrustBadge({ level }) {
  return (
    <span style={{
      background: TRUST_COLORS[level] + "22",
      color: TRUST_COLORS[level],
      border: `1px solid ${TRUST_COLORS[level]}44`,
      padding: "2px 10px",
      borderRadius: "4px",
      fontSize: "12px",
      fontFamily: "monospace",
      fontWeight: "600"
    }}>
      {TRUST_LABELS[level]}
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

function AuthorTab({ author }) {
  return (
    <div style={{ marginTop: "24px" }}>
      {/* Author header */}
      <div style={{
        background: "#161b22",
        border: "1px solid #30363d",
        borderRadius: "10px",
        padding: "20px 24px",
        marginBottom: "16px",
        display: "flex",
        alignItems: "center",
        gap: "20px"
      }}>
        <img
          src={author.avatar_url}
          alt={author.username}
          style={{ width: "64px", height: "64px", borderRadius: "50%", border: "2px solid #30363d" }}
        />
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "6px" }}>
            <span style={{ color: "#e6edf3", fontSize: "18px", fontWeight: "600" }}>
              {author.name}
            </span>
            <TrustBadge level={author.trust_level} />
          </div>
          <a
            href={author.profile_url}
            target="_blank"
            rel="noreferrer"
            style={{ color: "#6e7681", fontFamily: "monospace", fontSize: "13px", textDecoration: "none" }}
          >
            @{author.username} ↗
          </a>
          {author.bio && (
            <p style={{ color: "#8b949e", fontSize: "13px", margin: "6px 0 0 0" }}>{author.bio}</p>
          )}
        </div>
      </div>

      {/* Stats grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px", marginBottom: "16px" }}>
        {[
          { label: "Commits to Repo", value: author.commit_count_to_repo, color: "#4ade80" },
          { label: "PRs to Repo", value: author.pr_count_to_repo, color: "#60a5fa" },
          { label: "PR Commits", value: author.pr_commits, color: "#facc15" },
        ].map(stat => (
          <div key={stat.label} style={{
            background: "#161b22",
            border: "1px solid #30363d",
            borderRadius: "8px",
            padding: "16px",
            textAlign: "center"
          }}>
            <div style={{ color: stat.color, fontSize: "28px", fontWeight: "700", fontFamily: "monospace" }}>
              {stat.value}
            </div>
            <div style={{ color: "#6e7681", fontSize: "12px", marginTop: "4px" }}>{stat.label}</div>
          </div>
        ))}
      </div>

      {/* PR details */}
      <div style={{
        background: "#161b22",
        border: "1px solid #30363d",
        borderRadius: "10px",
        padding: "20px 24px",
        marginBottom: "16px"
      }}>
        <div style={{
          color: "#6e7681", fontSize: "12px", fontFamily: "monospace",
          textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "14px"
        }}>
          // PR Details
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
          {[
            { label: "Files Changed", value: author.pr_changed_files },
            { label: "Lines Added", value: `+${author.pr_additions}` },
            { label: "Lines Removed", value: `-${author.pr_deletions}` },
            { label: "Account Age", value: `${author.account_age_years} years` },
            { label: "Public Repos", value: author.public_repos },
            { label: "Followers", value: author.followers }
          ].map(item => (
            <div key={item.label} style={{
              display: "flex", justifyContent: "space-between",
              padding: "8px 0", borderBottom: "1px solid #21262d"
            }}>
              <span style={{ color: "#6e7681", fontSize: "13px" }}>{item.label}</span>
              <span style={{ color: "#e6edf3", fontSize: "13px", fontFamily: "monospace" }}>{item.value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Trust explanation */}
      <div style={{
        background: "#161b22",
        border: `1px solid ${TRUST_COLORS[author.trust_level]}33`,
        borderLeft: `3px solid ${TRUST_COLORS[author.trust_level]}`,
        borderRadius: "6px",
        padding: "12px 16px",
      }}>
        <div style={{ color: TRUST_COLORS[author.trust_level], fontSize: "12px", fontFamily: "monospace", marginBottom: "4px" }}>
          {TRUST_LABELS[author.trust_level]}
        </div>
        <p style={{ color: "#8b949e", fontSize: "13px", margin: 0 }}>
          {author.trust_level === "maintainer" && "This contributor has write access to the repository. High trust."}
          {author.trust_level === "contributor" && `This contributor has made ${author.commit_count_to_repo} commits to this repo. Established trust.`}
          {author.trust_level === "occasional" && `This contributor has made ${author.commit_count_to_repo} commit(s) to this repo. Review carefully.`}
          {author.trust_level === "first-timer" && "This is the author's first contribution to this repo. Review with extra care."}
        </p>
      </div>
    </div>
  )
}

function ReviewResult({ result, prUrl }) {
  // result = { pr_url, review: { summary, bugs, style_issues, suggestions, overall_severity, approve } }
  const review = result.review
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
            <SeverityBadge severity={review.overall_severity} />
            <span style={{
              color: review.approve ? "#4ade80" : "#ef4444",
              fontFamily: "monospace",
              fontSize: "13px",
              fontWeight: "600"
            }}>
              {review.approve ? "✓ APPROVE" : "✗ REQUEST CHANGES"}
            </span>
          </div>
          <p style={{ color: "#c9d1d9", fontSize: "14px", margin: 0, lineHeight: "1.6" }}>
            {review.summary}
          </p>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px", marginBottom: "20px" }}>
        {[
          { label: "Bugs", count: review.bugs.length, color: "#ef4444" },
          { label: "Style Issues", count: review.style_issues.length, color: "#facc15" },
          { label: "Suggestions", count: review.suggestions.length, color: "#60a5fa" }
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
        review[section.key]?.length > 0 && (
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
              {section.icon} {section.label} ({review[section.key].length})
            </h3>
            {review[section.key].map((issue, i) => (
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
  const [author, setAuthor] = useState(null)
  const [activeTab, setActiveTab] = useState("review")

  async function handleReview() {
  if (!prUrl.trim()) return
  setLoading(true)
  setError(null)
  setResult(null)
  setAuthor(null)
  setActiveTab("review")

  try {
    const [reviewRes, authorRes] = await Promise.all([
      axios.post(`${API_URL}/review-pr`, { pr_url: prUrl }),
      axios.get(`${API_URL}/pr-author`, { params: { pr_url: prUrl } })
    ])
    setResult(reviewRes.data)
    setAuthor(authorRes.data)
    setHistory(prev => [{ prUrl, result: reviewRes.data, time: new Date().toLocaleTimeString() }, ...prev.slice(0, 9)])
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

        {/* Tabs */}
        {result && (
          <>
            <div style={{ display: "flex", gap: "4px", marginTop: "32px", borderBottom: "1px solid #21262d" }}>
              {[
                { key: "review", label: "// Code Review" },
                { key: "author", label: "// Author Info" }
              ].map(tab => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  style={{
                    background: activeTab === tab.key ? "#161b22" : "transparent",
                    color: activeTab === tab.key ? "#e6edf3" : "#6e7681",
                    border: "1px solid",
                    borderColor: activeTab === tab.key ? "#30363d" : "transparent",
                    borderBottom: activeTab === tab.key ? "1px solid #161b22" : "1px solid transparent",
                    borderRadius: "6px 6px 0 0",
                    padding: "8px 16px",
                    fontFamily: "monospace",
                    fontSize: "13px",
                    cursor: "pointer",
                    marginBottom: "-1px"
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            {activeTab === "review" && <ReviewResult result={result} prUrl={result.pr_url} />}
            {activeTab === "author" && author && <AuthorTab author={author} />}
          </>
        )}

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