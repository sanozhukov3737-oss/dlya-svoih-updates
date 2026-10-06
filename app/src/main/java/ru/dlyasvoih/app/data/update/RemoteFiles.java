package ru.dlyasvoih.app.data.update;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/** Bounded HTTPS transfers. TLS uses the system trust store and hostname checks. */
public final class RemoteFiles {
    private static final int MAX_REDIRECTS = 5;
    private static final long MAX_TRANSFER_NANOS = 5L * 60 * 1_000_000_000;
    interface ConnectionFactory { HttpURLConnection open(URL url) throws IOException; }
    public interface Progress { void downloaded(long bytes); }
    private final ConnectionFactory connections;

    public RemoteFiles() { this(url -> (HttpURLConnection) url.openConnection()); }
    RemoteFiles(ConnectionFactory connections) { this.connections = connections; }

    public static URL httpsUrl(String value) {
        try {
            if (value == null || value.length() > 2048) throw new IllegalArgumentException();
            URI uri = new URI(value);
            if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null ||
                    uri.getHost().isEmpty() || uri.getUserInfo() != null || uri.getFragment() != null)
                throw new IllegalArgumentException();
            return uri.toURL();
        } catch (URISyntaxException | MalformedURLException | IllegalArgumentException e) {
            throw new IllegalArgumentException("Укажите полную HTTPS-ссылку без логина и пароля");
        }
    }

    private HttpURLConnection open(String address) throws IOException {
        URL url = httpsUrl(address);
        for (int redirect = 0; redirect <= MAX_REDIRECTS; redirect++) {
            HttpURLConnection connection = connections.open(url);
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(15_000);
            connection.setReadTimeout(20_000);
            connection.setUseCaches(false);
            connection.setRequestProperty("Accept-Encoding", "identity");
            connection.setRequestProperty("User-Agent", "DlyaSvoih-Catalog/1");
            try {
                int status = connection.getResponseCode();
                if (status == HttpURLConnection.HTTP_OK) return connection;
                if (status == 301 || status == 302 || status == 303 || status == 307 || status == 308) {
                    String location = connection.getHeaderField("Location");
                    if (location == null || redirect == MAX_REDIRECTS) throw new IOException("Invalid redirect");
                    url = httpsUrl(new URL(url, location).toString());
                } else throw new IOException("Update server returned HTTP " + status);
            } catch (IOException | RuntimeException e) {
                connection.disconnect();
                throw e;
            }
            connection.disconnect();
        }
        throw new IOException("Too many redirects");
    }

    public String text(String address) throws IOException {
        HttpURLConnection connection = open(address);
        try {
            if (connection.getContentLengthLong() > 64 * 1024) throw new IOException("Feed too large");
            try (InputStream input = connection.getInputStream(); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192];
                int count;
                long started = System.nanoTime();
                while ((count = input.read(buffer)) != -1) {
                    if (Thread.currentThread().isInterrupted()) throw new InterruptedIOException();
                    if (System.nanoTime() - started > 45L * 1_000_000_000 || output.size() + count > 64 * 1024)
                        throw new IOException("Feed exceeds limits");
                    output.write(buffer, 0, count);
                }
                return new String(output.toByteArray(), StandardCharsets.UTF_8);
            }
        } finally { connection.disconnect(); }
    }

    public File download(String address, File target, long expectedBytes, String expectedHash, Progress progress) throws IOException {
        if (expectedBytes <= 0 || expectedBytes > PackFiles.MAX_ARCHIVE || expectedHash == null ||
                !expectedHash.matches("[a-fA-F0-9]{64}")) throw new IllegalArgumentException("Некорректное описание обновления");
        HttpURLConnection connection = open(address);
        boolean complete = false;
        try {
            long length = connection.getContentLengthLong();
            if (length >= 0 && length != expectedBytes) throw new IOException("Unexpected download size");
            long started = System.nanoTime(), lastTick = started, lastReported = 0, total = 0;
            progress.downloaded(0);
            try (InputStream input = connection.getInputStream(); FileOutputStream output = new FileOutputStream(target)) {
                byte[] buffer = new byte[32768];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    if (Thread.currentThread().isInterrupted()) throw new InterruptedIOException();
                    long now = System.nanoTime();
                    if (now - started > MAX_TRANSFER_NANOS) throw new IOException("Download timeout");
                    total += count;
                    if (total > expectedBytes) throw new IOException("Download exceeds declared size");
                    output.write(buffer, 0, count);
                    if (total - lastReported >= 256 * 1024 || now - lastTick >= 150_000_000) {
                        progress.downloaded(total);
                        lastReported = total;
                        lastTick = now;
                    }
                }
                output.getFD().sync();
            }
            if (total != expectedBytes || !PackFiles.sha256(target).equals(expectedHash.toLowerCase(Locale.ROOT)))
                throw new IOException("Downloaded update failed verification");
            progress.downloaded(total);
            complete = true;
            return target;
        } finally {
            connection.disconnect();
            if (!complete) target.delete();
        }
    }
}
