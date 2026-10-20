#!/usr/bin/env python3
"""Sign the byte-for-byte recovered 0.3.134 candidate with the existing CI key."""
import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import tempfile
import zipfile
from pathlib import Path


CERT = "2f0a0908f269bc039311edb58fca8863347f1e4c3a7cfaddd909991cf1f0b509"
ARCHIVE_SHA = "4d4ea41cf03a341f7def67fda7d9238440fd9947b0a2b03cf403890577b0e8c1"
UNSIGNED_SHA = "43ffc8b8d8ba2a632d3d13a5f287a4fb6a6a43bddf008122026186aa2a0197f4"
PREVIOUS_SHA = "8cff50f9d76dbeec261ca928603277bdf540d0d0b42913bde919a82ce8d5d49f"
BUNDLE_SHA = "17f54a6770eb980241edd5fd2ac356b93cda4785bac3b708bcda9c6d8d078104"
DB_SHA = "937b641c3296fb7ea381674d5854e514b7ea84d604060fcc6b52ee9890b4ed8b"
REPAIRED_DB_SHA = "fbbb7a38d77b09b963520011ef64b8111991e03ed1b2ae6277ec335761a107ed"
MANIFEST_SHA = "11402c11a9f2ac1ad95770ced7f5d25073c8016ba5d4fa0c33b1e943ccd797f4"
SOURCE_COMMIT = "e5eb15076c4727ec0deb32a4f7b2ac43b1e3b812"
DB_ASSET = "assets/database/guide-v29.db"
MODELS_ASSET = "assets/viewer3d/models.json"
VIEWER_ASSET = "assets/viewer3d/viewer.bundle.js"
VIEWER_SHA = "4a9cb38da18262a7c6c31faf6360ad8d356fb8ba866dba799360d2ab40e5c713"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(args):
    result = subprocess.run([str(x) for x in args], check=True, capture_output=True)
    return result.stdout.decode("utf-8", errors="replace")


def database(apk, directory, name):
    with zipfile.ZipFile(apk) as z:
        raw = z.read(DB_ASSET)
    path = directory / name
    path.write_bytes(raw)
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    require(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "Invalid database")
    require(not db.execute("PRAGMA foreign_key_check").fetchall(), "Database foreign keys failed")
    return db, hashlib.sha256(raw).hexdigest()


def inspect_catalog(unsigned, previous, expected_db_sha=DB_SHA):
    with tempfile.TemporaryDirectory(prefix="recovery134-db-") as tmp:
        directory = Path(tmp)
        new, db_hash = database(unsigned, directory, "new.db")
        old, _ = database(previous, directory, "old.db")
        try:
            require(db_hash == expected_db_sha, "Prepared catalog SHA-256 changed")
            cards = new.execute("SELECT count(*) FROM cards").fetchone()[0]
            images = new.execute("SELECT count(*) FROM images").fetchone()[0]
            metadata = dict(new.execute("SELECT key,value FROM metadata"))
            require((cards, images) == (1697, 1600), "Unexpected catalog counts")
            require("195" in metadata.values(), "Catalog content version is not 195")
            old_ids = dict(old.execute("SELECT id,rowid FROM cards"))
            new_ids = dict(new.execute("SELECT id,rowid FROM cards"))
            require(len(old_ids) == 1426, "Published baseline is not catalog 190")
            require(all(new_ids.get(k) == v for k, v in old_ids.items()), "Published card IDs/rowids changed")
            media = {r[0] for r in new.execute("SELECT localPath FROM images")}
            media.update(r[0] for r in new.execute("SELECT thumbnailPath FROM cards WHERE thumbnailPath IS NOT NULL"))
        finally:
            new.close()
            old.close()
    with zipfile.ZipFile(unsigned) as z, zipfile.ZipFile(previous) as base:
        manifest_raw = z.read(MODELS_ASSET)
        require(hashlib.sha256(manifest_raw).hexdigest() == MANIFEST_SHA, "Model manifest changed")
        models = json.loads(manifest_raw)["models"]
        require(len(models) == 19, "Expected 19 offline models")
        for m in models:
            raw = z.read("assets/viewer3d/" + m["file"])
            require(hashlib.sha256(raw).hexdigest() == m["packagedSha256"], "Model hash mismatch: " + m["id"])
            require(m.get("author") and m.get("license") and m.get("source"), "Missing attribution")
            require(m.get("displayColorMode") in ("source", "illustrative"), "Missing colour mode")
        for path in media:
            require("assets/" + path in z.namelist(), "Missing media: " + path)
        baseline_media = [n for n in base.namelist() if n.startswith(("assets/images/", "assets/thumbs/")) and not n.endswith("/")]
        for name in baseline_media:
            require(z.read(name) == base.read(name), "Published media changed: " + name)
    return {"contentVersion": 195, "cards": cards, "images": images, "offlineModels": 19,
            "databaseSha256": db_hash, "modelManifestSha256": MANIFEST_SHA,
            "preservedPublishedCardIdsAndRowids": len(old_ids), "preservedPublishedMedia": len(baseline_media),
            "referencedMediaPresent": len(media), "integrityCheck": "ok", "foreignKeyViolations": 0}


