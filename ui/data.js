// Mock PR data — a Java/Kotlin payments change
window.MOCK_PR = {
  id: "I7a3f8c2",
  cl: "318429",
  title: "Refactor PaymentProcessor to use coroutine-based retry",
  branch: "feature/payment-retry",
  target: "main",
  author: { name: "Lin Wei", role: "L4 · Payments", initials: "LW" },
  repo: "platform/payments-svc",
  time: "5 min ago",
  filesChanged: 4,
  additions: 142,
  deletions: 87,
  model: "claude-haiku-4.5",
  scanned: "12.3s",
  summary: "Wraps the synchronous retry loop in a suspending function and pulls timeout/backoff into a config object. Splits PaymentProcessor.process() into orchestration vs. transport. Adds a coroutine scope owned by the service.",
};

window.MOCK_FILES = [
  {
    path: "src/main/kotlin/payments/PaymentProcessor.kt",
    lang: "kotlin",
    add: 64,
    del: 41,
    sev: { critical: 1, warning: 2, suggestion: 1 },
  },
  {
    path: "src/main/kotlin/payments/RetryPolicy.kt",
    lang: "kotlin",
    add: 38,
    del: 0,
    sev: { critical: 0, warning: 1, suggestion: 2 },
  },
  {
    path: "src/main/java/payments/TransportClient.java",
    lang: "java",
    add: 22,
    del: 31,
    sev: { critical: 0, warning: 0, suggestion: 1 },
  },
  {
    path: "src/test/kotlin/payments/PaymentProcessorTest.kt",
    lang: "kotlin",
    add: 18,
    del: 15,
    sev: { critical: 0, warning: 1, suggestion: 0 },
  },
];

// Diff hunks for the active file
window.MOCK_DIFF = [
  { type: "hunk", text: "@@ -34,18 +34,32 @@ class PaymentProcessor(" },
  { type: "ctx", old: 34, new: 34, text: "    private val client: TransportClient," },
  { type: "ctx", old: 35, new: 35, text: "    private val metrics: MetricsRegistry," },
  { type: "del", old: 36, new: null, text: "    private val maxRetries: Int = 3" },
  { type: "add", old: null, new: 36, text: "    private val policy: RetryPolicy = RetryPolicy.default()" },
  { type: "ctx", old: 37, new: 37, text: ") {" },
  { type: "ctx", old: 38, new: 38, text: "" },
  { type: "del", old: 39, new: null, text: "    fun process(payment: Payment): PaymentResult {" },
  { type: "del", old: 40, new: null, text: "        var attempt = 0" },
  { type: "del", old: 41, new: null, text: "        while (attempt < maxRetries) {" },
  { type: "del", old: 42, new: null, text: "            try {" },
  { type: "del", old: 43, new: null, text: "                return client.send(payment)" },
  { type: "del", old: 44, new: null, text: "            } catch (e: Exception) {" },
  { type: "del", old: 45, new: null, text: "                attempt++" },
  { type: "del", old: 46, new: null, text: "                Thread.sleep(100L * attempt)" },
  { type: "del", old: 47, new: null, text: "            }" },
  { type: "del", old: 48, new: null, text: "        }" },
  { type: "del", old: 49, new: null, text: "        throw PaymentFailedException()" },
  { type: "del", old: 50, new: null, text: "    }" },
  { type: "add", old: null, new: 39, text: "    suspend fun process(payment: Payment): PaymentResult = coroutineScope {" },
  { type: "add", old: null, new: 40, text: "        var lastError: Throwable? = null" },
  { type: "add", old: null, new: 41, text: "        repeat(policy.maxAttempts) { attempt ->" },
  { type: "add", old: null, new: 42, text: "            try {" },
  { type: "add", old: null, new: 43, text: "                return@coroutineScope client.send(payment)" },
  { type: "add", old: null, new: 44, text: "            } catch (e: Throwable) {" },
  { type: "add", old: null, new: 45, text: "                lastError = e" },
  { type: "add", old: null, new: 46, text: "                delay(policy.backoff(attempt))" },
  { type: "add", old: null, new: 47, text: "            }" },
  { type: "add", old: null, new: 48, text: "        }" },
  { type: "add", old: null, new: 49, text: "        throw PaymentFailedException(cause = lastError)" },
  { type: "add", old: null, new: 50, text: "    }" },
  // critical comment anchors on line 44
  { type: "comment", anchorNew: 44, id: "c1" },
  { type: "ctx", old: 51, new: 51, text: "" },
  { type: "ctx", old: 52, new: 52, text: "    fun cancel(id: PaymentId) {" },
  { type: "ctx", old: 53, new: 53, text: "        client.cancel(id)" },
  { type: "ctx", old: 54, new: 54, text: "    }" },
  { type: "hunk", text: "@@ -78,7 +82,12 @@ class PaymentProcessor(" },
  { type: "ctx", old: 78, new: 82, text: "    private fun record(result: PaymentResult) {" },
  { type: "del", old: 79, new: null, text: "        metrics.counter(\"payment.result\").increment()" },
  { type: "add", old: null, new: 83, text: "        metrics.counter(\"payment.result\")" },
  { type: "add", old: null, new: 84, text: "            .tag(\"status\", result.status.name)" },
  { type: "add", old: null, new: 85, text: "            .increment()" },
  { type: "comment", anchorNew: 85, id: "c2" },
  { type: "ctx", old: 80, new: 86, text: "    }" },
  { type: "ctx", old: 81, new: 87, text: "}" },
  { type: "comment", anchorNew: 87, id: "c3" },
];

