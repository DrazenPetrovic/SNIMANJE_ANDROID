
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from pathlib import Path
from datetime import datetime
import base64
import ctypes
from ctypes import wintypes
import hashlib
import re
import subprocess
import os
import socket
import sys
import threading
import webbrowser
import zipfile

APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
ADB_EXE = APP_DIR / "platform-tools" / "adb.exe"
SCRCPY_EXE = APP_DIR / "scrcpy" / "scrcpy.exe"
ADB_SERVER_PORT = 5038
# U --windowed exe verziji svaki konzolni program bi otvorio crni prozor.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# Folderi na telefonu u kojima završe exporti chatova: WhatsApp dokumenti
# (kad se export pošalje sebi) i Download/Documents (kad se sačuva u Files).
WHATSAPP_FOLDERI = [
    "/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Documents",
    "/sdcard/Android/media/com.whatsapp.w4b/WhatsApp Business/Media/"
    "WhatsApp Business Documents",
    "/sdcard/WhatsApp/Media/WhatsApp Documents",
    # Drugi WhatsApp: Xiaomi "Dual apps" (korisnik 999),
    # Samsung "Dual Messenger" (korisnik 95).
    "/storage/emulated/999/Android/media/com.whatsapp/WhatsApp/Media/"
    "WhatsApp Documents",
    "/storage/emulated/999/WhatsApp/Media/WhatsApp Documents",
    "/storage/emulated/95/Android/media/com.whatsapp/WhatsApp/Media/"
    "WhatsApp Documents",
    "/sdcard/Download",
    "/sdcard/Documents",
]

folder = Path.home() / "Pictures" / "SNIMCI"
folder.mkdir(parents=True, exist_ok=True)

proces = None
snimanje = False
putanja_snimanja = None
faza = "spremno"
dugmad = {}
zapisi_sesije = []
prozor_loga = None
arhiva_aktivna = False
arhiva_dimenzije = None
arhiva_potpis = None
arhiva_broj = 0
arhiva_stabilna = 0
arhiva_paket = None
broj_snimljenih_slika = 0
rezim = "izbor"
kamera = None
kamera_writer = None
kamera_prozor = None
kamera_slika_widget = None
kamera_photo = None
kamera_zadnji_frame = None
kamera_video_putanja = None
automatski_screenshot_aktivan = False
automatski_screenshot_job = None
adb_status_job = None
info_telefona_job = None
boje_dugmadi = {
    "pokreni": ("#1769D2", "white"),
    "video": ("#D9485F", "white"),
    "screenshot": ("#E8F1FC", "#1456A0"),
    "razgovor": ("#6B4CCB", "white"),
    "zaustavi": ("#C62828", "white"),
    "kamera_pokreni": ("#1769D2", "white"),
    "kamera_video": ("#D9485F", "white"),
    "kamera_screenshot": ("#E8F1FC", "#1456A0"),
    "kamera_postavke": ("#E8F1FC", "#1456A0"),
    "kamera_zaustavi": ("#C62828", "white"),
    "automatski_screenshot": ("#1769D2", "white"),
}

def zabiljezi(poruka):
    zapis = f"{datetime.now().strftime('%H:%M:%S')}  {poruka}"
    zapisi_sesije.append(zapis)
    if prozor_loga and prozor_loga.winfo_exists():
        tekst_loga.config(state="normal")
        tekst_loga.insert("end", zapis + "\n")
        tekst_loga.see("end")
        tekst_loga.config(state="disabled")

overlay_slike = None
overlay_slike_job = None

def prikazi_overlay_slike(broj):
    global overlay_slike, overlay_slike_job
    try:
        app.update_idletasks()
        if overlay_slike_job is not None:
            app.after_cancel(overlay_slike_job)
            overlay_slike_job = None
        if overlay_slike is not None and overlay_slike.winfo_exists():
            overlay_slike.destroy()
        okvir = tk.Toplevel(app)
        okvir.overrideredirect(True)
        okvir.attributes("-topmost", True)
        okvir.attributes("-alpha", 0.88)
        okvir.configure(bg="#174A7E")
        okvir.geometry(
            f"{app.winfo_width()}x{app.winfo_height()}"
            f"+{app.winfo_rootx()}+{app.winfo_rooty()}"
        )
        tk.Label(
            okvir,
            text=f"\U0001F4F7\n{broj}",
            bg="#174A7E",
            fg="white",
            font=("Segoe UI", 110, "bold"),
        ).pack(expand=True, fill="both")
        overlay_slike = okvir
        overlay_slike_job = app.after(900, sakrij_overlay_slike)
    except tk.TclError:
        overlay_slike = None

def sakrij_overlay_slike():
    global overlay_slike, overlay_slike_job
    overlay_slike_job = None
    if overlay_slike is not None:
        try:
            overlay_slike.destroy()
        except tk.TclError:
            pass
        overlay_slike = None

overlay_zauzeto = None

def prikazi_zauzeto(tekst):
    global overlay_zauzeto
    sakrij_zauzeto()
    try:
        app.update_idletasks()
        okvir = tk.Toplevel(app)
        okvir.overrideredirect(True)
        okvir.attributes("-topmost", True)
        okvir.attributes("-alpha", 0.92)
        okvir.configure(bg="#795800", cursor="watch")
        okvir.geometry(
            f"{app.winfo_width()}x{app.winfo_height()}"
            f"+{app.winfo_rootx()}+{app.winfo_rooty()}"
        )
        tk.Label(
            okvir,
            text=f"\u23F3\n{tekst}\nSačekaj, ne klikći.",
            bg="#795800",
            fg="white",
            font=("Segoe UI", 28, "bold"),
            wraplength=max(app.winfo_width() - 40, 200),
            cursor="watch",
        ).pack(expand=True, fill="both")
        overlay_zauzeto = okvir
        okvir.update()
    except tk.TclError:
        overlay_zauzeto = None

def sakrij_zauzeto():
    global overlay_zauzeto
    if overlay_zauzeto is not None:
        try:
            overlay_zauzeto.destroy()
        except tk.TclError:
            pass
        overlay_zauzeto = None

def evidentiraj_snimljenu_sliku():
    global broj_snimljenih_slika
    broj_snimljenih_slika += 1
    broj_slika_status.set(f"Snimljeno slika: {broj_snimljenih_slika}")
    prikazi_overlay_slike(broj_snimljenih_slika)

def verzija_adb():
    if not ADB_EXE.is_file():
        return "nije pronađen"
    try:
        rezultat = subprocess.run(
            [str(ADB_EXE), "version"],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=5
        )
    except (OSError, subprocess.TimeoutExpired):
        return "nije dostupna"
    if rezultat.returncode != 0:
        return "nije dostupna"
    poklapanje = re.search(r"^Version\s+(.+)$", rezultat.stdout, re.MULTILINE)
    return poklapanje.group(1).strip() if poklapanje else "nepoznata"

def osvjezi_adb_status():
    global adb_status_job
    try:
        with socket.create_connection(
            ("127.0.0.1", ADB_SERVER_PORT), timeout=0.4
        ):
            server_status = f"aktivan na portu {ADB_SERVER_PORT}"
    except OSError:
        server_status = f"neaktivan na portu {ADB_SERVER_PORT}"
    adb_status.set(f"ADB {adb_verzija_localna}: server {server_status}")
    adb_status_job = app.after(2000, osvjezi_adb_status)

def osvjezi_info_telefona():
    global info_telefona_job
    try:
        uredjaji = adb_poziv(["devices"], timeout=5).decode(errors="replace")
        serijski = [
            red.split("\t")[0] for red in uredjaji.splitlines()[1:]
            if "\tdevice" in red
        ]
        if not serijski:
            info_telefona.set("Telefon: nije spojen / nije prepoznat")
        else:
            model = adb_getprop("ro.product.model", timeout=5) or "nepoznat model"
            info_telefona.set(f"Telefon: {model}  ·  Serijski broj: {serijski[0]}")
    except RuntimeError:
        info_telefona.set("Telefon: ne mogu se spojiti (provjeri USB/ADB)")
    info_telefona_job = app.after(3000, osvjezi_info_telefona)

def adb_server_aktivan():
    try:
        with socket.create_connection(
            ("127.0.0.1", ADB_SERVER_PORT), timeout=0.4
        ):
            return True
    except OSError:
        return False

def ugasi_adb_server():
    if not adb_server_aktivan():
        return
    zabiljezi(f"ADB server je ostao aktivan na portu {ADB_SERVER_PORT}, gasim ga.")
    bez_prozora = subprocess.CREATE_NO_WINDOW
    try:
        subprocess.run(
            [str(ADB_EXE), "-P", str(ADB_SERVER_PORT), "kill-server"],
            capture_output=True,
            timeout=10,
            creationflags=bez_prozora
        )
        if adb_server_aktivan():
            # Rezerva: prekini samo adb.exe koji sluša na tom portu
            subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "Get-NetTCPConnection -State Listen "
                    f"-LocalPort {ADB_SERVER_PORT} -ErrorAction SilentlyContinue "
                    "| ForEach-Object { Get-Process -Id $_.OwningProcess } "
                    "| Where-Object { $_.ProcessName -eq 'adb' } "
                    "| Stop-Process -Force"
                ],
                capture_output=True,
                timeout=15,
                creationflags=bez_prozora
            )
    except (OSError, subprocess.TimeoutExpired) as e:
        zabiljezi(f"Greška pri gašenju ADB servera: {e}")
        return
    if adb_server_aktivan():
        zabiljezi(f"ADB server na portu {ADB_SERVER_PORT} nije ugašen.")
    else:
        zabiljezi(f"ADB server na portu {ADB_SERVER_PORT} je ugašen.")

def centriraj_prozor(prozor, roditelj=None):
    prozor.update_idletasks()
    sirina = prozor.winfo_width()
    visina = prozor.winfo_height()
    if roditelj and roditelj.winfo_exists():
        x = roditelj.winfo_rootx() + (roditelj.winfo_width() - sirina) // 2
        y = roditelj.winfo_rooty() + (roditelj.winfo_height() - visina) // 2
    else:
        x = (prozor.winfo_screenwidth() - sirina) // 2
        y = (prozor.winfo_screenheight() - visina) // 2
    x = max(0, x)
    y = max(0, y)
    prozor.geometry(f"+{x}+{y}")

