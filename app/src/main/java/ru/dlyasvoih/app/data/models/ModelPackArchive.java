package ru.dlyasvoih.app.data.models;

import java.io.*;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import java.util.function.BooleanSupplier;
import java.util.zip.*;

/** Pinned data-only archive. Nothing is extracted or executed. */
public final class ModelPackArchive {
    public static final long MAX_MODEL_BYTES = 32L * 1024 * 1024;
    public static final class Entry {
        public final long bytes;
        public final String sha256;
        public Entry(long bytes, String sha256) {
            if (bytes <= 0 || bytes > MAX_MODEL_BYTES || sha256 == null || !sha256.matches("[a-f0-9]{64}"))
                throw new IllegalArgumentException("Некорректная запись модели");
            this.bytes = bytes; this.sha256 = sha256;
        }
    }
    private static MessageDigest digest() {
        try { return MessageDigest.getInstance("SHA-256"); }
        catch (NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }
    private static String hex(byte[] bytes) {
        StringBuilder s = new StringBuilder();
        for (byte b : bytes) s.append(String.format(Locale.ROOT, "%02x", b & 255));
        return s.toString();
    }
    public static void verify(File file, long bytes, String sha256, Map<String, Entry> expected,
            BooleanSupplier cancelled) throws IOException {
        if (!file.isFile() || file.length() != bytes) throw new IOException("Пакет скачан не полностью");
        MessageDigest hash = digest();
        try (InputStream stream = new BufferedInputStream(new FileInputStream(file))) {
            byte[] buffer = new byte[131072]; int count;
            while ((count = stream.read(buffer)) != -1) {
                if (cancelled.getAsBoolean() || Thread.currentThread().isInterrupted()) throw new InterruptedIOException();
                hash.update(buffer, 0, count);
            }
        }
        if (!hex(hash.digest()).equals(sha256)) throw new IOException("Пакет повреждён. Скачайте модели ещё раз.");
        try (ZipFile zip = new ZipFile(file)) {
            Set<String> seen = new HashSet<>();
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry e = entries.nextElement(); Entry record = expected.get(e.getName());
                if (e.isDirectory() || record == null || !seen.add(e.getName()) || e.getSize() != record.bytes)
                    throw new IOException("Содержимое пакета не соответствует коллекции");
            }
            if (!seen.equals(expected.keySet())) throw new IOException("В пакете отсутствуют модели");
        }
    }
    public static byte[] read(File file, String name, Entry expected) throws IOException {
        if (!name.matches("[a-z0-9-]+\\.glb")) throw new IOException("Недопустимое имя модели");
        try (ZipFile zip = new ZipFile(file)) {
            ZipEntry entry = zip.getEntry(name);
            if (entry == null || entry.getSize() != expected.bytes) throw new IOException("Модель недоступна в пакете");
            byte[] raw = new byte[(int)expected.bytes];
            try (DataInputStream input = new DataInputStream(zip.getInputStream(entry))) {
                input.readFully(raw);
                if (input.read() != -1) throw new IOException("Размер модели изменился");
            }
            if (!hex(digest().digest(raw)).equals(expected.sha256)) throw new IOException("Модель повреждена");
            return raw;
        }
    }
}
