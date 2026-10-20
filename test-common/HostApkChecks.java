package ru.dlyasvoih.app.data.update;

import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

public final class HostApkChecks {
    static ApkUpdatePolicy.Identity identity(String pkg, long code, String name, int sdk, String signer) {
        return new ApkUpdatePolicy.Identity(pkg, code, name, sdk,
            signer.isEmpty() ? Collections.emptySet() : Collections.singleton(signer));
    }
    interface Action { void run(); }
    static void rejects(Action action) {
        try { action.run(); } catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("Unsafe APK was accepted");
    }
    public static void main(String[] args) {
        ApkUpdatePolicy.Identity installed = identity("ru.dlyasvoih.app", 117, "0.3.113", 26, "same-key");
        ApkUpdatePolicy.Identity expected = identity("ru.dlyasvoih.app", 118, "0.3.114", 26, "same-key");
        ApkUpdatePolicy.validate(installed, expected, expected, 36);
        rejects(() -> ApkUpdatePolicy.validate(installed, expected, identity("other.app", 118, "0.3.114", 26, "same-key"), 36));
        rejects(() -> ApkUpdatePolicy.validate(installed, identity("other.app", 118, "0.3.114", 26, "same-key"), expected, 36));
        rejects(() -> ApkUpdatePolicy.validate(installed, expected, identity("ru.dlyasvoih.app", 117, "0.3.114", 26, "same-key"), 36));
        rejects(() -> ApkUpdatePolicy.validate(installed, expected, identity("ru.dlyasvoih.app", 119, "0.3.114", 26, "same-key"), 36));
        rejects(() -> ApkUpdatePolicy.validate(installed, expected, identity("ru.dlyasvoih.app", 118, "wrong-name", 26, "same-key"), 36));
        rejects(() -> ApkUpdatePolicy.validate(installed, expected, identity("ru.dlyasvoih.app", 118, "0.3.114", 27, "same-key"), 36));
        rejects(() -> ApkUpdatePolicy.validate(installed, expected, expected, 25));
        rejects(() -> ApkUpdatePolicy.validate(installed, expected, identity("ru.dlyasvoih.app", 118, "0.3.114", 26, "other-key"), 36));
        rejects(() -> ApkUpdatePolicy.validate(installed, expected, identity("ru.dlyasvoih.app", 118, "0.3.114", 26, ""), 36));
        rejects(() -> ApkUpdatePolicy.validate(installed, identity("ru.dlyasvoih.app", 118, "0.3.114", 26, "other-key"), expected, 36));
        rejects(() -> ApkUpdatePolicy.validate(installed, installed, installed, 36));
        Set<String> original = new HashSet<>(Collections.singleton("same-key"));
        ApkUpdatePolicy.Identity snapshot = new ApkUpdatePolicy.Identity("ru.dlyasvoih.app", 118, "0.3.114", 26, original);
        original.clear();
        ApkUpdatePolicy.validate(installed, expected, snapshot, 36);
        System.out.println("APK identity, version and signing checks passed");
    }
}