def pozicioniraj_glavni_prozor_desno():
    app.update_idletasks()
    x = max(0, app.winfo_screenwidth() - app.winfo_width())
    y = max(0, (app.winfo_screenheight() - app.winfo_height()) // 2)
    app.geometry(f"+{x}+{y}")

def prikazi_log():
    global prozor_loga, tekst_loga
    if prozor_loga and prozor_loga.winfo_exists():
        prozor_loga.lift()
        return

    prozor_loga = tk.Toplevel(app)
    prozor_loga.title("Privremeni log sesije")
    prozor_loga.geometry("620x360")
    prozor_loga.configure(bg="#EAF2FB")
    centriraj_prozor(prozor_loga, app)
    tk.Label(
        prozor_loga,
        text="Događaji i snimljene datoteke ove sesije",
        bg="#EAF2FB",
        fg="#174A7E",
        font=("Segoe UI", 11, "bold")
    ).pack(anchor="w", padx=12, pady=(12, 6))

    okvir = tk.Frame(prozor_loga, bg="#FFFFFF")
    okvir.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    klizac = tk.Scrollbar(okvir)
    klizac.pack(side="right", fill="y")
    tekst_loga = tk.Text(
        okvir,
        wrap="word",
        state="disabled",
        bg="#FFFFFF",
        fg="#243B53",
        font=("Consolas", 9),
        relief="flat",
        yscrollcommand=klizac.set
    )
    tekst_loga.pack(side="left", fill="both", expand=True, padx=8, pady=8)
    klizac.config(command=tekst_loga.yview)
    if zapisi_sesije:
        tekst_loga.config(state="normal")
        tekst_loga.insert("end", "\n".join(zapisi_sesije) + "\n")
        tekst_loga.see("end")
        tekst_loga.config(state="disabled")

def stil_dugmeta(dugme, pozadina, tekst):
    aktivno = dugme["state"] == "normal"
    if not aktivno:
        pozadina, tekst = "#DDE3EA", "#788493"
    dugme.config(
        bg=pozadina,
        fg=tekst,
        activebackground=pozadina,
        activeforeground=tekst,
        disabledforeground=tekst,
        relief="flat",
        bd=0 if aktivno else 1,
        highlightthickness=0 if aktivno else 1,
        highlightbackground="#A61F1F" if aktivno else "#DDE3EA",
        cursor="hand2" if aktivno else "arrow",
        font=("Segoe UI", 11 if aktivno and dugme is dugmad.get("zaustavi") else 10, "bold")
    )

def osvjezi_dugmad():
    if rezim == "kamera":
        kamera_aktivna = faza in ("kamera_prikaz", "kamera_snimanje")
        dugmad["kamera_pokreni"].config(
            state="disabled" if kamera_aktivna else "normal"
        )
        dugmad["kamera_video"].config(
            state="normal" if kamera_aktivna else "disabled",
            text=(
                "Zaustavi MP4 snimanje"
                if faza == "kamera_snimanje"
                else "Pokreni MP4 snimanje"
            )
        )
        dugmad["kamera_screenshot"].config(
            state="normal" if kamera_aktivna else "disabled"
        )
        dugmad["kamera_postavke"].config(
            state="normal" if kamera_aktivna else "disabled"
        )
        dugmad["kamera_zaustavi"].config(
            state="normal" if kamera_aktivna else "disabled"
        )
    else:
        dugmad["pokreni"].config(
            state="normal" if faza == "spremno" else "disabled"
        )
        dugmad["video"].config(
            state="normal" if faza == "prikaz" else "disabled"
        )
        dugmad["screenshot"].config(
            state="normal" if faza in ("prikaz", "snimanje") else "disabled"
        )
        dugmad["razgovor"].config(
            state="normal" if faza in (
                "prikaz", "arhiva_pocetak", "arhiva_snimanje"
            ) else "disabled",
            text=(
                "Zaustavi snimanje razgovora"
                if faza in ("arhiva_pocetak", "arhiva_snimanje")
                else "Snimi razgovor (screenshotovi sa preklapanjem)"
            )
        )
        dugmad["zaustavi"].config(
            state="normal" if faza in (
                "prikaz", "snimanje", "arhiva_pocetak", "arhiva_snimanje"
            ) else "disabled",
            text=(
                "ZAUSTAVI MP4 SNIMANJE"
                if snimanje else "ZAUSTAVI SCRCPY"
            )
        )
    spreman_za_screenshot = (
        faza in ("kamera_prikaz", "kamera_snimanje")
        if rezim == "kamera"
        else faza in ("prikaz", "snimanje")
    )
    dugmad["automatski_screenshot"].config(
        state=(
            "normal"
            if automatski_screenshot_aktivan or spreman_za_screenshot
            else "disabled"
        ),
        text=(
            "Zaustavi automatske screenshotove"
            if automatski_screenshot_aktivan
            else "Pokreni automatske screenshotove"
        )
    )
    for ime, dugme in dugmad.items():
        stil_dugmeta(dugme, *boje_dugmadi[ime])

def postavi_fazu(nova_faza):
    global faza
    faza = nova_faza
    osvjezi_dugmad()

def potvrdi_pokretanje(novi_proces, pokrenuto_snimanje, putanja=None):
    global proces, snimanje, putanja_snimanja
    sakrij_zauzeto()
    if proces is not novi_proces:
        return
    if novi_proces.poll() is not None:
        proces = None
        snimanje = False
        putanja_snimanja = None
        postavi_fazu("spremno")
        if pokrenuto_snimanje and putanja:
            prijavi_zavrsetak_videa(putanja)
        else:
            status.set("scrcpy se nije uspješno pokrenuo")
            zabiljezi("Greška: scrcpy se odmah zatvorio.")
            messagebox.showerror(
                "Greška",
                "scrcpy se odmah zatvorio. Provjeri telefon, USB debugging "
                "i instalaciju scrcpy.",
                parent=app
            )
        return

    snimanje = pokrenuto_snimanje
    if pokrenuto_snimanje:
        status.set(f"Snimanje: {putanja.name}")
        zabiljezi(f"Pokrenuto MP4 snimanje: {putanja}")
        postavi_fazu("snimanje")
    else:
        status.set("scrcpy je pokrenut. Izaberi Screenshot ili MP4 snimanje.")
        zabiljezi("scrcpy je pokrenut.")
        postavi_fazu("prikaz")
    app.after(500, prati_proces, novi_proces, pokrenuto_snimanje, putanja)

def prijavi_zavrsetak_videa(putanja):
    try:
        uspjesno = putanja.is_file() and putanja.stat().st_size > 0
    except OSError as e:
        status.set("Nije moguće provjeriti MP4 datoteku")
        zabiljezi(f"Greška pri provjeri MP4 datoteke {putanja}: {e}")
        messagebox.showerror(
            "Greška",
            f"Nije moguće provjeriti snimljeni video:\n{e}",
            parent=app
        )
        return

    if uspjesno:
        status.set(f"Video uspješno snimljen: {putanja.name}")
        zabiljezi(f"MP4 uspješno snimljen: {putanja}")
        messagebox.showinfo(
            "Snimanje završeno",
            f"Video je uspješno snimljen:\n{putanja}",
            parent=app
        )
    else:
        status.set("MP4 snimanje nije uspješno sačuvano")
        zabiljezi(f"Greška: MP4 datoteka nije sačuvana: {putanja}")
        messagebox.showwarning(
            "Snimanje nije uspjelo",
            "MP4 datoteka nije pronađena ili je prazna.",
            parent=app
        )

def prati_proces(novi_proces, pokrenuto_snimanje, putanja=None):
    global proces, snimanje, putanja_snimanja
    if proces is not novi_proces:
        return
    if novi_proces.poll() is None:
        app.after(500, prati_proces, novi_proces, pokrenuto_snimanje, putanja)
        return

    proces = None
    snimanje = False
    putanja_snimanja = None
    postavi_fazu("spremno")
    ugasi_adb_server()
    if pokrenuto_snimanje:
        prijavi_zavrsetak_videa(putanja)
    else:
        status.set("scrcpy je zatvoren")
        zabiljezi("scrcpy sesija je zatvorena.")

def pokreni_scrcpy(komanda, pokrenuto_snimanje=False, putanja=None):
    global proces, putanja_snimanja
    if not SCRCPY_EXE.is_file():
        status.set("Lokalni scrcpy.exe nije pronađen")
        zabiljezi(f"Greška: nije pronađen izvršni fajl {SCRCPY_EXE}")
        messagebox.showerror(
            "Nedostaje scrcpy.exe",
            "U folderu scrcpy trenutno nije pronađen scrcpy.exe:\n"
            f"{SCRCPY_EXE}\n\n"
            "Dodaj Windows izdanje scrcpy u ovaj folder. Sam izvorni kod "
            "scrcpy nije moguće pokrenuti direktno.",
            parent=app
        )
        return

    visina_ekrana = app.winfo_screenheight()
    visina_prozora = round(visina_ekrana * 0.85)
    komanda = [
        str(SCRCPY_EXE),
        *komanda[1:],
        "--no-audio",
        "--window-x=0",
        f"--window-y={(visina_ekrana - visina_prozora) // 2}",
        f"--window-height={visina_prozora}",
    ]
    okruzenje = os.environ.copy()
    okruzenje["ADB_SERVER_SOCKET"] = f"tcp:localhost:{ADB_SERVER_PORT}"
    try:
        proces = subprocess.Popen(
            komanda,
            cwd=SCRCPY_EXE.parent,
            env=okruzenje,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    except OSError as e:
        proces = None
        putanja_snimanja = None
        status.set("scrcpy nije moguće pokrenuti")
        zabiljezi(f"Greška pri pokretanju scrcpy: {e}")
        if pokrenuto_snimanje:
            zabiljezi(f"MP4 snimanje nije pokrenuto: {putanja}")
        postavi_fazu("spremno")
        messagebox.showerror(
            "Greška",
            f"Pokretanje scrcpy nije uspjelo:\n{e}",
            parent=app
        )
        return

    novi_proces = proces
    putanja_snimanja = putanja if pokrenuto_snimanje else None
    zabiljezi("Pokretanje scrcpy...")
    status.set("Provjeravam da li se scrcpy uspješno pokrenuo...")
    postavi_fazu("pokretanje")
    prikazi_zauzeto("Pokreće se scrcpy...")
    app.after(
        1500,
        potvrdi_pokretanje,
        novi_proces,
        pokrenuto_snimanje,
        putanja
    )

def proveri_telefon():
    try:
        rezultat = subprocess.run(
            [str(ADB_EXE), "-P", str(ADB_SERVER_PORT), "devices"],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=10
        )
    except FileNotFoundError:
        status.set("ADB nije pronađen")
        zabiljezi("Greška: ADB nije pronađen.")
        messagebox.showerror(
            "Greška",
            "Lokalni ADB nije pronađen. Provjeri da postoji fajl:\n"
            f"{ADB_EXE}",
            parent=app
        )
        return False
    except subprocess.TimeoutExpired:
        status.set("Provjera telefona je istekla")
        zabiljezi("Greška: provjera telefona putem ADB-a je istekla.")
        messagebox.showerror(
            "Greška", "ADB nije odgovorio na vrijeme.", parent=app
        )
        return False

    if rezultat.returncode != 0:
        status.set("Greška pri provjeri telefona")
        zabiljezi(
            "Greška pri provjeri telefona: "
            + (rezultat.stderr.strip() or "ADB je vratio grešku.")
        )
        messagebox.showerror(
            "Greška",
            rezultat.stderr.strip() or "Provjera povezanog telefona nije uspjela.",
            parent=app
        )
        return False

    povezani = any(
        len(red.split()) >= 2 and red.split()[1] == "device"
        for red in rezultat.stdout.splitlines()[1:]
    )
    if not povezani:
        status.set("Telefon nije spojen")
        zabiljezi("Provjera telefona nije uspjela: telefon nije spojen.")
        messagebox.showwarning(
            "Telefon nije spojen",
            "Poveži telefon i omogući USB debugging. "
            "Ako je već povezan, provjeri da li je autorizovan.",
            parent=app
        )
        return False
    zabiljezi("Telefon je povezan i autorizovan.")
    return True

def naziv(ext):
    datum = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return folder / f"{datum}.{ext}"

def pokreni():
    if not proveri_telefon():
        return
    zabiljezi("----- Nova scrcpy sesija -----")
    pokreni_scrcpy(["scrcpy"])

def zatvori_prozore_procesa(pid):
    # WM_CLOSE je isto kao klik na X: scrcpy uredno završi i MP4 fajl.
    # CTRL_BREAK ne radi iz --windowed exe-a jer on nema konzolu.
    user32 = ctypes.windll.user32
    pronadjeni = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def obradi(hwnd, _lparam):
        vlasnik = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(vlasnik))
        if vlasnik.value == pid and user32.IsWindowVisible(hwnd):
            pronadjeni.append(hwnd)
        return True

    user32.EnumWindows(obradi, 0)
    for hwnd in pronadjeni:
        user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
    return bool(pronadjeni)

def zaustavi_proces(tiho=False):
    if not proces or proces.poll() is not None:
        return True
    try:
        if zatvori_prozore_procesa(proces.pid):
            try:
                proces.wait(timeout=10)
                return True
            except subprocess.TimeoutExpired:
                zabiljezi("scrcpy se nije zatvorio na vrijeme; prisilno gašenje.")
        proces.kill()
        proces.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired) as e:
        zabiljezi(f"Greška pri zaustavljanju scrcpy: {e}")
        if not tiho:
            messagebox.showerror("Greška", str(e), parent=app)
        return False
    return True

def video():
    global proces, snimanje
    if not proveri_telefon():
        return
    if not zaustavi_proces():
        return
    if proces and proces.poll() is not None:
        zabiljezi("scrcpy pregled zatvoren radi pokretanja MP4 snimanja.")
    proces = None
    snimanje = False
    postavi_fazu("spremno")
    putanja = naziv("mp4")
    zabiljezi("----- MP4 snimanje -----")
    pokreni_scrcpy(
        ["scrcpy", "--record", str(putanja)],
        pokrenuto_snimanje=True,
        putanja=putanja
    )

def zaustavi():
    global proces, snimanje, putanja_snimanja, arhiva_aktivna
    zaustavi_automatske_screenshotove()
    bilo_snimanje = snimanje
    putanja_videa = putanja_snimanja if bilo_snimanje else None
    if arhiva_aktivna:
        arhiva_aktivna = False
        zabiljezi("Automatsko snimanje razgovora prekinuto zatvaranjem scrcpy.")
    if not zaustavi_proces():
        return
    proces = None
    snimanje = False
    putanja_snimanja = None
    zabiljezi(
        "MP4 snimanje je zaustavljeno." if bilo_snimanje
        else "scrcpy sesija je zaustavljena."
    )
    ugasi_adb_server()
    if bilo_snimanje and putanja_videa:
        prijavi_zavrsetak_videa(putanja_videa)
    else:
        status.set("scrcpy zaustavljen")
    postavi_fazu("spremno")

def zaustavi_automatske_screenshotove():
    global automatski_screenshot_aktivan, automatski_screenshot_job
    automatski_screenshot_aktivan = False
    if automatski_screenshot_job is not None:
        try:
            app.after_cancel(automatski_screenshot_job)
        except tk.TclError:
            pass
        automatski_screenshot_job = None
    if "timer_status" in globals():
        timer_status.set("Automatski screenshotovi su isključeni")
    if "automatski_screenshot" in dugmad:
        osvjezi_dugmad()

def rasporedi_automatski_screenshot():
    global automatski_screenshot_job
    if not automatski_screenshot_aktivan:
        return
    try:
        interval = int(timer_interval_var.get())
    except ValueError:
        status.set("Unesi valjan interval u sekundama")
        zaustavi_automatske_screenshotove()
        return
    automatski_screenshot_job = app.after(
        interval * 1000, napravi_automatski_screenshot
    )

def napravi_automatski_screenshot():
    global automatski_screenshot_job
    automatski_screenshot_job = None
    if not automatski_screenshot_aktivan:
        return

    if rezim == "kamera":
        if faza not in ("kamera_prikaz", "kamera_snimanje"):
            zaustavi_automatske_screenshotove()
            return
        if not kamera_screenshot(automatski=True):
            return
    else:
        if faza not in ("prikaz", "snimanje"):
            zaustavi_automatske_screenshotove()
            return
        if not screenshot(automatski=True):
            return

    rasporedi_automatski_screenshot()

def ukljuci_automatske_screenshotove():
    global automatski_screenshot_aktivan
    if automatski_screenshot_aktivan:
        zaustavi_automatske_screenshotove()
        zabiljezi("Automatski screenshotovi su zaustavljeni.")
        return

    spreman = (
        faza in ("kamera_prikaz", "kamera_snimanje")
        if rezim == "kamera"
        else faza in ("prikaz", "snimanje")
    )
    if not spreman:
        messagebox.showwarning(
            "Snimanje nije pokrenuto",
            "Prvo pokreni pregled Androida ili USB kamere.",
            parent=app
        )
        return
    try:
        interval = int(timer_interval_var.get())
    except ValueError:
        interval = 0
    if not 1 <= interval <= 3600:
        messagebox.showwarning(
            "Neispravan interval",
            "Unesi interval od 1 do 3600 sekundi.",
            parent=app
        )
        return

    automatski_screenshot_aktivan = True
    timer_status.set(f"Automatski screenshot uključen — svakih {interval} s")
    zabiljezi(
        f"Automatski screenshotovi uključeni (svakih {interval} sekundi)."
    )
    osvjezi_dugmad()
    rasporedi_automatski_screenshot()

