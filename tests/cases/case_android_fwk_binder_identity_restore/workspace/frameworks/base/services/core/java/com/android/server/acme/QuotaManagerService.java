package com.android.server.acme;

import android.os.Binder;
import android.os.RemoteException;
import android.util.Slog;
import java.util.HashMap;
import java.util.Map;

public final class QuotaManagerService {
    private static final String TAG = "QuotaManagerService";
    private final Map<String, Integer> mOverrides = new HashMap<>();
    private final QuotaStore mStore;

    public QuotaManagerService(QuotaStore store) {
        mStore = store;
    }

    public void setTemporaryQuota(String packageName, int quota) throws RemoteException {
        if (quota < 0) {
            throw new IllegalArgumentException("quota must be positive");
        }
        long token = Binder.clearCallingIdentity();
        PackageState state = mStore.load(packageName);
        if (state == null) {
            Slog.w(TAG, "Unknown package " + packageName);
            return;
        }
        if (!state.isInstalled()) {
            return;
        }
        mOverrides.put(packageName, quota);
        mStore.persist(packageName, quota);
        Binder.restoreCallingIdentity(token);
    }

    public interface QuotaStore {
        PackageState load(String packageName) throws RemoteException;
        void persist(String packageName, int quota);
    }

    public interface PackageState {
        boolean isInstalled();
    }
}
