package com.acme.themes;

import android.content.Context;
import android.net.Uri;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public final class SafeThemePackInstaller {
    private final Context context;

    public SafeThemePackInstaller(Context context) {
        this.context = context.getApplicationContext();
    }

    public File install(Uri packUri) throws IOException {
        File installRoot = new File(context.getFilesDir(), "themes/current");
        if (!installRoot.exists() && !installRoot.mkdirs()) {
            throw new IOException("Could not create theme directory");
        }

        File canonicalRootFile = installRoot.getCanonicalFile();
        String canonicalRoot = canonicalRootFile.getPath() + File.separator;

        try (
            InputStream raw = context.getContentResolver().openInputStream(packUri);
            ZipInputStream zip = new ZipInputStream(raw)
        ) {
            if (raw == null) {
                throw new IOException("Could not open theme pack");
            }

            ZipEntry entry;
            byte[] buffer = new byte[4096];
            while ((entry = zip.getNextEntry()) != null) {
                if (entry.isDirectory()) {
                    zip.closeEntry();
                    continue;
                }

                File target = new File(canonicalRootFile, entry.getName());
                String canonicalTarget = target.getCanonicalPath();
                if (!canonicalTarget.startsWith(canonicalRoot)) {
                    throw new IOException("Blocked zip path traversal: " + entry.getName());
                }

                File parent = target.getParentFile();
                if (parent != null && !parent.exists() && !parent.mkdirs()) {
                    throw new IOException("Could not create parent directory");
                }
                try (FileOutputStream out = new FileOutputStream(target)) {
                    int read;
                    while ((read = zip.read(buffer)) != -1) {
                        out.write(buffer, 0, read);
                    }
                }
                zip.closeEntry();
            }
        }

        return canonicalRootFile;
    }
}