def screenshot(automatski=False):
    if faza not in ("prikaz", "snimanje"):
        return False
    if not automatski and not proveri_telefon():
        return False
    putanja = naziv("png")
    try:
        with open(putanja, "wb") as fajl:
            rezultat = subprocess.run(
                [
                    str(ADB_EXE), "-P", str(ADB_SERVER_PORT),
                    "exec-out", "screencap", "-p"
                ],
                stdout=fajl,
                stderr=subprocess.PIPE,
                timeout=20
            )
        if rezultat.returncode != 0:
            putanja.unlink(missing_ok=True)
            raise RuntimeError(
                rezultat.stderr.decode(errors="replace")
            )
        status.set(f"Sačuvano: {putanja.name}")
        evidentiraj_snimljenu_sliku()
        zabiljezi(f"Screenshot sačuvan: {putanja}")
        return True
    except Exception as e:
        zabiljezi(f"Greška pri izradi screenshota: {e}")
        if automatski:
            status.set("Automatski screenshot nije uspio; timer je zaustavljen")
            zaustavi_automatske_screenshotove()
        else:
            messagebox.showerror("Greška", str(e), parent=app)
        return False

def adb_poziv(argumenti, timeout=20):
    try:
        rezultat = subprocess.run(
            [str(ADB_EXE), "-P", str(ADB_SERVER_PORT), *argumenti],
            capture_output=True,
            timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"ADB naredba nije uspjela: {e}") from e
    if rezultat.returncode != 0:
        greska = rezultat.stderr.decode(errors="replace").strip()
        raise RuntimeError(greska or "ADB naredba nije uspjela.")
    return rezultat.stdout

def adb_getprop(ime, timeout=10):
    # Vraća "" ako property ne postoji na ovom modelu/firmware-u — ne baca
    # grešku, jer dobar dio ovih property-ja zavisi od proizvođača.
    try:
        return adb_poziv(["shell", "getprop", ime], timeout=timeout).decode(
            errors="replace"
        ).strip()
    except RuntimeError:
        return ""

def paket_u_prednjem_planu():
    izlazi = [
        (
            ["shell", "dumpsys", "window"],
            ("mCurrentFocus", "mFocusedApp")
        ),
        (
            ["shell", "dumpsys", "activity", "activities"],
            ("topResumedActivity", "mResumedActivity", "ResumedActivity",
             "mFocusedActivity")
        ),
    ]
    for komanda, oznake in izlazi:
        tekst = adb_poziv(komanda, timeout=15).decode(errors="replace")
        for red in tekst.splitlines():
            if not any(oznaka in red for oznaka in oznake):
                continue
            poklapanje = re.search(
                r"\b([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+)/"
                r"[A-Za-z0-9_.$]+",
                red
            )
            if poklapanje:
                return poklapanje.group(1)
    return None

def izaberi_aplikaciju_za_poruke(paket_u_fokusu):
    greska_liste = None
    try:
        izlaz = adb_poziv(["shell", "pm", "list", "packages"], timeout=20)
        paketi = sorted(
            red[len("package:"):].strip()
            for red in izlaz.decode(errors="replace").splitlines()
            if red.startswith("package:")
        )
    except RuntimeError as e:
        paketi = []
        greska_liste = str(e)

    prozor = tk.Toplevel(app)
    prozor.title("Izaberi aplikaciju za poruke")
    prozor.configure(bg="#EAF2FB")
    prozor.resizable(False, False)
    prozor.transient(app)

    tk.Label(
        prozor,
        text="Izaberi aplikaciju u kojoj je otvoren razgovor:",
        bg="#EAF2FB",
        fg="#174A7E",
        font=("Segoe UI", 10, "bold")
    ).pack(anchor="w", padx=16, pady=(16, 6))
    tk.Label(
        prozor,
        text="Pretraži listu ili ručno unesi naziv paketa aplikacije.",
        bg="#EAF2FB",
        fg="#38536D",
        font=("Segoe UI", 9)
    ).pack(anchor="w", padx=16, pady=(0, 8))
    tk.Label(
        prozor,
        text=(
            "Ako Android ne prijavi aplikaciju u prvom planu, "
            "promenu aplikacije tokom snimanja nije moguće automatski proveriti."
        ),
        bg="#EAF2FB",
        fg="#795800",
        wraplength=430,
        justify="left",
        font=("Segoe UI", 9)
    ).pack(anchor="w", padx=16, pady=(0, 8))
    if greska_liste:
        zabiljezi(f"Nije moguće učitati listu aplikacija: {greska_liste}")
        tk.Label(
            prozor,
            text="Lista aplikacija nije dostupna; unesi naziv paketa ručno.",
            bg="#EAF2FB",
            fg="#A12622",
            font=("Segoe UI", 9)
        ).pack(anchor="w", padx=16, pady=(0, 8))

    pretraga = tk.StringVar()
    vrednost = tk.StringVar(value=paket_u_fokusu or "")
    tk.Entry(
        prozor,
        textvariable=pretraga,
        font=("Segoe UI", 10),
        relief="solid",
        bd=1
    ).pack(fill="x", padx=16, pady=(0, 6))

    lista_okvir = tk.Frame(prozor, bg="#FFFFFF")
    lista_okvir.pack(fill="both", expand=True, padx=16, pady=(0, 8))
    klizac = tk.Scrollbar(lista_okvir)
    klizac.pack(side="right", fill="y")
    lista = tk.Listbox(
        lista_okvir,
        height=9,
        bg="#FFFFFF",
        fg="#243B53",
        selectbackground="#1769D2",
        selectforeground="white",
        yscrollcommand=klizac.set,
        relief="flat",
        font=("Consolas", 9)
    )
    lista.pack(side="left", fill="both", expand=True)
    klizac.config(command=lista.yview)

    def filtriraj(_event=None):
        pojam = pretraga.get().strip().casefold()
        lista.delete(0, "end")
        for paket in paketi:
            if pojam in paket.casefold():
                lista.insert("end", paket)

    def izaberi_sa_liste(_event=None):
        izbori = lista.curselection()
        if izbori:
            vrednost.set(lista.get(izbori[0]))

    pretraga.trace_add("write", filtriraj)
    lista.bind("<<ListboxSelect>>", izaberi_sa_liste)
    filtriraj()

    tk.Label(
        prozor,
        text="Izabrani naziv paketa:",
        bg="#EAF2FB",
        fg="#38536D",
        font=("Segoe UI", 9)
    ).pack(anchor="w", padx=16, pady=(0, 4))
    tk.Entry(
        prozor,
        textvariable=vrednost,
        font=("Segoe UI", 10),
        relief="solid",
        bd=1
    ).pack(fill="x", padx=16, pady=(0, 12))

    izabrani_paket = {"vrednost": None}

    def potvrdi():
        paket = vrednost.get().strip()
        if not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+",
            paket
        ):
            messagebox.showerror(
                "Neispravan naziv paketa",
                "Unesi naziv paketa, na primer com.viber.voip.",
                parent=prozor
            )
            return
        izabrani_paket["vrednost"] = paket
        prozor.destroy()

    dugmad_prozora = tk.Frame(prozor, bg="#EAF2FB")
    dugmad_prozora.pack(fill="x", padx=12, pady=(0, 12))
    tk.Button(
        dugmad_prozora,
        text="Potvrdi aplikaciju",
        command=potvrdi,
        bg="#1769D2",
        fg="white",
        activebackground="#1456A0",
        activeforeground="white",
        relief="flat",
        padx=12,
        pady=7
    ).pack(side="right", padx=4)
    tk.Button(
        dugmad_prozora,
        text="Otkaži",
        command=prozor.destroy,
        bg="#D8E8FA",
        fg="#174A7E",
        activebackground="#C6DDF5",
        activeforeground="#123F6B",
        relief="flat",
        padx=12,
        pady=7
    ).pack(side="right", padx=4)

    prozor.bind("<Return>", lambda _event: potvrdi())
    prozor.bind("<Escape>", lambda _event: prozor.destroy())
    prozor.grab_set()
    centriraj_prozor(prozor, app)
    app.wait_window(prozor)
    return izabrani_paket["vrednost"]

def podesi_pocetni_prikaz(pocetna_slika, paket):
    prozor = tk.Toplevel(app)
    prozor.title("Podesi početnu tačku")
    prozor.configure(bg="#EAF2FB")
    prozor.resizable(False, False)
    prozor.transient(app)

    tk.Label(
        prozor,
        text="Podesi početnu tačku razgovora",
        bg="#EAF2FB",
        fg="#174A7E",
        font=("Segoe UI", 11, "bold")
    ).pack(anchor="w", padx=16, pady=(14, 4))
    tk.Label(
        prozor,
        text=(
            "Na telefonu pomeri razgovor do mesta od kog želiš da počne "
            "snimanje. Zatim osveži pregled i potvrdi. Snimanje će ići ka "
            "novijim porukama."
        ),
        bg="#EAF2FB",
        fg="#38536D",
        wraplength=380,
        justify="left",
        font=("Segoe UI", 9)
    ).pack(anchor="w", padx=16, pady=(0, 8))

    prikaz = tk.Label(prozor, bg="#FFFFFF", relief="solid", bd=1)
    prikaz.pack(padx=16, pady=(0, 10))
    stanje = {"slika": None, "photo": None}
    rezultat = {"slika": None}
    info = tk.StringVar(value="")
    tk.Label(
        prozor,
        textvariable=info,
        bg="#EAF2FB",
        fg="#38536D",
        font=("Segoe UI", 9)
    ).pack(anchor="w", padx=16, pady=(0, 8))

    def prikazi_sliku(png):
        slika = tk.PhotoImage(
            master=prozor,
            data=base64.b64encode(png).decode("ascii"),
            format="png"
        )
        faktor = max(
            1,
            (slika.width() + 319) // 320,
            (slika.height() + 399) // 400
        )
        umanjena = slika.subsample(faktor, faktor)
        stanje["slika"] = png
        stanje["photo"] = umanjena
        prikaz.config(image=umanjena)
        info.set(f"Pregled: {slika.width()} × {slika.height()} px")

    def osvezi():
        try:
            paket_u_fokusu = paket_u_prednjem_planu()
            if paket_u_fokusu and paket_u_fokusu != paket:
                raise RuntimeError(
                    "Izabrana aplikacija nije u prvom planu. "
                    "Vrati razgovor na telefon pa osveži pregled."
                )
            prikazi_sliku(snimi_png())
        except (RuntimeError, tk.TclError) as e:
            messagebox.showerror("Greška", str(e), parent=prozor)

    def potvrdi():
        rezultat["slika"] = stanje["slika"]
        prozor.destroy()

    dugmad_prozora = tk.Frame(prozor, bg="#EAF2FB")
    dugmad_prozora.pack(fill="x", padx=12, pady=(0, 12))
    tk.Button(
        dugmad_prozora,
        text="Osveži pregled",
        command=osvezi,
        bg="#D8E8FA",
        fg="#174A7E",
        relief="flat",
        padx=12,
        pady=7
    ).pack(side="left", padx=4)
    tk.Button(
        dugmad_prozora,
        text="Počni od ovog prikaza",
        command=potvrdi,
        bg="#1769D2",
        fg="white",
        activebackground="#1456A0",
        activeforeground="white",
        relief="flat",
        padx=12,
        pady=7
    ).pack(side="right", padx=4)
    tk.Button(
        dugmad_prozora,
        text="Otkaži",
        command=prozor.destroy,
        bg="#D8E8FA",
        fg="#174A7E",
        relief="flat",
        padx=12,
        pady=7
    ).pack(side="right", padx=4)

    prozor.bind("<Escape>", lambda _event: prozor.destroy())
    prozor.grab_set()
    centriraj_prozor(prozor, app)
    prikazi_sliku(pocetna_slika)
    app.wait_window(prozor)
    return rezultat["slika"]

def dimenzije_ekrana():
    izlaz = adb_poziv(["shell", "wm", "size"], timeout=10)
    velicine = re.findall(r"(\d+)x(\d+)", izlaz.decode(errors="replace"))
    if not velicine:
        raise RuntimeError("Nije moguće pročitati dimenzije ekrana telefona.")
    return tuple(map(int, velicine[-1]))

def snimi_png():
    izlaz = adb_poziv(["exec-out", "screencap", "-p"], timeout=20)
    if not izlaz.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("ADB nije vratio ispravnu PNG sliku.")
    return izlaz

def potpis_sadrzaja_slika(png):
    slika = tk.PhotoImage(
        master=app,
        data=base64.b64encode(png).decode("ascii"),
        format="png"
    )
    sirina, visina = slika.width(), slika.height()
    uzorak = tuple(
        slika.get(round(sirina * x), round(visina * y))
        for y in (0.22, 0.28, 0.34, 0.40, 0.46, 0.52, 0.58, 0.64, 0.70, 0.76)
        for x in (0.15, 0.35, 0.5, 0.65, 0.85)
    )
    slika.tk.call("image", "delete", slika)
    return uzorak

def iste_stranice(prvi, drugi):
    return sum(a != b for a, b in zip(prvi, drugi)) <= 2

def geste_pomjeri(prema_pocetku, udio=None):
    if udio is None:
        udio = 0.70
        if rucni_pomak_aktivan.get():
            try:
                udio = min(max(float(rucni_pomak.get()), 10), 100) / 100
            except ValueError:
                pass
    sirina, visina = arhiva_dimenzije
    sredina = round(sirina / 2)
    vrh_poruka = round(visina * 0.16)
    dno_poruka = round(visina * 0.84)
    visina_poruka = dno_poruka - vrh_poruka
    pomeraj = round(visina_poruka * udio)
    sredina_poruka = (vrh_poruka + dno_poruka) // 2
    y_gore = sredina_poruka - pomeraj // 2
    y_dole = sredina_poruka + pomeraj // 2
    y_pocetak, y_kraj = (y_gore, y_dole) if prema_pocetku else (y_dole, y_gore)
    adb_poziv(
        ["shell", "input", "swipe", str(sredina), str(y_pocetak),
         str(sredina), str(y_kraj), "600"],
        timeout=10
    )

def sacuvaj_sliku(png, putanja):
    with putanja.open("wb") as fajl:
        upisano = fajl.write(png)
        if upisano != len(png):
            raise OSError(
                f"Nije upisana cela slika: {upisano} od {len(png)} bajtova."
            )
        fajl.flush()
        os.fsync(fajl.fileno())

def prekini_snimanje_razgovora(razlog, greska=False):
    global arhiva_aktivna
    arhiva_aktivna = False
    postavi_fazu("prikaz")
    status.set(razlog)
    zabiljezi(razlog)
    if greska:
        messagebox.showerror(
            "Greška pri snimanju razgovora", razlog, parent=app
        )

