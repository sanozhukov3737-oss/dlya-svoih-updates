package ru.dlyasvoih.app.data.update;

import java.io.*;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import java.util.zip.*;

/** Shared by Android and host tests. No network, SQL, or external path resolution. */
public final class PackFiles {
    public static final long MAX_ARCHIVE = 256L * 1024 * 1024;
    public static final long MAX_TOTAL = 512L * 1024 * 1024;
    public static final int MAX_ENTRIES = 20002;
    private PackFiles() {}

    public static boolean isMediaPath(String path) {
        return path != null && path.matches("(?:images|thumbs)/[a-zA-Z0-9_-]{1,96}\\.(?:webp|png|jpg|jpeg)");
    }

    public static long entryLimit(String name) throws IOException {
        if (name.equals("manifest.json")) return 2L * 1024 * 1024;
        if (name.equals("guide.db")) return 64L * 1024 * 1024;
        if (isMediaPath(name)) return 4L * 1024 * 1024;
        throw new IOException("Unexpected pack entry");
    }

    public static long copyLimited(InputStream input, OutputStream output, long limit) throws IOException {
        byte[] buffer = new byte[32768];
        long size = 0;
        int count;
        while ((count = input.read(buffer)) != -1) {
            if (Thread.currentThread().isInterrupted()) throw new InterruptedIOException();
            size += count;
            if (size > limit) throw new IOException("Pack size limit exceeded");
            output.write(buffer, 0, count);
        }
        return size;
    }

    public static Set<String> extract(File archive, File destination) throws IOException {
        if (archive.length() > MAX_ARCHIVE) throw new IOException("Archive too large");
        if (!destination.mkdir()) throw new IOException("Staging directory must be new");
        Set<String> names = new HashSet<>();
        long total = 0;
        try (ZipFile zip = new ZipFile(archive)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String name = entry.getName();
                long limit = entryLimit(name);
                if (entry.isDirectory() || !names.add(name) || names.size() > MAX_ENTRIES)
                    throw new IOException("Duplicate or invalid pack entry");
                if (entry.getSize() < 0 || entry.getSize() > limit) throw new IOException("Entry too large");
                File output = new File(destination, name);
                File parent = output.getParentFile();
                if (!parent.isDirectory() && !parent.mkdirs()) throw new IOException("Cannot create staging directory");
                try (InputStream input = zip.getInputStream(entry); FileOutputStream stream = new FileOutputStream(output)) {
                    long copied = copyLimited(input, stream, Math.min(limit, MAX_TOTAL - total));
                    if (copied != entry.getSize()) throw new IOException("Truncated pack entry");
                    total += copied;
                    stream.getFD().sync();
                }
            }
        }
        if (!names.contains("guide.db") || !names.contains("manifest.json")) throw new IOException("Incomplete pack");
        return Collections.unmodifiableSet(names);
    }

    public static String sha256(File file) throws IOException {
        final MessageDigest digest;
        try { digest = MessageDigest.getInstance("SHA-256"); }
        catch (NoSuchAlgorithmException e) { throw new AssertionError(e); }
        byte[] buffer = new byte[32768];
        try (InputStream input = Files.newInputStream(file.toPath())) {
            int count;
            while ((count = input.read(buffer)) != -1) digest.update(buffer, 0, count);
        }
        StringBuilder result = new StringBuilder(64);
        for (byte value : digest.digest()) result.append(String.format(Locale.ROOT, "%02x", value & 255));
        return result.toString();
    }
}
