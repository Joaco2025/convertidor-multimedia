"""Genera assets/icon.ico (ejecutado por build.bat)."""
import os
from PIL import Image, ImageDraw

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(root, "assets", "icon.ico")
os.makedirs(os.path.dirname(out), exist_ok=True)

S = 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((16, 16, S - 16, S - 16), radius=110, fill=(37, 99, 235, 255))
# flecha de descarga
d.rectangle((216, 96, 296, 270), fill="white")
d.polygon([(146, 250), (366, 250), (256, 370)], fill="white")
# barra base
d.rounded_rectangle((126, 396, 386, 432), radius=18, fill=(255, 255, 255, 230))
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icono:", out)