def zavrsi_snimanje_razgovora():
    global arhiva_aktivna
    arhiva_aktivna = False
    postavi_fazu("prikaz")
    status.set(f"Razgovor snimljen u {arhiva_broj} screenshotova")
    zabiljezi(f"Razgovor snimljen: {arhiva_broj} screenshotova.")
    messagebox.showinfo(
        "Snimanje završeno",
        f"Razgovor je sačuvan u {arhiva_broj} screenshotova.\nFolder: {folder}",
        parent=app
    )

def provjeri_aplikaciju_i_snimi():
    paket = paket_u_prednjem_planu()
    if paket and paket != arhiva_paket:
        raise RuntimeError(
            "Izabrana aplikacija više nije u prvom planu. Snimanje je "
            "zaustavljeno da se ne bi snimao drugi ekran."
        )
    return snimi_png()

def snimi_stranicu_razgovora(slika=None):
    global arhiva_broj, arhiva_potpis, arhiva_stabilna
    if not arhiva_aktivna:
        return
    try:
        if slika is None:
            slika = provjeri_aplikaciju_i_snimi()
        potpis = potpis_sadrzaja_slika(slika)
        if arhiva_broj and iste_stranice(potpis, arhiva_potpis):
            arhiva_stabilna += 1
            if arhiva_stabilna >= 3:
                zavrsi_snimanje_razgovora()
            else:
                app.after(150, pomjeri_na_slijedecu_stranicu)
            return
        arhiva_potpis = potpis
        arhiva_stabilna = 0
        putanja = naziv("png")
        sacuvaj_sliku(slika, putanja)
        arhiva_broj += 1
        evidentiraj_snimljenu_sliku()
        zabiljezi(f"Stranica razgovora {arhiva_broj} sačuvana: {putanja}")
        status.set(f"Snimljeno {arhiva_broj} stranica razgovora...")
        if arhiva_broj >= 1000:
            raise RuntimeError(
                "Dostignut je sigurnosni limit od 1000 screenshotova."
            )
        app.after(150, pomjeri_na_slijedecu_stranicu)
    except (OSError, RuntimeError, tk.TclError) as e:
        prekini_snimanje_razgovora(str(e), greska=True)

def pomjeri_na_slijedecu_stranicu():
    if not arhiva_aktivna:
        return
    try:
        geste_pomjeri(prema_pocetku=False)
        app.after(600, snimi_stranicu_razgovora)
    except RuntimeError as e:
        prekini_snimanje_razgovora(str(e), greska=True)

def snimi_razgovor():
    global arhiva_aktivna, arhiva_dimenzije, arhiva_potpis
    global arhiva_broj, arhiva_stabilna, arhiva_paket
    if faza in ("arhiva_pocetak", "arhiva_snimanje"):
        prekini_snimanje_razgovora("Automatsko snimanje razgovora je prekinuto.")
        return
    if faza != "prikaz":
        return
    if not proveri_telefon():
        return
    if not messagebox.askokcancel(
        "Snimi razgovor",
        "Otvori željeni razgovor u aplikaciji za poruke i ostavi ga "
        "na ekranu. U sledećem prozoru možeš pomeriti razgovor do željene "
        "početne tačke i proveriti pregled.\n\n"
        "Program će od izabranog prikaza sačuvati "
        "screenshote uz preklapanje (dno jedne slike = vrh sljedeće). "
        "Neće slati poruke. Možeš prekinuti snimanje ovim dugmetom.",
        parent=app
    ):
        return
    try:
        paket_u_fokusu = paket_u_prednjem_planu()
        arhiva_paket = izaberi_aplikaciju_za_poruke(paket_u_fokusu)
        if not arhiva_paket:
            return
        if paket_u_fokusu and arhiva_paket != paket_u_fokusu:
            raise RuntimeError(
                f"Izabrana aplikacija {arhiva_paket} nije trenutno u prvom "
                f"planu. Trenutno je otvorena {paket_u_fokusu}. "
                "Otvori željenu aplikaciju i pokušaj ponovo."
            )
        arhiva_dimenzije = dimenzije_ekrana()
        pocetna_slika = snimi_png()
        pocetna_slika = podesi_pocetni_prikaz(pocetna_slika, arhiva_paket)
        if pocetna_slika is None:
            return
        paket_u_fokusu = paket_u_prednjem_planu()
        if paket_u_fokusu and paket_u_fokusu != arhiva_paket:
            raise RuntimeError(
                "Izabrana aplikacija više nije u prvom planu. "
                "Otvori razgovor i pokušaj ponovo."
            )
        arhiva_potpis = potpis_sadrzaja_slika(pocetna_slika)
    except (RuntimeError, tk.TclError) as e:
        messagebox.showerror(
            "Ne mogu započeti snimanje", str(e), parent=app
        )
        return

    arhiva_broj = 0
    arhiva_stabilna = 0
    arhiva_aktivna = True
    postavi_fazu("arhiva_snimanje")
    status.set("Snimanje razgovora je počelo...")
    zabiljezi(f"Automatsko snimanje razgovora je počelo ({arhiva_paket}).")
    snimi_stranicu_razgovora(pocetna_slika)

def izaberi_folder():
    global folder
    novi = filedialog.askdirectory(initialdir=folder, parent=app)
    if novi:
        folder = Path(novi)
        status.set(f"Folder: {folder}")
        zabiljezi(f"Promijenjen folder za snimke: {folder}")

def uvezi_opencv():
    try:
        import cv2
    except ImportError:
        messagebox.showerror(
            "Nedostaje OpenCV",
            "Za korištenje USB kamere instaliraj zavisnosti komandom:\n"
            "pip install -r requirements.txt",
            parent=app
        )
        return None
    return cv2

def osvjezi_kamere():
    cv2 = uvezi_opencv()
    if cv2 is None:
        return

    dostupne = []
    for indeks in range(10):
        uredjaj = cv2.VideoCapture(indeks, cv2.CAP_DSHOW)
        try:
            if uredjaj.isOpened():
                dostupne.append(str(indeks))
        finally:
            uredjaj.release()

    kamera_izbor["values"] = dostupne
    if dostupne:
        if kamera_izbor_var.get() not in dostupne:
            kamera_izbor_var.set(dostupne[0])
        status.set(f"Pronađene kamere: {', '.join(dostupne)}")
        zabiljezi(f"Pronađene USB kamere na indeksima: {', '.join(dostupne)}")
    else:
        kamera_izbor_var.set("")
        status.set("Nije pronađena USB kamera")
        zabiljezi("Nije pronađena dostupna USB kamera.")

def pokreni_kameru():
    global kamera, kamera_prozor, kamera_slika_widget, kamera_zadnji_frame
    cv2 = uvezi_opencv()
    if cv2 is None:
        return
    indeks = kamera_izbor_var.get()
    if not indeks:
        messagebox.showwarning(
            "Nije izabrana kamera",
            "Osvježi listu i izaberi povezanu USB kameru.",
            parent=app
        )
        return

    kamera = cv2.VideoCapture(int(indeks), cv2.CAP_DSHOW)
    if not kamera.isOpened():
        kamera.release()
        kamera = None
        messagebox.showerror(
            "Kamera nije dostupna",
            f"Nije moguće otvoriti kameru {indeks}. Provjeri vezu i pokušaj "
            "osvježiti listu kamera.",
            parent=app
        )
        return

    uspjeh, kadar = kamera.read()
    if not uspjeh:
        kamera.release()
        kamera = None
        messagebox.showerror(
            "Greška kamere",
            "Kamera se otvorila, ali nije moguće pročitati sliku.",
            parent=app
        )
        return

    kamera_zadnji_frame = kadar
    kamera_prozor = tk.Toplevel(app)
    kamera_prozor.title(f"USB kamera {indeks} — pregled")
    kamera_slika_widget = tk.Label(
        kamera_prozor, text="Pokretanje pregleda...", bg="#202020", fg="white"
    )
    kamera_slika_widget.pack()
    kamera_prozor.protocol("WM_DELETE_WINDOW", zaustavi_kameru)
    postavi_fazu("kamera_prikaz")
    status.set(f"USB kamera {indeks} je aktivna")
    zabiljezi(f"Pokrenut pregled USB kamere {indeks}.")
    osvjezi_pregled_kamere()

def osvjezi_pregled_kamere():
    global kamera_photo, kamera_zadnji_frame
    if kamera is None or kamera_prozor is None or not kamera_prozor.winfo_exists():
        return
    cv2 = uvezi_opencv()
    if cv2 is None:
        zaustavi_kameru()
        return
    uspjeh, kadar = kamera.read()
    if not uspjeh:
        zaustavi_kameru()
        messagebox.showerror(
            "Greška kamere",
            "USB kamera je prekinula slanje slike.",
            parent=app
        )
        return

    kamera_zadnji_frame = kadar
    if kamera_writer is not None:
        kamera_writer.write(kadar)
    visina, sirina = kadar.shape[:2]
    faktor = min(1, 1280 / sirina, 720 / visina)
    prikazni_kadar = (
        cv2.resize(kadar, (round(sirina * faktor), round(visina * faktor)))
        if faktor < 1 else kadar
    )
    uspjeh, png = cv2.imencode(".png", prikazni_kadar)
    if not uspjeh:
        zaustavi_kameru()
        messagebox.showerror(
            "Greška kamere",
            "Nije moguće prikazati sliku sa USB kamere.",
            parent=app
        )
        return
    kamera_photo = tk.PhotoImage(
        data=base64.b64encode(png.tobytes()).decode("ascii")
    )
    kamera_slika_widget.config(image=kamera_photo, text="")
    kamera_prozor.after(30, osvjezi_pregled_kamere)

def kamera_screenshot(automatski=False):
    if kamera_zadnji_frame is None:
        return False
    cv2 = uvezi_opencv()
    if cv2 is None:
        return False
    putanja = naziv("png")
    try:
        if not cv2.imwrite(str(putanja), kamera_zadnji_frame):
            raise RuntimeError(f"Nije moguće sačuvati screenshot u {putanja}.")
    except (OSError, RuntimeError) as e:
        zabiljezi(f"Greška pri izradi screenshota USB kamere: {e}")
        if automatski:
            status.set("Automatski screenshot nije uspio; timer je zaustavljen")
            zaustavi_automatske_screenshotove()
        else:
            messagebox.showerror("Greška", str(e), parent=app)
        return False
    status.set(f"Sačuvano: {putanja.name}")
    evidentiraj_snimljenu_sliku()
    zabiljezi(f"Screenshot USB kamere sačuvan: {putanja}")
    return True

def postavke_kamere():
    if kamera is None:
        return
    cv2 = uvezi_opencv()
    if cv2 is None:
        return
    try:
        podrzano = kamera.set(cv2.CAP_PROP_SETTINGS, 0)
    except cv2.error as e:
        zabiljezi(f"Greška pri otvaranju postavki kamere: {e}")
        messagebox.showerror(
            "Postavke kamere",
            f"Nije moguće otvoriti postavke kamere:\n{e}",
            parent=app
        )
        return
    if not podrzano:
        status.set("Kamera ne podržava Windows postavke fokusa")
        messagebox.showinfo(
            "Postavke fokusa nisu dostupne",
            "Ova kamera ili njen drajver ne izlažu Windows postavke fokusa. "
            "Ako kamera podržava ručni fokus, provjeri njenu aplikaciju ili "
            "postavke proizvođača.",
            parent=app
        )
        zabiljezi("Kamera/drajver ne podržava OpenCV postavke uređaja.")
        return
    status.set("Zatvori prozor postavki kamere za nastavak")
    zabiljezi("Otvorene Windows postavke USB kamere.")

def kamera_video():
    global kamera_writer, kamera_video_putanja
    cv2 = uvezi_opencv()
    if cv2 is None:
        return
    if kamera_writer is not None:
        kamera_writer.release()
        kamera_writer = None
        putanja = kamera_video_putanja
        kamera_video_putanja = None
        postavi_fazu("kamera_prikaz")
        prijavi_zavrsetak_videa(putanja)
        return
    if kamera_zadnji_frame is None:
        return

    visina, sirina = kamera_zadnji_frame.shape[:2]
    fps = kamera.get(cv2.CAP_PROP_FPS)
    if not 1 <= fps <= 120:
        fps = 30.0
    putanja = naziv("mp4")
    writer = cv2.VideoWriter(
        str(putanja),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (sirina, visina)
    )
    if not writer.isOpened():
        writer.release()
        messagebox.showerror(
            "Greška snimanja",
            "Nije moguće pokrenuti MP4 snimanje. Provjeri podršku za MP4 "
            "kodek u instalaciji OpenCV-a.",
            parent=app
        )
        return
    kamera_writer = writer
    kamera_video_putanja = putanja
    postavi_fazu("kamera_snimanje")
    status.set(f"Snimanje USB kamere: {putanja.name}")
    zabiljezi(f"Pokrenuto MP4 snimanje USB kamere: {putanja}")

def zaustavi_kameru():
    global kamera, kamera_writer, kamera_prozor, kamera_slika_widget
    global kamera_photo, kamera_zadnji_frame, kamera_video_putanja
    zaustavi_automatske_screenshotove()
    putanja = kamera_video_putanja if kamera_writer is not None else None
    if kamera_writer is not None:
        kamera_writer.release()
        kamera_writer = None
    if kamera is not None:
        kamera.release()
        kamera = None
    if kamera_prozor is not None and kamera_prozor.winfo_exists():
        kamera_prozor.destroy()
    kamera_prozor = None
    kamera_slika_widget = None
    kamera_photo = None
    kamera_zadnji_frame = None
    kamera_video_putanja = None
    postavi_fazu("spremno")
    status.set("USB kamera je zaustavljena")
    zabiljezi("USB kamera je zaustavljena.")
    if putanja:
        prijavi_zavrsetak_videa(putanja)

def otvori_folder():
    os.startfile(folder)

