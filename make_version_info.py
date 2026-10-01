"""Erzeugt version_info.txt fuer PyInstaller (--version-file), damit die EXE
unter Eigenschaften -> Details Name und Version anzeigt. Die Version kommt
aus __version__ in starmoney_export.py (einzige Stelle, an der sie gepflegt
wird).

Aufruf: python make_version_info.py
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "starmoney_export.py"), encoding="utf-8") as fh:
    version = re.search(r'^__version__\s*=\s*"([^"]+)"', fh.read(), re.M).group(1)

# Windows erwartet vier Zahlen, z.B. 0.2 -> (0, 2, 0, 0)
nums = [int(n) for n in re.findall(r"\d+", version)][:4]
nums += [0] * (4 - len(nums))
tup = tuple(nums)

TEMPLATE = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tup}, prodvers={tup}),
  kids=[
    StringFileInfo([StringTable('040704B0', [
      StringStruct('ProductName', 'csv2pdf'),
      StringStruct('FileDescription', 'StarMoney-CSV in PDF-Kontoauszuege umwandeln'),
      StringStruct('CompanyName', 'Lutherschule Hannover'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('ProductVersion', '{version}'),
    ])]),
    VarFileInfo([VarStruct('Translation', [0x0407, 1200])]),
  ]
)
"""

with open(os.path.join(HERE, "version_info.txt"), "w", encoding="utf-8") as fh:
    fh.write(TEMPLATE)
print(f"version_info.txt fuer Version {version} geschrieben")
