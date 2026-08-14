"""E.V.'s icon, drawn rather than stored.

    make icons

A glowing head-up display: concentric rings, tick marks, and the letters in
the middle. The look is the one every fictional machine intelligence has had
since 2008, which is the point -- it says "this thing listens" before the name
is read.

Written as a program for two reasons. An icon that only exists as a PNG is an
icon nobody can change without the original file, and this project keeps its
generated artifacts in the repository *with* the thing that generates them
(`protocol/generated/` is the same rule). And it needs no dependencies: pure
Python writes the PNGs and macOS's own `iconutil` turns them into `.icns`, so
regenerating it needs nothing installed that is not already here.

Everything is drawn from distance fields and anti-aliased analytically --
coverage from a smoothstep of the distance -- rather than by supersampling,
which keeps a 1024px render inside a few seconds of pure Python.
"""

from __future__ import annotations

import math
import struct
import subprocess
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent

SIZE = 1024
"""What everything is rendered at. Every other size is a box filter of it."""

# The macOS icon grid: the artwork does not reach the edge of the canvas, and
# the corner radius is roughly a fifth of the tile. Anything drawn to the very
# edge looks bigger than every other icon in the Dock.
TILE = 0.90
RADIUS = 0.225

BACKDROP_IN = (0x0D, 0x1F, 0x33)
BACKDROP_OUT = (0x04, 0x08, 0x11)
CYAN = (0x38, 0xBD, 0xF8)
BRIGHT = (0xBA, 0xEC, 0xFF)
LETTERS = (0xEA, 0xF9, 0xFF)


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge1 == edge0:
        return 0.0 if x < edge0 else 1.0
    t = min(1.0, max(0.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def coverage(distance: float, feather: float) -> float:
    """How much of a pixel a shape covers, from its signed distance.

    Negative is inside. The feather is a pixel or so wide, which is what makes
    a curve drawn this way look drawn rather than counted.
    """
    return smoothstep(feather, -feather, distance)


def segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Distance from a point to a line segment. Every stroke is one of these
    with a thickness subtracted, which is why they all have round caps."""
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    length = vx * vx + vy * vy
    t = 0.0 if length == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / length))
    dx, dy = wx - t * vx, wy - t * vy
    return math.hypot(dx, dy)


def rounded_box(px: float, py: float, half: float, radius: float) -> float:
    """Signed distance to a rounded square centred on the origin."""
    qx = abs(px) - (half - radius)
    qy = abs(py) - (half - radius)
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    return outside + min(max(qx, qy), 0.0) - radius


# --- the letters ----------------------------------------------------------
#
# Drawn as strokes rather than set in a typeface: the icon has to survive being
# 16 pixels wide, and a font at that size is a smudge. Two bars and a vee are
# still two bars and a vee.

STROKE = 0.022
HEIGHT = 0.165
TOP, BOTTOM = -HEIGHT / 2, HEIGHT / 2

# `E.V.` is wider on the right than the left -- two full stops hang off the
# end of it -- so the whole word is nudged back to sit on the centre of the
# rings rather than on the centre of its own bounding box.
CENTRING = 0.038

E_LEFT, E_RIGHT = -0.198 + CENTRING, -0.108 + CENTRING
V_LEFT, V_MID, V_RIGHT = -0.028 + CENTRING, 0.037 + CENTRING, 0.102 + CENTRING

STROKES: tuple[tuple[float, float, float, float], ...] = (
    # E: the stem, then three arms. The middle arm is short, as it is in every
    # grotesque, because an E with three equal arms reads as a comb.
    (E_LEFT, TOP, E_LEFT, BOTTOM),
    (E_LEFT, TOP, E_RIGHT, TOP),
    (E_LEFT, 0.0, E_RIGHT - 0.018, 0.0),
    (E_LEFT, BOTTOM, E_RIGHT, BOTTOM),
    # V.
    (V_LEFT, TOP, V_MID, BOTTOM),
    (V_MID, BOTTOM, V_RIGHT, TOP),
)

DOTS: tuple[tuple[float, float], ...] = (
    (E_RIGHT + 0.028, BOTTOM),
    (V_RIGHT + 0.028, BOTTOM),
)
DOT = 0.017


def letters(px: float, py: float) -> float:
    """Distance to `E.V.`, whichever part of it is nearest."""
    nearest = min(
        segment(px, py, ax, ay, bx, by) - STROKE for ax, ay, bx, by in STROKES
    )
    for dx, dy in DOTS:
        nearest = min(nearest, math.hypot(px - dx, py - dy) - DOT)
    return nearest


# --- the rings ------------------------------------------------------------

TICKS = 32
TICK_INNER, TICK_OUTER = 0.340, 0.372

ARC_RADIUS = 0.302
ARC_WIDTH = 0.020
ARC_GAPS = ((25, 3.5), (115, 3.5), (205, 3.5), (295, 3.5))
"""Where the bright ring is broken, in degrees: a ring with gaps in it reads as
a readout, and a closed one reads as a badge.

Not on the diagonals, and not where the long tick marks are. They were both,
and the four unlit wedges lined up with the four long ticks into a dark X
across the whole icon -- visible in the picture, invisible in the numbers,
which is why this is drawn and looked at rather than only computed."""


def in_gap(degrees: float) -> bool:
    for start, width in ARC_GAPS:
        delta = (degrees - start) % 360.0
        if delta < width or delta > 360.0 - width:
            return True
    return False


def paint(x: int, y: int, feather: float) -> tuple[float, float, float, float]:
    """One pixel, in premultiplied-by-nothing float RGB and alpha."""
    px = (x + 0.5) / SIZE - 0.5
    py = (y + 0.5) / SIZE - 0.5

    tile = coverage(rounded_box(px, py, TILE / 2, RADIUS), feather)
    if tile <= 0.0:
        return 0.0, 0.0, 0.0, 0.0

    radius = math.hypot(px, py)

    # The backdrop: a dark disc of sky, lighter where the rings sit.
    lift = smoothstep(0.50, 0.0, radius) + 0.45 * smoothstep(0.26, 0.04, radius)
    red = BACKDROP_OUT[0] + (BACKDROP_IN[0] - BACKDROP_OUT[0]) * lift
    green = BACKDROP_OUT[1] + (BACKDROP_IN[1] - BACKDROP_OUT[1]) * lift
    blue = BACKDROP_OUT[2] + (BACKDROP_IN[2] - BACKDROP_OUT[2]) * lift

    def glow(distance: float, colour: tuple[int, int, int], reach: float, gain: float):
        nonlocal red, green, blue
        # Light does not stop at an edge. The exponential is what makes a
        # stroke look lit rather than filled.
        amount = gain * math.exp(-max(distance, 0.0) / reach)
        if amount <= 0.002:
            return
        red = min(255.0, red + colour[0] * amount)
        green = min(255.0, green + colour[1] * amount)
        blue = min(255.0, blue + colour[2] * amount)

    def stroke(distance: float, colour: tuple[int, int, int]):
        nonlocal red, green, blue
        inside = coverage(distance, feather)
        if inside <= 0.0:
            return
        red += (colour[0] - red) * inside
        green += (colour[1] - green) * inside
        blue += (colour[2] - blue) * inside

    # The lit edge of the tile itself, rather than a circle that runs off the
    # corners of it. The first version put a ring at 0.455 and the rounded
    # square cut four holes in it.
    bezel = abs(rounded_box(px, py, TILE / 2, RADIUS)) - 0.0035
    glow(bezel, CYAN, 0.012, 0.22)
    stroke(bezel, (0x5F, 0xC8, 0xF5))

    # A faint ring just inside it, the boundary of the display.
    outer = abs(radius - 0.400) - 0.0030
    glow(outer, CYAN, 0.010, 0.28)
    stroke(outer, (0x7F, 0xD8, 0xFF))

    # Tick marks around it: the thing that says this is an instrument.
    if TICK_INNER - 0.02 < radius < TICK_OUTER + 0.02:
        angle = math.degrees(math.atan2(py, px)) % 360.0
        step = 360.0 / TICKS
        offset = abs(((angle + step / 2) % step) - step / 2)
        # Distance in the angular direction, turned back into a length.
        across = math.radians(offset) * radius - 0.0045
        along = max(TICK_INNER - radius, radius - TICK_OUTER)
        tick = max(across, along)
        # Every fourth one is longer, the way a dial is marked.
        if round(angle / step) % 4 == 0:
            tick = max(across, max(0.324 - radius, radius - TICK_OUTER))
        glow(tick, CYAN, 0.008, 0.25)
        stroke(tick, (0x6C, 0xCF, 0xFF))

    # The bright broken ring.
    ring = abs(radius - ARC_RADIUS) - ARC_WIDTH / 2
    if not in_gap(math.degrees(math.atan2(py, px)) % 360.0):
        glow(ring, CYAN, 0.030, 0.55)
        stroke(ring, BRIGHT)
    else:
        # The gap is not empty: it is dimmer, so the ring still reads as a ring.
        glow(ring, CYAN, 0.024, 0.26)

    # A thin inner ring, close to the letters.
    inner = abs(radius - 0.244) - 0.0022
    glow(inner, CYAN, 0.012, 0.22)
    stroke(inner, (0x6C, 0xCF, 0xFF))

    # The letters, lit from inside.
    text = letters(px, py)
    glow(text, BRIGHT, 0.022, 0.45)
    stroke(text, LETTERS)

    return red / 255.0, green / 255.0, blue / 255.0, tile


def render() -> list[list[tuple[float, float, float, float]]]:
    feather = 0.9 / SIZE
    rows = []
    for y in range(SIZE):
        rows.append([paint(x, y, feather) for x in range(SIZE)])
        if y % 128 == 0:
            print(f"  {y * 100 // SIZE}%", end="\r", flush=True)
    return rows


def downsample(rows: list[list[tuple[float, float, float, float]]], size: int) -> bytes:
    """A box filter, in linear-ish space. Good enough, and it keeps the glow
    from crawling the way a nearest-neighbour scale does."""
    step = SIZE // size
    out = bytearray()
    for y in range(size):
        out.append(0)  # PNG filter byte: none
        for x in range(size):
            red = green = blue = alpha = 0.0
            for sy in range(y * step, (y + 1) * step):
                row = rows[sy]
                for sx in range(x * step, (x + 1) * step):
                    r, g, b, a = row[sx]
                    red += r * a
                    green += g * a
                    blue += b * a
                    alpha += a
            count = step * step
            if alpha <= 0.0:
                out.extend((0, 0, 0, 0))
                continue
            out.extend(
                (
                    min(255, round(red / alpha * 255)),
                    min(255, round(green / alpha * 255)),
                    min(255, round(blue / alpha * 255)),
                    min(255, round(alpha / count * 255)),
                )
            )
    return bytes(out)


def png(raw: bytes, size: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


# --- the menu bar ---------------------------------------------------------


def tray(size: int, listening: bool = False) -> bytes:
    """The menu bar mark: black with alpha, which macOS calls a template.

    Not the app icon shrunk. A menu bar is 22 points tall and monochrome by
    convention; a glowing badge up there looks like something went wrong.
    macOS inverts a template for dark menu bars, so this is drawn once and is
    correct in both.

    Two of them: the ring, and the ring with its middle filled. The filled one
    is on screen for exactly as long as the microphone is open, which is what
    `CLAUDE.md` invariant 8 asks for -- macOS shows its own indicator, and its
    own indicator does not say which application is listening.
    """
    scale = 4
    big = size * scale
    feather = 0.9 / big
    alpha = [[0.0] * big for _ in range(big)]

    for y in range(big):
        for x in range(big):
            px = (x + 0.5) / big - 0.5
            py = (y + 0.5) / big - 0.5
            radius = math.hypot(px, py)

            # A ring with a gap at the top right, and a dot in the middle: the
            # silhouette of the icon, at the only size that matters here.
            ring = abs(radius - 0.34) - 0.055
            angle = math.degrees(math.atan2(py, px)) % 360.0
            if 300.0 < angle < 345.0:
                ring = 1.0
            dot = radius - (0.19 if listening else 0.11)
            alpha[y][x] = max(coverage(ring, feather), coverage(dot, feather))

    out = bytearray()
    for y in range(size):
        out.append(0)
        for x in range(size):
            total = 0.0
            for sy in range(y * scale, (y + 1) * scale):
                for sx in range(x * scale, (x + 1) * scale):
                    total += alpha[sy][sx]
            value = round(total / (scale * scale) * 255)
            out.extend((0, 0, 0, min(255, value)))
    return png(bytes(out), size)


def main() -> int:
    print("drawing E.V. at 1024px")
    rows = render()

    iconset = HERE / "icon.iconset"
    iconset.mkdir(exist_ok=True)

    # What the app bundle and Tauri's config ask for.
    wanted = {
        HERE / "icon.png": 1024,
        HERE / "128x128@2x.png": 256,
        HERE / "128x128.png": 128,
        HERE / "32x32.png": 32,
    }
    # What iconutil wants, which is every size at 1x and 2x.
    for size in (16, 32, 128, 256, 512):
        wanted[iconset / f"icon_{size}x{size}.png"] = size
        wanted[iconset / f"icon_{size}x{size}@2x.png"] = size * 2

    for path, size in sorted(wanted.items(), key=lambda pair: -pair[1]):
        path.write_bytes(png(downsample(rows, size), size))
        print(f"  wrote {path.name} ({size}px)")

    done = subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "icon.icns")],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        print(done.stderr.strip(), file=sys.stderr)
        return 1
    print("  wrote icon.icns")

    # The iconset is scaffolding for `iconutil` and nothing reads it
    # afterwards. Committing intermediates would mean two copies of the same
    # pixels in the repository.
    for stale in iconset.iterdir():
        stale.unlink()
    iconset.rmdir()

    for path, size, live in (
        (HERE / "tray.png", 22, False),
        (HERE / "tray@2x.png", 44, False),
        (HERE / "tray-live.png", 22, True),
        (HERE / "tray-live@2x.png", 44, True),
    ):
        path.write_bytes(tray(size, live))
        print(f"  wrote {path.name} ({size}px, template)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