def pronadji_whatsapp_exporte(dodatni_folder=None, sve=False):
    # Kad se export pošalje sebi, WhatsApp zip preimenuje u
    # "DOC-20261028-WA0001.zip", pa se zip prepoznaje po sadržaju:
    # unutra mora biti .txt sa "WhatsApp" u imenu (radi na svakom jeziku:
    # "WhatsApp Chat with...", "WhatsApp Chat mit...", "Chat de WhatsApp...").
    # sve=True prikazuje i ostale .zip/.txt fajlove.
    folderi = WHATSAPP_FOLDERI + ([dodatni_folder] if dodatni_folder else [])
    folderi = " ".join("'" + f.replace("'", "'\\''") + "'" for f in folderi)
    skripta = (
        f"SVE={1 if sve else 0}; "
        f"find {folderi} -type f \\( -iname '*.zip' -o -iname '*.txt' \\) "
        "2>/dev/null | while IFS= read -r f; do "
        "case \"$f\" in "
        "*.zip|*.ZIP) ime=$(unzip -l \"$f\" 2>/dev/null "
        "| sed -nE 's/^ *[0-9]+ +[0-9-]+ +[0-9:]+ +//p' "
        "| grep -i 'whatsapp.*\\.txt$' | head -n 1) ;; "
        "*) ime=$(echo \"${f##*/}\" | grep -i 'whatsapp') ;; "
        "esac; "
        "[ -z \"$ime\" ] && [ \"$SVE\" = 1 ] && ime=${f##*/}; "
        "[ -n \"$ime\" ] && echo \"$(stat -c '%Y|%s' \"$f\")|$f|${ime##*/}\"; "
        "done; true"
    )
    izlaz = adb_poziv(["shell", skripta], timeout=180)
    fajlovi = {}
    for red in izlaz.decode("utf-8", errors="replace").splitlines():
        dijelovi = red.strip().split("|")
        if len(dijelovi) < 4 or not (dijelovi[0].isdigit() and dijelovi[1].isdigit()):
            continue
        putanja = "|".join(dijelovi[2:-1])
        roditelj = putanja.rsplit("/", 2)[-2] if putanja.count("/") >= 1 else ""
        # Raspakovane kopije zip-a (folder "DOC-...-WA0001" ili "... (1)")
        # se preskaču; original je zip pored njih.
        if not putanja.lower().endswith(".zip") and re.fullmatch(
            r"DOC-\d{8}-WA\d+( \(\d+\))?", roditelj
        ):
            continue
        fajlovi[putanja] = (
            int(dijelovi[0]), int(dijelovi[1]), putanja, dijelovi[-1]
        )
    # Najnoviji prvi.
    return sorted(fajlovi.values(), reverse=True)

def lokalno_ime_exporta(putanja, ime_chata):
    # "DOC-...zip" s chatom "WhatsApp Chat with Ana.txt" →
    # "WhatsApp Chat with Ana.zip".
    if putanja.lower().endswith(".zip"):
        ime = ime_chata.rsplit(".", 1)[0] + ".zip"
    else:
        ime = putanja.rsplit("/", 1)[-1]
    return re.sub(r'[<>:"/\\|?*]', "_", ime)

def kopiraj_whatsapp_exporte(stavke, odrediste, rezultati):
    # Radi u posebnoj niti: ne dira Tk, samo puni listu rezultata.
    for putanja, ime in stavke:
        privremeni = odrediste / f".preuzimanje_{putanja.rsplit('/', 1)[-1]}"
        try:
            adb_poziv(["pull", "-a", putanja, str(privremeni)], timeout=1800)
            if privremeni.suffix.lower() == ".zip":
                # Ime chata iz zip-a čita Python: unzip na telefonu
                # zna pokvariti naša slova (č, ć, ž...).
                with zipfile.ZipFile(privremeni) as arhiva:
                    chat = next(
                        (n for n in arhiva.namelist()
                         if "whatsapp" in n.lower() and n.lower().endswith(".txt")),
                        None
                    )
                if chat:
                    ime = lokalno_ime_exporta(putanja, chat.rsplit("/", 1)[-1])
            cilj = odrediste / ime
            broj = 1
            while cilj.exists():
                cilj = odrediste / f"{Path(ime).stem}_{broj}{Path(ime).suffix}"
                broj += 1
            privremeni.rename(cilj)
            with cilj.open("rb") as fajl:
                sha = hashlib.sha256()
                for blok in iter(lambda: fajl.read(1024 * 1024), b""):
                    sha.update(blok)
            rezultati.append((putanja, cilj, sha.hexdigest(), None))
        except (RuntimeError, OSError, zipfile.BadZipFile) as e:
            privremeni.unlink(missing_ok=True)
            rezultati.append((putanja, None, None, str(e)))

def whatsapp_eksport():
    prozor = tk.Toplevel(app)
    prozor.title("WhatsApp eksport chata")
    prozor.configure(bg="#EAF2FB")
    prozor.resizable(False, False)
    prozor.transient(app)

    tk.Label(
        prozor,
        text="Eksport WhatsApp chata na računar",
        bg="#EAF2FB",
        fg="#174A7E",
        font=("Segoe UI", 11, "bold")
    ).pack(anchor="w", padx=16, pady=(14, 6))
    koraci = (
        "Na telefonu (WhatsApp na engleskom):\n\n"
        "1.  Otvori chat koji želiš sačuvati.\n"
        "2.  Gore desno klikni  ⋮  →  More  →  Export chat.\n"
        "3.  Izaberi  Without media  (samo tekst) ili\n"
        "      Include media  (sa slikama i glasovnim porukama).\n"
        "4.  U listi za dijeljenje izaberi  WhatsApp.\n"
        "5.  Za primaoca izaberi sebe  —  (You)  /  Message yourself\n"
        "      →  Send.\n"
        "      (Ako u listi imaš  Files:  Files  →  Download  →  Save.)\n"
        "6.  Ponovi za ostale chatove koje želiš.\n\n"
        "Kad završiš, telefon ostavi spojen i klikni\n"
        "„Uradio sam — pronađi fajlove”."
    )
    tk.Label(
        prozor,
        text=koraci,
        bg="#FFFFFF",
        fg="#243B53",
        justify="left",
        anchor="w",
        font=("Segoe UI", 10),
        padx=12,
        pady=10
    ).pack(fill="x", padx=16, pady=(0, 10))

    dodatni_folder = tk.StringVar()
    prikazi_sve = tk.BooleanVar(value=False)
    opcije = tk.LabelFrame(
        prozor,
        text=" Ako export nije pronađen (drugi telefon, drugi folder) ",
        bg="#EAF2FB",
        fg="#38536D",
        font=("Segoe UI", 9),
        padx=8,
        pady=6
    )
    opcije.pack(fill="x", padx=16, pady=(0, 8))
    red_foldera = tk.Frame(opcije, bg="#EAF2FB")
    red_foldera.pack(fill="x")
    tk.Label(
        red_foldera, text="Dodatni folder na telefonu:",
        bg="#EAF2FB", fg="#243B53", font=("Segoe UI", 9)
    ).pack(side="left")
    tk.Entry(
        red_foldera, textvariable=dodatni_folder,
        font=("Consolas", 9), relief="solid", bd=1
    ).pack(side="left", fill="x", expand=True, padx=(6, 0))
    tk.Label(
        opcije,
        text="npr. /sdcard/Download/WhatsApp  ·  /sdcard = cijeli telefon "
             "(sporije)  ·  prazno = standardne lokacije",
        bg="#EAF2FB", fg="#6B7C8F", font=("Segoe UI", 8)
    ).pack(anchor="w", pady=(2, 2))
    tk.Checkbutton(
        opcije,
        text="Prikaži sve .zip/.txt fajlove (ne samo WhatsApp exporte)",
        variable=prikazi_sve,
        bg="#EAF2FB", activebackground="#EAF2FB", font=("Segoe UI", 9)
    ).pack(anchor="w")

    info = tk.StringVar(value="Pronađeni fajlovi će se pojaviti ovdje.")
    tk.Label(
        prozor,
        textvariable=info,
        bg="#EAF2FB",
        fg="#38536D",
        wraplength=460,
        justify="left",
        font=("Segoe UI", 9)
    ).pack(anchor="w", padx=16, pady=(0, 4))

    lista_okvir = tk.Frame(prozor, bg="#FFFFFF")
    lista_okvir.pack(fill="both", expand=True, padx=16, pady=(0, 8))
    klizac = tk.Scrollbar(lista_okvir)
    klizac.pack(side="right", fill="y")
    lista = tk.Listbox(
        lista_okvir,
        height=7,
        width=70,
        selectmode="extended",
        bg="#FFFFFF",
        fg="#243B53",
        selectbackground="#1769D2",
        selectforeground="white",
        yscrollcommand=klizac.set,
        relief="flat",
        font=("Consolas", 9)
    )
    lista.pack(side="left", fill="both", expand=True)
    klizac.config(command=lista.yview)

    pronadjeni = []

    def pretrazi():
        dodatni = dodatni_folder.get().strip().rstrip("/")
        if dodatni and not dodatni.startswith("/"):
            messagebox.showwarning(
                "Neispravan folder",
                "Folder na telefonu mora počinjati sa /, npr. /sdcard/Download",
                parent=prozor
            )
            return
        if not proveri_telefon():
            return
        info.set("Tražim fajlove na telefonu...")
        prozor.update_idletasks()
        try:
            fajlovi = pronadji_whatsapp_exporte(dodatni or None, prikazi_sve.get())
        except RuntimeError as e:
            info.set("Pretraga nije uspjela.")
            messagebox.showerror("Greška", str(e), parent=prozor)
            return
        pronadjeni[:] = fajlovi
        lista.delete(0, "end")
        if not fajlovi:
            info.set(
                "Nije pronađen nijedan export. Provjeri da li je Send završen. "
                "Ako je export negdje drugdje, upiši folder iznad ili uključi "
                "„Prikaži sve .zip/.txt fajlove”."
            )
            kopiraj_dugme.config(state="disabled")
            return
        granica = datetime.now().timestamp() - 30 * 60
        for vrijeme, velicina, putanja, ime_chata in fajlovi:
            naziv_fajla = putanja.rsplit("/", 1)[-1]
            opis = ime_chata.rsplit(".", 1)[0]
            if naziv_fajla.lower().endswith(".zip"):
                opis += f"  (zip, {naziv_fajla})"
            else:
                opis += "  (txt)"
            lista.insert(
                "end",
                f"{datetime.fromtimestamp(vrijeme):%d.%m.%Y %H:%M}  "
                f"{velicina / 1024:>9.0f} KB  {opis}"
            )
        # Unaprijed označi exporte iz zadnjih 30 minuta (ili najnoviji).
        novi = [i for i, f in enumerate(fajlovi) if f[0] >= granica] or [0]
        for i in novi:
            lista.selection_set(i)
        info.set(
            f"Pronađeno fajlova: {len(fajlovi)}. Označeni su najnoviji; "
            "Ctrl/Shift + klik za drugačiji izbor."
        )
        kopiraj_dugme.config(state="normal")
        zabiljezi(f"WhatsApp eksport: pronađeno {len(fajlovi)} fajlova na telefonu.")

    def kopiraj():
        izbori = lista.curselection()
        if not izbori:
            messagebox.showwarning(
                "Ništa nije izabrano", "Izaberi bar jedan fajl.", parent=prozor
            )
            return
        odrediste = folder / "WHATSAPP_EXPORT"
        try:
            odrediste.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Greška", str(e), parent=prozor)
            return
        stavke = [
            (pronadjeni[i][2], lokalno_ime_exporta(pronadjeni[i][2], pronadjeni[i][3]))
            for i in izbori
        ]
        putanje = [putanja for putanja, _ime in stavke]
        rezultati = []
        nit = threading.Thread(
            target=kopiraj_whatsapp_exporte,
            args=(stavke, odrediste, rezultati),
            daemon=True
        )
        for dugme in (trazi_dugme, kopiraj_dugme):
            dugme.config(state="disabled")
        info.set(f"Kopiram {len(putanje)} fajl(ova) na računar...")
        nit.start()

        def provjeri_kraj():
            if nit.is_alive():
                info.set(
                    f"Kopiram... {len(rezultati)} od {len(putanje)} završeno"
                )
                app.after(300, provjeri_kraj)
                return
            uspjesni = [r for r in rezultati if r[3] is None]
            for putanja, cilj, sha, greska in rezultati:
                if greska:
                    zabiljezi(f"WhatsApp eksport — greška za {putanja}: {greska}")
                else:
                    zabiljezi(f"WhatsApp eksport kopiran: {cilj} (SHA-256 {sha})")
            if not prozor.winfo_exists():
                return
            for dugme in (trazi_dugme, kopiraj_dugme):
                dugme.config(state="normal")
            info.set(
                f"Kopirano {len(uspjesni)} od {len(putanje)} u {odrediste}"
            )
            status.set(f"WhatsApp eksport: kopirano {len(uspjesni)} fajl(ova)")
            greske = [r for r in rezultati if r[3]]
            poruka = f"Kopirano {len(uspjesni)} fajl(ova) u:\n{odrediste}"
            if greske:
                poruka += f"\n\nNije uspjelo: {len(greske)} (detalji u logu sesije)."
            if uspjesni and messagebox.askyesno(
                "Kopiranje završeno",
                poruka + "\n\nOtvoriti folder?",
                parent=prozor
            ):
                os.startfile(odrediste)
            elif not uspjesni:
                messagebox.showerror("Kopiranje nije uspjelo", poruka, parent=prozor)

        app.after(300, provjeri_kraj)

    dugmad_prozora = tk.Frame(prozor, bg="#EAF2FB")
    dugmad_prozora.pack(fill="x", padx=12, pady=(0, 12))
    trazi_dugme = tk.Button(
        dugmad_prozora,
        text="Uradio sam — pronađi fajlove",
        command=pretrazi,
        bg="#1769D2",
        fg="white",
        activebackground="#1456A0",
        activeforeground="white",
        relief="flat",
        padx=12,
        pady=7
    )
    trazi_dugme.pack(side="left", padx=4)
    kopiraj_dugme = tk.Button(
        dugmad_prozora,
        text="Kopiraj izabrane na računar",
        command=kopiraj,
        state="disabled",
        bg="#2E7D32",
        fg="white",
        activebackground="#1B5E20",
        activeforeground="white",
        relief="flat",
        padx=12,
        pady=7
    )
    kopiraj_dugme.pack(side="left", padx=4)
    tk.Button(
        dugmad_prozora,
        text="Zatvori",
        command=prozor.destroy,
        bg="#D8E8FA",
        fg="#174A7E",
        relief="flat",
        padx=12,
        pady=7
    ).pack(side="right", padx=4)

    prozor.bind("<Escape>", lambda _event: prozor.destroy())
    centriraj_prozor(prozor, app)

