"""Sign the store channel; keep the permanent key encrypted, never in build artifacts.

The existing owner-controlled Actions secret wraps the new key with HKDF/AES-GCM.
Future builds must reuse the committed encrypted envelope, not create another key.
Only Android 9+ receives the rotated signature; the public GitHub feed is untouched.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[1]
OLD_CERT = '2f0a0908f269bc039311edb58fca8863347f1e4c3a7cfaddd909991cf1f0b509'
INFO = b'DLYA SVOIH RuStore release signing envelope v1'


def wrap_key(secret, salt):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=INFO).derive(secret)


def seal(secret, payload):
    salt, nonce = secrets.token_bytes(32), secrets.token_bytes(12)
    cipher = AESGCM(wrap_key(secret, salt)).encrypt(nonce, payload, INFO)
    return json.dumps(dict(formatVersion=1, salt=base64.b64encode(salt).decode(),
                           nonce=base64.b64encode(nonce).decode(),
                           ciphertext=base64.b64encode(cipher).decode()), indent=2).encode() + b'\n'


def unseal(secret, envelope):
    obj = json.loads(envelope)
    if obj['formatVersion'] != 1:
        raise ValueError('Unsupported encrypted key format')
    salt, nonce, cipher = [base64.b64decode(obj[k], validate=True) for k in ('salt', 'nonce', 'ciphertext')]
    return AESGCM(wrap_key(secret, salt)).decrypt(nonce, cipher, INFO)


def run(args, env=None):
    result = subprocess.run(args, env=env, capture_output=True, timeout=90)
    if result.returncode:
        # Never include an environment or secret input in a diagnostic.
        raise RuntimeError(Path(args[0]).name + ' failed: ' + result.stderr.decode(errors='replace')[-1600:])
    return result.stdout


def sign(apk, output, initialize=False):
    secret = base64.b64decode(''.join(os.environ.get('ANDROID_DEBUG_KEYSTORE_BASE64', '').split()), validate=True)
    if not secret:
        raise ValueError('Existing owner signing secret is required')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    signer = str(Path(os.environ['ANDROID_HOME']) / 'build-tools/36.0.0/apksigner')
    analyzer = str(Path(os.environ['ANDROID_HOME']) / 'cmdline-tools/latest/bin/apkanalyzer')
    envelope_path = ROOT / 'docs/releases/rustore-release-key.enc'
    with tempfile.TemporaryDirectory(prefix='rustore-signing-') as tmp:
        folder = Path(tmp)
        old = folder / 'old.jks'
        old.write_bytes(secret)
        old.chmod(0o600)
        certificate = run(['keytool', '-exportcert', '-keystore', str(old), '-storepass', 'android', '-alias', 'androiddebugkey'])
        if hashlib.sha256(certificate).hexdigest() != OLD_CERT:
            raise ValueError('Owner signing certificate differs from published APK')
        release = folder / 'release.jks'
        if envelope_path.is_file():
            envelope = envelope_path.read_bytes()
            payload = json.loads(unseal(secret, envelope))
            password = payload['password']
            release.write_bytes(base64.b64decode(payload['keystore'], validate=True))
        else:
            if not initialize:
                raise ValueError('Permanent key is missing; initialization must be explicit')
            password = secrets.token_urlsafe(36)
            env = dict(os.environ, RUSTORE_KEY_PASSWORD=password)
            run(['keytool', '-genkeypair', '-keystore', str(release), '-storetype', 'JKS',
                 '-storepass:env', 'RUSTORE_KEY_PASSWORD', '-keypass:env', 'RUSTORE_KEY_PASSWORD',
                 '-alias', 'dlyasvoih-release', '-keyalg', 'RSA', '-keysize', '3072', '-validity', '10000',
                 '-dname', 'CN=DLYA SVOIH Release', '-noprompt'], env)
            payload = dict(password=password, keystore=base64.b64encode(release.read_bytes()).decode())
            envelope = seal(secret, json.dumps(payload).encode())
        release.chmod(0o600)
        env = dict(os.environ, RUSTORE_KEY_PASSWORD=password)
        cert = run(['keytool', '-exportcert', '-keystore', str(release), '-storepass:env', 'RUSTORE_KEY_PASSWORD',
                    '-alias', 'dlyasvoih-release'], env)
        fingerprint = hashlib.sha256(cert).hexdigest()
        pin = ROOT / 'docs/releases/rustore-signing.json'
        if pin.is_file() and json.loads(pin.read_text())['signerSha256'] != fingerprint:
            raise ValueError('Permanent signing certificate changed')
        if fingerprint == OLD_CERT:
            raise ValueError('Store signer is still the debug certificate')
        lineage = output / 'rustore-signing-lineage.bin'
        run([signer, 'rotate', '--out', str(lineage), '--old-signer', '--ks', str(old),
             '--ks-key-alias', 'androiddebugkey', '--ks-pass', 'pass:android', '--key-pass', 'pass:android',
             '--new-signer', '--ks', str(release), '--ks-key-alias', 'dlyasvoih-release',
             '--ks-pass', 'env:RUSTORE_KEY_PASSWORD', '--key-pass', 'env:RUSTORE_KEY_PASSWORD'], env)
        target = output / 'DLYA_SVOIH_v0.3.126_RUSTORE.apk'
        # v3-only prevents the old debug certificate being a current v1/v2 signer.
        # Android 9 is the earliest system supporting this authenticated rotation.
        run([signer, 'sign', '--ks', str(release), '--ks-key-alias', 'dlyasvoih-release',
             '--ks-pass', 'env:RUSTORE_KEY_PASSWORD', '--key-pass', 'env:RUSTORE_KEY_PASSWORD',
             '--lineage', str(lineage), '--rotation-min-sdk-version', '28',
             '--v1-signing-enabled', 'false', '--v2-signing-enabled', 'false',
             '--v3-signing-enabled', 'true', '--v4-signing-enabled', 'false',
             '--out', str(target), str(apk)], env)
        verified = run([signer, 'verify', '--verbose', '--print-certs', str(target)]).decode()
        if fingerprint not in verified or 'CN=Android Debug' in verified:
            raise ValueError('Unexpected current APK certificate')
        identity = {k: run([analyzer, 'manifest', k, str(target)]).decode().strip()
                    for k in ('application-id', 'version-code', 'version-name', 'min-sdk', 'debuggable')}
        if identity != {'application-id':'ru.dlyasvoih.app', 'version-code':'130', 'version-name':'0.3.126',
                        'min-sdk':'28', 'debuggable':'false'}:
            raise ValueError('Wrong store APK identity: ' + str(identity))
        permissions = run([analyzer, 'manifest', 'permissions', str(target)]).decode().splitlines()
        if 'android.permission.REQUEST_INSTALL_PACKAGES' in permissions:
            raise ValueError('Store APK still installs packages directly')
        (output / 'rustore-release-key.enc').write_bytes(envelope)
        (output / 'rustore-release-cert.der').write_bytes(cert)
        report = dict(packageName='ru.dlyasvoih.app', versionCode=130, versionName='0.3.126', minSdk=28,
                      signerSha256=fingerprint, previousSignerSha256=OLD_CERT,
                      signingScheme='v3 with proof of rotation', permissions=permissions,
                      bytes=target.stat().st_size, sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        (output / 'rustore-signing.json').write_text(json.dumps(report, indent=2) + '\n')
        (output / 'signature-verification.txt').write_text(verified)
        print(json.dumps(report))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--apk', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--initialize-signing', action='store_true')
    args = p.parse_args()
    sign(args.apk, args.output, args.initialize_signing)