window.MOCK_COMMENTS = {
  c1: {
    severity: "critical",
    file: "PaymentProcessor.kt",
    line: 44,
    confidence: 0.92,
    title: "Catching Throwable masks CancellationException",
    body: "Catching <code>Throwable</code> inside a coroutine will swallow <code>CancellationException</code>, breaking structured concurrency. If a parent scope is cancelled, this loop will retry instead of propagating cancellation. Re-throw <code>CancellationException</code> explicitly or narrow the catch.",
    suggestion: {
      remove: ["            } catch (e: Throwable) {"],
      add: [
        "            } catch (e: CancellationException) {",
        "                throw e",
        "            } catch (e: Exception) {",
      ],
    },
  },
  c2: {
    severity: "warning",
    file: "PaymentProcessor.kt",
    line: 85,
    confidence: 0.78,
    title: "Counter is rebuilt on every call",
    body: "Each invocation creates a tagged counter, which Micrometer caches but at the cost of a lookup on the hot path. Hoist the tagged counter into a private val keyed by status, or use <code>MeterRegistry.counter(name, \"status\", status)</code> once per status.",
    suggestion: null,
  },
  c3: {
    severity: "suggestion",
    file: "PaymentProcessor.kt",
    line: 87,
    confidence: 0.64,
    title: "Consider exposing a SupervisorJob",
    body: "Since <code>process()</code> is now <code>suspend</code>, callers control the scope. If <code>PaymentProcessor</code> ever fans out work internally, a supervised scope avoids one failed child cancelling the whole batch. Not blocking — flagging for the next pass.",
    suggestion: null,
  },
};

// All comments across all files for the by-severity view
window.MOCK_ALL_COMMENTS = [
  {
    id: "c1", severity: "critical",
    file: "PaymentProcessor.kt", line: 44, confidence: 0.92,
    title: "Catching Throwable masks CancellationException",
    body: "Catching <code>Throwable</code> inside a coroutine will swallow <code>CancellationException</code>, breaking structured concurrency.",
  },
  {
    id: "c4", severity: "warning",
    file: "PaymentProcessor.kt", line: 41, confidence: 0.81,
    title: "repeat(N) doesn't expose the final attempt index cleanly",
    body: "Consider <code>for (attempt in 0 until policy.maxAttempts)</code> so the last attempt can skip the backoff delay and avoid a wasted sleep before the throw.",
  },
  {
    id: "c2", severity: "warning",
    file: "PaymentProcessor.kt", line: 85, confidence: 0.78,
    title: "Counter is rebuilt on every call",
    body: "Each invocation creates a tagged counter, which Micrometer caches but at the cost of a lookup on the hot path.",
  },
  {
    id: "c5", severity: "warning",
    file: "RetryPolicy.kt", line: 18, confidence: 0.74,
    title: "Backoff overflows at attempt > 20",
    body: "<code>1L shl attempt</code> overflows past attempt 62, but more importantly the resulting delay is unbounded. Cap at <code>maxBackoffMs</code>.",
  },
  {
    id: "c6", severity: "warning",
    file: "PaymentProcessorTest.kt", line: 52, confidence: 0.71,
    title: "Test relies on Thread.sleep instead of virtual time",
    body: "Switch to <code>runTest { advanceTimeBy(...) }</code> — the current implementation makes this suite ~3s slower than it needs to be.",
  },
  {
    id: "c3", severity: "suggestion",
    file: "PaymentProcessor.kt", line: 87, confidence: 0.64,
    title: "Consider exposing a SupervisorJob",
    body: "If <code>PaymentProcessor</code> ever fans out work internally, a supervised scope avoids one failed child cancelling the whole batch.",
  },
  {
    id: "c7", severity: "suggestion",
    file: "RetryPolicy.kt", line: 8, confidence: 0.66,
    title: "Data class would simplify equality + copy",
    body: "<code>RetryPolicy</code> looks like a value object. Making it a <code>data class</code> gives you <code>equals</code>, <code>hashCode</code> and <code>copy</code> for free.",
  },
  {
    id: "c8", severity: "suggestion",
    file: "RetryPolicy.kt", line: 24, confidence: 0.58,
    title: "Document the jitter strategy",
    body: "A short KDoc on <code>backoff()</code> explaining the full-jitter approach would help future readers.",
  },
  {
    id: "c9", severity: "suggestion",
    file: "TransportClient.java", line: 67, confidence: 0.55,
    title: "Use try-with-resources for HttpResponse",
    body: "<code>HttpResponse</code> implements <code>AutoCloseable</code> since JDK 21 — consider a try-with-resources block.",
  },
];

