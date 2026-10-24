import argparse
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


MAX_DURATION = 180


def _adb_command(adb, serial, *arguments):
    command = [adb]
    if serial:
        command.extend(["-s", serial])
    command.extend(arguments)
    return command


def record_screen(output, duration=MAX_DURATION, serial=None):
    if not 1 <= duration <= MAX_DURATION:
        raise ValueError(f"Duration must be between 1 and {MAX_DURATION} seconds.")

    adb = shutil.which("adb")
    if not adb:
        raise RuntimeError("adb was not found. Install Android Platform Tools and add adb to PATH.")

    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Output file already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    remote_path = f"/sdcard/snimanje_{uuid.uuid4().hex}.mp4"
    try:
        subprocess.run(
            _adb_command(
                adb, serial, "shell", "screenrecord", "--time-limit",
                str(duration), remote_path,
            ),
            check=True,
        )
        subprocess.run(
            _adb_command(adb, serial, "pull", remote_path, str(output)),
            check=True,
        )
    finally:
        subprocess.run(
            _adb_command(adb, serial, "shell", "rm", "-f", remote_path),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Record an Android device screen to an MP4 file.")
    parser.add_argument("output", nargs="?", default="screenrecord.mp4", help="output MP4 path")
    parser.add_argument(
        "--duration",
        type=int,
        default=MAX_DURATION,
        help=f"recording duration in seconds (1-{MAX_DURATION}; default: {MAX_DURATION})",
    )
    parser.add_argument("-s", "--serial", help="ADB device serial when multiple devices are connected")
    args = parser.parse_args(argv)

    try:
        record_screen(args.output, args.duration, args.serial)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Recording saved to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
