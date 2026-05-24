/* glue.js — connects the UI to the backend (scripts/serve.py).
 *
 * window.runRealReview(input) calls POST /api/review, then writes the
 * response into the same window.MOCK_* globals that the demo data.js
 * uses. After it returns, the UI re-renders with real data.
 *
 * The input may be:
 *   - a local diff file path (e.g. tests/cases/case_resource_leak/change.diff)
 *   - eventually a Gerrit / GitHub URL (deferred to Stage 4 DiffSource adapters)
 */

(function () {
  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatInline(value) {
    const codeSpans = [];
    let text = escapeHtml(value);

    text = text.replace(/`([^`]+)`/g, (_, code) => {
      const token = `@@CODE_SPAN_${codeSpans.length}@@`;
      codeSpans.push(`<code>${code}</code>`);
      return token;
    });

    text = text
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/__([^_]+)__/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');

    return text.replace(/@@CODE_SPAN_(\d+)@@/g, (_, idx) => codeSpans[Number(idx)] || "");
  }

  function isTableSeparator(line) {
    return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
  }

  function splitTableLine(line) {
    return line
      .trim()
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim());
  }

  function renderTable(lines, start) {
    const header = splitTableLine(lines[start]);
    const rows = [];
    let i = start + 2;
    while (i < lines.length && /\|/.test(lines[i]) && lines[i].trim()) {
      rows.push(splitTableLine(lines[i]));
      i += 1;
    }

    const head = header.map((cell) => `<th>${formatInline(cell)}</th>`).join("");
    const body = rows.map((row) => {
      const cells = header.map((_, idx) => `<td>${formatInline(row[idx] || "")}</td>`).join("");
      return `<tr>${cells}</tr>`;
    }).join("");

    return {
      html: `<div class="md-table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`,
      next: i,
    };
  }

  function renderMarkdown(value) {
    const lines = String(value ?? "").replace(/\r\n/g, "\n").split("\n");
    const html = [];
    let i = 0;

    const startsBlock = (line, nextLine) => {
      const trimmed = line.trim();
      return !trimmed
        || /^```/.test(trimmed)
        || /^#{1,6}\s+/.test(trimmed)
        || /^>\s?/.test(trimmed)
        || /^[-*+]\s+/.test(trimmed)
        || /^\d+\.\s+/.test(trimmed)
        || (/\|/.test(line) && nextLine && isTableSeparator(nextLine));
    };

    const renderList = (ordered) => {
      const markerRe = ordered ? /^\s*\d+\.\s+(.*)$/ : /^\s*[-*+]\s+(.*)$/;
      const otherListRe = ordered ? /^\s*[-*+]\s+/ : /^\s*\d+\.\s+/;
      const items = [];

      while (i < lines.length) {
        const first = markerRe.exec(lines[i]);
        if (!first) break;

        const itemLines = [first[1]];
        i += 1;

        while (i < lines.length) {
          const line = lines[i];
          const trimmed = line.trim();

          if (markerRe.test(line)) break;
          if (otherListRe.test(line)) break;

          if (!trimmed) {
            let next = i + 1;
            while (next < lines.length && !lines[next].trim()) next += 1;
            if (next < lines.length && markerRe.test(lines[next])) {
              i = next;
              break;
            }
            break;
          }

          if (
            /^```/.test(trimmed)
            || /^#{1,6}\s+/.test(trimmed)
            || /^>\s?/.test(trimmed)
            || (/\|/.test(line) && i + 1 < lines.length && isTableSeparator(lines[i + 1]))
          ) {
            break;
          }

          itemLines.push(trimmed);
          i += 1;
        }

        items.push(`<li>${formatInline(itemLines.join("\n")).replace(/\n/g, "<br>")}</li>`);
      }

      return `<${ordered ? "ol" : "ul"}>${items.join("")}</${ordered ? "ol" : "ul"}>`;
    };

    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      if (!trimmed) {
        i += 1;
        continue;
      }

      if (/^```/.test(trimmed)) {
        const lang = trimmed.replace(/^```/, "").trim();
        const body = [];
        i += 1;
        while (i < lines.length && !/^```/.test(lines[i].trim())) {
          body.push(lines[i]);
          i += 1;
        }
        if (i < lines.length) i += 1;
        const className = lang ? ` class="language-${escapeHtml(lang)}"` : "";
        html.push(`<pre><code${className}>${escapeHtml(body.join("\n"))}</code></pre>`);
        continue;
      }

      if (/\|/.test(line) && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
        const table = renderTable(lines, i);
        html.push(table.html);
        i = table.next;
        continue;
      }

      const heading = /^(#{1,6})\s+(.+)$/.exec(trimmed);
      if (heading) {
        const level = Math.min(6, heading[1].length);
        html.push(`<h${level}>${formatInline(heading[2])}</h${level}>`);
        i += 1;
        continue;
      }

      if (/^>\s?/.test(trimmed)) {
        const quote = [];
        while (i < lines.length && /^>\s?/.test(lines[i].trim())) {
          quote.push(lines[i].trim().replace(/^>\s?/, ""));
          i += 1;
        }
        html.push(`<blockquote>${formatInline(quote.join("\n")).replace(/\n/g, "<br>")}</blockquote>`);
        continue;
      }

      if (/^[-*+]\s+/.test(trimmed)) {
        html.push(renderList(false));
        continue;
      }

      if (/^\d+\.\s+/.test(trimmed)) {
        html.push(renderList(true));
        continue;
      }

      const paragraph = [line];
      i += 1;
      while (i < lines.length && !startsBlock(lines[i], lines[i + 1])) {
        paragraph.push(lines[i]);
        i += 1;
      }
      html.push(`<p>${formatInline(paragraph.join("\n")).replace(/\n/g, "<br>")}</p>`);
    }

    return html.join("");
  }

  function fmtSeconds(s) {
    if (typeof s !== "number") return "—";
    if (s < 10) return `${s.toFixed(1)}s`;
    return `${Math.round(s)}s`;
  }

  function fileBasename(path) {
    if (!path) return "";
    return path.split(/[\\/]/).pop();
  }

  function transformPr(review) {
    const m = review.review;
    const path = m.diff_path || "";
    // UI uses {cl} for Gerrit change-list number. v1 substitutes the diff
    // file path (basename) so the header still has something to show.
    const clDisplay = fileBasename(path) || path || "(unknown)";
    const author = m.author || { name: "—", role: "", initials: "—" };
    return {
      id: path,
      cl: clDisplay,
      title: m.title || clDisplay,
      branch: m.branch || "(local)",
      target: m.target || "(local)",
      author: {
        name: author.name || "—",
        role: author.role || "",
        initials: author.initials || (author.name || "?").slice(0, 2).toUpperCase(),
      },
      repo: m.repo || "(local)",
      time: "just now",
      filesChanged: m.files_changed || 0,
      additions: m.additions || 0,
      deletions: m.deletions || 0,
      model: m.model || "—",
      scanned: fmtSeconds(m.scanned_seconds),
      summary: m.summary || "",
    };
  }

  function transformFiles(files) {
    // Shape already matches the UI's MOCK_FILES: {path, lang, add, del, sev}.
    return (files || []).map((f) => ({
      path: f.path,
      lang: f.lang || "text",
      add: f.add || 0,
      del: f["del"] || 0,
      sev: f.sev || { critical: 0, warning: 0, suggestion: 0 },
      diff_hunks: f.diff_hunks || [],   // kept so the app can switch active file
    }));
  }

  function transformComments(findings) {
    const out = {};
    for (const f of findings || []) {
      out[f.id] = {
        severity: f.severity,
        file: f.file,
        line: f.line,
        confidence: typeof f.confidence === "number" ? f.confidence : 0.5,
        title: f.title || "",
        body: f.body || "",
        suggestion: f.suggestion || null,
      };
    }
    return out;
  }

  function transformAllComments(findings) {
    return (findings || []).map((f) => ({
      id: f.id,
      severity: f.severity,
      file: f.file,
      line: f.line,
      confidence: typeof f.confidence === "number" ? f.confidence : 0.5,
      title: f.title || "",
      body: f.body || "",
    }));
  }

  function buildCurrentReviewSnapshot() {
    return {
      schema_version: "1.0",
      review: {
        diff_path: window.MOCK_PR?.id || "",
        title: window.MOCK_PR?.title || "",
        branch: window.MOCK_PR?.branch || null,
        target: window.MOCK_PR?.target || null,
        repo: window.MOCK_PR?.repo || null,
        summary: window.MOCK_PR?.summary || "",
        language: window.MOCK_REVIEW_LANGUAGE || "en",
      },
      files: (window.MOCK_FILES || []).map((f) => ({
        path: f.path,
        lang: f.lang,
        add: f.add,
        del: f.del,
        sev: f.sev,
        diff_hunks: f.diff_hunks || [],
      })),
      findings: Object.entries(window.MOCK_COMMENTS || {}).map(([id, c]) => ({
        id,
        severity: c.severity,
        file: c.file,
        line: c.line,
        confidence: c.confidence,
        title: c.title,
        body: c.body,
        suggestion: c.suggestion || null,
      })),
    };
  }

  async function runRealReview(input, options = {}) {
    // Server accepts either ``identifier`` (preferred) or the legacy
    // ``diff_path`` alias. Send ``identifier`` so the server can dispatch
    // to LocalDiffSource / GitHubDiffSource based on the shape.
    const body = {
      identifier: input,
      review_language: options.reviewLanguage || options.review_language || "en",
    };
    const resp = await fetch("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      let detail = `HTTP ${resp.status}`;
      try {
        const j = await resp.json();
        if (j && j.error) detail = j.error;
      } catch (_) { /* not JSON */ }
      throw new Error(detail);
    }
    const review = await resp.json();

    window.MOCK_PR = transformPr(review);
    window.MOCK_FILES = transformFiles(review.files);
    // MOCK_DIFF is the active file's hunks; default to file 0.
    window.MOCK_DIFF = window.MOCK_FILES[0] ? window.MOCK_FILES[0].diff_hunks : [];
    window.MOCK_COMMENTS = transformComments(review.findings);
    window.MOCK_ALL_COMMENTS = transformAllComments(review.findings);
    window.MOCK_REVIEW_RAW = review;
    window.MOCK_REVIEW_LANGUAGE = review.review?.language || body.review_language;

    return review;
  }

  function localChatFallback(question, review, language) {
    const zh = language === "zh";
    const findings = review.findings || [];
    const top = findings.find((f) => f.severity === "critical") || findings[0];
    if (!top) {
      return zh
        ? "当前 review 没有结构化 finding 可用于回答这个问题。可以先完成一次真实 review，或者切到 summary 查看当前 diff 摘要。"
        : "This review has no structured finding to answer from yet. Run a real review first, or check the summary tab for the loaded diff.";
    }
    const intro = zh
      ? "后端 chat 暂时不可用；下面是基于当前 finding 的本地回答："
      : "The chat backend is unavailable; here is a local answer from the current finding:";
    return [
      intro,
      `${top.severity || "finding"}: ${top.title || ""}`,
      `${top.file || ""}${top.line ? ":" + top.line : ""}`,
      top.body || "",
    ].filter(Boolean).join("\n");
  }

  async function askReviewChat(question, options = {}) {
    const language = options.reviewLanguage || window.MOCK_REVIEW_LANGUAGE || "en";
    const review = window.MOCK_REVIEW_RAW || buildCurrentReviewSnapshot();
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        review,
        review_language: language,
      }),
    });
    if (!resp.ok) {
      return localChatFallback(question, review, language);
    }
    const data = await resp.json();
    return data.answer || localChatFallback(question, review, language);
  }

  window.runRealReview = runRealReview;
  window.askReviewChat = askReviewChat;
  window.renderChatText = renderMarkdown;
  window.MOCK_REVIEW_RAW = window.MOCK_REVIEW_RAW || buildCurrentReviewSnapshot();
  window.MOCK_REVIEW_LANGUAGE = window.MOCK_REVIEW_LANGUAGE || "en";
  // Expose helpers for app.jsx to swap active file's diff_hunks into MOCK_DIFF.
  window.setActiveDiff = function (idx) {
    if (window.MOCK_FILES && window.MOCK_FILES[idx]) {
      window.MOCK_DIFF = window.MOCK_FILES[idx].diff_hunks || [];
    }
  };
})();
