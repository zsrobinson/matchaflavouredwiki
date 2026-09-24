#!/usr/bin/env python3
"""Extract every entity model from the Minecraft client into tools/render/src/entity_models.json.

Java Edition defines mob shapes in code (the model classes), not in data files, so the renders read
them from the game itself: this downloads the client for tools/mc_version.txt (unobfuscated since 26.1)
and its libraries into source/minecraft-client/, and runs tools/render/ModelDump.java, which calls the
game's LayerDefinitions.createRoots() and writes each layer's parts, pivots, rotations and cubes.

    python3 tools/entity_models.py

Run it when tools/mc_version.txt changes, and commit the JSON. It needs a Java at least as new as the
game's (its version JSON says which); it uses `java` from PATH or $MFW_JAVA if new enough, and
otherwise downloads a JDK from Adoptium into source/.
"""
import json, os, re, shutil, subprocess, sys, tarfile, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MC = open(f'{ROOT}/tools/mc_version.txt').read().strip()
DIR = f'{ROOT}/source/minecraft-client/{MC}'
OUT = f'{ROOT}/tools/render/src/entity_models.json'
MANIFEST = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'


def fetch(url, path):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        urllib.request.urlretrieve(url, path + '.part')
        os.replace(path + '.part', path)
    return path


def java_major(exe):
    try:
        out = subprocess.run([exe, '-version'], capture_output=True, text=True).stderr
    except OSError:
        return 0
    m = re.search(r'version "(\d+)', out)
    return int(m.group(1)) if m else 0


def find_java(need):
    for exe in (os.environ.get('MFW_JAVA'), shutil.which('java')):
        if exe and java_major(exe) >= need:
            return exe
    home = f'{ROOT}/source/jdk-{need}'
    exe = f'{home}/bin/java'
    if not os.path.exists(exe):
        arch = {'x86_64': 'x64', 'amd64': 'x64', 'arm64': 'aarch64', 'aarch64': 'aarch64'}[os.uname().machine.lower()]
        osname = 'mac' if sys.platform == 'darwin' else 'linux'
        tgz = fetch(f'https://api.adoptium.net/v3/binary/latest/{need}/ga/{osname}/{arch}/jdk/hotspot/normal/eclipse',
                    f'{ROOT}/source/jdk-{need}.tar.gz')
        with tarfile.open(tgz) as t:
            top = t.getnames()[0].split('/')[0]
            t.extractall(f'{ROOT}/source')
        shutil.move(f'{ROOT}/source/{top}', home)
        os.remove(tgz)
        if sys.platform == 'darwin':
            os.rename(home, home + '.bundle')
            shutil.move(home + '.bundle/Contents/Home', home)
    return exe


def main():
    manifest = json.load(urllib.request.urlopen(MANIFEST))
    entry = next(v for v in manifest['versions'] if v['id'] == MC)
    version = json.load(urllib.request.urlopen(entry['url']))
    classpath = [fetch(version['downloads']['client']['url'], f'{DIR}/client.jar')]
    for lib in version['libraries']:
        art = lib.get('downloads', {}).get('artifact')
        if not art or 'natives' in art['path']:
            continue
        classpath.append(fetch(art['url'], f'{DIR}/libs/{os.path.basename(art["path"])}'))
    java = find_java(version['javaVersion']['majorVersion'])
    run = subprocess.run([java, '-cp', os.pathsep.join(classpath), f'{ROOT}/tools/render/ModelDump.java'],
                         capture_output=True, text=True, cwd=DIR)
    if run.returncode:
        sys.exit(run.stderr)
    models = json.loads(run.stdout)
    with open(OUT, 'w') as f:
        f.write('{\n' + ',\n'.join(f'{json.dumps(k)}:{json.dumps(v, separators=(",", ":"))}' for k, v in models.items()) + '\n}\n')
    print(f'{len(models)} entity models from Minecraft {MC} -> {os.path.relpath(OUT, ROOT)}')


if __name__ == '__main__':
    main()
