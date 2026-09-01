"""
纯本地校验/规整「昵称/梗黑名单」：data/nickname_blacklist.json
- 不调用任何 AI（内容由人工直接撰写，见文件内 note）。
- 作用：检查每条规则结构是否合法、去重、按 kind+match 排序后写回，保证文件整洁可用。
- 用法：python data/gen_blacklist.py   （迭代时直接改 JSON 即可，本脚本仅做校验规整）
规则字段：
  match   命中串（中文，对「名」不含姓做包含匹配；或 pinyin 类的 ascii 全拼）
  kind    seq(名含 match) / pinyin(名全拼==match)
  penalty 命中后扣总分
  note    命中时给用户的提示文案
"""
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'nickname_blacklist.json')


def normalize(doc):
    rules = doc.get('rules', [])
    clean, seen = [], set()
    for r in rules:
        if not isinstance(r, dict):
            print('  skip: 非对象', r)
            continue
        m = r.get('match')
        if not m:
            print('  skip: 缺 match', r)
            continue
        kind = r.get('kind', 'seq')
        if kind not in ('seq', 'pinyin'):
            print('  skip: 未知 kind', r)
            continue
        if kind == 'seq' and len(m) < 2:   # 防止单字误伤
            print('  skip: seq 单字', r)
            continue
        key = (kind, m)
        if key in seen:
            print('  dedupe:', key)
            continue
        seen.add(key)
        clean.append({
            'match': m,
            'kind': kind,
            'penalty': int(r.get('penalty', 30)),
            'note': r.get('note', m),
        })
    clean.sort(key=lambda x: (x['kind'] != 'seq', x['kind'], x['match']))
    return clean


def main():
    if not os.path.exists(OUT):
        print('文件不存在:', OUT)
        return
    with open(OUT, encoding='utf-8') as f:
        doc = json.load(f)
    clean = normalize(doc)
    new_doc = {
        'version': doc.get('version', ''),
        'note': doc.get('note', ''),
        'rules': clean,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(new_doc, f, ensure_ascii=False, indent=2)
    print('OK ->', len(clean), '条规则已规整写回', OUT)
    by_kind = {}
    for r in clean:
        by_kind[r['kind']] = by_kind.get(r['kind'], 0) + 1
    print('按 kind 统计:', by_kind)


if __name__ == '__main__':
    main()