ROOT_KORACI = (
    "Identifikacija telefona",
    "Firmware",
    "Opcije za programere",
    "Otključavanje bootloadera",
    "Magisk patch",
    "Odin flash",
    "Provjera roota",
    "Rezime",
)

def root_eksport():
    prozor = tk.Toplevel(app)
    prozor.title("ROOT eksport — hodogram rootovanja")
    prozor.configure(bg="#EAF2FB")
    prozor.resizable(False, False)
    prozor.transient(app)

    tk.Label(
        prozor,
        text="ROOT eksport — hodogram rootovanja Samsung telefona",
        bg="#EAF2FB",
        fg="#174A7E",
        font=("Segoe UI", 11, "bold")
    ).pack(anchor="w", padx=16, pady=(14, 4))
    koraci_oznaka = tk.StringVar()
    tk.Label(
        prozor,
        textvariable=koraci_oznaka,
        bg="#EAF2FB",
        fg="#38536D",
        font=("Segoe UI", 9, "bold")
    ).pack(anchor="w", padx=16, pady=(0, 8))

    podaci = {
        "model": tk.StringVar(),
        "pda": tk.StringVar(),
        "csc": tk.StringVar(),
        "android": tk.StringVar(),
        "serijski": tk.StringVar(),
        "knox_pocetno": tk.StringVar(value="nepoznato"),
        "bootloader_pocetno": tk.StringVar(value="nepoznato"),
        "bootloader_sada": tk.StringVar(value="nije provjereno"),
        "oem_status": tk.StringVar(value="nije provjereno"),
        "ap_fajl": tk.StringVar(),
        "patch_fajl": tk.StringVar(),
        "firmware_preuzet": tk.BooleanVar(value=False),
        "dev_opcije": tk.BooleanVar(value=False),
        "bootloader_otkljucan": tk.BooleanVar(value=False),
        "magisk_patch": tk.BooleanVar(value=False),
        "odin_flash": tk.BooleanVar(value=False),
        "root_status": tk.StringVar(value="nije provjereno"),
    }

    sadrzaj = tk.Frame(prozor, bg="#FFFFFF")
    sadrzaj.pack(fill="both", expand=True, padx=16, pady=(0, 8))

    def naslov_koraka(roditelj, tekst):
        tk.Label(
            roditelj, text=tekst, bg="#FFFFFF", fg="#51677F",
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", pady=(0, 6))

    def uputstvo(roditelj, tekst):
        tk.Label(
            roditelj, text=tekst, bg="#FFFFFF", fg="#243B53",
            justify="left", anchor="w", wraplength=460, font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(0, 8))

    def red_polja(roditelj, oznaka, var, sirina=30):
        red = tk.Frame(roditelj, bg="#FFFFFF")
        red.pack(fill="x", pady=2)
        tk.Label(
            red, text=oznaka, bg="#FFFFFF", fg="#243B53", width=22,
            anchor="w", font=("Segoe UI", 9)
        ).pack(side="left")
        tk.Entry(
            red, textvariable=var, font=("Consolas", 9), relief="solid", bd=1,
            width=sirina
        ).pack(side="left", fill="x", expand=True)

    # --- Korak 1: identifikacija ---
    k1 = tk.Frame(sadrzaj, bg="#FFFFFF", padx=16, pady=14)
    naslov_koraka(k1, "1. KORAK  ·  IDENTIFIKACIJA TELEFONA")
    uputstvo(
        k1,
        "Klikni „Pročitaj sa telefona” da automatski popuniš podatke, ili "
        "ih upiši ručno iz Settings → About phone → Software information."
    )
    red_polja(k1, "Model:", podaci["model"])
    red_polja(k1, "Build number / PDA:", podaci["pda"])
    red_polja(k1, "CSC kod (regija):", podaci["csc"])
    red_polja(k1, "Android verzija:", podaci["android"])
    red_polja(k1, "Serijski broj:", podaci["serijski"])
    status_k1 = tk.StringVar(value="Knox / bootloader status: nepoznato")
    tk.Label(
        k1, textvariable=status_k1, bg="#FFFFFF", fg="#795800",
        font=("Segoe UI", 9), wraplength=460, justify="left"
    ).pack(anchor="w", pady=(8, 0))

    def ucitaj_identifikaciju():
        if not proveri_telefon():
            return
        podaci["model"].set(adb_getprop("ro.product.model") or podaci["model"].get())
        podaci["pda"].set(adb_getprop("ro.build.display.id") or podaci["pda"].get())
        podaci["csc"].set(adb_getprop("ro.csc.sales_code") or podaci["csc"].get())
        podaci["android"].set(
            adb_getprop("ro.build.version.release") or podaci["android"].get()
        )
        podaci["serijski"].set(adb_getprop("ro.serialno") or podaci["serijski"].get())
        knox = adb_getprop("ro.boot.warranty_bit")
        zakljucan = adb_getprop("ro.boot.flash.locked")
        podaci["knox_pocetno"].set(knox or "nepoznato")
        podaci["bootloader_pocetno"].set(zakljucan or "nepoznato")
        status_k1.set(
            "Knox warranty bit: " + (
                {"0": "0 (nije tripovan)", "1": "1 (već tripovan — "
                 "neki prethodni korak je već izveden)"}.get(knox, "nepoznato")
            ) + "\nBootloader: " + (
                {"0": "otključan", "1": "zaključan"}.get(zakljucan, "nepoznato")
            )
        )
        zabiljezi(
            f"ROOT eksport: pročitani podaci telefona "
            f"({podaci['model'].get()}, CSC {podaci['csc'].get()})."
        )

    tk.Button(
        k1, text="Pročitaj sa telefona", command=ucitaj_identifikaciju,
        bg="#1769D2", fg="white", relief="flat", padx=12, pady=6
    ).pack(anchor="w", pady=(10, 0))

    # --- Korak 2: firmware ---
    k2 = tk.Frame(sadrzaj, bg="#FFFFFF", padx=16, pady=14)
    naslov_koraka(k2, "2. KORAK  ·  FIRMWARE")
    uputstvo(
        k2,
        "Na sajtu za preuzimanje firmware-a unesi tačno ova dva podatka "
        "(iz 1. koraka):"
    )
    podaci_oznaka = tk.StringVar()
    tk.Label(
        k2, textvariable=podaci_oznaka, bg="#F4F8FC", fg="#174A7E",
        font=("Consolas", 10, "bold"), justify="left", anchor="w",
        padx=10, pady=8, relief="solid", bd=1
    ).pack(fill="x", pady=(0, 8))

    def osvjezi_podatke_oznaku():
        model = podaci["model"].get() or "(nije pročitano — vrati se na 1. korak)"
        csc = podaci["csc"].get() or "(nije pročitano — vrati se na 1. korak)"
        podaci_oznaka.set(f"Model:    {model}\nCSC kod:  {csc}")

    link_status = tk.StringVar()

    def otvori_samfw():
        model = podaci["model"].get().strip()
        csc = podaci["csc"].get().strip()
        if not model or not csc:
            messagebox.showwarning(
                "Nedostaju podaci",
                "Prvo se vrati na 1. korak i pročitaj podatke sa telefona "
                "(ili ih upiši ručno).",
                parent=prozor
            )
            return
        webbrowser.open(f"https://samfw.com/firmware/{model}/{csc}")
        link_status.set(
            "Otvoreno u pretraživaču. Napomena: link nije softverski "
            "provjeren (SamFw blokira automatske provjere) — ako stranica "
            "ne prikaže firmware, na sajtu ručno pretraži model i CSC kod "
            "iz polja iznad, ili koristi alat Frija."
        )

    tk.Button(
        k2, text="Otvori SamFw za ovaj model i CSC kod →",
        command=otvori_samfw,
        bg="#1769D2", fg="white", relief="flat", padx=12, pady=7
    ).pack(anchor="w", pady=(0, 6))
    tk.Label(
        k2, textvariable=link_status, bg="#FFFFFF", fg="#795800",
        wraplength=460, justify="left", font=("Segoe UI", 8)
    ).pack(anchor="w", pady=(0, 10))

    uputstvo(
        k2,
        "Paket sadrži AP, BL, CP i CSC/HOME_CSC fajlove — za patch treba "
        "samo AP."
    )
    red_polja(k2, "Naziv AP fajla:", podaci["ap_fajl"])
    tk.Checkbutton(
        k2, text="Preuzeo sam odgovarajući firmware",
        variable=podaci["firmware_preuzet"], bg="#FFFFFF", font=("Segoe UI", 9)
    ).pack(anchor="w", pady=(10, 0))

    # --- Korak 3: opcije za programere ---
    k3 = tk.Frame(sadrzaj, bg="#FFFFFF", padx=16, pady=14)
    naslov_koraka(k3, "3. KORAK  ·  OPCIJE ZA PROGRAMERE")
    uputstvo(
        k3,
        "Settings → About phone → Software information → tapni 7× na Build "
        "number. Zatim Settings → Developer options → uključi "
        "„OEM unlocking” i „USB debugging”."
    )
    oem_oznaka = tk.StringVar(value="OEM unlocking: nije provjereno")
    tk.Label(
        k3, textvariable=oem_oznaka, bg="#FFFFFF", fg="#795800",
        font=("Segoe UI", 9)
    ).pack(anchor="w", pady=(4, 0))

    def provjeri_oem():
        if not proveri_telefon():
            return
        vrijednost = adb_getprop("sys.oem_unlock_allowed")
        podaci["oem_status"].set(
            {"1": "uključeno", "0": "isključeno"}.get(vrijednost, "nepoznato")
        )
        oem_oznaka.set(f"OEM unlocking: {podaci['oem_status'].get()}")

    tk.Button(
        k3, text="Provjeri sa telefona", command=provjeri_oem,
        bg="#1769D2", fg="white", relief="flat", padx=12, pady=6
    ).pack(anchor="w", pady=(6, 0))
    tk.Checkbutton(
        k3, text="Uradio sam ovaj korak", variable=podaci["dev_opcije"],
        bg="#FFFFFF", font=("Segoe UI", 9)
    ).pack(anchor="w", pady=(10, 0))

    # --- Korak 4: otključavanje bootloadera ---
    k4 = tk.Frame(sadrzaj, bg="#FFFFFF", padx=16, pady=14)
    naslov_koraka(k4, "4. KORAK  ·  OTKLJUČAVANJE BOOTLOADERA (DOWNLOAD MODE)")
    uputstvo(
        k4,
        "Isključi telefon. Pritisni i zadrži Volume Up + Volume Down, pa "
        "prikopčaj USB. Volume Up za nastavak u Download Mode, pa ponovo "
        "Volume Up da potvrdiš otključavanje.\n\n"
        "⚠️ Ovo radi factory reset — briše internu memoriju. Knox "
        "warranty bit se trajno postavlja na 1 i to se ne vraća."
    )
    bootloader_oznaka = tk.StringVar(value="Bootloader sada: nije provjereno")
    tk.Label(
        k4, textvariable=bootloader_oznaka, bg="#FFFFFF", fg="#795800",
        font=("Segoe UI", 9), wraplength=460, justify="left"
    ).pack(anchor="w", pady=(4, 0))

    def provjeri_bootloader():
        if not proveri_telefon():
            return
        sada = adb_getprop("ro.boot.flash.locked")
        podaci["bootloader_sada"].set(sada or "nepoznato")
        opis = {"0": "otključan", "1": "zaključan"}.get(sada, "nepoznato")
        prije = podaci["bootloader_pocetno"].get()
        promjena = (
            "  (promijenjeno od 1. koraka)"
            if sada and prije not in ("nepoznato", sada) else ""
        )
        bootloader_oznaka.set(f"Bootloader sada: {opis}{promjena}")

    tk.Button(
        k4, text="Provjeri status sa telefona", command=provjeri_bootloader,
        bg="#1769D2", fg="white", relief="flat", padx=12, pady=6
    ).pack(anchor="w", pady=(6, 0))
    tk.Checkbutton(
        k4, text="Uradio sam ovaj korak", variable=podaci["bootloader_otkljucan"],
        bg="#FFFFFF", font=("Segoe UI", 9)
    ).pack(anchor="w", pady=(10, 0))

    # --- Korak 5: Magisk patch ---
    k5 = tk.Frame(sadrzaj, bg="#FFFFFF", padx=16, pady=14)
    naslov_koraka(k5, "5. KORAK  ·  MAGISK PATCH")
    uputstvo(
        k5,
        "Izaberi Magisk APK sa računara i prebaci ga na telefon, pa ga "
        "instaliraj kroz Files aplikaciju na telefonu. Zatim prebaci AP "
        "fajl na telefon (adb push ... /sdcard/Download/). U Magisk app: "
        "Install → Select and Patch a File → izaberi AP fajl."
    )

    magisk_status = tk.StringVar()
    magisk_status_boja = tk.StringVar(value="#174A7E")
    ap_status = tk.StringVar()
    ap_status_boja = tk.StringVar(value="#174A7E")

    def posalji_fajl_na_telefon(naslov_dijaloga, status_var, boja_var, poruka_uspjeh):
        putanja = filedialog.askopenfilename(
            title=naslov_dijaloga,
            filetypes=[("APK/TAR fajlovi", "*.apk;*.tar;*.tar.md5"), ("Svi fajlovi", "*.*")],
            parent=prozor
        )
        if not putanja:
            return
        naziv = Path(putanja).name
        boja_var.set("#174A7E")
        status_var.set(f"Prebacujem {naziv} na telefon...")
        prozor.update_idletasks()
        try:
            adb_poziv(["push", putanja, "/sdcard/Download/"], timeout=120)
            boja_var.set("#1E7B34")
            status_var.set(f"✓ Prebačeno: /sdcard/Download/{naziv}\n{poruka_uspjeh}")
        except RuntimeError as e:
            boja_var.set("#B3261E")
            status_var.set(f"✗ Greška kod prebacivanja: {e}")

    tk.Button(
        k5, text="Izaberi Magisk APK i pošalji na telefon →",
        command=lambda: posalji_fajl_na_telefon(
            "Izaberi Magisk APK", magisk_status, magisk_status_boja,
            "Otvori Files aplikaciju na telefonu → Download → tapni na fajl "
            "da ga instaliraš (dozvoli 'Install unknown apps' ako se to "
            "pojavi)."
        ),
        bg="#1769D2", fg="white", relief="flat", padx=12, pady=7
    ).pack(anchor="w", pady=(0, 6))
    oznaka_magisk = tk.Label(
        k5, textvariable=magisk_status, bg="#FFFFFF", fg=magisk_status_boja.get(),
        wraplength=460, justify="left", font=("Segoe UI", 8)
    )
    oznaka_magisk.pack(anchor="w", pady=(0, 10))
    magisk_status_boja.trace_add(
        "write", lambda *a: oznaka_magisk.config(fg=magisk_status_boja.get())
    )

    tk.Button(
        k5, text="Izaberi AP fajl i pošalji na telefon →",
        command=lambda: posalji_fajl_na_telefon(
            "Izaberi AP fajl (tar / tar.md5)", ap_status, ap_status_boja,
            "Sada u Magisk app: Install → Select and Patch a File → izaberi "
            "ovaj fajl u Download folderu."
        ),
        bg="#1769D2", fg="white", relief="flat", padx=12, pady=7
    ).pack(anchor="w", pady=(0, 6))
    oznaka_ap = tk.Label(
        k5, textvariable=ap_status, bg="#FFFFFF", fg=ap_status_boja.get(),
        wraplength=460, justify="left", font=("Segoe UI", 8)
    )
    oznaka_ap.pack(anchor="w", pady=(0, 10))
    ap_status_boja.trace_add(
        "write", lambda *a: oznaka_ap.config(fg=ap_status_boja.get())
    )

    red_polja(k5, "Naziv patchovanog fajla:", podaci["patch_fajl"])
    tk.Checkbutton(
        k5, text="Uradio sam ovaj korak", variable=podaci["magisk_patch"],
        bg="#FFFFFF", font=("Segoe UI", 9)
    ).pack(anchor="w", pady=(10, 0))

    # --- Korak 6: Odin flash ---
    k6 = tk.Frame(sadrzaj, bg="#FFFFFF", padx=16, pady=14)
    naslov_koraka(k6, "6. KORAK  ·  ODIN FLASH")
    uputstvo(
        k6,
        "Ponovo uđi u Download Mode. U Odinu klikni AP i izaberi "
        "patchovani fajl (BL/CP/CSC ostaju prazni). U Options neka budu "
        "uključeni samo Auto Reboot i F. Reset Time. Start → sačekaj PASS."
    )
    tk.Checkbutton(
        k6, text="Uradio sam ovaj korak", variable=podaci["odin_flash"],
        bg="#FFFFFF", font=("Segoe UI", 9)
    ).pack(anchor="w", pady=(10, 0))

    # --- Korak 7: provjera roota ---
    k7 = tk.Frame(sadrzaj, bg="#FFFFFF", padx=16, pady=14)
    naslov_koraka(k7, "7. KORAK  ·  PROVJERA ROOTA")
    uputstvo(
        k7,
        "Nakon restarta telefona klikni dugme ispod da provjerimo root "
        "preko ADB-a. Isto možeš provjeriti i u Magisk app."
    )
    root_oznaka = tk.StringVar(value="Status: nije provjereno")
    tk.Label(
        k7, textvariable=root_oznaka, bg="#FFFFFF", fg="#795800",
        font=("Segoe UI", 9, "bold")
    ).pack(anchor="w", pady=(4, 0))

    def provjeri_root():
        if not proveri_telefon():
            return
        try:
            izlaz = adb_poziv(["shell", "su", "-c", "id"], timeout=15).decode(
                errors="replace"
            )
        except RuntimeError as e:
            podaci["root_status"].set(f"neuspješno ({e})")
            root_oznaka.set(f"Status: {podaci['root_status'].get()}")
            return
        if "uid=0" in izlaz:
            podaci["root_status"].set("uspješno — telefon je rootovan")
        else:
            podaci["root_status"].set(f"neuspješno (odgovor: {izlaz.strip()})")
        root_oznaka.set(f"Status: {podaci['root_status'].get()}")
        zabiljezi(f"ROOT eksport: provjera roota — {podaci['root_status'].get()}")

    tk.Button(
        k7, text="Provjeri root sa telefona", command=provjeri_root,
        bg="#1769D2", fg="white", relief="flat", padx=12, pady=6
    ).pack(anchor="w", pady=(6, 0))

    # --- Korak 8: rezime ---
    k8 = tk.Frame(sadrzaj, bg="#FFFFFF", padx=16, pady=14)
    naslov_koraka(k8, "8. KORAK  ·  REZIME")
    uputstvo(k8, "Provjeri rezime i sačuvaj ga kao TXT fajl na računar.")
    rezime_tekst = tk.Text(
        k8, height=14, width=58, wrap="word", bg="#F4F8FC", fg="#243B53",
        font=("Consolas", 9), relief="solid", bd=1
    )
    rezime_tekst.pack(fill="both", expand=True, pady=(4, 8))

    def da_ne(vrijednost):
        return "DA" if vrijednost else "NE"

    def sastavi_rezime():
        redovi = [
            f"ROOT hodogram — {datetime.now():%d.%m.%Y %H:%M:%S}",
            "=" * 50,
            "",
            "1. IDENTIFIKACIJA TELEFONA",
            f"   Model: {podaci['model'].get() or '-'}",
            f"   Build number / PDA: {podaci['pda'].get() or '-'}",
            f"   CSC kod: {podaci['csc'].get() or '-'}",
            f"   Android verzija: {podaci['android'].get() or '-'}",
            f"   Serijski broj: {podaci['serijski'].get() or '-'}",
            f"   Knox warranty bit (prije): {podaci['knox_pocetno'].get()}",
            f"   Bootloader (prije): {podaci['bootloader_pocetno'].get()}",
            "",
            "2. FIRMWARE",
            f"   AP fajl: {podaci['ap_fajl'].get() or '-'}",
            f"   Preuzet firmware: {da_ne(podaci['firmware_preuzet'].get())}",
            "",
            "3. OPCIJE ZA PROGRAMERE",
            f"   OEM unlocking (zadnja provjera): {podaci['oem_status'].get()}",
            f"   Urađeno: {da_ne(podaci['dev_opcije'].get())}",
            "",
            "4. OTKLJUČAVANJE BOOTLOADERA",
            f"   Bootloader (zadnja provjera): {podaci['bootloader_sada'].get()}",
            f"   Urađeno: {da_ne(podaci['bootloader_otkljucan'].get())}",
            "",
            "5. MAGISK PATCH",
            f"   Patchovan fajl: {podaci['patch_fajl'].get() or '-'}",
            f"   Urađeno: {da_ne(podaci['magisk_patch'].get())}",
            "",
            "6. ODIN FLASH",
            f"   Urađeno: {da_ne(podaci['odin_flash'].get())}",
            "",
            "7. PROVJERA ROOTA",
            f"   Rezultat: {podaci['root_status'].get()}",
            "",
            "Napomena: Knox warranty bit, jednom postavljen na 1, ostaje "
            "trajan i ne vraća se flešovanjem stock firmware-a.",
        ]
        return "\n".join(redovi)

    def osvjezi_rezime():
        rezime_tekst.config(state="normal")
        rezime_tekst.delete("1.0", "end")
        rezime_tekst.insert("1.0", sastavi_rezime())
        rezime_tekst.config(state="disabled")

    def sacuvaj_rezime():
        odrediste = folder / "ROOT_LOG"
        try:
            odrediste.mkdir(parents=True, exist_ok=True)
            putanja = odrediste / f"{datetime.now():%Y%m%d_%H%M%S}_root_hodogram.txt"
            putanja.write_text(sastavi_rezime(), encoding="utf-8")
        except OSError as e:
            messagebox.showerror("Greška", str(e), parent=prozor)
            return
        zabiljezi(f"ROOT eksport: rezime sačuvan u {putanja}")
        status.set(f"ROOT hodogram sačuvan: {putanja.name}")
        if messagebox.askyesno(
            "Sačuvano", f"Rezime je sačuvan:\n{putanja}\n\nOtvoriti folder?",
            parent=prozor
        ):
            os.startfile(odrediste)

    red_rezime_dugmad = tk.Frame(k8, bg="#FFFFFF")
    red_rezime_dugmad.pack(fill="x")
    tk.Button(
        red_rezime_dugmad, text="Osvježi rezime", command=osvjezi_rezime,
        bg="#D8E8FA", fg="#174A7E", relief="flat", padx=12, pady=6
    ).pack(side="left", padx=(0, 6))
    tk.Button(
        red_rezime_dugmad, text="Sačuvaj kao TXT", command=sacuvaj_rezime,
        bg="#2E7D32", fg="white", relief="flat", padx=12, pady=6
    ).pack(side="left")

    koraci_frame = (k1, k2, k3, k4, k5, k6, k7, k8)
    indeks = {"trenutni": 0}

    def prikazi_korak(novi_indeks):
        koraci_frame[indeks["trenutni"]].pack_forget()
        indeks["trenutni"] = novi_indeks
        koraci_frame[novi_indeks].pack(fill="both", expand=True)
        koraci_oznaka.set(
            f"Korak {novi_indeks + 1} od {len(koraci_frame)}  ·  "
            f"{ROOT_KORACI[novi_indeks]}"
        )
        if novi_indeks == 1:
            osvjezi_podatke_oznaku()
        if novi_indeks == len(koraci_frame) - 1:
            osvjezi_rezime()
        nazad_dugme.config(state="normal" if novi_indeks > 0 else "disabled")
        dalje_dugme.config(
            state="normal" if novi_indeks < len(koraci_frame) - 1 else "disabled"
        )

    navigacija = tk.Frame(prozor, bg="#EAF2FB")
    navigacija.pack(fill="x", padx=16, pady=(0, 14))
    nazad_dugme = tk.Button(
        navigacija, text="← Nazad",
        command=lambda: prikazi_korak(indeks["trenutni"] - 1),
        bg="#D8E8FA", fg="#174A7E", relief="flat", padx=12, pady=7,
        state="disabled"
    )
    nazad_dugme.pack(side="left")
    tk.Button(
        navigacija, text="Zatvori", command=prozor.destroy,
        bg="#D8E8FA", fg="#174A7E", relief="flat", padx=12, pady=7
    ).pack(side="right")
    dalje_dugme = tk.Button(
        navigacija, text="Dalje →",
        command=lambda: prikazi_korak(indeks["trenutni"] + 1),
        bg="#1769D2", fg="white", relief="flat", padx=12, pady=7
    )
    dalje_dugme.pack(side="right", padx=(0, 6))

    prikazi_korak(0)
    prozor.bind("<Escape>", lambda _event: prozor.destroy())
    centriraj_prozor(prozor, app)

def ugasi_adb_server():
    try:
        subprocess.run(
            [str(ADB_EXE), "-P", str(ADB_SERVER_PORT), "kill-server"],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=5,
            creationflags=NO_WINDOW
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
    # Rezerva: ugasi preostale adb.exe procese iz foldera aplikacije
    # (platform-tools i scrcpy), ali ne i tuđe adb procese.
    folder_aplikacije = str(APP_DIR).replace("'", "''") + "\\"
    skripta = (
        "Get-CimInstance Win32_Process -Filter \"Name='adb.exe'\" | "
        "Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith("
        f"'{folder_aplikacije}', [StringComparison]::OrdinalIgnoreCase) }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
        "-ErrorAction SilentlyContinue }"
    )
    try:
        aktivni = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq adb.exe", "/NH"],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=5,
            creationflags=NO_WINDOW
        )
        if "adb.exe" in aktivni.stdout.lower():
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", skripta],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=15,
                creationflags=NO_WINDOW
            )
    except (OSError, subprocess.TimeoutExpired):
        pass

