#!/usr/bin/env python3
"""Research helper: print everything the extracted data knows about an item, loot table,
enchantment, advancement or profession. Run tools/extract.py first.

  tools/query.py item "Pumpkin Empanada"     components, recipes, uses, sources, trades
  tools/query.py search pumpkin              names containing a string
  tools/query.py loot minecraft:entities/zombie
  tools/query.py ench matcha:warding_1
  tools/query.py adv matcha:tutorial/...     (or: adv search <text>)
  tools/query.py trades farmer
  tools/query.py renames                     vanilla -> pack names
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
D = json.load(open(os.path.join(ROOT, 'build', 'data.json'), encoding='utf-8'))


def p(x):
    print(json.dumps(x, indent=1, ensure_ascii=False))


def main(a):
    if not a:
        print(__doc__)
        return
    cmd = a[0]
    if cmd == 'search':
        q = ' '.join(a[1:]).lower()
        for k in sorted(D['items']):
            if q in k.lower():
                print(k)
    elif cmd == 'item':
        import generate as g
        name = ' '.join(a[1:])
        it = D['items'].get(name)
        if not it:
            print('not found; try search')
            return
        print('== components (pack) =='); p(it)
        print('== recipes producing =='); p([{k: r[k] for k in r if k not in ('key',)} for r in g.producing(name)])
        print('== used in =='); [print(' ', r['id'], '->', r['output']['name'], '(%s)' % r['station']) for r in g.USES.get(name, [])]
        print('== loot sources =='); [print(' ', s[2], g.pct(g.chance_at_least_one(s[3], s[6])), s[4], s[5]) for s in g.SOURCES.get(name, [])]
        print('== sold by =='); [print(' ', pr, lk, t['wants'], t.get('additional_wants')) for pr, lk, t in g.TRADE_GIVES.get(name, [])]
        print('== bought by =='); [print(' ', pr, lk, t['wants'], '->', t['gives']) for pr, lk, t in g.TRADE_WANTS.get(name, [])]
    elif cmd == 'loot':
        p(D['loot'].get(a[1]))
    elif cmd == 'ench':
        e = D['enchantments'].get(a[1]); p(e)
    elif cmd == 'adv':
        if a[1] == 'search':
            q = ' '.join(a[2:]).lower()
            for k, v in D['advancements'].items():
                if q in json.dumps(v, ensure_ascii=False).lower():
                    print(k, '|', v.get('title'), '|', v.get('description'))
        else:
            p(D['advancements'].get(a[1]))
    elif cmd == 'trades':
        p(D['trades'].get(a[1]))
    elif cmd == 'renames':
        for k, v in sorted(D['renames'].items()):
            print('%-60s %-35s -> %s' % (k, v['vanilla'], v['pack']))
    else:
        print(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
