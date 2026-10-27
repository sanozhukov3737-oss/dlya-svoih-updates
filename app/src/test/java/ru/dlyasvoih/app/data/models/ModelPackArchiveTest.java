package ru.dlyasvoih.app.data.models;

import org.junit.Test;
import static org.junit.Assert.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.*;

public class ModelPackArchiveTest {
    private static final byte[] MODEL = "reviewed-model-data".getBytes(StandardCharsets.UTF_8);
    private String sha(byte[] bytes) throws Exception {
        StringBuilder s = new StringBuilder();
        for (byte b : MessageDigest.getInstance("SHA-256").digest(bytes)) s.append(String.format(Locale.ROOT,"%02x", b & 255));
        return s.toString();
    }
    private File archive(boolean extra) throws Exception {
        File p = File.createTempFile("model-pack-", ".zip"); p.deleteOnExit();
        try (ZipOutputStream z = new ZipOutputStream(new FileOutputStream(p))) {
            z.putNextEntry(new ZipEntry("model.glb")); z.write(MODEL); z.closeEntry();
            if (extra) { z.putNextEntry(new ZipEntry("../escape.glb")); z.write(MODEL); z.closeEntry(); }
        }
        return p;
    }
    private Map<String,ModelPackArchive.Entry> expected() throws Exception {
        return Collections.singletonMap("model.glb", new ModelPackArchive.Entry(MODEL.length, sha(MODEL)));
    }
    @Test public void exactPinnedArchiveReadsUnchangedBytes() throws Exception {
        File p=archive(false);
        ModelPackArchive.verify(p,p.length(),sha(Files.readAllBytes(p.toPath())),expected(),()->false);
        assertArrayEquals(MODEL,ModelPackArchive.read(p,"model.glb",expected().get("model.glb")));
    }
    @Test public void changedArchiveIsRejected() throws Exception {
        File p=archive(false);
        assertThrows(IOException.class,()->ModelPackArchive.verify(p,p.length(),"0".repeat(64),expected(),()->false));
    }
    @Test public void extraTraversalEntryIsRejectedEvenWithMatchingArchiveHash() throws Exception {
        File p=archive(true);
        assertThrows(IOException.class,()->ModelPackArchive.verify(p,p.length(),sha(Files.readAllBytes(p.toPath())),expected(),()->false));
    }
    @Test public void missingModelIsRejected() throws Exception {
        File p=archive(false); Map<String,ModelPackArchive.Entry> files=new HashMap<>(expected());
        files.put("other.glb",new ModelPackArchive.Entry(MODEL.length,sha(MODEL)));
        assertThrows(IOException.class,()->ModelPackArchive.verify(p,p.length(),sha(Files.readAllBytes(p.toPath())),files,()->false));
    }
    @Test public void perModelHashPreventsReadingTamperedExternalStorage() throws Exception {
        File p=archive(false);
        assertThrows(IOException.class,()->ModelPackArchive.read(p,"model.glb",new ModelPackArchive.Entry(MODEL.length,"0".repeat(64))));
        assertThrows(IOException.class,()->ModelPackArchive.read(p,"../model.glb",expected().get("model.glb")));
    }
    @Test public void cancelledVerificationStopsBeforeActivation() throws Exception {
        File p=archive(false);
        assertThrows(InterruptedIOException.class,()->ModelPackArchive.verify(p,p.length(),sha(Files.readAllBytes(p.toPath())),expected(),()->true));
        assertTrue(p.isFile());
    }
    @Test public void oversizedModelIsRejectedBeforeAllocation() {
        assertThrows(IllegalArgumentException.class,()->new ModelPackArchive.Entry(ModelPackArchive.MAX_MODEL_BYTES+1,"0".repeat(64)));
    }
}
