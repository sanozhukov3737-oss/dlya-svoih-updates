"""Add a signed APK offer to an existing catalog feed, preserving the catalog URL/version."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit
import zipfile

MAX_BYTES = 256 * 1024 * 1024
PACKAGE = 'ru.dlyasvoih.app'


def https_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('Invalid HTTPS URL')
    p = urlsplit(value)
    if p.scheme != 'https' or not p.hostname or p.username is not None or p.password is not None or p.fragment:
        raise ValueError('Use an absolute HTTPS URL without credentials or fragment')


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Invalid numeric publication metadata')


def validate_app_metadata(app):
    if not isinstance(app, dict) or type(app.get('formatVersion')) is not int or app['formatVersion'] != 1:
        raise ValueError('Unsupported APK feed')
    integer(app.get('versionCode'), 1, 2147483647)
    integer(app.get('minSdk'), 26, 2147483647)
    integer(app.get('bytes'), 1, MAX_BYTES)
    if app.get('packageName') != PACKAGE:
        raise ValueError('Wrong APK package')
    name = app.get('versionName')
    changes = app.get('changes', '')
    if not isinstance(name, str) or not name.strip() or len(name) > 80 or not isinstance(changes, str) or len(changes) > 5000:
        raise ValueError('Invalid APK version name or changes')
    https_url(app.get('url'))
    for field in ('sha256', 'signerSha256'):
        if not isinstance(app.get(field), str) or not re.fullmatch('[a-f0-9]{64}', app[field]):
            raise ValueError('Invalid APK hash or signing certificate')
    return app


def validate_catalog_feed(feed):
    if not isinstance(feed, dict) or type(feed.get('formatVersion')) is not int or feed['formatVersion'] != 1:
        raise ValueError('Unsupported catalog feed')
    integer(feed.get('contentVersion'), 1, 9223372036854775807)
    integer(feed.get('bytes'), 1, MAX_BYTES)
    integer(feed.get('minAppCode', 1), 1, 2147483647)
    https_url(feed.get('url'))
    if not isinstance(feed.get('sha256'), str) or not re.fullmatch('[a-f0-9]{64}', feed['sha256']):
        raise ValueError('Invalid catalog hash')
    if not isinstance(feed.get('changes', ''), str) or len(feed.get('changes', '')) > 5000:
        raise ValueError('Invalid catalog changes')
    if 'app' in feed:
        validate_app_metadata(feed['app'])
    return feed


def sdk_tool(name):
    found = shutil.which(name) or shutil.which(name + '.bat')
    if found:
        return found
    sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if sdk:
        if name == 'apkanalyzer':
            candidates = [Path(sdk) / 'cmdline-tools/latest/bin' / (name + ext) for ext in ('', '.bat')]
        else:
            candidates = [p / (name + ext) for p in sorted((Path(sdk) / 'build-tools').glob('*'), reverse=True) for ext in ('', '.bat')]
        for p in candidates:
            if p.is_file():
                return str(p)
    raise ValueError('Android SDK tool not found: ' + name)


def signing_certificate_digest(signature):
    # apksigner prints SDK-range labels for v3.1/v3 signers. The same
    # certificate can appear in more than one range; key rotation cannot.
    records = re.findall(
        r'^Signer (#[1-9][0-9]*|\(minSdkVersion=[0-9]+(?: \(dev release=true\))?, '
        r'maxSdkVersion=[0-9]+\)) certificate SHA-256 digest:[ \t]*([A-Fa-f0-9]{64})[ \t\r]*$',
        signature, re.MULTILINE)
    digests = {digest.lower() for _, digest in records}
    numbered = {label for label, _ in records if label.startswith('#')}
    if len(digests) != 1 or len(numbered) > 1:
        raise ValueError('Use one verified APK signing certificate '
                         f'(found {len(records)} records, {len(digests)} distinct certificates)')
    return next(iter(digests))


def apk_metadata(apk, analyzer=None, signer=None):
    analyzer = analyzer or sdk_tool('apkanalyzer')
    signer = signer or sdk_tool('apksigner')
    def run(args):
        try:
            return subprocess.run(args, capture_output=True, text=True, check=True, timeout=90).stdout.strip()
        except subprocess.CalledProcessError as e:
            raise ValueError('APK validation failed: ' + Path(args[0]).name) from e
    signature = run([signer, 'verify', '--print-certs', str(apk)])
    digest = signing_certificate_digest(signature)
    values = {key: run([analyzer, 'manifest', key, str(apk)]) for key in ('application-id', 'version-code', 'version-name', 'min-sdk')}
    return dict(packageName=values['application-id'], versionCode=int(values['version-code']),
                versionName=values['version-name'], minSdk=int(values['min-sdk']), signerSha256=digest)


def write_app_feed(apk, catalog_feed, url, output, changes='', analyzer=None, signer=None):
    apk, output = Path(apk), Path(output)
    if output.resolve() == apk.resolve() or output.with_suffix(output.suffix + '.tmp').resolve() == apk.resolve():
        raise ValueError('Feed must not overwrite the APK')
    integer(apk.stat().st_size, 1, MAX_BYTES)
    https_url(url)
    with zipfile.ZipFile(apk) as z:
        if 'AndroidManifest.xml' not in z.namelist() or z.testzip() is not None:
            raise ValueError('Invalid APK archive')
    text = Path(catalog_feed).read_text(encoding='utf-8')
    if len(text.encode('utf-8')) > 64 * 1024:
        raise ValueError('Feed too large')
    feed = validate_catalog_feed(json.loads(text))
    app = dict(formatVersion=1, **apk_metadata(apk, analyzer, signer), url=url,
               bytes=apk.stat().st_size, sha256=hashlib.sha256(apk.read_bytes()).hexdigest(), changes=changes)
    validate_app_metadata(app)
    previous = feed.get('app')
    if previous and app['versionCode'] <= previous['versionCode']:
        raise ValueError('Increase versionCode: built APK has '
                         f"{app['versionCode']}, published APK has {previous['versionCode']}")
    if previous and app['signerSha256'] != previous['signerSha256']:
        raise ValueError('Keep the existing signing key: '
                         f"built APK certificate={app['signerSha256']}; "
                         f"published APK certificate={previous['signerSha256']}")
    feed['app'] = app
    payload = json.dumps(feed, ensure_ascii=False, indent=2) + '\n'
    if len(payload.encode('utf-8')) > 64 * 1024:
        raise ValueError('Feed too large')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    try:
        temporary.write_text(payload, encoding='utf-8')
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return feed


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--catalog-feed', type=Path, required=True)
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--changes-file', type=Path)
    parser.add_argument('--apkanalyzer')
    parser.add_argument('--apksigner')
    args = parser.parse_args()
    changes = args.changes_file.read_text(encoding='utf-8') if args.changes_file else ''
    result = write_app_feed(args.apk, args.catalog_feed, args.url, args.output, changes, args.apkanalyzer, args.apksigner)
    print(json.dumps({'versionName': result['app']['versionName'], 'versionCode': result['app']['versionCode'],
                      'contentVersion': result['contentVersion'], 'bytes': result['app']['bytes']}, ensure_ascii=False))
