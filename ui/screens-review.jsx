/* global React, Ico */

// ─── PR input (empty) ──────────────────────────────────────────────────
function EmptyState({ onSubmit, error }) {
  const [val, setVal] = React.useState("tests/cases/case_resource_leak/change.diff");
  return (
    <div className="center-wrap">
      <div className="empty-card">
        <div className="empty-icon">
          <Ico.Sparkle style={{ width: 22, height: 22 }} />
        </div>
        <h1 className="empty-title">Review a change</h1>
        <p className="empty-sub">
          Paste one of: a local diff file path, a GitHub PR URL, or the
          shorthand <code style={{ fontFamily: "var(--mono)" }}>owner/repo#NN</code>.
          Gerrit is planned for Stage 4.
        </p>
        <div style={{ display: "flex", gap: 8 }}>
          <div className="input" style={{ flex: 1 }}>
            <Ico.Link className="ico" />
            <input
              value={val}
              onChange={(e) => setVal(e.target.value)}
              placeholder="path/to/change.diff   |   github.com/owner/repo/pull/NN   |   owner/repo#NN"
              spellCheck={false}
              onKeyDown={(e) => e.key === "Enter" && onSubmit(val)}
            />
            <span className="kbd">⏎</span>
          </div>
          <button className="btn primary" onClick={() => onSubmit(val)}>
            <Ico.Sparkle className="ico" />
            Review
          </button>
        </div>
        <div className="empty-examples">
          <span style={{ alignSelf: "center", color: "var(--faint)" }}>try:</span>
          <span className="ex" onClick={() => onSubmit("tests/cases/case_resource_leak/change.diff")}>
            local · case_resource_leak
          </span>
          <span className="ex" onClick={() => onSubmit("python/cpython#1000")}>
            github · python/cpython#1000
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── Loading (terminal-style progress) ─────────────────────────────────
function LoadingState({ url }) {
  // Honest pipeline stages — the backend is synchronous from the UI's
  // viewpoint (one POST that takes ~30s). We can't actually track per-step
  // progress without SSE/WebSocket (Stage 2+), so we mark the agent step
  // as the running one and let the bar animate.
  const steps = [
    { t: "parse unified diff", d: "done" },
    { t: "load and filter rules", d: "done" },
    { t: "build prompts (skill + recalled rules + diff)", d: "done" },
    { t: "call agent (running, can use Read/Glob/Grep on workspace)", d: "running" },
    { t: "parse agent output (finding blocks + summary)", d: "pending" },
    { t: "build review.json (severity counts, diff hunks, anchors)", d: "pending" },
  ];
  const [progress, setProgress] = React.useState(40);
  React.useEffect(() => {
    const id = setInterval(() => setProgress((p) => Math.min(94, p + Math.random() * 2)), 600);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="center-wrap">
      <div className="loading-card">
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <span className="chip accent"><span className="dot" />analyzing</span>
          <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--muted)" }}>
            running pipeline · expected &lt; 30s
          </span>
        </div>
        {steps.map((s, i) => {
          const state = s.d === "running" ? "running" : s.d === "pending" ? "pending" : "done";
          return (
            <div key={i} className={`term-line ${state}`}>
              <span className="prompt">{state === "pending" ? "○" : state === "running" ? "▸" : "▸"}</span>
              <span className="t">
                {s.t}
                {state === "done" && <span className="tt">ok</span>}
              </span>
            </div>
          );
        })}
        <div className="progress-bar">
          <div className="fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="progress-meta">
          <span>pipeline · diff → rules → agent → findings → report</span>
          <span>{Math.round(progress)}%</span>
        </div>
      </div>
    </div>
  );
}

// ─── Error ─────────────────────────────────────────────────────────────
function ErrorState({ onRetry, onBack, message }) {
  const detail = message && message.length > 0 ? message : "(no detail available)";
  return (
    <div className="center-wrap">
      <div className="error-card">
        <div className="error-head">
          <span className="e">ERR_REVIEW_FAILED</span>
          <span className="error-title">Review didn't complete</span>
        </div>
        <p className="error-body">
          The pipeline raised an error. Common causes: diff path doesn't exist, workspace
          doesn't match the diff's after-state, agent endpoint not reachable, or the agent's
          output didn't follow the expected format.
        </p>
        <div className="error-log">
          <span className="k">!</span> {detail}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn primary" onClick={onBack}>Try a different path</button>
          <span className="spacer" />
          <button className="btn ghost">View settings</button>
        </div>
      </div>
    </div>
  );
}

// ─── File list (left rail) ─────────────────────────────────────────────
function FileList({ files, activeIdx, setActiveIdx }) {
  return (
    <div className="review-files">
      <div className="section-head">
        <span>Files</span>
        <span style={{ fontFamily: "var(--mono)", color: "var(--text-2)" }}>{files.length}</span>
        <span className="grow" />
        <Ico.Filter style={{ width: 12, height: 12, color: "var(--muted)" }} />
      </div>
      {files.map((f, i) => {
        const name = f.path.split("/").pop();
        const dir = f.path.slice(0, -name.length);
        return (
          <div key={f.path} className={`file-row ${i === activeIdx ? "active" : ""}`} onClick={() => setActiveIdx(i)}>
            <Ico.File style={{ width: 12, height: 12, color: "var(--muted)", flex: "0 0 12px" }} />
            <span className="path">
              <span style={{ color: "var(--faint)" }}>{dir}</span>
              <span>{name}</span>
            </span>
            <span className="badges">
              {f.sev.critical > 0 && <span className="b crit">{f.sev.critical}</span>}
              {f.sev.warning > 0 && <span className="b warn">{f.sev.warning}</span>}
              {f.sev.suggestion > 0 && <span className="b sugg">{f.sev.suggestion}</span>}
            </span>
          </div>
        );
      })}
      <div className="section-head" style={{ marginTop: 8 }}>
        <span>Patchsets</span>
      </div>
      {[3, 2, 1].map((n) => (
        <div key={n} className={`file-row ${n === 3 ? "active" : ""}`}>
          <span style={{ fontFamily: "var(--mono)", color: "var(--muted)", width: 12 }}>{n}</span>
          <span className="path">patchset {n}</span>
          <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)" }}>
            {n === 3 ? "current" : n === 2 ? "−2h" : "−1d"}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── PR header ─────────────────────────────────────────────────────────
function PrHeader({ pr, totals }) {
  return (
    <div className="pr-head">
      <div className="pr-title">
        <span>{pr.title}</span>
        <span className="pr-id">#{pr.cl}</span>
      </div>
      <div className="pr-meta">
        <span>
          <span className="avatar" style={{ width: 16, height: 16, fontSize: 9, display: "inline-grid", verticalAlign: "-3px", marginRight: 6 }}>{pr.author.initials}</span>
          {pr.author.name}
        </span>
        <span className="dot-sep">·</span>
        <span>{pr.repo}</span>
        <span className="dot-sep">·</span>
        <span>{pr.branch} → {pr.target}</span>
        <span className="dot-sep">·</span>
        <span style={{ color: "var(--suggestion)" }}>+{pr.additions}</span>
        <span style={{ color: "var(--critical)" }}>−{pr.deletions}</span>
        <span className="dot-sep">·</span>
        <span>scanned in {pr.scanned}</span>
      </div>
      <div className="pr-summary">
        <div className="cell">
          <div className="v">{pr.filesChanged}</div>
          <div className="l">files</div>
        </div>
        <div className="cell crit">
          <div className="v">{totals.c}<span className="delta">critical</span></div>
          <div className="l">must fix before merge</div>
        </div>
        <div className="cell warn">
          <div className="v">{totals.w}<span className="delta">warnings</span></div>
          <div className="l">recommended</div>
        </div>
        <div className="cell sugg">
          <div className="v">{totals.s}<span className="delta">suggestions</span></div>
          <div className="l">nits & nice-to-haves</div>
        </div>
      </div>
    </div>
  );
}

// ─── Inline comment ────────────────────────────────────────────────────
function InlineComment({ id, comment, state, setState, showConfidence }) {
  return (
    <div className={`cmt-row ${state || ""}`}>
      <span className="ln" />
      <span className="ln2" />
      <div className="cmt">
        <div className="cmt-head">
          <span className={`chip ${comment.severity}`}>
            <span className="dot" />
            {comment.severity}
          </span>
          <span className="cmt-author">kit · ai reviewer</span>
          {showConfidence && (
            <span className="cmt-conf">confidence {Math.round(comment.confidence * 100)}%</span>
          )}
        </div>
        <div className="cmt-body">
          <strong>{comment.title}.</strong>{" "}
          <span dangerouslySetInnerHTML={{ __html: comment.body }} />
        </div>
        {comment.suggestion && (
          <div className="cmt-suggestion">
            <div className="h">
              <span>suggested fix</span>
              <span className="grow" />
              <button className="btn sm ghost" style={{ height: 20 }}><Ico.Copy className="ico" />Copy</button>
            </div>
            <div className="b">
              {comment.suggestion.remove.map((l, i) => (
                <div key={"r" + i} className="sline del">- {l}</div>
              ))}
              {comment.suggestion.add.map((l, i) => (
                <div key={"a" + i} className="sline add">+ {l}</div>
              ))}
            </div>
          </div>
        )}
        <div className="cmt-actions">
          {state === "applied" && <span className="applied-tag">✓ applied to patchset 3</span>}
          {state === "dismissed" && <span className="dismiss-tag">— dismissed</span>}
          {!state && (
            <React.Fragment>
              <button className="btn sm primary" onClick={() => setState(id, "applied")}>
                <Ico.Check className="ico" />
                Apply
              </button>
              <button className="btn sm" onClick={() => setState(id, "dismissed")}>
                <Ico.X className="ico" />
                Dismiss
              </button>
              <button className="btn sm ghost">Reply</button>
            </React.Fragment>
          )}
          {state && (
            <button className="btn sm ghost" onClick={() => setState(id, null)}>Undo</button>
          )}
          <span className="right">
            <Ico.Link style={{ width: 10, height: 10 }} />
            <span>{comment.file}:{comment.line}</span>
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── Diff block (one file) ─────────────────────────────────────────────
function FileDiff({ file, diff, comments, commentStates, setCommentState, showConfidence }) {
  return (
    <div className="file-block">
      <div className="file-head">
        <Ico.File className="icon" />
        <span>{file.path}</span>
        <span style={{ color: "var(--suggestion)" }}>+{file.add}</span>
        <span style={{ color: "var(--critical)" }}>−{file.del}</span>
        <span className="lang">{file.lang}</span>
      </div>
      <div className="code">
        {diff.map((row, i) => {
          if (row.type === "hunk") {
            return (
              <div key={i} className="row hunk">
                <span className="ln">…</span>
                <span className="ln2">…</span>
                <span className="src">{row.text}</span>
              </div>
            );
          }
          if (row.type === "comment") {
            const c = comments[row.id];
            if (!c) return null;
            return (
              <InlineComment
                key={i}
                id={row.id}
                comment={c}
                state={commentStates[row.id]}
                setState={setCommentState}
                showConfidence={showConfidence}
              />
            );
          }
          const klass = row.type === "add" ? "add" : row.type === "del" ? "del" : "";
          const prefix = row.type === "add" ? "+ " : row.type === "del" ? "- " : "  ";
          return (
            <div key={i} className={`row ${klass}`}>
              <span className="ln">{row.old ?? ""}</span>
              <span className="ln2">{row.new ?? ""}</span>
              <span className="src">{prefix}{row.text}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── By-severity view ──────────────────────────────────────────────────
function BySeverity({ allComments, commentStates, setCommentState, showConfidence }) {
  const groups = {
    critical: allComments.filter((c) => c.severity === "critical"),
    warning: allComments.filter((c) => c.severity === "warning"),
    suggestion: allComments.filter((c) => c.severity === "suggestion"),
  };
  return (
    <div className="sev-list">
      {["critical", "warning", "suggestion"].map((sev) => (
        <div key={sev} className={`sev-group ${sev}`}>
          <h3>
            <span className="marker" />
            <span>{sev}</span>
            <span className="count">{groups[sev].length}</span>
          </h3>
          {groups[sev].map((c) => (
            <div key={c.id} className="sev-card" style={{
              opacity: commentStates[c.id] === "dismissed" ? 0.4 : commentStates[c.id] === "applied" ? 0.65 : 1,
            }}>
              <div className="loc">
                <Ico.File style={{ width: 11, height: 11 }} />
                <span className="file">{c.file}</span>
                <span style={{ color: "var(--faint)" }}>:</span>
                <span>{c.line}</span>
                {showConfidence && (
                  <React.Fragment>
                    <span style={{ color: "var(--faint)" }}>·</span>
                    <span>confidence {Math.round(c.confidence * 100)}%</span>
                  </React.Fragment>
                )}
                {commentStates[c.id] === "applied" && <span className="applied-tag" style={{ marginLeft: 8 }}>✓ applied</span>}
                {commentStates[c.id] === "dismissed" && <span className="dismiss-tag" style={{ marginLeft: 8 }}>— dismissed</span>}
              </div>
              <div className="body">
                <strong>{c.title}.</strong>{" "}
                <span dangerouslySetInnerHTML={{ __html: c.body }} />
              </div>
              <div className="actions">
                {!commentStates[c.id] ? (
                  <React.Fragment>
                    <button className="btn sm primary" onClick={() => setCommentState(c.id, "applied")}>
                      <Ico.Check className="ico" />Apply
                    </button>
                    <button className="btn sm" onClick={() => setCommentState(c.id, "dismissed")}>
                      <Ico.X className="ico" />Dismiss
                    </button>
                    <button className="btn sm ghost">Reply</button>
                  </React.Fragment>
                ) : (
                  <button className="btn sm ghost" onClick={() => setCommentState(c.id, null)}>Undo</button>
                )}
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

// ─── Side panel (chat / findings) ──────────────────────────────────────
function buildChatIntro(pr, totals, language) {
  if (language === "zh") {
    return {
      who: "ai",
      text: `已加载当前 review：${pr.filesChanged} 个文件，${totals.c} 个 critical、${totals.w} 个 warning、${totals.s} 个 suggestion。你可以继续问某条 finding 的风险、修改建议，或者需要补哪些测试。`,
    };
  }
  return {
    who: "ai",
    text: `I loaded this review: ${pr.filesChanged} file(s), ${totals.c} critical, ${totals.w} warning(s), and ${totals.s} suggestion(s). Ask about a finding, a fix, or what tests are missing.`,
  };
}

function SidePanel({ pr, totals, language = "en", dataVersion = 0 }) {
  const [tab, setTab] = React.useState("chat");
  const [draft, setDraft] = React.useState("");
  const [msgs, setMsgs] = React.useState(() => [buildChatIntro(pr, totals, language)]);
  const [isSending, setIsSending] = React.useState(false);
  const scroller = React.useRef(null);
  const allComments = window.MOCK_ALL_COMMENTS || [];
  React.useEffect(() => {
    setMsgs([buildChatIntro(pr, totals, language)]);
    setDraft("");
  }, [pr.id, dataVersion, language, totals.c, totals.w, totals.s]);
  React.useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [msgs]);
  const renderChatText = (text) => (
    window.renderChatText ? window.renderChatText(text) : String(text || "")
  );
  const send = async (text) => {
    const question = (text || "").trim();
    if (!question || isSending) return;
    const pendingId = `pending-${Date.now()}`;
    setMsgs((m) => [
      ...m,
      { who: "user", text: question },
      {
        id: pendingId,
        who: "ai",
        text: language === "zh" ? "正在根据当前 review 分析..." : "Checking the current review context...",
      },
    ]);
    setDraft("");
    setIsSending(true);
    try {
      const answer = window.askReviewChat
        ? await window.askReviewChat(question, { reviewLanguage: language })
        : (language === "zh" ? "当前 chat 后端还没有连接。" : "The chat backend is not connected yet.");
      setMsgs((m) => m.map((msg) => (
        msg.id === pendingId ? { who: "ai", text: answer } : msg
      )));
    } catch (e) {
      const detail = e && e.message ? e.message : String(e);
      const answer = language === "zh"
        ? `chat 请求失败：${detail}`
        : `Chat request failed: ${detail}`;
      setMsgs((m) => m.map((msg) => (
        msg.id === pendingId ? { who: "ai", text: answer } : msg
      )));
    } finally {
      setIsSending(false);
    }
  };
  return (
    <div className="review-side">
      <div className="side-tabs">
        <button className={`side-tab ${tab === "chat" ? "active" : ""}`} onClick={() => setTab("chat")}>
          chat<span className="count">·ai</span>
        </button>
        <button className={`side-tab ${tab === "summary" ? "active" : ""}`} onClick={() => setTab("summary")}>
          summary
        </button>
        <button className={`side-tab ${tab === "checks" ? "active" : ""}`} onClick={() => setTab("checks")}>
          checks<span className="count">0</span>
        </button>
      </div>
      {tab === "chat" && (
        <div className="chat-area">
          <div className="chat-msgs" ref={scroller}>
            {msgs.map((m, i) => (
              <div key={i} className={`msg ${m.who}`}>
                <span className="who">{m.who === "user" ? "you" : "kit"}</span>
                <div className="text" dangerouslySetInnerHTML={{ __html: renderChatText(m.text) }} />
              </div>
            ))}
          </div>
          <div className="chip-row">
            <button className="chip-btn" onClick={() => send(language === "zh" ? "解释当前最有风险的改动。" : "Explain the riskiest change in this CL.")}>
              {language === "zh" ? "解释最高风险" : "explain the riskiest change"}
            </button>
            <button className="chip-btn" onClick={() => send(language === "zh" ? "这次改动需要补哪些测试？" : "What tests should cover this change?")}>
              {language === "zh" ? "需要哪些测试" : "what tests are missing"}
            </button>
            <button className="chip-btn" onClick={() => send(language === "zh" ? "生成一段 Gerrit review 总结。" : "Generate a Gerrit comment summary.")}>
              {language === "zh" ? "生成 gerrit 总结" : "generate gerrit summary"}
            </button>
          </div>
          <div className="chat-input-row">
            <textarea
              className="chat-input"
              placeholder={language === "zh" ? "询问 kit 关于这次改动的问题..." : "Ask kit about this change..."}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(draft);
                }
              }}
              disabled={isSending}
            />
            <button className="btn primary" onClick={() => send(draft)} disabled={isSending} style={{ alignSelf: "flex-end", height: 32 }}>
              <Ico.Send className="ico" />
            </button>
          </div>
        </div>
      )}
      {tab === "summary" && (
        <div style={{ padding: 16, fontSize: 12.5, lineHeight: 1.6, color: "var(--text-2)", overflowY: "auto" }}>
          <div className="section-head" style={{ padding: 0, margin: "0 0 10px" }}>
            {language === "zh" ? "变更摘要" : "What changed"}
          </div>
          <p style={{ margin: "0 0 14px" }}>{pr.summary}</p>
          <div className="section-head" style={{ padding: 0, margin: "0 0 10px" }}>
            {language === "zh" ? "Finding" : "Findings"}
          </div>
          {allComments.length === 0 ? (
            <p style={{ margin: 0 }}>{language === "zh" ? "当前没有结构化 finding。" : "No structured findings in the current review."}</p>
          ) : (
            <ul style={{ paddingLeft: 18, margin: 0 }}>
              {allComments.map((c) => (
                <li key={c.id} style={{ marginBottom: 8 }}>
                  <strong style={{ color: "var(--text)" }}>{c.severity}</strong>
                  <span> - {c.title}</span>
                  <span style={{ display: "block", fontFamily: "var(--mono)", color: "var(--muted)", fontSize: 11 }}>
                    {c.file}:{c.line}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {tab === "checks" && (
        <div style={{ padding: 16, fontSize: 12.5, lineHeight: 1.6, color: "var(--text-2)" }}>
          {language === "zh"
            ? "当前还没有接入 CI/check 数据。这里不会再展示 demo 检查结果，避免和真实 review 混淆。"
            : "CI/check data is not connected yet. Demo check results are hidden so they are not confused with the current review."}
        </div>
      )}
    </div>
  );
}

Object.assign(window, {
  EmptyState, LoadingState, ErrorState,
  FileList, PrHeader, FileDiff, BySeverity, SidePanel,
});