def identity(apk, aapt):
    raw = run([aapt, "dump", "badging", apk])
    package = re.search(r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", raw, re.M)
    require(package is not None, "aapt2 did not return APK identity")
    return {"packageName": package[1], "versionCode": int(package[2]), "versionName": package[3],
            "debuggable": bool(re.search(r"^application-debuggable", raw, re.M))}


def certificate(apk, signer, proof_path):
    proof = run([signer, "verify", "--verbose", "--print-certs", apk])
    proof_path.write_text(proof, encoding="utf-8")
    digests = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]+)", proof)
    require(len(digests) == 1 and digests[0].lower() == CERT, "APK signing certificate differs from 0.3.133")
    return digests[0].lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--previous", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--sdk", type=Path)
    parser.add_argument("--keystore", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--repaired-unsigned", type=Path)
    args = parser.parse_args()
    require(sha(args.archive) == ARCHIVE_SHA, "Recovery archive SHA-256 mismatch")
    require(sha(args.previous) == PREVIOUS_SHA and args.previous.stat().st_size == 121074164,
            "Published 0.3.133 APK mismatch")
    args.work.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive) as z:
        for name in ("DLYA_SVOIH_v0.3.134-unsigned.apk", "DLYA_SVOIH_0.3.134.bundle"):
            (args.work / name).write_bytes(z.read(name))
        require(z.read("source-commit.txt").decode().strip() == SOURCE_COMMIT, "Source commit changed")
    unsigned = args.work / "DLYA_SVOIH_v0.3.134-unsigned.apk"
    require(unsigned.stat().st_size == 144614177 and sha(unsigned) == UNSIGNED_SHA, "Prepared APK mismatch")
    require(sha(args.work / "DLYA_SVOIH_0.3.134.bundle") == BUNDLE_SHA, "Source bundle mismatch")
    report = {"sourceCommit": SOURCE_COMMIT, "archiveSha256": ARCHIVE_SHA,
              "unsignedApkSha256": UNSIGNED_SHA, "reference133ApkSha256": PREVIOUS_SHA,
              "expectedCertificateSha256": CERT, "catalog": inspect_catalog(unsigned, args.previous),
              "signatureVerified": False, "signedApkPath": None, "signedApkSha256": None,
              "upgradeInstallation": "pending-Android", "favoritesPreserved": None,
              "settingsPreserved": None, "fullCatalogOnAndroid": None,
              "androidVisualReview": "pending-actual-initial-and-rotated-frames"}
    if args.preflight_only:
        (args.out / "stage-3-preflight.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    require(args.repaired_unsigned is not None, "The Android-discovered search repair is required")
    require(sha(args.repaired_unsigned) == "dd49b40f181544b3966a3725a8f21872cf1b7dc65f98215424da809cdafcf9d5",
            "Repaired unsigned APK differs from the reproducible catalog and renderer result")
    with zipfile.ZipFile(unsigned) as original, zipfile.ZipFile(args.repaired_unsigned) as fixed:
        require(original.namelist() == fixed.namelist(), "Repaired APK entry set changed")
        changed = [n for n in original.namelist() if original.read(n) != fixed.read(n)]
        require(len(changed)==2 and set(changed)=={DB_ASSET,VIEWER_ASSET}, "Unexpected repaired APK entries")
        require(hashlib.sha256(fixed.read(VIEWER_ASSET)).hexdigest()==VIEWER_SHA, "Renderer repair changed")
        require(hashlib.sha256(fixed.read(DB_ASSET)).hexdigest() == REPAIRED_DB_SHA,
                "Repaired catalog differs from the locally checked five-field repair")
    report["repairedUnsignedApkSha256"] = sha(args.repaired_unsigned)
    report["entriesChangedByRepair"] = [DB_ASSET,VIEWER_ASSET]
    report["rendererBundleSha256"] = VIEWER_SHA
    report["catalog"] = inspect_catalog(args.repaired_unsigned, args.previous, REPAIRED_DB_SHA)
    unsigned = args.repaired_unsigned
    require(args.sdk is not None and args.keystore is not None, "SDK and existing CI keystore are required")
    tools = args.sdk / "build-tools/36.0.0"
    signer, aapt, align = tools / "apksigner", tools / "aapt2", tools / "zipalign"
    old_identity = identity(args.previous, aapt)
    require(old_identity == {"packageName": "ru.dlyasvoih.app", "versionCode": 137,
                             "versionName": "0.3.133", "debuggable": False}, "Published APK identity mismatch")
    old_cert = certificate(args.previous, signer, args.out / "certificate-0.3.133.txt")
    certificate_bytes = subprocess.run(["keytool", "-exportcert", "-keystore", str(args.keystore),
                                       "-storepass", "android", "-alias", "androiddebugkey"],
                                      check=True, capture_output=True).stdout
    key_cert = hashlib.sha256(certificate_bytes).hexdigest()
    require(key_cert == old_cert == CERT, "Existing CI key differs from the published certificate")
    expected_identity = {"packageName": "ru.dlyasvoih.app", "versionCode": 138,
                         "versionName": "0.3.134", "debuggable": False}
    require(identity(unsigned, aapt) == expected_identity, "Prepared APK identity mismatch")
    aligned = args.work / "DLYA_SVOIH_v0.3.134-search-fixed-aligned.apk"
    run([align, "-f", "4", unsigned, aligned])
    unsigned = aligned
    run([align, "-c", "4", unsigned])
    signed = args.out / "DLYA_SVOIH_v0.3.134.apk"
    run([signer, "sign", "--ks", args.keystore, "--ks-key-alias", "androiddebugkey",
         "--ks-pass", "pass:android", "--key-pass", "pass:android", "--min-sdk-version", "26",
         "--v1-signing-enabled", "false", "--v2-signing-enabled", "true", "--v3-signing-enabled", "true",
         "--out", signed, unsigned])
    signed_cert = certificate(signed, signer, args.out / "certificate-0.3.134.txt")
    require(identity(signed, aapt) == expected_identity, "Signed APK identity mismatch")
    run([align, "-c", "4", signed])
    with zipfile.ZipFile(unsigned) as original, zipfile.ZipFile(signed) as result:
        require(len(set(original.namelist())) == len(original.namelist()), "Duplicate prepared ZIP entries")
        require(set(original.namelist()) == set(result.namelist()), "APK payload entry set changed")
        for name in original.namelist():
            require(original.read(name) == result.read(name), "APK payload changed while signing: " + name)
        payload_count = len(original.namelist())
    report.update(signatureVerified=True, signedApkPath=signed.name, signedApkSha256=sha(signed),
                  signedApkBytes=signed.stat().st_size, certificateSha256=signed_cert,
                  identity=expected_identity, payloadEntriesUnchanged=payload_count, zipalign="passed")
    (args.out / "stage-3-signature-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (args.out / "SHA256SUMS.txt").write_text(sha(signed) + "  " + signed.name + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
