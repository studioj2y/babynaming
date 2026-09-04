"""抠图 babynamepic/五行2.jpg → 透明 PNG，保存为 characters/char-wuxing-1.png。
背景是均匀浅灰(~#f0f0f0)，按像素颜色与背景色距离设 alpha（边缘抗锯齿）。"""
import os
from PIL import Image

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "babynamepic", "五行2.jpg")
SRC = os.path.normpath(SRC)
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "characters", "char-wuxing-1.png")
DST = os.path.normpath(DST)

im = Image.open(SRC).convert("RGBA")
W, H = im.size
print(f"source: {SRC}  size={W}x{H}")

# 取四角像素估计背景色
corners = [im.getpixel(p) for p in [(0,0), (W-1,0), (0,H-1), (W-1,H-1)]]
bg_r = sum(c[0] for c in corners) // 4
bg_g = sum(c[1] for c in corners) // 4
bg_b = sum(c[2] for c in corners) // 4
print(f"estimated bg color: rgb({bg_r},{bg_g},{bg_b})")

# 像素距离阈值：远于背景 → 实心；近于背景 → 透明；中间 → 半透明抗锯齿
THRESH_HARD = 36   # 距离 >= 此值 → 不透明
THRESH_SOFT = 10   # 距离 <  此值 → 完全透明

px = im.load()
for y in range(H):
    for x in range(W):
        r, g, b, _ = px[x, y]
        # 欧氏距离（RGB）
        d2 = (r - bg_r) ** 2 + (g - bg_g) ** 2 + (b - bg_b) ** 2
        d = (d2 ** 0.5)
        if d >= THRESH_HARD:
            a = 255
        elif d <= THRESH_SOFT:
            a = 0
        else:
            # 线性过渡：THRESH_SOFT → 0，THRESH_HARD → 255
            a = int(round((d - THRESH_SOFT) * 255 / (THRESH_HARD - THRESH_SOFT)))
            a = max(0, min(255, a))
        px[x, y] = (r, g, b, a)

im.save(DST, "PNG", optimize=True)
size = os.path.getsize(DST)
print(f"saved: {DST}  bytes={size}  size={W}x{H}")

# 简易自检：透明像素比例
solid = sum(1 for y in range(H) for x in range(W) if px[x, y][3] > 200)
total = W * H
print(f"opaque ratio: {solid}/{total} = {solid/total:.1%}")