window.MOCK_HISTORY = [
  { cl: "318429", title: "Refactor PaymentProcessor to use coroutine-based retry", repo: "payments-svc", author: "LW", branch: "feature/payment-retry", at: "5m ago", sev: { c: 1, w: 4, s: 4 }, status: "open" },
  { cl: "318401", title: "Add idempotency key to /charges endpoint", repo: "payments-svc", author: "TQ", branch: "feature/idem-key", at: "2h ago", sev: { c: 0, w: 2, s: 3 }, status: "merged" },
  { cl: "318384", title: "Bump kotlinx-coroutines to 1.9.0", repo: "platform-libs", author: "RH", branch: "deps/coroutines", at: "3h ago", sev: { c: 0, w: 0, s: 1 }, status: "merged" },
  { cl: "318377", title: "Migrate billing webhooks to new envelope schema", repo: "billing-svc", author: "MS", branch: "feature/v2-envelope", at: "Yesterday", sev: { c: 2, w: 5, s: 6 }, status: "changes" },
  { cl: "318359", title: "Replace ad-hoc cache with Caffeine", repo: "checkout-api", author: "LW", branch: "perf/caffeine", at: "Yesterday", sev: { c: 0, w: 1, s: 2 }, status: "merged" },
  { cl: "318340", title: "Wire OpenTelemetry into TransportClient", repo: "payments-svc", author: "TQ", branch: "obs/otel-client", at: "2d ago", sev: { c: 0, w: 3, s: 2 }, status: "merged" },
  { cl: "318312", title: "Strip PII from refund webhook payload", repo: "billing-svc", author: "MS", branch: "fix/pii-refund", at: "3d ago", sev: { c: 1, w: 1, s: 0 }, status: "merged" },
  { cl: "318298", title: "Promote experimental settlement adapter to default", repo: "payments-svc", author: "RH", branch: "feature/settlement", at: "4d ago", sev: { c: 0, w: 2, s: 4 }, status: "merged" },
];

window.MOCK_TEAM = [
  { name: "Lin Wei",   initials: "LW", role: "L4 · Payments",   reviews: 142, accepted: "73%", avg: "9.4s" },
  { name: "Tan Qing",  initials: "TQ", role: "L5 · Platform",   reviews: 118, accepted: "81%", avg: "8.2s" },
  { name: "Ruo Han",   initials: "RH", role: "L3 · Payments",   reviews: 96,  accepted: "68%", avg: "11.1s" },
  { name: "Mei Shan",  initials: "MS", role: "L4 · Billing",    reviews: 88,  accepted: "76%", avg: "9.9s" },
  { name: "Jiang Bo",  initials: "JB", role: "L4 · Checkout",   reviews: 64,  accepted: "70%", avg: "10.3s" },
  { name: "Yu Fei",    initials: "YF", role: "L3 · Platform",   reviews: 41,  accepted: "65%", avg: "12.7s" },
];

window.MOCK_WEEKLY = [
  { day: "Mon", c: 3, w: 9,  s: 14 },
  { day: "Tue", c: 1, w: 12, s: 18 },
  { day: "Wed", c: 4, w: 8,  s: 11 },
  { day: "Thu", c: 2, w: 14, s: 16 },
  { day: "Fri", c: 5, w: 11, s: 13 },
  { day: "Sat", c: 0, w: 2,  s: 4 },
  { day: "Sun", c: 1, w: 3,  s: 6 },
];
