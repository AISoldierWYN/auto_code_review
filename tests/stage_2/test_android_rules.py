"""Regression tests for the seeded Android typical-case rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code_review.diff.parser import parse_unified_diff
from ai_code_review.models.rule import Rule
from ai_code_review.rules.loader import load_rules
from ai_code_review.rules.recaller import recall_rules

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANDROID_RULES_DIR = PROJECT_ROOT / "rules" / "typical_case"

ANDROID_RULE_CASES = [
    (
        "RULE-ANDROID-APP-001",
        "app/src/main/java/com/acme/MainActivity.java",
        [
            "public void onClick(View v) {",
            "    HttpURLConnection c = (HttpURLConnection) url.openConnection();",
            "    c.connect();",
            "}",
        ],
    ),
    (
        "RULE-ANDROID-APP-002",
        "app/src/main/java/com/acme/UserDao.java",
        [
            "Cursor c = db.rawQuery(\"SELECT * FROM users\", null);",
            "return c.getCount();",
        ],
    ),
    (
        "RULE-ANDROID-APP-003",
        "app/src/main/java/com/acme/Uploader.java",
        [
            "PowerManager.WakeLock wakeLock = pm.newWakeLock(PARTIAL_WAKE_LOCK, TAG);",
            "wakeLock.acquire();",
            "upload();",
        ],
    ),
    (
        "RULE-ANDROID-APP-004",
        "app/src/main/java/com/acme/AlarmFactory.java",
        [
            "Intent intent = new Intent(ACTION_SYNC);",
            "PendingIntent pi = PendingIntent.getBroadcast(context, 0, intent, 0);",
        ],
    ),
    (
        "RULE-ANDROID-APP-005",
        "app/src/main/java/com/acme/HybridActivity.java",
        [
            "webView.getSettings().setJavaScriptEnabled(true);",
            "webView.addJavascriptInterface(new Bridge(), \"native\");",
            "webView.loadUrl(intent.getStringExtra(\"url\"));",
        ],
    ),
    (
        "RULE-ANDROID-APP-006",
        "app/src/main/java/com/acme/SearchDao.java",
        [
            "Cursor c = db.rawQuery(\"SELECT * FROM item WHERE name='\" + name + \"'\", null);",
        ],
    ),
    (
        "RULE-ANDROID-APP-007",
        "app/src/main/java/com/acme/NetworkActivity.java",
        [
            "protected void onStart() {",
            "    registerReceiver(receiver, new IntentFilter(CONNECTIVITY_ACTION));",
            "}",
        ],
    ),
    (
        "RULE-ANDROID-APP-008",
        "app/src/main/java/com/acme/SyncStarter.java",
        [
            "ContextCompat.startForegroundService(context, new Intent(context, SyncService.class));",
        ],
    ),
    (
        "RULE-ANDROID-APP-009",
        "app/src/main/java/com/acme/ApiClient.java",
        [
            "private static final String API = \"http://api.example.com/v1/profile\";",
        ],
    ),
    (
        "RULE-ANDROID-APP-010",
        "app/src/main/java/com/acme/AppHolder.java",
        [
            "private static Activity sActivity;",
            "static void init(Activity activity) { sActivity = activity; }",
        ],
    ),
    (
        "RULE-ANDROID-APP-011",
        "app/src/main/java/com/acme/ProfileFragment.kt",
        [
            "lifecycleScope.launch {",
            "    viewModel.state.collect { render(it) }",
            "}",
        ],
    ),
    (
        "RULE-ANDROID-APP-012",
        "app/src/main/java/com/acme/ProfileViewModel.kt",
        [
            "GlobalScope.launch(Dispatchers.IO) {",
            "    repository.refresh()",
            "}",
        ],
    ),
    (
        "RULE-ANDROID-APP-013",
        "app/src/main/java/com/acme/themes/ThemePackInstaller.java",
        [
            "ZipEntry entry;",
            "while ((entry = zip.getNextEntry()) != null) {",
            "    File target = new File(installRoot, entry.getName());",
            "    copy(zip, target);",
            "}",
        ],
    ),
    (
        "RULE-ANDROID-FWK-001",
        "frameworks/base/services/core/java/com/android/server/FooService.java",
        [
            "long token = Binder.clearCallingIdentity();",
            "if (!enabled) return;",
            "doPrivilegedWork();",
            "Binder.restoreCallingIdentity(token);",
        ],
    ),
    (
        "RULE-ANDROID-FWK-002",
        "frameworks/base/services/core/java/com/android/server/FooService.java",
        [
            "public void setFeatureEnabled(boolean enabled) {",
            "    mSettings.putBoolean(\"feature\", enabled);",
            "}",
        ],
    ),
    (
        "RULE-ANDROID-FWK-003",
        "frameworks/base/services/core/java/com/android/server/FooService.java",
        [
            "synchronized (mLock) {",
            "    mState = state;",
            "    callback.onStateChanged(state);",
            "}",
        ],
    ),
    (
        "RULE-ANDROID-FWK-004",
        "frameworks/base/services/core/java/com/android/server/FooService.java",
        [
            "int n = mCallbacks.beginBroadcast();",
            "for (int i = 0; i < n; i++) {",
            "    mCallbacks.getBroadcastItem(i).onChanged();",
            "}",
        ],
    ),
    (
        "RULE-ANDROID-FWK-005",
        "frameworks/base/services/core/java/com/android/server/FooService.java",
        [
            "client.asBinder().linkToDeath(record, 0);",
            "mClients.put(id, record);",
        ],
    ),
    (
        "RULE-ANDROID-FWK-006",
        "frameworks/base/services/core/java/com/android/server/FooService.java",
        [
            "public Bundle getProfile(int userId) {",
            "    return mStore.readProfile(userId);",
            "}",
        ],
    ),
]


def _make_diff(path: str, added_lines: list[str]) -> str:
    additions = "\n".join(f"+{line}" for line in added_lines)
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -1,1 +1,{len(added_lines) + 1} @@\n"
        " class Existing {}\n"
        f"{additions}\n"
    )


def _android_rules_by_id() -> dict[str, Rule]:
    return {
        rule.rule_id: rule
        for rule in load_rules(ANDROID_RULES_DIR)
        if rule.rule_id.startswith("RULE-ANDROID-")
    }


def test_seeded_android_rules_load() -> None:
    rules = _android_rules_by_id()

    assert len(rules) == 19
    assert all(rule.source.type == "typical_case" for rule in rules.values())
    assert all(rule.recall.keywords or rule.recall.regexes for rule in rules.values())


@pytest.mark.parametrize(
    ("rule_id", "path", "added_lines"),
    ANDROID_RULE_CASES,
    ids=[case[0] for case in ANDROID_RULE_CASES],
)
def test_seeded_android_rule_recall_hits(
    rule_id: str,
    path: str,
    added_lines: list[str],
) -> None:
    rule = _android_rules_by_id()[rule_id]
    diff_text = _make_diff(path, added_lines)
    diff = parse_unified_diff(diff_text)

    result = recall_rules([rule], diff, diff_text=diff_text)

    assert [r.rule_id for r in result.rules] == [rule_id]
