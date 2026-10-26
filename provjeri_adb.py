import json
import subprocess
import sys
from pathlib import Path

APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
NAS_ADB = APP_DIR / "platform-tools" / "adb.exe"

PS_SKRIPTA = r"""
$procesi = @(Get-CimInstance Win32_Process -Filter "Name='adb.exe' OR Name='scrcpy.exe'" |
    Select-Object ProcessId, Name, ExecutablePath)
$rezultat = foreach ($p in $procesi) {
    $portovi = @(Get-NetTCPConnection -OwningProcess $p.ProcessId -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { "$($_.LocalAddress):$($_.LocalPort)" })
    [pscustomobject]@{
        pid = $p.ProcessId
        ime = $p.Name
        putanja = $p.ExecutablePath
        portovi = $portovi
    }
}
ConvertTo-Json -InputObject @($rezultat) -Depth 3
"""


def dohvati_procese():
    izlaz = subprocess.run(
        ["powershell", "-NoProfile", "-Command", PS_SKRIPTA],
        capture_output=True,
        text=True,
        timeout=30,
    )
    tekst = izlaz.stdout.strip()
    if not tekst:
        return []
    podaci = json.loads(tekst)
    return [p for p in podaci if p]


def main():
    procesi = dohvati_procese()
    adb_procesi = [p for p in procesi if p["ime"].lower() == "adb.exe"]
    scrcpy_procesi = [p for p in procesi if p["ime"].lower() == "scrcpy.exe"]

    if not adb_procesi:
        print("Nijedan adb.exe nije aktivan.")
    for p in adb_procesi:
        putanja = p["putanja"] or "(nepoznata putanja)"
        nas = bool(p["putanja"]) and Path(p["putanja"]).resolve() == NAS_ADB.resolve()
        portovi = ", ".join(p["portovi"]) if p["portovi"] else "nema otvorenih portova"
        oznaka = "NAŠ (platform-tools)" if nas else "DRUGI"
        print(f"[{oznaka}] PID {p['pid']}: {putanja}")
        print(f"    port(ovi): {portovi}")

    if scrcpy_procesi:
        print("\nAktivni scrcpy procesi:")
        for p in scrcpy_procesi:
            print(f"  PID {p['pid']}: {p['putanja'] or '(nepoznata putanja)'}")

    drugi = [
        p for p in adb_procesi
        if not p["putanja"] or Path(p["putanja"]).resolve() != NAS_ADB.resolve()
    ]
    print()
    if drugi:
        print(f"UPOZORENJE: aktivno je {len(drugi)} drugih adb procesa - moguć konflikt.")
        return 1
    print("Nema drugih adb procesa - nema konflikta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
