/* global React, Ico */

// ─── History ────────────────────────────────────────────────────────────
function HistoryScreen() {
  const rows = window.MOCK_HISTORY;
  return (
    <div className="tbl-wrap">
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <div className="input" style={{ maxWidth: 320 }}>
          <Ico.Search className="ico" />
          <input placeholder="filter by CL, repo, author…" />
        </div>
        <button className="btn"><Ico.Filter className="ico" />status: all</button>
        <button className="btn">repo: all</button>
        <span className="spacer" />
        <button className="btn"><Ico.Plus className="ico" />new review</button>
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
                <span className={`chip ${r.status === "merged" ? "suggestion" : r.status === "changes" ? "critical" : "accent"}`}>
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
  const team = window.MOCK_TEAM;
  return (
    <div>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="l">Active reviewers</div>
          <div className="v">{team.length}</div>
          <div className="d up">+2 this quarter</div>
        </div>
        <div className="stat-card">
          <div className="l">Reviews this week</div>
          <div className="v">214</div>
          <div className="d up">+18%</div>
        </div>
        <div className="stat-card">
          <div className="l">Avg accept rate</div>
          <div className="v">72%</div>
          <div className="d up">+4pp</div>
        </div>
        <div className="stat-card">
          <div className="l">Avg review time</div>
          <div className="v">9.8s</div>
          <div className="d down">+0.6s</div>
        </div>
      </div>
      <div className="section-head" style={{ padding: "20px 24px 0" }}>
        <span>Members</span>
        <span className="grow" />
        <button className="btn sm"><Ico.Plus className="ico" />invite</button>
      </div>
      <div className="team-grid">
        {team.map((p) => (
          <div key={p.name} className="team-card">
            <div className="head">
              <span className="avatar">{p.initials}</span>
              <div>
                <div className="nm">{p.name}</div>
                <div className="rl">{p.role}</div>
              </div>
              <span className="spacer" />
              <button className="btn sm ghost">View</button>
            </div>
            <div className="meta">
              <div className="col">
                <span className="k">reviews</span>
                <span className="v">{p.reviews}</span>
              </div>
              <div className="col">
                <span className="k">accepted</span>
                <span className="v" style={{ color: "var(--suggestion)" }}>{p.accepted}</span>
              </div>
              <div className="col">
                <span className="k">avg time</span>
                <span className="v">{p.avg}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Stats ──────────────────────────────────────────────────────────────
function StatsScreen() {
  const week = window.MOCK_WEEKLY;
  const max = Math.max(...week.map((d) => d.c + d.w + d.s));
  // donut
  const breakdown = [
    { name: "null safety", v: 24, c: "var(--critical)" },
    { name: "concurrency", v: 18, c: "var(--warning)" },
    { name: "API design", v: 14, c: "var(--accent)" },
    { name: "performance", v: 11, c: "var(--suggestion)" },
    { name: "tests", v: 9, c: "var(--muted)" },
  ];
  const total = breakdown.reduce((a, b) => a + b.v, 0);
  let cum = 0;
  const R = 36, C = 2 * Math.PI * R;
  return (
    <div>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="l">Reviews · 7d</div>
          <div className="v">214</div>
          <div className="d up">↑ 18% vs prev</div>
        </div>
        <div className="stat-card">
          <div className="l">Findings · 7d</div>
          <div className="v">312</div>
          <div className="d down">↑ 12%</div>
        </div>
        <div className="stat-card">
          <div className="l">Critical caught</div>
          <div className="v" style={{ color: "var(--critical)" }}>16</div>
          <div className="d">11 fixed, 5 dismissed</div>
        </div>
        <div className="stat-card">
          <div className="l">Median scan time</div>
          <div className="v">8.4<span style={{ fontSize: 14, color: "var(--muted)", marginLeft: 4 }}>s</span></div>
          <div className="d up">↓ 1.2s</div>
        </div>
      </div>
      <div className="chart-row">
        <div className="chart-card">
          <h4>
            <span>Findings by day</span>
            <span className="sub">past 7 days · stacked</span>
          </h4>
          <div className="bars-wrap">
            <div className="bars">
              {week.map((d) => {
                const tot = d.c + d.w + d.s;
                const h = (tot / max) * 140;
                return (
                  <div key={d.day} className="bar" style={{ height: h + "px" }} title={`${d.day} · ${tot}`}>
                    <span className="seg crit" style={{ height: (d.c / tot * h) + "px" }} />
                    <span className="seg warn" style={{ height: (d.w / tot * h) + "px" }} />
                    <span className="seg sugg" style={{ height: (d.s / tot * h) + "px" }} />
                    <span className="lbl">{d.day}</span>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="legend">
            <span className="item"><span className="dot" style={{ background: "var(--critical)" }} />critical</span>
            <span className="item"><span className="dot" style={{ background: "var(--warning)" }} />warning</span>
            <span className="item"><span className="dot" style={{ background: "var(--suggestion)" }} />suggestion</span>
          </div>
        </div>
        <div className="chart-card">
          <h4>
            <span>Top categories</span>
            <span className="sub">7d</span>
          </h4>
          <div className="donut-wrap">
            <svg viewBox="0 0 100 100" width="110" height="110">
              <circle cx="50" cy="50" r={R} fill="none" stroke="var(--panel-2)" strokeWidth="12" />
              {breakdown.map((b) => {
                const frac = b.v / total;
                const len = frac * C;
                const off = -cum;
                cum += len;
                return (
                  <circle key={b.name} cx="50" cy="50" r={R} fill="none"
                    stroke={b.c} strokeWidth="12"
                    strokeDasharray={`${len} ${C - len}`}
                    strokeDashoffset={off}
                    transform="rotate(-90 50 50)"
                  />
                );
              })}
              <text x="50" y="48" textAnchor="middle" fill="var(--text)" style={{ font: "600 14px var(--mono)" }}>{total}</text>
              <text x="50" y="60" textAnchor="middle" fill="var(--muted)" style={{ font: "10px var(--mono)" }}>findings</text>
            </svg>
            <div className="donut-list">
              {breakdown.map((b) => (
                <div key={b.name} className="row">
                  <span className="dot" style={{ background: b.c }} />
                  <span className="name">{b.name}</span>
                  <span className="v">{b.v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Settings ───────────────────────────────────────────────────────────
function SettingsScreen({ tweak, setTweak }) {
  const Tog = ({ on, onClick }) => (
    <span className={`toggle ${on ? "on" : ""}`} onClick={onClick} />
  );
  return (
    <div className="set-wrap">
      <div className="set-section">
        <h3>Source</h3>
        <div className="set-row">
          <div className="l">
            <div>Gerrit host</div>
            <div className="desc">Where kit fetches changes from. OAuth token configured.</div>
          </div>
          <div className="input" style={{ width: 320 }}>
            <input defaultValue="https://gerrit.internal.corp" />
          </div>
        </div>
        <div className="set-row">
          <div className="l">
            <div>GitHub Enterprise</div>
            <div className="desc">Optional fallback host. Not connected.</div>
          </div>
          <button className="btn">Connect</button>
        </div>
        <div className="set-row">
          <div className="l">
            <div>Default project</div>
            <div className="desc">Used when a link omits the project slug.</div>
          </div>
          <div className="input" style={{ width: 320 }}>
            <input defaultValue="platform/payments-svc" />
          </div>
        </div>
      </div>

      <div className="set-section">
        <h3>Reviewer behavior</h3>
        <div className="set-row">
          <div className="l">
            <div>Model</div>
            <div className="desc">Used for all analysis passes.</div>
          </div>
          <div className="input" style={{ width: 240 }}>
            <input defaultValue="claude-haiku-4.5" />
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
            <div className="desc">Land kit's findings as draft comments on the change.</div>
          </div>
          <Tog on={true} />
        </div>
        <div className="set-row">
          <div className="l">
            <div>Block on critical</div>
            <div className="desc">Set CodeReview −1 when any critical finding is present.</div>
          </div>
          <Tog on={true} />
        </div>
        <div className="set-row">
          <div className="l">
            <div>Include suggestion-tier findings</div>
            <div className="desc">Nice-to-haves are posted but folded by default.</div>
          </div>
          <Tog on={false} />
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
