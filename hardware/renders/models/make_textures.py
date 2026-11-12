#!/usr/bin/env python3
"""Legend textures for the two stand-in modules, drawn from the photos of the real board.

    python3 models/make_textures.py

Writes pcm5102_back.png (the back of a PCM5102 module, which faces up on this board) and
dir9001_top.png (the LHY AUDIO DIR9001-I2S board). Both are drawn as the photos show
them with the carrier's east edge up: image x runs north to south, image y east to west.
Positions are read off the photos by eye; nothing here is a measured drawing.
"""
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
S = 40                                              # pixels per mm


def font_file():
    out = subprocess.run(['fc-match', '-f', '%{file}', 'sans:bold'], capture_output=True, text=True).stdout
    return out.strip()


FONT = font_file()
WHITE = (236, 236, 228)
TIN = (188, 190, 186)


def text(img, s, x, y, h, rot=0, fill=WHITE):
    """Text with cap height about h mm, centred on (x, y) mm, rot degrees anticlockwise."""
    f = ImageFont.truetype(FONT, int(h * S * 1.38))
    box = f.getbbox(s)
    t = Image.new('RGBA', (box[2] - box[0] + 8, box[3] - box[1] + 8), (0, 0, 0, 0))
    ImageDraw.Draw(t).text((4 - box[0], 4 - box[1]), s, font=f, fill=fill)
    if rot:
        t = t.rotate(rot, expand=True)
    img.alpha_composite(t, (int(x * S - t.width / 2), int(y * S - t.height / 2)))


def ring(d, x, y, outer, inner, fill=TIN, hole=(20, 20, 20)):
    d.ellipse([(x - outer / 2) * S, (y - outer / 2) * S, (x + outer / 2) * S, (y + outer / 2) * S], fill=fill)
    d.ellipse([(x - inner / 2) * S, (y - inner / 2) * S, (x + inner / 2) * S, (y + inner / 2) * S], fill=hole)


def rect(d, x, y, w, h, fill=None, outline=None, width=0.12):
    d.rectangle([(x - w / 2) * S, (y - h / 2) * S, (x + w / 2) * S, (y + h / 2) * S], fill=fill,
                outline=outline, width=max(1, int(width * S)))


def chip_part(d, x, y, vertical=False, body=(150, 120, 80)):
    """An 0805 part on its pads, inside a legend outline."""
    w, h = (1.3, 2.2) if vertical else (2.2, 1.3)
    rect(d, x, y, w + 0.7, h + 0.7, outline=WHITE)
    rect(d, x, y, w, h, fill=TIN)
    rect(d, x, y, w * (1 if vertical else 0.5), h * (0.5 if vertical else 1), fill=body)


def pcm5102():
    w, h = 17.11, 30.96
    img = Image.new('RGBA', (int(w * S), int(h * S)), (62, 18, 104, 255))
    d = ImageDraw.Draw(img)
    for i, name in enumerate(['SCK', 'BCK', 'DIN', 'LRCK', 'GND', 'VIN']):
        x = 2.14 + 2.54 * i
        ring(d, x, 0.88, 1.7, 0.9)
        text(img, name, x, 3.0, 0.62)
    for i, name in enumerate(['FLT', 'DEMP', 'XSMT', 'FMT', 'A3V3', 'AGND', 'ROUT', 'AGND', 'LROUT']):
        y = 7.37 + 2.54 * i
        ring(d, 1.75, y, 1.7, 0.9)
        f = ImageFont.truetype(FONT, int(1.15 * S * 1.38))
        d.text((3.1 * S, y * S), name, font=f, fill=WHITE, anchor='lm')
    for k, (x, y, name) in enumerate([(10.3, 7.2, 'H1L'), (13.6, 7.2, 'H3L'), (10.3, 10.0, 'H2L'), (13.6, 10.0, 'H4L')]):
        d.rounded_rectangle([(x - 1.3) * S, (y - 0.75) * S, (x + 1.3) * S, (y + 0.75) * S], radius=0.5 * S,
                            outline=WHITE, width=5)
        for dx in (-0.75, 0, 0.75):
            rect(d, x + dx, y, 0.5, 0.9, fill=TIN)
        text(img, name, x, y + (1.5 if k > 1 else -1.5), 0.75)
    for i, name in enumerate(['PCM5100', 'PCM5101', 'PCM5102']):
        x = 10.4 + 1.6 * i
        text(img, name, x, 17.6, 0.95, rot=90)
        rect(d, x, 21.6, 0.9, 0.9, fill=WHITE)
    img.convert('RGB').save(HERE / 'pcm5102_back.png')


