# Rootovanje Samsung telefona (Exynos, npr. SM-A750FN/DS)

Ovi koraci su namijenjeni za učenje na sopstvenom, po mogućnosti žrtvenom
telefonu. Rootovanje je ireverzibilno u jednom bitnom segmentu — pročitaj
upozorenja prije početka.

## ⚠️ Prije početka

- **Knox Warranty Void brojač se trajno postavlja na `0x1`** čim se otključa
  bootloader ili flešuje bilo šta nepotpisano od Samsunga (custom recovery,
  Magisk-patchovan AP fajl...). Ovo se **ne može vratiti** nikakvim
  softverskim korakom, ni flešovanjem originalnog firmware-a. Trajna
  posledica: Samsung Pay i Secure Folder ostaju zauvijek blokirani, a
  hardverska garancija je formalno poništena.
- **Otključavanje bootloadera radi factory reset** — briše sve podatke sa
  interne memorije (aplikacije, fotografije, naloge). Podaci na microSD
  kartici obično ostaju netaknuti.
- Prije otključavanja izvuci sve što ti treba, npr. preko
  `izvuci_telefon.py` iz ovog projekta ili ručnim `adb pull /sdcard ...`.
- Koristi **tačno odgovarajući firmware** za svoj model i regiju (CSC kod).
  Pogrešan firmware može trajno onesposobiti telefon (brick).

## 0. Priprema — zapiši podatke o telefonu

**Settings → About phone → Software information**:
- Build number / PDA verzija (npr. `A750FNXXU...`)
- CSC kod (regija) — vidi se i unosom `*#1234#` u Telefon aplikaciji

## 1. Uključi opcije za programere

1. **Settings → About phone → Software information**
2. Tapni 7 puta na **Build number** — pojavi se "Developer mode enabled"
3. **Settings → Developer options**:
   - Uključi **OEM unlocking**
   - Uključi **USB debugging**

## 2. Skini odgovarajući firmware

Preko alata kao **Frija** ili sajtova **SamFw** / **SamMobile**, unesi model
(npr. `SM-A750FN`) i CSC kod iz koraka 0. Preuzet paket sadrži:
- `AP_...tar.md5` — ovaj fajl se patchuje sa Magiskom
- `BL_...`, `CP_...`, `CSC_...` ili `HOME_CSC_...` — ostaju originalni

## 3. Otključaj bootloader (Download Mode)

Kombinacija za telefone bez fizičkog Home dugmeta (npr. A7 2018):

1. Isključi telefon potpuno.
2. Pritisni i zadrži istovremeno **Volume Up + Volume Down**.
3. Dok ih držiš, prikopčaj USB kabl na računar.
4. Pojavi se upozorenje — pritisni **Volume Up** da nastaviš u Download Mode.
5. Na ekranu Download Mode-a, pritisni **Volume Up** ponovo da **potvrdiš
   otključavanje bootloadera** (ovo radi factory reset).
6. Telefon se restartuje i provodi kroz podešavanje. Ponovo uključi
   Developer options → USB debugging (OEM unlocking ostaje otključan).

## 4. Instaliraj Magisk i patchuj AP fajl

1. Skini **Magisk APK** sa zvaničnog GitHub repoa `topjohnwu/Magisk` i
   instaliraj ga na telefon (dozvoli instalaciju iz nepoznatih izvora).
2. Prebaci `AP_...tar.md5` na telefon:
   ```
   platform-tools\adb.exe push AP_A750FN...tar.md5 /sdcard/Download/
   ```
3. U Magisk app: **Install → Select and Patch a File** → izaberi taj fajl.
4. Magisk pravi novi fajl, npr. `/sdcard/Download/magisk_patched_xxxxx.tar`.

## 5. Flešuj patchovani fajl preko Odina

1. Na računaru pokreni **Odin3** (verzija 3.14 ili novija).
2. Prebaci patchovani fajl sa telefona na računar:
   ```
   platform-tools\adb.exe pull /sdcard/Download/magisk_patched_xxxxx.tar C:\Odin\
   ```
3. Ponovo uđi u Download Mode (korak 3, tačke 1–4; bootloader je već
   otključan, ne ponavljaj potvrdu otključavanja).
4. U Odinu klikni dugme **AP** i izaberi `magisk_patched_xxxxx.tar`.
   **Ne diraj** BL, CP, CSC dugmad — ostaju prazna.
5. U tabu **Options** provjeri da su uključeni samo **Auto Reboot** i
   **F. Reset Time**.
6. Klikni **Start** i sačekaj zeleni **PASS**. Telefon se sam restartuje.

## 6. Provjeri root

Otvori **Magisk** app na telefonu — treba da pokaže da je instaliran i
aktivan. Potvrda preko ADB-a:
```
platform-tools\adb.exe shell su -c "id"
```
Ako vrati `uid=0(root)`, root je uspješan.

## Ako nešto krene po zlu

Download Mode je skoro uvijek dostupan. Tu možeš ponovo flešovati
kompletan originalni firmware (BL + AP + CP + HOME_CSC) preko Odina da
vratiš telefon u radno stanje, bez roota.

## Povratak na stock firmware (uklanjanje roota)

1. Uđi u Download Mode.
2. U Odinu učitaj originalni (nepatchovan) **AP**, plus **BL**, **CP** i
   **CSC** (ili **HOME_CSC** ako želiš sačuvati podatke).
3. Start → PASS.

Telefon radi softverski potpuno kao stock — bez Magiska, bez `su`. Knox
brojač ostaje trajno na `0x1` (vidljivo u Download Mode ekranu kao
`KNOX WARRANTY VOID: 0x1`) bez obzira na ovaj korak — to se ne vraća.

## Šta root otključava (za ovaj projekat)

| Šta | Putanja | Napomena |
|---|---|---|
| WhatsApp — živa baza | `/data/data/com.whatsapp/databases/msgstore.db` | Obična SQLite baza, čitljiva direktno, bez ključa |
| Viber — baza poruka | `/data/data/com.viber.voip/databases/viber_messages.db` | Provjeri sa `sqlite3 ... ".tables"` — nije potvrđeno da li je dodatno šifrovana |
| Kontakti / SMS / pozivi | `/data/data/com.android.providers.*/databases/` | Potpunije nego `content query` koji koristi `izvuci_telefon.py` |
| Keš, cookies, tokeni drugih aplikacija | `/data/data/<paket>/` | Npr. Chrome `Login Data` SQLite baza |

Neke aplikacije (npr. Signal) šifruju svoju bazu ključem iz Android
Keystore-a, hardverski zaštićenim — tu root ne pomaže, jer ključ ne
napušta čip.
