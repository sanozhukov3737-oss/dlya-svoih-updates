#!/usr/bin/env python3
"""Capture private evidence from a physical phone without changing app data."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

PACKAGE = 'ru.dlyasvoih.app'
VERSIONS = {
    'before': ('0.3.136', 140,
        '0a22658eab2cc409eebf1c9d62cb1139b79cbb160e238ebc5102b8abc4566162'),
    'after': ('0.3.137', 141,
        'f0a67816b64c831259f54c1da10b010e50ef781ad9bb75010dab89be3715eebe'),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def find_adb(explicit=None):
    candidates = [explicit, shutil.which('adb')]
    for variable in ('ANDROID_HOME', 'ANDROID_SDK_ROOT'):
        if os.environ.get(variable):
            candidates.append(Path(os.environ[variable]) / 'platform-tools' / 'adb.exe')
    if os.environ.get('LOCALAPPDATA'):
        candidates.append(Path(os.environ['LOCALAPPDATA']) / 'Android/Sdk/platform-tools/adb.exe')
    properties = Path(__file__).resolve().parents[1] / 'local.properties'
    if properties.is_file():
        for line in properties.read_text(encoding='utf-8').splitlines():
            if line.startswith('sdk.dir='):
                sdk = line.partition('=')[2].replace('\\:', ':').replace('\\\\', '\\')
                candidates.append(Path(sdk) / 'platform-tools' / ('adb.exe' if os.name == 'nt' else 'adb'))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise ValueError('ADB не найден. Установите Android SDK Platform-Tools в Android Studio '
        'или передайте --adb "полный путь к adb.exe".')


def adb_run(adb, serial, *command):
    prefix = [adb] + (['-s', serial] if serial else [])
    result = subprocess.run(prefix + list(command), capture_output=True, timeout=90)
    if result.returncode:
        raise ValueError('ADB: ' + result.stderr.decode(errors='replace').strip())
    return result.stdout


def select_phone(adb, serial=None, interactive=False):
    if serial:
        require(adb_run(adb, serial, 'get-state').decode().strip() == 'device',
            'Разрешите отладку по USB для этого ПК на телефоне.')
        require(not serial.startswith('emulator-') and
            adb_run(adb, serial, 'shell', 'getprop', 'ro.kernel.qemu').decode().strip() != '1',
            'Нужен физический телефон; эмулятор не засчитывается.')
        return serial
    rows = adb_run(adb, None, 'devices', '-l').decode(errors='replace').splitlines()[1:]
    phones = []
    unauthorized = False
    for row in rows:
        fields = row.split()
        if len(fields) < 2:
            continue
        unauthorized |= fields[1] == 'unauthorized'
        if fields[1] != 'device' or fields[0].startswith('emulator-'):
            continue
        if adb_run(adb, fields[0], 'shell', 'getprop', 'ro.kernel.qemu').decode().strip() != '1':
            phones.append(fields[0])
    require(phones, 'Подключённый телефон не найден. Включите отладку по USB и разрешите этот ПК.'
        + (' На телефоне ожидается подтверждение доступа.' if unauthorized else ''))
    if len(phones) == 1:
        return phones[0]
    require(interactive, 'Подключено несколько телефонов. Укажите --serial из списка adb devices -l.')
    for number, phone in enumerate(phones, 1):
        print(f'{number}. {phone}')
    chosen = input('Номер телефона: ').strip()
    require(chosen.isdigit() and 1 <= int(chosen) <= len(phones), 'Неверный номер телефона.')
    return phones[int(chosen) - 1]


def read_phase(adb, serial, requested=None):
    package = adb_run(adb, serial, 'shell', 'dumpsys', 'package', PACKAGE).decode(errors='replace')
    for phase, (version, code, _) in VERSIONS.items():
        if (re.search(r'\bversionName=' + re.escape(version) + r'(?:\s|$)', package)
                and re.search(r'\bversionCode=' + str(code) + r'\b', package)):
            require(requested is None or requested == phase,
                f'Установлена {version}; запрошен другой этап. Не удаляйте и не откатывайте приложение.')
            return phase, package
    expected = ' или '.join(version for version, _, _ in VERSIONS.values())
    raise ValueError('Ожидалась установленная ' + expected + '. '
        'Приложение не установлено либо имеет другую версию; ничего не удаляйте.')


def capture(adb, serial, phase, label, out, require_offline=False):
    require(re.fullmatch(r'[a-zA-Z0-9_-]{1,60}', label), 'Метка: 1–60 латинских букв, цифр, _ или -.')
    select_phone(adb, serial)
    phase, package = read_phase(adb, serial, phase)
    version, code, expected_sha = VERSIONS[phase]
    connectivity = adb_run(adb, serial, 'shell', 'dumpsys', 'connectivity').decode(errors='replace')
    no_network = bool(re.search(r'Active default network:\s*(none|null|-1)\b', connectivity, re.I))
    require(not require_offline or no_network,
        'Офлайн-режим не подтверждён. Отключите Wi-Fi и мобильные данные и повторите снимок.')
    paths = adb_run(adb, serial, 'shell', 'pm', 'path', PACKAGE).decode().splitlines()
    require(len(paths) == 1 and paths[0].startswith('package:'), 'Неожиданная установка из нескольких APK.')
    raw = adb_run(adb, serial, 'exec-out', 'cat', paths[0][len('package:'):].strip())
    digest = hashlib.sha256(raw).hexdigest()
    require(digest == expected_sha, 'APK на телефоне отличается от опубликованного: ' + digest)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    dest = out / (stamp + '-' + phase + '-' + label)
    dest.mkdir(parents=True, exist_ok=False)
    (dest / 'package.txt').write_text(package, encoding='utf-8')
    (dest / 'device.txt').write_bytes(adb_run(adb, serial, 'shell', 'getprop'))
    (dest / 'connectivity.txt').write_text(connectivity, encoding='utf-8')
    adb_run(adb, serial, 'shell', 'uiautomator', 'dump', '/sdcard/dlya-svoih-phone-check.xml')
    (dest / 'screen.xml').write_bytes(adb_run(adb, serial, 'exec-out', 'cat', '/sdcard/dlya-svoih-phone-check.xml'))
    (dest / 'screen.png').write_bytes(adb_run(adb, serial, 'exec-out', 'screencap', '-p'))
    (dest / 'crash.log').write_bytes(adb_run(adb, serial, 'logcat', '-d', '-b', 'crash'))
    evidence = dict(phase=phase, label=label, timestampUtc=stamp, physicalDevice=True,
        package=PACKAGE, versionName=version, versionCode=code, installedApkSha256=digest,
        noActiveDefaultNetwork=no_network, manualFunctionalReview='not-asserted-by-capture-script',
        preservationComparison='compare-before-and-after-screens-manually')
    (dest / 'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Снимок сохранён: ' + str(dest.resolve()))
    return dest


def wizard(adb, serial, out):
    phase, _ = read_phase(adb, serial)
    print('\nДЛЯ СВОИХ — проверка телефона. Установлена ' + VERSIONS[phase][0])
    print('Приложение и его данные сохраняются. Откройте нужный экран на телефоне.')
    if phase == 'after':
        print(VERSIONS['after'][0] + ' уже установлена: начинаем проверку текущей версии. Откат не нужен.')
        print('Сохранение избранного при прошлой установке задним числом не подтверждается.')
    print('Снимки и журналы могут содержать личные данные. Архив автоматически никуда не отправляется.')
    labels = {'1': 'favorites', '2': 'appearance', '3': 'gallery', '4': 'navigation', '7': 'comparison'}
    captured = []
    try:
        while True:
            print('\n1 — Избранное; 2 — Тема и текст; 3 — Галерея; 4 — Навигация')
            print('5 — 3D-модель; 6 — Текущий экран без интернета; 0 — Завершить и собрать ZIP')
            print('7 — Сравнение карточек')
            choice = input('Номер: ').strip()
            if choice == '0':
                break
            offline = choice == '6'
            label = labels.get(choice)
            if choice == '5':
                model = input('1 — M14; 2 — ПМН-2; 3 — M16; 4 — Британская дрейфующая: ').strip()
                name = {'1': 'm14', '2': 'pmn2', '3': 'm16', '4': 'british-drifting'}.get(model)
                angle = input('1 — Начальный вид; 2 — После вращения: ').strip()
                if not name or angle not in ('1', '2'):
                    print('Выберите существующий номер.')
                    continue
                label = name + ('-initial' if angle == '1' else '-rotated')
            elif offline:
                label = 'offline-screen'
            if label is None:
                print('Выберите номер из меню.')
                continue
            input('Откройте нужный экран' + (' и отключите Wi-Fi/мобильные данные' if offline else '')
                + ', затем нажмите Enter здесь. ')
            try:
                phase, _ = read_phase(adb, serial)
                captured.append(capture(adb, serial, phase, label, out, offline))
            except (ValueError, OSError, subprocess.TimeoutExpired) as error:
                print('Снимок не засчитан: ' + str(error))
    finally:
        if captured:
            archive = out.parent / ('DLYA_SVOIH_PHONE_RESULT_' +
                datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.zip')
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
                for folder in captured:
                    for path in sorted(folder.iterdir()):
                        bundle.write(path, str(path.relative_to(out)))
            print('\nАрхив этой проверки: ' + str(archive.resolve()))
            print('Функции приложения оцениваются по снимкам и вашим наблюдениям; успех не объявляется автоматически.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', type=Path)
    parser.add_argument('--serial', help='Автоматический выбор, если подключён один физический телефон')
    parser.add_argument('--phase', choices=VERSIONS, help='По умолчанию определяется по установленной версии')
    parser.add_argument('--label', help='favorites, appearance, gallery, m14-rotated и т. п.')
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1]
        / ('build/physical-android-' + VERSIONS['after'][0]))
    parser.add_argument('--require-offline', action='store_true')
    parser.add_argument('--wizard', action='store_true', help='Пошаговое меню и частный ZIP результатов')
    args = parser.parse_args()
    if not args.wizard and not args.label:
        parser.error('Укажите --label или запустите --wizard.')
    try:
        adb = find_adb(args.adb)
        serial = select_phone(adb, args.serial, args.wizard)
        phase, _ = read_phase(adb, serial, args.phase)
        if args.wizard:
            wizard(adb, serial, args.out)
        else:
            capture(adb, serial, phase, args.label, args.out, args.require_offline)
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print('Проверка не выполнена: ' + str(error), file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print('\nПроверка остановлена пользователем.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
