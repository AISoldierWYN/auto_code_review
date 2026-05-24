/* global React, Ico */

// ─── History ────────────────────────────────────────────────────────────
function HistoryScreen() {
  const rows = window.CURRENT_HISTORY || [];
  if (rows.length === 0) {
    return (
      <div className="panel-empty">
        <h3>No review runs yet</h3>
        <p>Run a local diff, GitHub PR, or Gerrit CL from the Review page. Completed runs will appear here for this browser session.</p>
      </div>
    );
  }
  return (
    <div className="tbl-wrap">
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <div className="input" style={{ maxWidth: 320 }}>
          <Ico.Search className="ico" />
          <input placeholder="filter by CL, repo, author…" />
        </div>
        <button className="btn" disabled><Ico.Filter className="ico" />status: all</button>
        <button className="btn" disabled>repo: all</button>
        <span className="spacer" />
        <button className="btn" disabled><Ico.Plus className="ico" />new review</button>
      </div>
      <table className="tbl">
        <thead>
          <tr>
            <th style={{ width: 100 }}>CL</th>
            <th>Change</th>
            <th style={{ width: 130 }}>Repo</th>
            <th style={{ width: 90 }}>Author</th>
            <th style={{ width: 130 }}>Findings</th>
            <th style={{ width: 100 }}>Status</th>
            <th style={{ width: 90 }}>Time</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.cl} style={{ cursor: "pointer" }}>
              <td className="mono" style={{ color: "var(--accent)" }}>#{r.cl}</td>
              <td>
                <div className="title">{r.title}</div>
                <div className="sub">{r.branch}</div>
              </td>
              <td className="mono">{r.repo}</td>
              <td>
                <span className="avatar" style={{ width: 22, height: 22, fontSize: 10 }}>{r.author}</span>
              </td>
              <td>
                <div className="sev-cell">
                  {r.sev.c > 0 && <span className="chip critical"><span className="dot" />{r.sev.c}</span>}
                  {r.sev.w > 0 && <span className="chip warning"><span className="dot" />{r.sev.w}</span>}
                  {r.sev.s > 0 && <span className="chip suggestion"><span className="dot" />{r.sev.s}</span>}
                  {r.sev.c + r.sev.w + r.sev.s === 0 && <span className="chip"><span className="dot" />clean</span>}
                </div>
              </td>
              <td>
                <span className="chip accent">
                  <span className="dot" />{r.status}
                </span>
              </td>
              <td className="mono" style={{ color: "var(--muted)" }}>{r.at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Team ───────────────────────────────────────────────────────────────
function TeamScreen() {
  return (
    <div className="panel-empty">
      <h3>Organization data is not connected</h3>
      <p>Team membership and reviewer metrics need a real org directory or review platform API. Demo names are hidden here to keep production runs unambiguous.</p>
    </div>
  );
}

// ─── Stats ──────────────────────────────────────────────────────────────
function StatsScreen() {
  const rows = window.CURRENT_HISTORY || [];
  const totals = rows.reduce(
    (acc, row) => ({
      runs: acc.runs + 1,
      c: acc.c + (row.sev?.c || 0),
      w: acc.w + (row.sev?.w || 0),
      s: acc.s + (row.sev?.s || 0),
    }),
    { runs: 0, c: 0, w: 0, s: 0 }
  );
  if (rows.length === 0) {
    return (
      <div className="panel-empty">
        <h3>No local stats yet</h3>
        <p>Stats are derived from real review runs in this browser. Run a review first, then this page will summarize the resulting findings.</p>
      </div>
    );
  }
  return (
    <div>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="l">Review runs</div>
          <div className="v">{totals.runs}</div>
          <div className="d">local browser history</div>
        </div>
        <div className="stat-card">
          <div className="l">Findings</div>
          <div className="v">{totals.c + totals.w + totals.s}</div>
          <div className="d">all severities</div>
        </div>
        <div className="stat-card">
          <div className="l">Critical</div>
          <div className="v" style={{ color: "var(--critical)" }}>{totals.c}</div>
          <div className="d">must-fix findings</div>
        </div>
        <div className="stat-card">
          <div className="l">Latest source</div>
          <div className="v" style={{ fontSize: 20 }}>{rows[0].source || "local"}</div>
          <div className="d">{rows[0].at}</div>
        </div>
      </div>
      <div className="chart-row">
        <div className="chart-card">
          <h4><span>Recent runs</span><span className="sub">local</span></h4>
          <table className="tbl compact">
            <tbody>
              {rows.slice(0, 8).map((row) => (
                <tr key={`${row.cl}-${row.createdAt || row.at}`}>
                  <td className="mono">#{row.cl}</td>
                  <td>{row.title}</td>
                  <td className="mono">{row.sev.c}/{row.sev.w}/{row.sev.s}</td>
                  <td className="mono">{row.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ─── Settings ───────────────────────────────────────────────────────────
function SettingsScreen({ tweak, setTweak }) {
  const Tog = ({ on, onClick, disabled }) => (
    <span className={`toggle ${on ? "on" : ""} ${disabled ? "disabled" : ""}`} onClick={disabled ? undefined : onClick} />
  );
  const currentTarget = window.CURRENT_PR?.id || "No review loaded";
  const currentPlatform = window.getCurrentPublishPlatform ? (window.getCurrentPublishPlatform() || "local") : "local";
  return (
    <div className="set-wrap">
      <div className="set-section">
        <h3>Source</h3>
        <div className="set-row">
          <div className="l">
            <div>Current target</div>
            <div className="desc">Loaded from the latest review run.</div>
          </div>
          <div className="input" style={{ width: 320 }}>
            <input value={currentTarget} readOnly />
          </div>
        </div>
        <div className="set-row">
          <div className="l">
            <div>Detected platform</div>
            <div className="desc">Used by publish dry-run actions.</div>
          </div>
          <span className="chip accent"><span className="dot" />{currentPlatform}</span>
        </div>
        <div className="set-row">
          <div className="l">
            <div>Server endpoints</div>
            <div className="desc">Review, chat, and publish are served by the local aiohttp process.</div>
          </div>
          <span className="chip"><span className="dot" />/api/review · /api/chat · /api/publish</span>
        </div>
      </div>

      <div className="set-section">
        <h3>Reviewer behavior</h3>
        <div className="set-row">
          <div className="l">
            <div>Model</div>
            <div className="desc">Resolved on the server from `.env` endpoint settings.</div>
          </div>
          <div className="input" style={{ width: 240 }}>
            <input value="server configured" readOnly />
          </div>
        </div>
        <div className="set-row">
          <div className="l">
            <div>Review language</div>
            <div className="desc">Controls finding comments, summary text, and follow-up chat answers.</div>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button className={`btn sm ${tweak.commentLanguage === "zh" ? "primary" : ""}`} onClick={() => setTweak("commentLanguage", "zh")}>中文</button>
            <button className={`btn sm ${tweak.commentLanguage === "en" ? "primary" : ""}`} onClick={() => setTweak("commentLanguage", "en")}>English</button>
          </div>
        </div>
        <div className="set-row">
          <div className="l">
            <div>Auto-post to Gerrit</div>
            <div className="desc">Disabled by default; the toolbar generates a draft payload first.</div>
          </div>
          <Tog on={false} disabled />
        </div>
        <div className="set-row">
          <div className="l">
            <div>Block on critical</div>
            <div className="desc">Gating is intentionally off until production credentials are configured.</div>
          </div>
          <Tog on={false} disabled />
        </div>
        <div className="set-row">
          <div className="l">
            <div>Include suggestion-tier findings</div>
            <div className="desc">All validated findings stay visible in the report and publish payload.</div>
          </div>
          <Tog on={true} disabled />
        </div>
      </div>

      <div className="set-section">
        <h3>Display</h3>
        <div className="set-row">
          <div className="l">
            <div>Show AI confidence on findings</div>
            <div className="desc">Surfaces the model's self-reported certainty next to each comment.</div>
          </div>
          <Tog on={tweak.showConfidence} onClick={() => setTweak("showConfidence", !tweak.showConfidence)} />
        </div>
        <div className="set-row">
          <div className="l">
            <div>Default review layout</div>
            <div className="desc">"By file" mirrors Gerrit; "By severity" surfaces criticals first.</div>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button className={`btn sm ${tweak.viewMode === "byFile" ? "primary" : ""}`} onClick={() => setTweak("viewMode", "byFile")}>by file</button>
            <button className={`btn sm ${tweak.viewMode === "bySeverity" ? "primary" : ""}`} onClick={() => setTweak("viewMode", "bySeverity")}>by severity</button>
          </div>
        </div>
        <div className="set-row">
          <div className="l">
            <div>Theme</div>
            <div className="desc">Dark by default. Light reads better in shared screens.</div>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button className={`btn sm ${!tweak.light ? "primary" : ""}`} onClick={() => setTweak("light", false)}>dark</button>
            <button className={`btn sm ${tweak.light ? "primary" : ""}`} onClick={() => setTweak("light", true)}>light</button>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { HistoryScreen, TeamScreen, StatsScreen, SettingsScreen });
