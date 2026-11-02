
"""Koppelt de V6-zendverbetering en tabbladen aan de V5-build."""

from pathlib import Path


source = Path("main.py")
text = source.read_text(encoding="utf-8")

old = "from radio_engine import RadioEngine"
new = "from radio_v6 import RadioEngine, install_interface"

if text.count(old) != 1:
    raise SystemExit(
        "V5 is niet toegepast of import gewijzigd."
    )

text = text.replace(old, new, 1)

old = "\ndef main():"
new = "\ninstall_interface(ChristmasRadio)\n\ndef main():"

if text.count(old) != 1:
    raise SystemExit(
        "Einde van hoofdprogramma niet gevonden."
    )

text = text.replace(old, new, 1)

source.write_text(
    text,
    encoding="utf-8",
)

print(
    "Christmas Radio V6: spraak + kanalen + "
    "TG-groepen toegevoegd"
)
