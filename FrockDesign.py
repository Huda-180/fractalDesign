"""
Dragon Curve + Snowflake Fractal Art Generator
------------------------------------------------
Recreates a piece with:
  - Several gold-to-dark-brown "dragon curve" fractal blobs, rendered
    in a chunky/pixelated style.
  - Soft, blurred light-gray snowflake fractals scattered in the background.

Color scheme (kept exactly as in the reference art):
  Dragon curve gradient : dark brown  -> orange -> bright gold
  Snowflakes             : light gray, semi-transparent, blurred
  Background             : white

Requires: pillow  (pip install pillow --break-system-packages)
"""

import math
import random
from PIL import Image, ImageDraw, ImageFilter

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
CANVAS_W, CANVAS_H = 600, 800          # final image size
BG_COLOR = (255, 255, 255, 255)

# Dragon curve color gradient (dark brown -> gold), matches reference art
DRAGON_COLOR_STOPS = [
    (92, 51, 15),     # dark brown
    (170, 97, 15),    # burnt orange
    (224, 145, 22),   # amber
    (247, 181, 33),   # bright gold
]

SNOWFLAKE_COLOR = (185, 195, 205)      # light gray-blue
SNOWFLAKE_ALPHA_RANGE = (35, 90)       # translucency range

random.seed(7)


# ----------------------------------------------------------------------
# DRAGON CURVE (L-SYSTEM)
# ----------------------------------------------------------------------
def dragon_curve_string(order: int) -> str:
    """Generate the dragon curve L-system string."""
    s = "FX"
    rules = {"X": "X+YF+", "Y": "-FX-Y-"}
    for _ in range(order):
        s = "".join(rules.get(c, c) for c in s)
    return s


def dragon_curve_points(order: int, step: float = 1.0):
    """Turn the L-system string into a list of (x, y) points."""
    s = dragon_curve_string(order)
    x, y, angle = 0.0, 0.0, 0.0
    pts = [(x, y)]
    for c in s:
        if c == "F":
            x += step * math.cos(math.radians(angle))
            y += step * math.sin(math.radians(angle))
            pts.append((x, y))
        elif c == "+":
            angle += 90
        elif c == "-":
            angle -= 90
    return pts


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def gradient_color(t, stops=DRAGON_COLOR_STOPS):
    """t in [0,1] -> interpolated color across multiple stops."""
    n = len(stops) - 1
    seg = min(int(t * n), n - 1)
    local_t = (t * n) - seg
    return lerp_color(stops[seg], stops[seg + 1], local_t)


