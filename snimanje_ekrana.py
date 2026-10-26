
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime
import base64
import re
import subprocess
import os
import signal

folder = Path("D:/PROGRAMI/SNIMANJE_ANDROID/SNIMCI")
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
boje_dugmadi = {
    "pokreni": ("#1769D2", "white"),
    "video": ("#D9485F", "white"),
    "screenshot": ("#E8F1FC", "#1456A0"),
    "razgovor": ("#6B4CCB", "white"),
    "zaustavi": ("#C62828", "white"),
}

def zabiljezi(poruka):
    zapis = f"{datetime.now().strftime('%H:%M:%S')}  {poruka}"
    zapisi_sesije.append(zapis)
    if prozor_loga and prozor_loga.winfo_exists():
        tekst_loga.config(state="normal")
        tekst_loga.insert("end", zapis + "\n")
        tekst_loga.see("end")
        tekst_loga.config(state="disabled")

def evidentiraj_snimljenu_sliku():
    global broj_snimljenih_slika
    broj_snimljenih_slika += 1
    broj_slika_status.set(f"Snimljeno slika: {broj_snimljenih_slika}")

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
    dugmad["pokreni"].config(
        state="normal" if faza == "spremno" else "disabled"
    )
    dugmad["video"].config(
        state="normal" if faza == "prikaz" else "disabled"
    )
    dugmad["screenshot"].config(
        state="normal" if faza == "prikaz" else "disabled"
    )
    dugmad["razgovor"].config(
        state="normal" if faza in ("prikaz", "arhiva_pocetak", "arhiva_snimanje")
        else "disabled",
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
    for ime, dugme in dugmad.items():
        stil_dugmeta(dugme, *boje_dugmadi[ime])

def postavi_fazu(nova_faza):
    global faza
    faza = nova_faza
    osvjezi_dugmad()

def potvrdi_pokretanje(novi_proces, pokrenuto_snimanje, putanja=None):
    global proces, snimanje, putanja_snimanja
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
    if pokrenuto_snimanje:
        prijavi_zavrsetak_videa(putanja)
    else:
        status.set("scrcpy je zatvoren")
        zabiljezi("scrcpy sesija je zatvorena.")

def pokreni_scrcpy(komanda, pokrenuto_snimanje=False, putanja=None):
    global proces, putanja_snimanja
    visina_ekrana = app.winfo_screenheight()
    visina_prozora = round(visina_ekrana * 0.85)
    komanda = [
        *komanda,
        "--window-x=0",
        f"--window-y={(visina_ekrana - visina_prozora) // 2}",
        f"--window-height={visina_prozora}",
    ]
    try:
        proces = subprocess.Popen(
            komanda,
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
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=10
        )
    except FileNotFoundError:
        status.set("ADB nije pronađen")
        zabiljezi("Greška: ADB nije pronađen.")
        messagebox.showerror(
            "Greška",
            "ADB nije pronađen. Provjeri instalaciju Android platform-tools.",
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

def zaustavi_proces():
    if proces and proces.poll() is None:
        try:
            proces.send_signal(signal.CTRL_BREAK_EVENT)
            proces.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired) as e:
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
    if bilo_snimanje and putanja_videa:
        prijavi_zavrsetak_videa(putanja_videa)
    else:
        status.set("scrcpy zaustavljen")
    postavi_fazu("spremno")

def screenshot():
    if faza != "prikaz":
        return
    if not proveri_telefon():
        return
    putanja = naziv("png")
    try:
        with open(putanja, "wb") as fajl:
            rezultat = subprocess.run(
                ["adb", "exec-out", "screencap", "-p"],
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
    except Exception as e:
        zabiljezi(f"Greška pri izradi screenshota: {e}")
        messagebox.showerror("Greška", str(e), parent=app)

def adb_poziv(argumenti, timeout=20):
    try:
        rezultat = subprocess.run(
            ["adb", *argumenti],
            capture_output=True,
            timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"ADB naredba nije uspjela: {e}") from e
    if rezultat.returncode != 0:
        greska = rezultat.stderr.decode(errors="replace").strip()
        raise RuntimeError(greska or "ADB naredba nije uspjela.")
    return rezultat.stdout

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
        udio = 0.60
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
         str(sredina), str(y_kraj), "1200"],
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

def otvori_folder():
    os.startfile(folder)

app = tk.Tk()
app.title("Android Screen Recorder")
app.geometry("460x620")
app.configure(bg="#EAF2FB")
app.update_idletasks()
pozicioniraj_glavni_prozor_desno()

status = tk.StringVar(value="Spremno")
broj_slika_status = tk.StringVar(value="Snimljeno slika: 0")
rucni_pomak_aktivan = tk.BooleanVar(value=False)
rucni_pomak = tk.StringVar(value="85")

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
    text="Android Screen Recorder",
    bg="#1557A0",
    fg="white",
    font=("Segoe UI", 16, "bold")
).pack(anchor="w")
tk.Label(
    naslov,
    text="Upravljanje prikazom i snimanjem telefona",
    bg="#1557A0",
    fg="#D8E8FA",
    font=("Segoe UI", 9)
).pack(anchor="w", pady=(2, 0))

sadrzaj = tk.Frame(app, bg="#FFFFFF", padx=20, pady=14)
sadrzaj.pack(fill="both", expand=True, padx=16, pady=14)

tk.Label(
    sadrzaj,
    text="1. KORAK  ·  POKRETANJE",
    bg="#FFFFFF",
    fg="#51677F",
    font=("Segoe UI", 9, "bold")
).pack(anchor="w", pady=(0, 6))
dugmad["pokreni"] = tk.Button(
    sadrzaj, text="POKRENI SCRCPY", command=pokreni, height=2
)
dugmad["pokreni"].pack(fill="x", pady=(0, 12))

tk.Label(
    sadrzaj,
    text="2. KORAK  ·  IZABERI ŠTA ŽELIŠ SNIMITI",
    bg="#FFFFFF",
    fg="#51677F",
    font=("Segoe UI", 9, "bold")
).pack(anchor="w", pady=(0, 6))
dugmad["screenshot"] = tk.Button(
    sadrzaj, text="Napravi screenshot", command=screenshot, height=2
)
dugmad["screenshot"].pack(fill="x", pady=3)
dugmad["razgovor"] = tk.Button(
    sadrzaj,
    text="Snimi razgovor (screenshotovi sa preklapanjem)",
    command=snimi_razgovor,
    height=2
)
dugmad["razgovor"].pack(fill="x", pady=3)
pomak_okvir = tk.Frame(sadrzaj, bg="#FFFFFF")
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
    sadrzaj, text="Pokreni MP4 snimanje", command=video, height=2
)
dugmad["video"].pack(fill="x", pady=3)
dugmad["zaustavi"] = tk.Button(
    sadrzaj, text="ZAUSTAVI SCRCPY", command=zaustavi, height=2
)
dugmad["zaustavi"].pack(fill="x", pady=(8, 5))

folder_dugmad = tk.Frame(sadrzaj, bg="#FFFFFF")
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
    sadrzaj,
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
    wraplength=420,
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

osvjezi_dugmad()
pozicioniraj_glavni_prozor_desno()

zabiljezi("Aplikacija je pokrenuta. Log se čuva samo dok je aplikacija otvorena.")

app.mainloop()


