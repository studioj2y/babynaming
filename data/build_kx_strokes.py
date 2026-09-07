# -*- coding: utf-8 -*-
"""构建期一次性脚本：给字库补「康熙笔画」字段 stroke_kx（五格数理的传统标准）。

背景
----
原字库 `chars.json` / `good_chars.json` 的 stroke 是**简体画数**（华=6、国=8、云=4），
而五格数理（天/人/地/总/外格 81 数理）在传统姓名学里按**康熙字典笔画**计算
（華=14、國=11、雲=12）。两者在字库里 56% 的字上不同，导致原来算出的五格系统性偏小。

做法
----
数据源：kangxi-strokecount（MIT，Unihan 整理的康熙字典笔画，32957 字）
  CSV 列序：CodePoint, Value, Character, Strokes
下载（GitHub raw 在本机常被 SSL 拦，走 jsDelivr CDN 成功）：
  https://fastly.jsdelivr.net/gh/TonyFoster/kangxi-strokecount@master/kangxi-strokecount.csv

注意：现代简化字在康熙字典里没有字头，直查会拿到简体画数（华=6 而非 14）。
故必须 **先用 OpenCC s2t 转成繁体再查**（华→華→14）。已验证 14/14 简化字准确。

运行时零依赖：本脚本只在构建期跑一次，把结果烘进 json；
core.py 只读 stroke_kx 字段，不 import opencc、不读 CSV。

用法
----
  python data/build_kx_strokes.py [csv_path]
默认 csv 路径：data/_kx/kx_raw.csv
"""
import io
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(HERE, "_kx", "kx_raw.csv")


def load_kx_table(csv_path):
    """解析 kangxi-strokecount CSV -> {字符: 康熙笔画}"""
    if not os.path.exists(csv_path):
        sys.exit(
            "找不到康熙笔画表：%s\n"
            "请先下载（GitHub raw 常被拦，用 jsDelivr）：\n"
            "  curl -sSL -o data/_kx/kx_raw.csv "
            "https://fastly.jsdelivr.net/gh/TonyFoster/kangxi-strokecount@master/kangxi-strokecount.csv"
            % csv_path
        )
    table = {}
    with io.open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            # 列序：CodePoint, Value, Character, Strokes（前几行是 license 文本，长度不足会自动跳过）
            if len(row) >= 4:
                try:
                    table[row[2].strip()] = int(row[3].strip())
                except (ValueError, IndexError):
                    continue
    return table


def make_lookup(table):
    """返回 func(字) -> 康熙笔画 or None。简化字先 s2t 转繁体再查。"""
    try:
        from opencc import OpenCC
    except ImportError:
        sys.exit("需要 opencc：pip install opencc-python-reimplemented（仅构建期用）")
    cc = OpenCC("s2t")

    def lookup(ch):
        # 必须先「转繁体再查」：康熙表里对现代简化字收录的字头，其值往往是简体画数
        # （如 华=6 而非 14），直查会拿到错值。华→華→14 才对。已验证 14/14 简化字准确。
        for t in cc.convert(ch):
            if t in table:
                return table[t]
        # 转繁后仍未收录，再直查（繁简同形字、或 OpenCC 未覆盖的字）
        return table.get(ch)

    return lookup


def patch_chars(path, lookup, is_list=False, indent=None):
    """给字库补 stroke_kx。is_list: good_chars.json 是 [{'c':..}, ..] 结构。

    indent 需与原文件保持一致，否则重写会让 git diff 爆炸：
      chars.json      原为紧凑格式 -> indent=None
      good_chars.json 原为 indent=1 -> indent=1
    """
    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)
    total = miss = diff = 0
    if is_list:
        for it in data:
            total += 1
            v = lookup(it["c"])
            if v is None:
                v = it.get("stroke")  # 兜底：沿用简体画数
                miss += 1
            elif v != it.get("stroke"):
                diff += 1
            it["stroke_kx"] = v
    else:
        for c, info in data.items():
            total += 1
            v = lookup(c)
            if v is None:
                v = info.get("stroke")
                miss += 1
            elif v != info.get("stroke"):
                diff += 1
            info["stroke_kx"] = v
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    return total, miss, diff


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    table = load_kx_table(csv_path)
    print("康熙笔画表载入：%d 字" % len(table))
    lookup = make_lookup(table)

    # 缩进与原文件保持一致：chars.json 紧凑，good_chars.json indent=1
    for name, is_list, indent in (
        ("chars.json", False, None),
        ("good_chars.json", True, 1),
    ):
        p = os.path.join(HERE, name)
        total, miss, diff = patch_chars(p, lookup, is_list, indent)
        print(
            "%-16s 总 %5d 字 | 补齐 %5d | 兜底 %3d | 康熙≠简体 %5d"
            % (name, total, total - miss, miss, diff)
        )
    print("完成：字库已写入 stroke_kx 字段")


if __name__ == "__main__":
    main()
