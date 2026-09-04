"""验证 score_gender：指定性别(M/F)的候选名气韵不应恒为 100，且应随组合变化。
期望：
- 纯同性别(M/M/M 或 F/F/F) → 90（不再 100）
- 含一枚中性(U)字（刚柔相济） → 更高（约 94~96）
- 全中性(U/U/U) 男/女名 → 84
- 不限(U)：纯中性 90、纯单性别 84、M+F 混搭 55
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import generate, score_gender

print('=== 单元：score_gender 各组合 ===')
cases = [
    ('M', ['M','M','M'], 90), ('M', ['M','M','U'], 96), ('M', ['M','U','U'], 94),
    ('M', ['U','U','U'], 84),
    ('F', ['F','F','F'], 90), ('F', ['F','F','U'], 96), ('F', ['F','U','U'], 94),
    ('U', ['U','U','U'], 90), ('U', ['M','M','M'], 84), ('U', ['M','F','U'], 55),
]
ok = True
for req, g, exp in cases:
    got = score_gender(g, req)
    flag = 'OK' if got == exp else 'FAIL'
    if got != exp: ok = False
    print(f'  {req} {g} -> {got} (期望 {exp}) [{flag}]')

print('=== 集成：generate 候选不应出现 100 ===')
for g in ['M', 'F', 'U']:
    names, _ = generate('林', '王', 'F', 3, g, None, [], '', 8)
    vals = [n['dims']['gender'] for n in names]
    has100 = 100 in vals
    if has100: ok = False
    print(f'  req={g} 气韵取值={sorted(set(vals))} 含100={has100}')

print('ALL OK' if ok else 'HAS FAILURE')
