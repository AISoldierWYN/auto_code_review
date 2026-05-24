package com.acme.profile;

import android.content.ContentResolver;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.ContactsContract;

public final class ProfileRepository {
    private final ContentResolver resolver;

    public ProfileRepository(Context context) {
        this.resolver = context.getContentResolver();
    }

    public String resolveDisplayName(String accountId, String fallback) {
        String cached = ProfileCache.get(accountId);
        if (cached != null) {
            return cached;
        }
        String display = queryLocalDisplayName(accountId);
        return display == null ? fallback : display;
    }

    private String queryLocalDisplayName(String accountId) {
        Uri uri = ContactsContract.Profile.CONTENT_URI;
        String[] projection = new String[] {
                ContactsContract.Profile.DISPLAY_NAME_PRIMARY,
                ContactsContract.Profile.LOOKUP_KEY
        };
        Cursor cursor = resolver.query(uri, projection, "lookup = ?", new String[] { accountId }, null);
        if (cursor == null) {
            return null;
        }
        if (!cursor.moveToFirst()) {
            return null;
        }
        String name = cursor.getString(0);
        if (name == null || name.trim().isEmpty()) {
            return cursor.getString(1);
        }
        return name.trim();
    }

    private static final class ProfileCache {
        static String get(String key) {
            return null;
        }
    }
}