def draw_dragon_blob(base_img: Image.Image, center, scale, order=11,
                      pixel_block=4, rotation_deg=0):
    """
    Renders one dragon-curve fractal 'blob' onto base_img (RGBA),
    in a chunky pixelated style, colored with the gold/brown gradient.
    """
    pts = dragon_curve_points(order, step=1.0)

    # normalize to unit bounding box centered at origin
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w = maxx - minx or 1
    h = maxy - miny or 1
    norm = [((p[0] - minx) / w - 0.5, (p[1] - miny) / h - 0.5) for p in pts]

    # rotate + scale + translate to final position
    rad = math.radians(rotation_deg)
    cos_r, sin_r = math.cos(rad), math.sin(rad)
    placed = []
    for (nx, ny) in norm:
        rx = nx * cos_r - ny * sin_r
        ry = nx * sin_r + ny * cos_r
        placed.append((center[0] + rx * scale, center[1] + ry * scale))

    # Draw at low resolution first (for the blocky pixel look), then upscale
    low_res_scale = 1.0 / pixel_block
    low_w, low_h = base_img.width // pixel_block, base_img.height // pixel_block
    low_img = Image.new("RGBA", (low_w, low_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(low_img)

    n = len(placed)
    line_width = max(1, int(2))
    for i in range(n - 1):
        t = i / n
        color = gradient_color(t) + (255,)
        x1, y1 = placed[i][0] * low_res_scale, placed[i][1] * low_res_scale
        x2, y2 = placed[i + 1][0] * low_res_scale, placed[i + 1][1] * low_res_scale
        draw.line([(x1, y1), (x2, y2)], fill=color, width=line_width)

    # upscale with NEAREST to get crisp square "pixels"
    big = low_img.resize(base_img.size, Image.NEAREST)
    base_img.alpha_composite(big)


# ----------------------------------------------------------------------
# SNOWFLAKE FRACTAL (recursive branching, koch-style arms)
# ----------------------------------------------------------------------
def draw_branch(draw, x, y, angle, length, depth, width):
    if depth == 0 or length < 2:
        return
    x2 = x + length * math.cos(math.radians(angle))
    y2 = y + length * math.sin(math.radians(angle))
    draw.line([(x, y), (x2, y2)], fill=(255, 255, 255, 255), width=max(1, width))

    # small side spikes partway along the branch (snowflake teeth)
    for frac in (0.4, 0.7):
        bx = x + (x2 - x) * frac
        by = y + (y2 - y) * frac
        for side_angle in (angle - 45, angle + 45):
            side_len = length * 0.35
            sx = bx + side_len * math.cos(math.radians(side_angle))
            sy = by + side_len * math.sin(math.radians(side_angle))
            draw.line([(bx, by), (sx, sy)], fill=(255, 255, 255, 255),
                      width=max(1, width - 1))

    draw_branch(draw, x2, y2, angle, length * 0.55, depth - 1, max(1, width - 1))


def make_snowflake(size=160, depth=3):
    """Return an RGBA image containing one 6-armed fractal snowflake (white)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size / 2, size / 2
    arm_len = size * 0.42
    for i in range(6):
        angle = i * 60
        draw_branch(draw, cx, cy, angle, arm_len, depth, width=3)
    return img


def scatter_snowflakes(base_img: Image.Image, count=16):
    """Paste multiple blurred, tinted, semi-transparent snowflakes as background."""
    base_flake = make_snowflake(size=160, depth=3)

    for _ in range(count):
        size = random.randint(70, 220)
        flake = base_flake.resize((size, size), Image.LANCZOS)
        flake = flake.rotate(random.uniform(0, 360), expand=True)

        # tint white pixels to the snowflake gray color
        r, g, b, a = flake.split()
        tint = Image.new("RGBA", flake.size, SNOWFLAKE_COLOR + (0,))
        tint.putalpha(a)
        flake = tint

        # random translucency + blur (some sharper/closer, some hazier/farther)
        alpha_val = random.randint(*SNOWFLAKE_ALPHA_RANGE)
        r2, g2, b2, a2 = flake.split()
        a2 = a2.point(lambda p: int(p * alpha_val / 255))
        flake.putalpha(a2)

        blur_radius = random.uniform(0.5, 2.5)
        flake = flake.filter(ImageFilter.GaussianBlur(blur_radius))

        px = random.randint(-20, CANVAS_W - size + 20)
        py = random.randint(-20, CANVAS_H - size + 20)
        base_img.alpha_composite(flake, (px, py))


# ----------------------------------------------------------------------
# MAIN COMPOSITION
# ----------------------------------------------------------------------
def generate_art(output_path="fractal_art.png"):
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), BG_COLOR)

    # 1) background snowflakes (behind everything)
    scatter_snowflakes(canvas, count=18)

    # 2) gold/brown dragon-curve blobs, positioned roughly like the reference
    dragon_spots = [
        {"center": (190, 170), "scale": 230, "rotation": 10},
        {"center": (430, 400), "scale": 190, "rotation": -15},
        {"center": (190, 660), "scale": 210, "rotation": 5},
    ]
    for spot in dragon_spots:
        draw_dragon_blob(
            canvas,
            center=spot["center"],
            scale=spot["scale"],
            order=11,
            pixel_block=4,
            rotation_deg=spot["rotation"],
        )

    canvas.convert("RGB").save(output_path)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    generate_art("fractal_art.png")