def zatvori_aplikaciju():
    global arhiva_aktivna, kamera, kamera_writer
    aktivno_snimanje = snimanje or kamera_writer is not None or arhiva_aktivna
    if aktivno_snimanje and not messagebox.askyesno(
        "Snimanje je aktivno",
        "Snimanje je u toku. Zaustaviti snimanje i zatvoriti aplikaciju?",
        parent=app
    ):
        return
    # Svaki korak je zaštićen da greška u jednom ne spriječi zatvaranje.
    koraci = [zaustavi_automatske_screenshotove]
    if adb_status_job is not None:
        koraci.append(lambda: app.after_cancel(adb_status_job))
    if info_telefona_job is not None:
        koraci.append(lambda: app.after_cancel(info_telefona_job))
    koraci.append(lambda: zaustavi_proces(tiho=True))
    if kamera_writer is not None:
        koraci.append(kamera_writer.release)
    if kamera is not None:
        koraci.append(kamera.release)
    koraci.append(ugasi_adb_server)
    arhiva_aktivna = False
    for korak in koraci:
        try:
            korak()
        except Exception as e:
            zabiljezi(f"Greška pri zatvaranju: {e}")
    kamera_writer = None
    kamera = None
    app.destroy()

def prijavi_gresku_callbacka(tip, vrijednost, _traceback):
    # U --windowed exe-u nema stderr-a, pa greške idu u log sesije.
    zabiljezi(f"Neočekivana greška: {tip.__name__}: {vrijednost}")

app = tk.Tk()
app.title("Screen Recorder")
app.geometry("506x620")
app.configure(bg="#EAF2FB")
app.protocol("WM_DELETE_WINDOW", zatvori_aplikaciju)
app.report_callback_exception = prijavi_gresku_callbacka

