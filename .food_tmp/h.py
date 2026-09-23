import os
G='/Users/zsrobinson/code/matcha-wiki/wiki/generated/Template/'
OUT='/Users/zsrobinson/code/matcha-wiki/wiki/pages/Main/'
def has(kind,name): return os.path.exists(G+'Data%2F'+kind+'%2F'+name.replace('/','%2F')+'.wiki')
def S(p): return '<ref>{{Source|'+p+'}}</ref>'
def R(p): return 'MF_datapack/data/matcha/recipe/'+p+'.json'
def V(q,v='video'):
    return '<ref>{{Cite video|quote='+q+'}}</ref>' if v=='video' else '<ref>{{Cite changelog|'+v+'|quote='+q+'}}</ref>'
def H(*lines): return '{{History|\n'+'\n'.join('{{History line|%s|%s}}'%l for l in lines)+'\n}}'
def write(title,text):
    open(OUT+title.replace('/','%2F')+'.wiki','w').write(text.strip()+'\n')
def redirect(title,target,cat=None):
    write(title,'#REDIRECT [['+target+']]'+('\n[[Category:'+cat+']]' if cat else ''))
def page(title, lead, item=None, vanilla=None, obtaining=None, food=None, usage=None, behavior=None,
         history=None, trivia=None, see=None, cats=('Food',), infobox_extra='', sections_after=None, spoiler=False):
    item=item or title
    o=[]
    if vanilla: o.append('{{Vanilla|'+vanilla+'}}' if vanilla!=True else '{{Vanilla}}')
    o.append('{{Infobox auto'+('|'+item if item!=title else '')+infobox_extra+'}}')
    if spoiler: o.append('{{Spoiler}}')
    o.append(lead.strip())
    o.append('== Obtaining ==')
    if obtaining: o.append(obtaining.strip())
    else:
        if has('Recipes',item): o.append('{{Recipes'+('|'+item if item!=title else '')+'}}')
        if has('Sources',item): o.append('{{Sources'+('|'+item if item!=title else '')+'}}')
    if o[-1]=='== Obtaining ==': o.pop()
    o.append('== Usage ==')
    if food: o.append('=== Food ===\n'+food.strip())
    if usage: o.append(usage.strip())
    if has('Uses',item) and '{{Uses' not in (usage or ''):
        o.append('=== Crafting ingredient ===\n{{Uses'+('|'+item if item!=title else '')+'}}')
    if o[-1]=='== Usage ==': o.pop()
    if behavior: o.append('== Behavior ==\n'+behavior.strip())
    if sections_after: o.append(sections_after.strip())
    if history: o.append('== History ==\n'+history)
    if trivia: o.append('== Trivia ==\n'+'\n'.join('* '+t for t in trivia))
    if see: o.append('== See also ==\n'+'\n'.join('* [['+s+']]' for s in see))
    body='\n\n'.join(o)
    if '<ref' in body: body+='\n\n== References ==\n{{Reflist}}'
    body+='\n\n{{Navbox food}}\n'+'\n'.join('[[Category:'+c+']]' for c in cats)
    write(title,body)
