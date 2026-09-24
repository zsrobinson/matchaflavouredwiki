"""Read the 26.3 data format as 26.2's.

Minecraft 26.3 renamed keys in loot tables, predicates, villager trades and advancement criteria.
extract.py (and generate.py, through data.json) reads the 26.2 names, so each file is translated to
them as it is loaded, and data.json has the same shape whichever version the pack is for:
  "modifier": one function, a list, or a minecraft:sequence  -> "functions": a flat list
  "condition": one predicate, a list, or one all_of           -> "conditions": a list
  a predicate's or function's "type"                          -> "condition" / "function"
  a predicate named by its ID ("minecraft:tool/can_silk_touch") -> that predicate file, inlined
  a tag entry's "items": "#tag"                               -> "name": "tag"
  minecraft:match_block with "blocks" and "state"             -> block_state_property, "block", "properties"
  a trade's "given_item_modifier"                             -> "given_item_modifiers"
  a criterion's {"type": "minecraft:entity_properties", "entity": "this", "predicate": P} -> P
  a criterion's other single predicate                        -> a list of predicates
  recipe_crafted's and recipe_unlocked's "recipes": "id"      -> "recipe_id" / "recipe": "id"
A file in the 26.2 format comes back with the same content, so the wiki built from it can't change.
tests/test_mcformat.py has an example of each.
"""
import json


def norm_ns(i):
    return i if ':' in i else 'minecraft:' + i


def renamed(d, names):
    """d with keys renamed, in their places."""
    return {names.get(k, k): v for k, v in d.items()}


class Legacy:
    """find_predicate(id) gives the path of a predicate file, or None. unknown(kind, key, src) is called
    for anything that can't be translated (extract.py's format guard)."""

    def __init__(self, find_predicate, unknown):
        self.find_predicate = find_predicate
        self.unknown = unknown

    def cond(self, c, src, seen=()):
        if isinstance(c, str):  # 26.3: a predicate named by its ID
            pid = norm_ns(c)
            path = self.find_predicate(pid) if pid not in seen else None
            if path:
                with open(path, encoding='utf-8') as f:
                    d = json.load(f)
                if isinstance(d, list):  # a predicate file can be a list: all of them must pass
                    return {'condition': 'minecraft:all_of', 'terms': self.conds(d, src, seen + (pid,))}
                return self.cond(d, src, seen + (pid,))
            self.unknown('condition', 'predicate %s, which does not exist' % pid, src)
            return {'condition': 'minecraft:reference', 'name': pid}
        if not isinstance(c, dict):
            return c  # extract.py's expect_conditions() reports it
        if 'type' in c and 'condition' not in c:
            c = renamed(c, {'type': 'condition'})
        if norm_ns(str(c.get('condition', ''))) == 'minecraft:match_block':  # 26.3's block_state_property
            c = dict(renamed(c, {'blocks': 'block', 'state': 'properties'}), condition='minecraft:block_state_property')
        if 'term' in c:
            c = dict(c, term=self.cond(c['term'], src, seen))
        if 'terms' in c:
            c = dict(c, terms=self.conds(c['terms'], src, seen))
        return c

    def conds(self, x, src, seen=()):
        """"conditions" or "condition" as a list of predicates in the 26.2 format."""
        if x is None:
            return None
        if isinstance(x, dict) and norm_ns(x.get('type', '')) == 'minecraft:all_of' and set(x) == {'type', 'terms'}:
            return self.conds(x['terms'], src, seen)  # 26.3 writes a list of conditions as one all_of
        return [self.cond(c, src, seen) for c in (x if isinstance(x, list) else [x])]

    def fns(self, x, src):
        """"functions" or "modifier" as a flat list of functions in the 26.2 format."""
        out = []
        for f in [] if x is None else x if isinstance(x, list) else [x]:
            if not isinstance(f, dict):
                self.unknown('loot function', 'a function that is not an object', src)
                continue
            if 'type' in f and 'function' not in f:
                f = renamed(f, {'type': 'function'})
            if norm_ns(f.get('function', '')) == 'minecraft:sequence':  # runs its functions in order, as a list does
                for k in set(f) - {'function', 'functions'}:
                    self.unknown('loot sequence', k, src)
                out += self.fns(f.get('functions'), src)
                continue
            if 'condition' in f and 'conditions' not in f:
                f = renamed(f, {'condition': 'conditions'})
            if 'conditions' in f:
                f = dict(f, conditions=self.conds(f['conditions'], src))
            out.append(f)
        return out

    def loot(self, d, src):
        """A loot table, pool or entry, and everything in it, in the 26.2 format."""
        if not isinstance(d, dict):
            return d
        for old, new in (('functions', 'modifier'), ('conditions', 'condition')):
            if old in d and new in d:
                self.unknown('loot', 'both "%s" and "%s"' % (old, new), src)
        tag_items = norm_ns(d.get('type', '')) == 'minecraft:tag' and 'items' in d and 'name' not in d
        d = renamed(d, {'modifier': 'functions', 'condition': 'conditions', **({'items': 'name'} if tag_items else {})})
        if 'functions' in d:
            d['functions'] = self.fns(d['functions'], src)
        if 'conditions' in d:
            d['conditions'] = self.conds(d['conditions'], src)
        for k in ('pools', 'entries', 'children'):
            if isinstance(d.get(k), list):
                d[k] = [self.loot(x, src) for x in d[k]]
        if tag_items and isinstance(d['name'], str):
            d['name'] = d['name'].lstrip('#')  # the 26.2 "name" is the tag's ID without the #
        return d

    def criteria(self, criteria, src):
        """An advancement's criteria in the 26.2 format."""
        if criteria is None:
            return None
        out = {}
        for name, crit in criteria.items():
            conds = crit.get('conditions') if isinstance(crit, dict) else None
            if isinstance(conds, dict):
                short = {}
                for k, v in conds.items():
                    if isinstance(v, dict) and set(v) == {'type', 'entity', 'predicate'} and v['entity'] == 'this' \
                            and norm_ns(v['type']) == 'minecraft:entity_properties':
                        v = v['predicate']
                    elif isinstance(v, dict) and 'type' in v and 'condition' not in v or isinstance(v, list):
                        v = self.conds(v, src)  # 26.3 gives one predicate where 26.2 gave a list
                    short[k] = v
                old = {'minecraft:recipe_crafted': 'recipe_id', 'minecraft:recipe_unlocked': 'recipe'}.get(
                    norm_ns(crit.get('trigger', '')))
                if old and isinstance(short.get('recipes'), str) and old not in short:
                    short = renamed(short, {'recipes': old})  # 26.3 calls both "recipes"
                crit = dict(crit, conditions=short)
            out[name] = crit
        return out

    def trade(self, t, src):
        if 'given_item_modifiers' in t and 'given_item_modifier' in t:
            self.unknown('villager trade', 'both "given_item_modifiers" and "given_item_modifier"', src)
        t = renamed(t, {'given_item_modifier': 'given_item_modifiers'})
        if 'given_item_modifiers' in t:
            t['given_item_modifiers'] = self.fns(t['given_item_modifiers'], src)
        if t.get('merchant_predicate') is not None:
            t['merchant_predicate'] = self.cond(t['merchant_predicate'], src)
        return t