def dir9001():
    w, h = 64.0, 48.0                               # estimate, see README
    img = Image.new('RGBA', (int(w * S), int(h * S)), (16, 112, 52, 255))
    d = ImageDraw.Draw(img)
    X = lambda n: w - n                             # n: mm from the south edge
    Y = lambda e: h - e                             # e: mm from the west (I2S-OUT) edge
    for n, e in [(60, 4), (4, 4), (60, 29), (4, 29)]:
        ring(d, X(n), Y(e), 6.0, 3.2)
    text(img, 'LHY AUDIO', 48.5, 12.6, 1.9)
    text(img, 'DIR9001-I2S', 48.5, 15.6, 1.5)
    text(img, 'I2S-OUT', 48.5, 44.6, 1.3)
    text(img, 'POWER', 8.4, 41.0, 1.2, rot=90)
    text(img, 'GND', 13.2, 37.6, 1.1)
    text(img, '+5V', 18.2, 37.6, 1.1)
    for x in (12.6, 18.0):
        rect(d, x, 42.3, 4.6, 5.0, outline=WHITE, width=0.2)
        ring(d, x, 42.0, 2.6, 1.3)
    text(img, 'FMT', 18.6, 18.2, 1.0, rot=90)
    text(img, 'FMT0', 28.0, 18.2, 1.0, rot=90)
    text(img, 'FMT1', 29.8, 18.2, 1.0, rot=90)
    text(img, 'LOCK', 37.6, 16.6, 1.0, rot=90)
    text(img, 'SCK0', 57.0, 24.2, 1.0, rot=90)
    text(img, 'SCK1', 58.8, 24.2, 1.0, rot=90)
    text(img, 'PSCK', 53.5, 34.0, 1.0, rot=90)
    for name, y in (('DATA', 0), ('BCLK', 1), ('LRCK', 2), ('MCLK', 3), ('+5V', 4), ('GND', 5)):
        text(img, name, 25.3 + 2.5 * y, 38.6, 0.8, rot=90)
    text(img, '379378A_Y150', 24.0, 1.4, 0.7)
    text(img, '260831', 24.0, 2.6, 0.7)
    for x, y, v in [(22.5, 10.5, 1), (25.0, 10.5, 1), (14.5, 12.5, 0), (14.5, 16.0, 0), (9.0, 22.5, 0),
                    (32.0, 21.0, 0), (36.5, 21.0, 0), (32.0, 24.5, 0), (37.0, 24.5, 0), (34.5, 16.5, 1),
                    (46.0, 19.0, 1), (48.6, 19.0, 1), (46.0, 23.5, 1), (48.6, 23.5, 1), (53.0, 19.0, 1),
                    (53.0, 23.5, 1), (55.6, 23.5, 1), (25.0, 28.0, 0), (14.0, 33.0, 0), (20.5, 26.5, 1),
                    (51.5, 33.5, 1)]:
        chip_part(d, x, y, vertical=bool(v))
    img.convert('RGB').save(HERE / 'dir9001_top.png')


pcm5102()
dir9001()
print('wrote', HERE / 'pcm5102_back.png', HERE / 'dir9001_top.png')
