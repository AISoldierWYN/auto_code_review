/* Verify the review diff column can scroll with a long Android case. */

const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const UI_DIR = path.join(ROOT, "ui");
const CASE_DIFF = path.join(
  ROOT,
  "tests",
  "cases",
  "case_android_app_main_thread_refresh_io",
  "change.diff"
);
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const EXTERNAL_UI_URL = process.env.VERIFY_UI_URL || "";

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".jsx": "text/babel; charset=utf-8",
  ".css": "text/css; charset=utf-8",
};
const NO_CACHE_HEADERS = {
  "cache-control": "no-store, no-cache, must-revalidate, max-age=0",
  pragma: "no-cache",
  expires: "0",
};

function buildDiffHunks(diffText) {
  const out = [];
  const lines = diffText.replace(/\r\n/g, "\n").split("\n");
  let oldLine = null;
  let newLine = null;

  for (const line of lines) {
    if (line.startsWith("@@")) {
      out.push({ type: "hunk", text: line });
      const match = /\-(\d+)(?:,\d+)? \+(\d+)(?:,\d+)?/.exec(line);
      oldLine = match ? Number(match[1]) : 0;
      newLine = match ? Number(match[2]) : 0;
      continue;
    }
    if (oldLine === null || newLine === null) continue;
    if (line.startsWith("+++")) continue;
    if (line.startsWith("+")) {
      out.push({ type: "add", old: null, new: newLine, text: line.slice(1) });
      if (newLine === 31) {
        out.push({ type: "comment", anchorNew: newLine, id: "c1" });
      }
      newLine += 1;
    } else if (line.startsWith("-")) {
      out.push({ type: "del", old: oldLine, new: null, text: line.slice(1) });
      oldLine += 1;
    } else if (line.length > 0 || out.length > 0) {
      out.push({ type: "ctx", old: oldLine, new: newLine, text: line.slice(1) });
      oldLine += 1;
      newLine += 1;
    }
  }
  return out;
}

function reviewJson() {
  const diffText = fs.readFileSync(CASE_DIFF, "utf8");
  const diffHunks = buildDiffHunks(diffText);
  return {
    schema_version: "1.0",
    review: {
      diff_path: "tests/cases/case_android_app_main_thread_refresh_io/change.diff",
      title: "change",
      branch: null,
      target: null,
      author: null,
      repo: null,
      model: "playwright-fixture",
      scanned_seconds: 0.1,
      files_changed: 1,
      additions: 51,
      deletions: 0,
      summary: "Adds FeedActivity with a synchronous refreshFeaturedStory path.",
      language: "en",
      metadata: { rules_total: 19, rules_after_filter: 1, rules_dropped_by_l4: [] },
    },
    files: [{
      path: "app/src/main/java/com/acme/news/FeedActivity.java",
      lang: "java",
      add: 51,
      del: 0,
      sev: { critical: 1, warning: 0, suggestion: 0 },
      diff_hunks: diffHunks,
    }],
    findings: [{
      id: "c1",
      rule_id: "RULE-ANDROID-APP-001",
      severity: "critical",
      category: "performance",
      file: "app/src/main/java/com/acme/news/FeedActivity.java",
      line: 31,
      confidence: 0.91,
      title: "Network I/O runs on the Activity main thread",
      body: "refreshFeaturedStory is called from onCreate and opens an HttpURLConnection synchronously, so Activity startup can block input and rendering.",
      suggestion: null,
      rationale: {
        rule_source_type: "typical_case",
        source_refs: ["https://developer.android.com/topic/performance/vitals/anr"],
      },
    }],
  };
}

function serve() {
  const server = http.createServer((req, res) => {
    const urlPath = decodeURIComponent((req.url || "/").split("?")[0]);
    if (req.method === "POST" && urlPath === "/api/review") {
      const body = JSON.stringify(reviewJson());
      res.writeHead(200, { "content-type": "application/json; charset=utf-8", ...NO_CACHE_HEADERS });
      res.end(body);
      return;
    }

    if (urlPath === "/favicon.ico") {
      res.writeHead(204, NO_CACHE_HEADERS);
      res.end();
      return;
    }

    const rel = urlPath === "/" ? "index.html" : urlPath.replace(/^\/+/, "");
    const file = path.resolve(UI_DIR, rel);
    const relative = path.relative(UI_DIR, file);
    if (relative.startsWith("..") || path.isAbsolute(relative) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404);
      res.end("not found");
      return;
    }
    res.writeHead(200, { "content-type": MIME[path.extname(file)] || "application/octet-stream", ...NO_CACHE_HEADERS });
    fs.createReadStream(file).pipe(res);
  });

  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

