package ru.dlyasvoih.app.data.update;

import ru.dlyasvoih.app.ui.ReaderIndex;
import java.io.*;
import java.net.*;
import java.nio.file.*;
import java.util.*;

/** Runs production Java logic with controlled responses, without a phone or external network. */
public final class HostFeatureChecks {
    static void check(boolean value, String message) { if (!value) throw new AssertionError(message); }
    interface Action { void run() throws Exception; }
    static void fails(Action action) throws Exception {
        try { action.run(); } catch (IOException | IllegalArgumentException expected) { return; }
        throw new AssertionError("Expected rejection");
    }
    static class Reply extends HttpURLConnection {
        final byte[] bytes;
        final int status;
        final String location;
        final long length;
        boolean disconnected;
        Reply(URL url, byte[] bytes, int status, String location, long length) {
            super(url); this.bytes = bytes; this.status = status; this.location = location; this.length = length;
        }
        public void connect() { }
        public boolean usingProxy() { return false; }
        public void disconnect() { disconnected = true; }
        public int getResponseCode() { return status; }
        public String getHeaderField(String name) { return "Location".equals(name) ? location : null; }
        public long getContentLengthLong() { return length; }
        public InputStream getInputStream() { return new ByteArrayInputStream(bytes); }
    }
    public static void main(String[] args) throws Exception {
        ReaderIndex index = new ReaderIndex(Arrays.asList("ТМ-62", "Ёлка", "Model A", "ТМ-15"));
        check(index.find("").equals(Arrays.asList(0,1,2,3)), "All cards keep original order");
        check(index.find("тм62").equals(Arrays.asList(0)), "Punctuation-insensitive model search");
        check(index.find("ЕЛКА").equals(Arrays.asList(1)), "Case and ё/е");
        check(index.find("MODEL a").equals(Arrays.asList(2)), "Latin case");
        check(index.find("3").equals(Arrays.asList(2)), "Page number is one-based");
        check(index.find("0").isEmpty() && index.find("5").isEmpty(), "Number bounds");
        check(index.find("999999999999999999").isEmpty() && index.find("!!!").isEmpty(), "Invalid input");
        check(index.find("тм").equals(Arrays.asList(0,3)), "Search does not renumber matches");
        for (String bad : Arrays.asList("http://example.com/a", "file:///a", "https://user:pass@example.com/a", "https://example.com/a#fragment", "https:///a"))
            fails(() -> RemoteFiles.httpsUrl(bad));
        check(RemoteFiles.httpsUrl("https://example.com/a?version=2").getHost().equals("example.com"), "HTTPS URL");

        Path directory = Files.createTempDirectory("catalog-download-check");
        try {
            File original = directory.resolve("original").toFile();
            byte[] data = "verified catalog package".getBytes(java.nio.charset.StandardCharsets.UTF_8);
            Files.write(original.toPath(), data);
            String hash = PackFiles.sha256(original);
            File target = directory.resolve("download.zip").toFile();
            List<Reply> calls = new ArrayList<>();
            RemoteFiles client = new RemoteFiles(url -> {
                Reply reply = new Reply(url, data, 200, null, -1);
                calls.add(reply); return reply;
            });
            List<Long> progress = new ArrayList<>();
            client.download("https://example.com/a.zip", target, data.length, hash, progress::add);
            check(Arrays.equals(Files.readAllBytes(target.toPath()), data), "Exact downloaded bytes");
            check(progress.get(0) == 0 && progress.get(progress.size()-1) == data.length, "Progress bounds");
            check(calls.get(0).disconnected, "Connection closes on success");
            fails(() -> client.download("https://example.com/a.zip", target, data.length, "0".repeat(64), bytes -> {}));
            check(!target.exists(), "Corrupt download removed");
            fails(() -> client.download("https://example.com/a.zip", target, data.length-1, hash, bytes -> {}));
            check(!target.exists(), "Oversized stream removed");
            fails(() -> client.download("https://example.com/a.zip", target, data.length+1, hash, bytes -> {}));
            check(!target.exists(), "Truncated stream removed");
            for (Reply reply : calls) check(reply.disconnected, "Connection closes on failure");
            RemoteFiles downgrade = new RemoteFiles(url -> new Reply(url, data, 302, "http://example.com/a.zip", -1));
            fails(() -> downgrade.text("https://example.com/feed"));
            RemoteFiles loop = new RemoteFiles(url -> new Reply(url, data, 302, "/feed", -1));
            fails(() -> loop.text("https://example.com/feed"));
            RemoteFiles oversized = new RemoteFiles(url -> new Reply(url, new byte[65537], 200, null, -1));
            fails(() -> oversized.text("https://example.com/feed"));
            RemoteFiles status = new RemoteFiles(url -> new Reply(url, data, 404, null, -1));
            fails(() -> status.text("https://example.com/feed"));
            RemoteFiles redirected = new RemoteFiles(url -> new Reply(url, data,
                url.getPath().equals("/feed") ? 302 : 200, "/latest.json", -1));
            check(redirected.text("https://example.com/feed").equals(new String(data, java.nio.charset.StandardCharsets.UTF_8)), "HTTPS redirect");
        } finally {
            try (java.util.stream.Stream<Path> files = Files.walk(directory)) {
                files.sorted(Comparator.reverseOrder()).forEach(path -> { try { Files.delete(path); } catch (IOException e) { throw new UncheckedIOException(e); } });
            }
        }
        System.out.println("Reader index and HTTPS transfer checks passed");
    }
}
