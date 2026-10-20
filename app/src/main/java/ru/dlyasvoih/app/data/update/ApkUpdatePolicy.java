package ru.dlyasvoih.app.data.update;

import java.util.Collections;
import java.util.HashSet;
import java.util.Objects;
import java.util.Set;

/** Rules shared by the Android verifier and executable host tests. */
public final class ApkUpdatePolicy {
    private ApkUpdatePolicy() { }
    public static final class Identity {
        public final String packageName, versionName;
        public final long versionCode;
        public final int minSdk;
        public final Set<String> signers;
        public Identity(String packageName, long versionCode, String versionName, int minSdk, Set<String> signers) {
            this.packageName = packageName; this.versionCode = versionCode;
            this.versionName = versionName; this.minSdk = minSdk;
            this.signers = Collections.unmodifiableSet(new HashSet<>(signers));
        }
    }
    public static void validate(Identity installed, Identity expected, Identity archive, int deviceSdk) {
        if (!Objects.equals(installed.packageName, expected.packageName) || !Objects.equals(installed.packageName, archive.packageName))
            throw new IllegalArgumentException("APK относится к другому приложению");
        if (archive.versionCode != expected.versionCode || archive.versionCode <= installed.versionCode ||
                !Objects.equals(archive.versionName, expected.versionName))
            throw new IllegalArgumentException("Версия APK не соответствует опубликованному обновлению");
        if (archive.minSdk != expected.minSdk || archive.minSdk > deviceSdk || archive.minSdk < 26)
            throw new IllegalArgumentException("APK не поддерживает эту версию Android");
        if (archive.signers.isEmpty() || !archive.signers.equals(installed.signers) || !archive.signers.equals(expected.signers))
            throw new IllegalArgumentException("Подпись APK отличается от установленного приложения. Установка отменена.");
    }
}