status = tk.StringVar(value="Izaberi izvor snimanja")
broj_slika_status = tk.StringVar(value="Snimljeno slika: 0")
adb_status = tk.StringVar()
info_telefona = tk.StringVar(value="Telefon: provjeravam konekciju...")
adb_verzija_localna = verzija_adb()
rucni_pomak_aktivan = tk.BooleanVar(value=False)
rucni_pomak = tk.StringVar(value="85")
kamera_izbor_var = tk.StringVar()
timer_interval_var = tk.StringVar(value="3")
timer_status = tk.StringVar(value="Automatski screenshotovi su isključeni")

header = tk.Frame(app, bg="#1557A0", padx=20, pady=16)
header.pack(fill="x")
icon = tk.Canvas(
    header, width=40, height=40,
    bg="#1557A0", highlightthickness=0
)
icon.create_rectangle(10, 2, 30, 38, outline="white", width=2)
icon.create_line(15, 7, 25, 7, fill="white", width=2)
icon.create_oval(18, 31, 22, 35, outline="white", width=1)
icon.pack(side="left", padx=(0, 12))

naslov = tk.Frame(header, bg="#1557A0")
naslov.pack(side="left")
tk.Label(
    naslov,
    text="Screen Recorder",
    bg="#1557A0",
    fg="white",
    font=("Segoe UI", 16, "bold")
).pack(anchor="w")
tk.Label(
    naslov,
    text="Android telefon ili USB kamera",
    bg="#1557A0",
    fg="#D8E8FA",
    font=("Segoe UI", 9)
).pack(anchor="w", pady=(2, 0))

sadrzaj = tk.Frame(app, bg="#FFFFFF", padx=20, pady=14)
sadrzaj.pack(fill="both", expand=True, padx=16, pady=14)

izbor_rezima = tk.Frame(sadrzaj, bg="#FFFFFF")
izbor_rezima.pack(fill="both", expand=True)
tk.Label(
    izbor_rezima, textvariable=info_telefona, bg="#F4F8FC", fg="#174A7E",
    font=("Consolas", 9, "bold"), justify="left", anchor="w",
    padx=10, pady=6, relief="solid", bd=1
).pack(fill="x", pady=(0, 10))
tk.Label(
    izbor_rezima,
    text="IZABERI IZVOR SNIMANJA",
    bg="#FFFFFF",
    fg="#51677F",
    font=("Segoe UI", 10, "bold")
).pack(anchor="w", pady=(4, 12))
tk.Button(
    izbor_rezima,
    text="ANDROID TELEFON  ·  SCRCPY",
    command=lambda: prikazi_rezim("android"),
    height=3
).pack(fill="x", pady=5)
tk.Button(
    izbor_rezima,
    text="USB EKSTERNA KAMERA",
    command=lambda: prikazi_rezim("kamera"),
    height=3
).pack(fill="x", pady=5)
tk.Button(
    izbor_rezima,
    text="IZVLAČENJE PODATAKA IZ TELEFONA  ·  ADB",
    command=lambda: pokreni_ekstrakciju(),
    height=3
).pack(fill="x", pady=5)
tk.Button(
    izbor_rezima,
    text="WHATSAPP EKSPORT CHATA",
    command=whatsapp_eksport,
    height=3
).pack(fill="x", pady=5)
tk.Button(
    izbor_rezima,
    text="ROOT EKSPORT  ·  HODOGRAM ROOTOVANJA",
    command=root_eksport,
    height=3
).pack(fill="x", pady=5)

android_panel = tk.Frame(sadrzaj, bg="#FFFFFF")
kamera_panel = tk.Frame(sadrzaj, bg="#FFFFFF")

tk.Button(
    android_panel, text="← Promijeni izvor",
    command=lambda: prikazi_izbor_rezima(),
    bg="#E8F1FC", fg="#1456A0", relief="flat", bd=0, pady=6
).pack(fill="x", pady=(0, 8))
tk.Label(
    android_panel,
    text="1. KORAK  ·  POKRETANJE",
    bg="#FFFFFF",
    fg="#51677F",
    font=("Segoe UI", 9, "bold")
).pack(anchor="w", pady=(0, 6))
dugmad["pokreni"] = tk.Button(
    android_panel, text="POKRENI SCRCPY", command=pokreni, height=2
)
dugmad["pokreni"].pack(fill="x", pady=(0, 12))
tk.Label(
    android_panel,
    text="2. KORAK  ·  IZABERI ŠTA ŽELIŠ SNIMITI",
    bg="#FFFFFF",
    fg="#51677F",
    font=("Segoe UI", 9, "bold")
).pack(anchor="w", pady=(0, 6))
dugmad["screenshot"] = tk.Button(
    android_panel, text="Napravi screenshot", command=screenshot, height=2
)
dugmad["screenshot"].pack(fill="x", pady=3)
dugmad["razgovor"] = tk.Button(
    android_panel,
    text="Snimi razgovor (screenshotovi sa preklapanjem)",
    command=snimi_razgovor,
    height=2
)
dugmad["razgovor"].pack(fill="x", pady=3)
pomak_okvir = tk.Frame(android_panel, bg="#FFFFFF")
pomak_okvir.pack(fill="x", pady=(0, 3))
tk.Checkbutton(
    pomak_okvir, text="Ručni pomak pri snimanju razgovora:",
    variable=rucni_pomak_aktivan, bg="#FFFFFF", font=("Segoe UI", 9)
).pack(side="left")
tk.Spinbox(
    pomak_okvir, from_=10, to=100, increment=5, width=4,
    textvariable=rucni_pomak
).pack(side="left", padx=4)
tk.Label(
    pomak_okvir, text="% visine", bg="#FFFFFF", font=("Segoe UI", 9)
).pack(side="left")
dugmad["video"] = tk.Button(
    android_panel, text="Pokreni MP4 snimanje", command=video, height=2
)
dugmad["video"].pack(fill="x", pady=3)
dugmad["zaustavi"] = tk.Button(
    android_panel, text="ZAUSTAVI SCRCPY", command=zaustavi, height=2
)
dugmad["zaustavi"].pack(fill="x", pady=(8, 5))

tk.Button(
    kamera_panel, text="← Promijeni izvor",
    command=lambda: prikazi_izbor_rezima(),
    bg="#E8F1FC", fg="#1456A0", relief="flat", bd=0, pady=6
).pack(fill="x", pady=(0, 12))
tk.Label(
    kamera_panel,
    text="USB KAMERA",
    bg="#FFFFFF",
    fg="#51677F",
    font=("Segoe UI", 9, "bold")
).pack(anchor="w", pady=(0, 6))
kamera_red = tk.Frame(kamera_panel, bg="#FFFFFF")
kamera_red.pack(fill="x", pady=(0, 8))
tk.Label(
    kamera_red, text="Kamera indeks:", bg="#FFFFFF", fg="#243B53"
).pack(side="left")
kamera_izbor = ttk.Combobox(
    kamera_red, textvariable=kamera_izbor_var, state="readonly", width=12
)
kamera_izbor.pack(side="left", padx=6)
tk.Button(
    kamera_red, text="Osvježi", command=osvjezi_kamere,
    bg="#E8F1FC", fg="#1456A0", relief="flat", bd=0, padx=10, pady=4
).pack(side="left")
dugmad["kamera_pokreni"] = tk.Button(
    kamera_panel, text="POKRENI PREGLED KAMERE",
    command=pokreni_kameru, height=2
)
dugmad["kamera_pokreni"].pack(fill="x", pady=4)
dugmad["kamera_screenshot"] = tk.Button(
    kamera_panel, text="Napravi screenshot",
    command=kamera_screenshot, height=2
)
dugmad["kamera_screenshot"].pack(fill="x", pady=4)
dugmad["kamera_postavke"] = tk.Button(
    kamera_panel, text="Postavke kamere / fokus",
    command=postavke_kamere, height=2
)
dugmad["kamera_postavke"].pack(fill="x", pady=4)
dugmad["kamera_video"] = tk.Button(
    kamera_panel, text="Pokreni MP4 snimanje",
    command=kamera_video, height=2
)
dugmad["kamera_video"].pack(fill="x", pady=4)
dugmad["kamera_zaustavi"] = tk.Button(
    kamera_panel, text="ZAUSTAVI KAMERU",
    command=zaustavi_kameru, height=2
)
dugmad["kamera_zaustavi"].pack(fill="x", pady=(8, 5))
tk.Label(
    kamera_panel,
    text="Pregled kamere otvara se u posebnom prozoru.",
    bg="#FFFFFF",
    fg="#51677F",
    font=("Segoe UI", 9)
).pack(anchor="w", pady=(4, 0))

zajednicke_opcije = tk.Frame(sadrzaj, bg="#FFFFFF")
timer_okvir = tk.Frame(zajednicke_opcije, bg="#FFFFFF")
timer_okvir.pack(fill="x", pady=(4, 0))
tk.Label(
    timer_okvir, text="Screenshot svakih:", bg="#FFFFFF", fg="#243B53"
).pack(side="left")
tk.Spinbox(
    timer_okvir, from_=1, to=3600, increment=1, width=5,
    textvariable=timer_interval_var
).pack(side="left", padx=(6, 4))
tk.Label(
    timer_okvir, text="sekundi", bg="#FFFFFF", fg="#243B53"
).pack(side="left")
dugmad["automatski_screenshot"] = tk.Button(
    zajednicke_opcije,
    text="Pokreni automatske screenshotove",
    command=ukljuci_automatske_screenshotove,
    height=2
)
dugmad["automatski_screenshot"].pack(fill="x", pady=(5, 0))
tk.Label(
    zajednicke_opcije,
    textvariable=timer_status,
    bg="#FFFFFF",
    fg="#174A7E",
    font=("Segoe UI", 9, "bold")
).pack(anchor="w", pady=(3, 0))

folder_dugmad = tk.Frame(zajednicke_opcije, bg="#FFFFFF")
folder_dugmad.pack(fill="x", pady=(10, 0))
for tekst, komanda in (
    ("Izaberi folder", izaberi_folder),
    ("Otvori folder sa snimcima", otvori_folder),
):
    tk.Button(
        folder_dugmad,
        text=tekst,
        command=komanda,
        bg="#E8F1FC",
        fg="#1456A0",
        activebackground="#D6E7FA",
        activeforeground="#10477F",
        relief="flat",
        bd=0,
        cursor="hand2",
        font=("Segoe UI", 9, "bold"),
        padx=10,
        pady=7
    ).pack(side="left", expand=True, fill="x", padx=3)
tk.Button(
    zajednicke_opcije,
    text="Prikaži privremeni log sesije",
    command=prikazi_log,
    bg="#D8E8FA",
    fg="#174A7E",
    activebackground="#C6DDF5",
    activeforeground="#123F6B",
    relief="flat",
    bd=0,
    cursor="hand2",
    font=("Segoe UI", 9, "bold"),
    pady=7
).pack(fill="x", padx=3, pady=(7, 0))

statusna_traka = tk.Frame(app, bg="#D8E8FA", padx=14, pady=8)
statusna_traka.pack(fill="x", side="bottom")
tk.Label(
    statusna_traka,
    textvariable=status,
    wraplength=470,
    bg="#D8E8FA",
    fg="#174A7E",
    font=("Segoe UI", 9)
).pack(anchor="w")
tk.Label(
    statusna_traka,
    textvariable=broj_slika_status,
    bg="#D8E8FA",
    fg="#174A7E",
    font=("Segoe UI", 9, "bold")
).pack(anchor="e")
tk.Label(
    statusna_traka,
    textvariable=adb_status,
    bg="#D8E8FA",
    fg="#174A7E",
    font=("Segoe UI", 8)
).pack(anchor="w")

def pokreni_ekstrakciju():
    if getattr(sys, "frozen", False):
        skripta = APP_DIR / "izvuci_telefon.exe"
        komanda = [str(skripta)]
    else:
        skripta = APP_DIR / "izvuci_telefon.py"
        komanda = [sys.executable, str(skripta)]
    if not skripta.exists():
        messagebox.showerror("Greška", f"Nije pronađena skripta:\n{skripta}")
        return
    if not messagebox.askyesno(
        "Izvlačenje podataka",
        "Kopirat će se javna memorija telefona (/sdcard) u folder:\n"
        f"{folder / 'EKSTRAKCIJE'}\n\n"
        "Telefon mora biti spojen i otključan. Nastaviti?"
    ):
        return
    okolina = os.environ.copy()
    okolina["IZVUCI_PAUZA"] = "1"
    subprocess.Popen(
        komanda + ["--izlaz", str(folder / "EKSTRAKCIJE")],
        cwd=str(APP_DIR),
        env=okolina,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )


def prikazi_rezim(novi_rezim):
    global rezim
    rezim = novi_rezim
    izbor_rezima.pack_forget()
    if rezim == "android":
        kamera_panel.pack_forget()
        android_panel.pack(fill="both", expand=True)
        status.set("Izabran Android / scrcpy režim")
    else:
        android_panel.pack_forget()
        kamera_panel.pack(fill="both", expand=True)
        status.set("Izabran režim USB kamere")
        osvjezi_kamere()
    zajednicke_opcije.pack(fill="x")
    osvjezi_dugmad()

def prikazi_izbor_rezima():
    if faza != "spremno":
        messagebox.showwarning(
            "Snimanje je aktivno",
            "Zaustavi trenutno snimanje prije promjene režima.",
            parent=app
        )
        return
    android_panel.pack_forget()
    kamera_panel.pack_forget()
    zajednicke_opcije.pack_forget()
    izbor_rezima.pack(fill="both", expand=True)
    status.set("Izaberi izvor snimanja")

osvjezi_dugmad()
app.update_idletasks()
visina_za_rezim = max(
    android_panel.winfo_reqheight(),
    kamera_panel.winfo_reqheight()
)
visina_minimalna = max(
    620,
    app.winfo_reqheight()
    - izbor_rezima.winfo_reqheight()
    + visina_za_rezim
    + zajednicke_opcije.winfo_reqheight()
    + 16
)
app.geometry(f"506x{visina_minimalna}")
app.minsize(506, visina_minimalna)
pozicioniraj_glavni_prozor_desno()
zabiljezi("Aplikacija je pokrenuta. Log se čuva samo dok je aplikacija otvorena.")
osvjezi_adb_status()
osvjezi_info_telefona()
app.mainloop()
