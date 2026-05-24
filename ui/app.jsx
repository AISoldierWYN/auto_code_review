/* global React, ReactDOM, Ico,
   EmptyState, LoadingState, ErrorState,
   FileList, PrHeader, FileDiff, BySeverity, SidePanel,
   HistoryScreen, TeamScreen, StatsScreen, SettingsScreen,
   useTweaks, TweaksPanel, TweakSection, TweakToggle, TweakRadio, TweakColor */

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "showConfidence": true,
  "viewMode": "byFile",
  "commentLanguage": "zh",
  "light": false,
  "accent": "#74b9ff"
}/*EDITMODE-END*/;

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [route, setRoute] = React.useState("review");
  // Review states: "empty" | "loading" | "result" | "error"
  const [reviewState, setReviewState] = React.useState("result");
  const [activeFileIdx, setActiveFileIdx] = React.useState(0);
  const [commentStates, setCommentStates] = React.useState({});
  const [errorMsg, setErrorMsg] = React.useState("");
  // Bumped after a real review lands, to force a re-render that picks up
  // the updated window.MOCK_* globals.
  const [dataVersion, setDataVersion] = React.useState(0);

  // apply theme + accent
  React.useEffect(() => {
    document.documentElement.className = t.light ? "theme-light" : "";
    document.documentElement.style.setProperty("--accent", t.accent);
  }, [t.light, t.accent]);

  // Swap MOCK_DIFF whenever the active file index changes, so the UI
  // shows hunks for the file the user picked.
  React.useEffect(() => {
    if (typeof window.setActiveDiff === "function") {
      window.setActiveDiff(activeFileIdx);
    }
  }, [activeFileIdx, dataVersion]);

  const setCommentState = (id, state) => {
    setCommentStates((s) => ({ ...s, [id]: state }));
  };

  const pr = window.MOCK_PR;
  const totals = window.MOCK_FILES.reduce(
    (acc, f) => ({
      c: acc.c + f.sev.critical,
      w: acc.w + f.sev.warning,
      s: acc.s + f.sev.suggestion,
    }),
    { c: 0, w: 0, s: 0 }
  );

  const startReview = async (link) => {
    const input = (link || "").trim();
    if (!input) return;
    setErrorMsg("");
    setReviewState("loading");
    try {
      await window.runRealReview(input, { reviewLanguage: t.commentLanguage });
      setActiveFileIdx(0);
      setDataVersion((v) => v + 1);
      setReviewState("result");
    } catch (e) {
      console.error("review failed", e);
      setErrorMsg(e && e.message ? e.message : String(e));
      setReviewState("error");
    }
  };

  return (
    <div className="app" data-screen-label={route}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">k</span>
          <span className="brand-name">kit</span>
          <span className="brand-tag">v0.4</span>
        </div>
        <nav className="nav">
          <div className="nav-section">Workspace</div>
          <button className={`nav-item ${route === "review" ? "active" : ""}`} onClick={() => setRoute("review")}>
            <Ico.Review className="ico" />
            <span>Review</span>
            {reviewState === "result" && <span className="count">1</span>}
          </button>
          <button className={`nav-item ${route === "history" ? "active" : ""}`} onClick={() => setRoute("history")}>
            <Ico.History className="ico" />
            <span>History</span>
            <span className="count">{window.MOCK_HISTORY.length}</span>
          </button>
          <button className={`nav-item ${route === "stats" ? "active" : ""}`} onClick={() => setRoute("stats")}>
            <Ico.Stats className="ico" />
            <span>Stats</span>
          </button>

          <div className="nav-section">Organization</div>
          <button className={`nav-item ${route === "team" ? "active" : ""}`} onClick={() => setRoute("team")}>
            <Ico.Team className="ico" />
            <span>Team</span>
            <span className="count">{window.MOCK_TEAM.length}</span>
          </button>
          <button className={`nav-item ${route === "settings" ? "active" : ""}`} onClick={() => setRoute("settings")}>
            <Ico.Settings className="ico" />
            <span>Settings</span>
          </button>

          <div className="nav-section">Demo · review states</div>
          {[
            ["result", "Result"],
            ["loading", "Loading"],
            ["empty", "Empty"],
            ["error", "Error"],
          ].map(([k, label]) => (
            <button key={k}
              className={`nav-item ${route === "review" && reviewState === k ? "active" : ""}`}
              onClick={() => { setRoute("review"); setReviewState(k); }}>
              <span className="ico" style={{
                width: 8, height: 8, borderRadius: "50%",
                background: reviewState === k && route === "review" ? "var(--accent)" : "var(--faint)",
                margin: "0 3px",
              }} />
              <span style={{ fontSize: 12 }}>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className="avatar">LW</span>
          <div>
            <div className="user-name">Lin Wei</div>
            <div className="user-role">payments-svc</div>
          </div>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div className="crumb">
            <span>workspace</span>
            <span className="sep">/</span>
            <span style={{ textTransform: "capitalize" }} className={route === "review" ? "here" : ""}>{route}</span>
            {route === "review" && reviewState === "result" && (
              <React.Fragment>
                <span className="sep">/</span>
                <span className="here">CL #{pr.cl}</span>
              </React.Fragment>
            )}
          </div>
          <div className="topbar-actions">
            {route === "review" && reviewState === "result" && (
              <React.Fragment>
                <div style={{ display: "flex", gap: 4, background: "var(--panel-2)", border: "1px solid var(--border)", padding: 2, borderRadius: 6 }}>
                  <button className={`btn sm ${t.viewMode === "byFile" ? "primary" : "ghost"}`} style={{ height: 22, border: 0 }} onClick={() => setTweak("viewMode", "byFile")}>by file</button>
                  <button className={`btn sm ${t.viewMode === "bySeverity" ? "primary" : "ghost"}`} style={{ height: 22, border: 0 }} onClick={() => setTweak("viewMode", "bySeverity")}>by severity</button>
                </div>
                <button className="btn"><Ico.Copy className="ico" />copy summary</button>
                <button className="btn primary"><Ico.Arrow className="ico" />post to gerrit</button>
              </React.Fragment>
            )}
            {route !== "review" && (
              <React.Fragment>
                <div className="input" style={{ width: 240, height: 28 }}>
                  <Ico.Search className="ico" />
                  <input placeholder="search…" />
                  <span className="kbd">⌘K</span>
                </div>
              </React.Fragment>
            )}
          </div>
        </div>

        <div className="scroll" style={{ display: "flex", flexDirection: "column" }}>
          {route === "review" && reviewState === "empty" && (
            <EmptyState onSubmit={startReview} />
          )}
          {route === "review" && reviewState === "loading" && (
            <LoadingState />
          )}
          {route === "review" && reviewState === "error" && (
            <ErrorState
              message={errorMsg}
              onRetry={() => setReviewState("loading")}
              onBack={() => setReviewState("empty")}
            />
          )}
          {route === "review" && reviewState === "result" && (
            <div className="review-layout">
              <FileList files={window.MOCK_FILES} activeIdx={activeFileIdx} setActiveIdx={setActiveFileIdx} />
              <div className="review-mid">
                <PrHeader pr={pr} totals={totals} />
                {t.viewMode === "byFile" ? (
                  <FileDiff
                    file={window.MOCK_FILES[activeFileIdx]}
                    diff={window.MOCK_DIFF}
                    comments={window.MOCK_COMMENTS}
                    commentStates={commentStates}
                    setCommentState={setCommentState}
                    showConfidence={t.showConfidence}
                  />
                ) : (
                  <BySeverity
                    allComments={window.MOCK_ALL_COMMENTS}
                    commentStates={commentStates}
                    setCommentState={setCommentState}
                    showConfidence={t.showConfidence}
                  />
                )}
              </div>
              <SidePanel pr={pr} totals={totals} language={t.commentLanguage} dataVersion={dataVersion} />
            </div>
          )}

          {route === "history" && <HistoryScreen />}
          {route === "team" && <TeamScreen />}
          {route === "stats" && <StatsScreen />}
          {route === "settings" && <SettingsScreen tweak={t} setTweak={setTweak} />}
        </div>
      </main>

      <TweaksPanel>
        <TweakSection label="Display" />
        <TweakRadio label="Theme" value={t.light ? "light" : "dark"}
          options={["dark", "light"]}
          onChange={(v) => setTweak("light", v === "light")} />
        <TweakRadio label="View mode" value={t.viewMode}
          options={[{ value: "byFile", label: "by file" }, { value: "bySeverity", label: "by severity" }]}
          onChange={(v) => setTweak("viewMode", v)} />
        <TweakRadio label="Review language" value={t.commentLanguage}
          options={[{ value: "zh", label: "中文" }, { value: "en", label: "English" }]}
          onChange={(v) => setTweak("commentLanguage", v)} />
        <TweakToggle label="Show AI confidence" value={t.showConfidence}
          onChange={(v) => setTweak("showConfidence", v)} />
        <TweakColor label="Accent" value={t.accent}
          options={["#74b9ff", "#7fcf9f", "#f0c674", "#c78bff", "#ff8b6b"]}
          onChange={(v) => setTweak("accent", v)} />
        <TweakSection label="Demo state" />
        <TweakRadio label="Review state" value={reviewState}
          options={["result", "loading", "empty", "error"]}
          onChange={(v) => { setRoute("review"); setReviewState(v); }} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
