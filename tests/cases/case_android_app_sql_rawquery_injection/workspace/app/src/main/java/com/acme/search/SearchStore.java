package com.acme.search;

import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import java.util.ArrayList;
import java.util.List;

public final class SearchStore {
    private final SQLiteDatabase db;

    public SearchStore(SQLiteDatabase db) {
        this.db = db;
    }

    public List<SearchHit> findRecent(String keyword, int limit) {
        String normalized = normalize(keyword);
        String sql = "SELECT doc_id, title, updated_at FROM docs "
                + "WHERE deleted = 0 AND title LIKE '%" + normalized + "%' "
                + "ORDER BY updated_at DESC LIMIT " + Math.min(limit, 50);
        Cursor cursor = db.rawQuery(sql, null);
        List<SearchHit> hits = new ArrayList<>();
        try {
            while (cursor.moveToNext()) {
                hits.add(new SearchHit(cursor.getString(0), cursor.getString(1)));
            }
            return hits;
        } finally {
            cursor.close();
        }
    }

    private static String normalize(String keyword) {
        if (keyword == null) {
            return "";
        }
        return keyword.trim().replace('\n', ' ');
    }

    public record SearchHit(String id, String title) {
    }
}
