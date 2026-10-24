# SNIMANJE_ANDROID
Python skripta za snimanje ekrana Android telefona

## Upotreba

Potrebni su Python 3 i Android Platform Tools (`adb`). Uključite USB debugging na
telefonu, povežite ga USB kablom i odobrite zahtev za debugging.

```sh
python snimanje_ekrana.py snimak.mp4 --duration 60
```

Snimak se podrazumevano čuva kao `screenrecord.mp4`, a maksimalno trajanje jednog
snimanja je 180 sekundi. Ako je povezano više uređaja, izaberite uređaj pomoću
`-s`:

```sh
python snimanje_ekrana.py snimak.mp4 -s DEVICE_SERIAL
```

Pokrenite testove komandom `python -m unittest`.