(async () => {
  const server = EXTERNAL_UI_URL ? null : await serve();
  const targetUrl = EXTERNAL_UI_URL || `http://127.0.0.1:${server.address().port}/`;
  const browser = await chromium.launch({
    executablePath: CHROME,
    headless: true,
    args: ["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox"],
  });
  const page = await browser.newPage({ viewport: { width: 1919, height: 923 } });
  page.on("console", (msg) => {
    if (msg.type() === "error") console.log("[browser error]", msg.text());
  });

  try {
    if (EXTERNAL_UI_URL) {
      await page.route("**/api/review", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json; charset=utf-8",
          headers: NO_CACHE_HEADERS,
          body: JSON.stringify(reviewJson()),
        });
      });
    }
    await page.route("**/api/chat", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json; charset=utf-8",
        headers: NO_CACHE_HEADERS,
        body: JSON.stringify({
          answer: [
            "### Risk",
            "**FeedActivity** is risky because `refreshFeaturedStory` opens `HttpURLConnection` from `onCreate` on the UI thread.",
            "",
            "| Line | Risk |",
            "| --- | --- |",
            "| 31 | Blocking network I/O |",
            "",
            "```java",
            "conn.connect();",
            "```",
            "",
            "1. **Native memory** - Cursor rows may keep JNI/native buffers alive.",
            "   Java GC cannot reclaim them directly while the cursor stays open.",
            "1. **Database handle** - The query can keep a database connection pinned.",
            "   Leaking it can starve later queries.",
            "1. **File descriptor** - Provider cursors may hold file descriptors.",
            "   Too many leaked descriptors can break unrelated I/O.",
          ].join("\n"),
        }),
      });
    });

    await page.goto(targetUrl, { waitUntil: "networkidle" });
    await page.locator(".empty-card").waitFor({ timeout: 10000 });
    await page.locator(".empty-card input").fill("tests/cases/case_android_app_main_thread_refresh_io/change.diff");
    await page.locator(".empty-card .btn.primary").click();
    await page.locator(".file-block").waitFor({ timeout: 10000 });

    const before = await page.locator(".review-mid").evaluate((el) => ({
      scrollTop: el.scrollTop,
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
    }));

    await page.locator(".code").hover();
    await page.mouse.wheel(0, 900);
    await page.waitForTimeout(200);

    const afterWheel = await page.locator(".review-mid").evaluate((el) => ({
      scrollTop: el.scrollTop,
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
    }));

    await page.locator(".review-mid").evaluate((el) => { el.scrollTop = el.scrollHeight; });
    await page.waitForTimeout(100);

    await page.locator(".chat-input").fill("what is the risk of FeedActivity.java");
    await page.locator(".chat-input-row .btn.primary").click();
    await page.waitForFunction(() => document.body.innerText.includes("FeedActivity is risky"));
    const chatText = await page.locator(".chat-msgs").innerText();
    const markdownOk = await page.locator(".chat-msgs").evaluate((el) => {
      const last = el.querySelector(".msg.ai:last-child .text");
      const orderedLists = last ? last.querySelectorAll("ol") : [];
      const orderedItems = orderedLists.length ? orderedLists[0].querySelectorAll("li") : [];
      return Boolean(
        last
        && last.querySelector("h3")
        && last.querySelector("strong")
        && last.querySelector("code")
        && last.querySelector("table")
        && last.querySelector("pre code")
        && orderedLists.length === 1
        && orderedItems.length === 3
      );
    });

    const afterProgrammatic = await page.locator(".review-mid").evaluate((el) => ({
      scrollTop: el.scrollTop,
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
    }));

    const screenshotPath = path.join(ROOT, "reviews", "playwright-scroll.png");
    fs.mkdirSync(path.dirname(screenshotPath), { recursive: true });
    await page.screenshot({ path: screenshotPath, fullPage: false });

    console.log(JSON.stringify({
      before,
      afterWheel,
      afterProgrammatic,
      chatOk: chatText.includes("FeedActivity is risky") && !chatText.includes("PaymentController"),
      markdownOk,
      screenshotPath,
      ok: afterWheel.scrollTop > before.scrollTop
        && afterProgrammatic.scrollTop > before.scrollTop
        && chatText.includes("FeedActivity is risky")
        && !chatText.includes("PaymentController")
        && markdownOk,
    }, null, 2));

    if (!(afterWheel.scrollTop > before.scrollTop
      && afterProgrammatic.scrollTop > before.scrollTop
      && chatText.includes("FeedActivity is risky")
      && !chatText.includes("PaymentController")
      && markdownOk)) {
      process.exitCode = 1;
    }
  } finally {
    await browser.close();
    if (server) server.close();
  }
})();
