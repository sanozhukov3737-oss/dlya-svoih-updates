#!/usr/bin/env python3
"""Run a command on one fresh KVM emulator and bound every shutdown operation.

Owns only the emulator process group it creates. Never kills another emulator.
The command is an argv after --, not evaluated through a shell.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=1200)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command: parser.error('A test command is required after --')
    sdk = Path(os.environ.get('ANDROID_SDK_ROOT') or os.environ['ANDROID_HOME'])
    emulator = sdk / 'emulator/emulator'
    adb = sdk / 'platform-tools/adb'
    args.out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, ANDROID_SERIAL='emulator-5554')
    env['PATH'] = str(adb.parent) + os.pathsep + env['PATH']
    def device(*values, timeout=20, check=True):
        return subprocess.run([str(adb), '-s', env['ANDROID_SERIAL'], *values],
            env=env, capture_output=True, text=True, timeout=timeout, check=check)
    subprocess.run([str(emulator), '-accel-check'], check=True, timeout=30)
    subprocess.run([str(adb), 'start-server'], check=True, timeout=30)
    listing = subprocess.run([str(adb), 'devices'], capture_output=True, text=True, check=True, timeout=15)
    if 'emulator-5554' in listing.stdout:
        raise RuntimeError('Refusing to reuse or stop an existing emulator on port 5554')
    started = time.monotonic()
    report = dict(serial=env['ANDROID_SERIAL'], acceleration='required-KVM', testPassed=False)
    code = 1
    with (args.out / 'emulator.log').open('wb') as log:
        process = subprocess.Popen([str(emulator), '-avd', 'recovery134', '-port', '5554',
            '-no-window', '-gpu', 'swiftshader_indirect', '-noaudio', '-no-boot-anim',
            '-no-snapshot', '-wipe-data', '-accel', 'on', '-memory', '4096', '-cores', '4',
            '-partition-size', '8192', '-camera-back', 'none', '-camera-front', 'none'],
            stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        try:
            deadline = started + 600
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Emulator exited before boot; see emulator.log')
                try:
                    if device('shell', 'getprop', 'sys.boot_completed', timeout=8, check=False).stdout.strip() == '1':
                        break
                except subprocess.TimeoutExpired:
                    pass
                time.sleep(2)
            else:
                raise TimeoutError('KVM emulator boot exceeded 600 seconds')
            report['bootSeconds'] = round(time.monotonic()-started, 2)
            device('shell', 'input', 'keyevent', '82')
            for setting in ('window_animation_scale', 'transition_animation_scale', 'animator_duration_scale'):
                device('shell', 'settings', 'put', 'global', setting, '0')
            completed = subprocess.run(command, env=env, timeout=args.timeout)
            code = completed.returncode
            report['testExitCode'] = code
            report['testPassed'] = code == 0
        except Exception as error:
            report['error'] = type(error).__name__ + ': ' + str(error)
            print(report['error'], file=sys.stderr, flush=True)
        finally:
            shutdown = time.monotonic()
            try:
                result = device('emu', 'kill', timeout=8, check=False)
                report['adbKill'] = dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
            except Exception as error:
                report['adbKill'] = type(error).__name__
            # The runner's old unbounded `adb emu kill` stalled after successful
            # tests. All waits below have deadlines, even if adb never returns.
            for sig, seconds in ((signal.SIGTERM, 10), (signal.SIGKILL, 5)):
                if process.poll() is not None: break
                try:
                    os.killpg(process.pid, sig)
                    process.wait(timeout=seconds)
                except ProcessLookupError:
                    break
                except subprocess.TimeoutExpired:
                    continue
            report['emulatorExitCode'] = process.poll()
            report['shutdownSeconds'] = round(time.monotonic()-shutdown, 2)
            report['totalSeconds'] = round(time.monotonic()-started, 2)
            (args.out / 'lifecycle.json').write_text(json.dumps(report, indent=2)+'\n')
            print(json.dumps(report, indent=2), flush=True)
    return code if report.get('emulatorExitCode') is not None else 1


if __name__ == '__main__':
    sys.exit(main())
