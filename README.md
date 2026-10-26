# SNIMANJE_ANDROID

Python aplikacija za snimanje Android ekrana putem scrcpy ili USB kamere.

Android alatke se učitavaju iz foldera aplikacije: ADB iz
`platform-tools/adb.exe`, a scrcpy iz `scrcpy/scrcpy.exe`. ADB koristi server
na portu `5038`. Folder `scrcpy` mora sadržavati Windows izdanje scrcpy
(`scrcpy.exe` i njegove prateće fajlove), ne samo izvorni kod.
scrcpy se pokreće bez zvuka (`--no-audio`), tako da nije potreban audio uređaj
na računaru.
Donja statusna traka prikazuje verziju lokalnog ADB-a i ažurira stanje servera
na portu 5038 svake dvije sekunde.

Za USB kameru instaliraj potrebni paket:

```powershell
pip install -r requirements.txt
```

Pokreni `snimanje_ekrana.py` i odaberi **Android telefon · scrcpy** ili
**USB eksterna kamera**. U režimu USB kamere osvježi listu, odaberi kameru,
pa pokreni pregled. Dostupni su MP4 snimanje i screenshotovi.
Tokom pregleda klikni **Postavke kamere / fokus** za Windows postavke
uređaja. Ručni fokus je dostupan samo ako ga kamera i njen drajver podržavaju.
Automatski screenshotovi rade u oba režima: postavi interval u sekundama
(podrazumijevano 3) i klikni **Pokreni automatske screenshotove**. Brojač
snimljenih slika prikazuje napredak; timer se zaustavlja zajedno sa kamerom ili
scrcpy sesijom.
