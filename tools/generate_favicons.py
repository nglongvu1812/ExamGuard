"""Generate multi-resolution favicon.ico, favicon.png, apple-touch-icon.png from scratch."""

from __future__ import annotations

import math
from pathlib import Path
from PIL import Image, ImageDraw


def render_examguard_master() -> Image.Image:
    """Render at 1024x1024 master canvas, then downsample with Lanczos."""
    w, h = 1024, 1024
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # Base gradient background
    base_grad = Image.new("RGBA", (w, h))
    grad_draw = ImageDraw.Draw(base_grad)
    for y in range(h):
        t = y / h
        r = int(0x1E * (1 - t) + 0x09 * t)
        g = int(0x3A * (1 - t) + 0x14 * t)
        b = int(0x5F * (1 - t) + 0x22 * t)
        grad_draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

    pad = 48
    radius = 224
    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((pad, pad, w - pad, h - pad), radius=radius, fill=255)
    im.paste(base_grad, (0, 0), mask)

    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle(
        (pad, pad, w - pad, h - pad),
        radius=radius,
        outline=(56, 189, 248, 200),
        width=16,
    )

    # Shield contour points
    cx = w // 2
    top_y = 210
    ctrl_y = 320
    bottom_y = 820
    half_w = 256

    shield_pts: list[tuple[float, float]] = []
    steps = 40
    for i in range(steps + 1):
        x = cx - half_w + (2 * half_w * i / steps)
        arch = math.sin(i / steps * math.pi) * 24
        shield_pts.append((x, top_y - arch))

    for i in range(1, steps + 1):
        t = i / steps
        bx = (1 - t) ** 2 * (cx + half_w) + 2 * (1 - t) * t * (cx + half_w * 0.95) + t**2 * cx
        by = (1 - t) ** 2 * top_y + 2 * (1 - t) * t * (ctrl_y + 220) + t**2 * bottom_y
        shield_pts.append((bx, by))

    for i in range(1, steps + 1):
        t = i / steps
        bx = (1 - t) ** 2 * cx + 2 * (1 - t) * t * (cx - half_w * 0.95) + t**2 * (cx - half_w)
        by = (1 - t) ** 2 * bottom_y + 2 * (1 - t) * t * (ctrl_y + 220) + t**2 * top_y
        shield_pts.append((bx, by))

    # Fill shield
    shield_mask = Image.new("L", (w, h), 0)
    shield_draw = ImageDraw.Draw(shield_mask)
    shield_draw.polygon(shield_pts, fill=255)

    shield_grad = Image.new("RGBA", (w, h))
    sg_draw = ImageDraw.Draw(shield_grad)
    for y in range(h):
        t = y / h
        r = int(0x24 * (1 - t) + 0x0D * t)
        g = int(0x4B * (1 - t) + 0x20 * t)
        b = int(0x77 * (1 - t) + 0x35 * t)
        sg_draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

    im.paste(shield_grad, (0, 0), shield_mask)

    # Shield outline
    draw.line(shield_pts, fill=(56, 189, 248, 220), width=20, joint="curve")

    # Subtle exam ledger lines
    draw.rounded_rectangle(
        (408, 360, 616, 376),
        radius=8,
        fill=(96, 165, 250, 90),
    )
    draw.rounded_rectangle(
        (408, 432, 536, 448),
        radius=8,
        fill=(96, 165, 250, 90),
    )

    # Bold Checkmark
    chk_w = 72
    p1 = (392, 544)
    p2 = (472, 628)
    p3 = (648, 428)

    # Glow under checkmark
    for g_offset, g_alpha in [(16, 40), (8, 80), (4, 120)]:
        draw.line([p1, p2, p3], fill=(16, 185, 129, g_alpha), width=chk_w + g_offset, joint="round")

    # Foreground checkmark
    draw.line([p1, p2, p3], fill=(52, 211, 153, 255), width=chk_w, joint="round")

    return im


def main() -> None:
    out_dir = Path(__file__).resolve().parents[1] / "frontend" / "public"
    out_dir.mkdir(parents=True, exist_ok=True)

    master = render_examguard_master()
    icon512 = master.resize((512, 512), Image.Resampling.LANCZOS)
    icon180 = master.resize((180, 180), Image.Resampling.LANCZOS)
    icon64 = master.resize((64, 64), Image.Resampling.LANCZOS)
    icon48 = master.resize((48, 48), Image.Resampling.LANCZOS)
    icon32 = master.resize((32, 32), Image.Resampling.LANCZOS)
    icon16 = master.resize((16, 16), Image.Resampling.LANCZOS)

    icon180.save(out_dir / "apple-touch-icon.png", format="PNG")
    icon512.save(out_dir / "icon-512.png", format="PNG")
    icon32.save(out_dir / "favicon-32x32.png", format="PNG")
    icon16.save(out_dir / "favicon-16x16.png", format="PNG")

    # Save multi-size ICO
    icon32.save(
        out_dir / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
        append_images=[icon16, icon48, icon64],
    )
    print(f"Generated icons successfully in {out_dir}")



if __name__ == "__main__":
    main()
