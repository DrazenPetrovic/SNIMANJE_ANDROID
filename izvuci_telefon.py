import argparse
import csv
import getpass
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
ADB_EXE = APP_DIR / "platform-tools" / "adb.exe"
ADB_SERVER_PORT = 5038
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

log_linije = []


def log(poruka):
    linija = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {poruka}"
    log_linije.append(linija)
    print(linija, flush=True)


def adb(*args, serial=None, timeout=None):
    cmd = [str(ADB_EXE), "-P", str(ADB_SERVER_PORT)]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, creationflags=NO_WINDOW,
    )


def pronadji_uredjaj():
    izlaz = adb("devices").stdout.splitlines()[1:]
    uredjaji = [r.split() for r in izlaz if r.strip()]
    spremni = [r[0] for r in uredjaji if len(r) > 1 and r[1] == "device"]
    if not spremni:
        stanja = ", ".join(f"{r[0]}={r[1]}" for r in uredjaji if len(r) > 1)
        raise RuntimeError(
            "Nema autorizovanog uredjaja"
            + (f" ({stanja})" if stanja else "")
            + ". Spojite telefon i odobrite USB debugging."
        )
    return spremni[0]


def sha256_fajla(putanja):
    h = hashlib.sha256()
    with open(putanja, "rb") as f:
        for blok in iter(lambda: f.read(1024 * 1024), b""):
            h.update(blok)
    return h.hexdigest()


def info_uredjaja(serial):
    props = {}
    for linija in adb("shell", "getprop", serial=serial).stdout.splitlines():
        if "]: [" in linija:
            k, v = linija.strip().split("]: [", 1)
            props[k.lstrip("[")] = v.rstrip("]")
    return {
        "serijski_broj": serial,
        "proizvodjac": props.get("ro.product.manufacturer"),
        "model": props.get("ro.product.model"),
        "android_verzija": props.get("ro.build.version.release"),
        "sigurnosni_patch": props.get("ro.build.version.security_patch"),
        "build": props.get("ro.build.display.id"),
        "svojstva": props,
    }


def aplikacije(serial):
    rezultat = []
    izlaz = adb(
        "shell", "pm", "list", "packages", "-3", "--show-versioncode",
        serial=serial,
    ).stdout
    for linija in izlaz.splitlines():
        if linija.startswith("package:"):
            dijelovi = linija[8:].split()
            paket = dijelovi[0]
            verzija = next(
                (d.split(":", 1)[1] for d in dijelovi if d.startswith("versionCode:")),
                None,
            )
            rezultat.append({"paket": paket, "versionCode": verzija})
    return rezultat


def napravi_manifest(korijen):
    stavke = []
    for putanja in sorted(korijen.rglob("*")):
        if putanja.is_file():
            st = putanja.stat()
            stavke.append({
                "putanja": putanja.relative_to(korijen).as_posix(),
                "velicina": st.st_size,
                "izmijenjen": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                "sha256": sha256_fajla(putanja),
            })
    return stavke


def main():
    parser = argparse.ArgumentParser(
        description="Logicka (bez roota) ekstrakcija javne memorije Android telefona preko ADB-a."
    )
    parser.add_argument(
        "--izlaz", default=str(Path.home() / "Pictures" / "SNIMCI" / "EKSTRAKCIJE"),
        help="Folder u kojem se pravi paket ekstrakcije.",
    )
    parser.add_argument("--izvor", default="/sdcard", help="Putanja na telefonu (zadano /sdcard).")
    parser.add_argument("--operater", default=getpass.getuser())
    parser.add_argument("--bez-zip", action="store_true")
    args = parser.parse_args()

    if not ADB_EXE.exists():
        print(f"Nije pronadjen {ADB_EXE}")
        return 2

    pocetak = datetime.now()
    try:
        serial = pronadji_uredjaj()
    except RuntimeError as greska:
        print(greska)
        return 1

    info = info_uredjaja(serial)
    ime = f"EKSTRAKCIJA_{info['model'] or 'ANDROID'}_{serial}_{pocetak:%Y%m%d_%H%M%S}"
    paket_dir = Path(args.izlaz) / ime
    fajlovi_dir = paket_dir / "fajlovi"
    fajlovi_dir.mkdir(parents=True, exist_ok=True)

    log(f"Uredjaj: {info['proizvodjac']} {info['model']} (Android {info['android_verzija']}), serijski {serial}")
    log(f"Operater: {args.operater}")
    log(f"Izlaz: {paket_dir}")

    (paket_dir / "info_uredjaja.json").write_text(
        json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    apps = aplikacije(serial)
    (paket_dir / "aplikacije.json").write_text(
        json.dumps(apps, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Instalirano korisnickih aplikacija: {len(apps)}")

    log(f"Kopiranje {args.izvor} (moze potrajati)...")
    pull = adb("pull", "-a", args.izvor, str(fajlovi_dir), serial=serial)
    for linija in (pull.stdout + pull.stderr).splitlines():
        if linija.strip():
            log(f"adb: {linija.strip()}")
    if pull.returncode != 0:
        log("UPOZORENJE: adb pull je zavrsio s greskom, paket moze biti nepotpun.")

    log("Racunanje SHA-256 hasheva...")
    stavke = napravi_manifest(fajlovi_dir)
    (paket_dir / "manifest.json").write_text(
        json.dumps(stavke, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(paket_dir / "manifest.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["putanja", "velicina", "izmijenjen", "sha256"])
        w.writeheader()
        w.writerows(stavke)
    ukupno = sum(s["velicina"] for s in stavke)
    log(f"Fajlova: {len(stavke)}, ukupno {ukupno / 1024 / 1024:.1f} MB")

    kraj = datetime.now()
    log(f"Zavrseno za {(kraj - pocetak).total_seconds():.0f} s")
    (paket_dir / "log_izvlacenja.txt").write_text("\n".join(log_linije), encoding="utf-8")

    if not args.bez_zip:
        zip_putanja = paket_dir.with_suffix(".zip")
        print("Pakovanje u ZIP...", flush=True)
        with zipfile.ZipFile(zip_putanja, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(paket_dir.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(paket_dir.parent).as_posix())
        zip_hash = sha256_fajla(zip_putanja)
        Path(str(zip_putanja) + ".sha256").write_text(
            f"{zip_hash}  {zip_putanja.name}\n", encoding="utf-8")
        print(f"ZIP: {zip_putanja}\nSHA-256: {zip_hash}")

    print(f"\nGotovo. Paket: {paket_dir}")
    return 0


if __name__ == "__main__":
    code = main()
    if os.environ.get("IZVUCI_PAUZA") == "1":
        input("\nPritisnite Enter za zatvaranje...")
    sys.exit(code)
