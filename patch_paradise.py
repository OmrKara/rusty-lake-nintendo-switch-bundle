"""Reproducible, fail-closed patches for the owned Paradise Steam 1.0.6 SWF.

No game data is embedded in this script. Game logic is preserved outside Main.
Code edits preserve instruction lengths, branch offsets and exception ranges.
Existing embedded font definitions/linkages are preloaded before Main.
"""
from pathlib import Path
import argparse
from collections import Counter
import hashlib
import json
import shutil
import struct
import zlib

SOURCE_SHA256 = '18386cacc08692b2b4245b3f7dec1be59431fa66ad19b33d17c53f0fdbb934cd'


def u30(value):
    out = bytearray()
    while True:
        chunk = value & 127
        value >>= 7
        out.append(chunk | (128 if value else 0))
        if not value:
            return bytes(out)


class ABC:
    def __init__(self, data):
        self.data = data
        self.p = 4
        self.edits = []
        self.strings = ['']
        self.namespaces = [None]
        self.namespace_sets = [None]
        self.multinames = [None]
        self.multiname_spans = [None]
        self.instances = []
        self.methods = []
        self.method_params = []
        self.bodies = {}
        for _ in range(2):
            for _ in range(max(0, self.num() - 1)):
                self.num()
        self.take(max(0, self.num() - 1) * 8)
        for _ in range(max(0, self.num() - 1)):
            self.strings.append(self.take(self.num()).decode('utf-8'))
        for _ in range(max(0, self.num() - 1)):
            self.namespaces.append((self.byte(), self.num()))
        for _ in range(max(0, self.num() - 1)):
            self.namespace_sets.append([self.num() for _ in range(self.num())])
        for _ in range(max(0, self.num() - 1)):
            entry_start = self.p
            kind = self.byte()
            if kind in (7, 13):
                value = (kind, self.num(), self.num())
            elif kind in (15, 16):
                value = (kind, 0, self.num())
            elif kind in (17, 18):
                value = (kind, 0, 0)
            elif kind in (9, 14):
                name = self.num()
                namespace_set = self.num()
                value = (kind, 0, name, namespace_set)
            elif kind in (27, 28):
                self.num()
                value = (kind, 0, 0)
            elif kind == 29:
                base = self.num()
                for _ in range(self.num()):
                    self.num()
                value = (kind, 0, 0)
            else:
                raise ValueError(f'Unsupported multiname kind {kind}')
            self.multinames.append(value)
            self.multiname_spans.append((entry_start, self.p))
        for _ in range(self.num()):
            count = self.num()
            self.num()
            params = []
            for _ in range(count):
                start = self.p
                param_type = self.num()
                params.append((start, self.p, param_type))
            name = self.num()
            flags = self.byte()
            if flags & 8:
                for _ in range(self.num()):
                    self.num()
                    self.byte()
            if flags & 128:
                for _ in range(count):
                    self.num()
            self.methods.append(self.strings[name])
            self.method_params.append(params)
        for _ in range(self.num()):
            self.num()
            count = self.num()
            for _ in range(count * 2):
                self.num()
        class_count = self.num()
        for _ in range(class_count):
            name = self.num()
            self.num()
            flags = self.byte()
            if flags & 8:
                self.num()
            for _ in range(self.num()):
                self.num()
            init = self.num()
            traits = self.traits()
            self.instances.append({'name': name, 'init': init, 'traits': traits})
        for _ in range(class_count):
            self.num()
            self.traits()
        for _ in range(self.num()):
            self.num()
            self.traits()
        for _ in range(self.num()):
            method = self.num()
            for _ in range(4):
                self.num()
            size = self.num()
            start = self.p
            self.take(size)
            self.bodies[method] = (start, size)
            for _ in range(self.num()):
                for _ in range(5):
                    self.num()
            self.traits()
        if self.p != len(data):
            raise ValueError('ABC parse did not consume the whole file')

    def byte(self):
        value = self.data[self.p]
        self.p += 1
        return value

    def take(self, count):
        start = self.p
        self.p += count
        if self.p > len(self.data):
            raise ValueError('Truncated ABC')
        return self.data[start:self.p]

    def num(self):
        value = 0
        for shift in range(0, 35, 7):
            b = self.byte()
            value |= (b & 127) << shift
            if not b & 128:
                return value
        raise ValueError('Invalid variable integer')

    def traits(self):
        result = []
        for _ in range(self.num()):
            name = self.num()
            attrs = self.byte()
            kind = attrs & 15
            trait = {'name': name, 'kind': kind}
            if kind in (0, 6):
                self.num()
                trait['type_start'] = self.p
                trait['type'] = self.num()
                trait['type_end'] = self.p
                trait['value'] = self.num()
                if trait['value']:
                    trait['value_kind_pos'] = self.p
                    trait['value_kind'] = self.byte()
            elif kind in (1, 2, 3):
                self.num()
                trait['method'] = self.num()
            elif kind in (4, 5):
                self.num()
                self.num()
            else:
                raise ValueError(f'Unsupported trait kind {kind}')
            if attrs & 64:
                for _ in range(self.num()):
                    self.num()
            result.append(trait)
        return result

    def name(self, index):
        entry = self.multinames[index]
        return self.strings[entry[2]] if entry else ''

    def qname(self, namespace, name):
        matches = []
        for i, entry in enumerate(self.multinames[1:], 1):
            if entry[0] in (7, 13) and self.strings[entry[2]] == name:
                ns = self.namespaces[entry[1]]
                if ns[0] == 22 and self.strings[ns[1]] == namespace:
                    matches.append(i)
        if len(matches) != 1:
            raise ValueError(f'Expected one QName {namespace}:{name}, got {matches}')
        return matches[0]

    def edit(self, start, end, replacement, label):
        if any(start < e and end > s for s, e, _, _ in self.edits):
            raise ValueError('Overlapping edit: ' + label)
        self.edits.append((start, end, replacement, label))

    def replace_code(self, method, old, new, label, count=1, branch_tail=None):
        start, size = self.bodies[method]
        code = self.data[start:start + size]
        positions = []
        pos = 0
        while True:
            pos = code.find(old, pos)
            if pos < 0:
                break
            if branch_tail is None or code[pos + len(old) + 3:].startswith(branch_tail):
                positions.append(pos)
            pos += len(old)
        if len(positions) != count:
            raise ValueError(f'{label}: expected {count} bytecode matches, got {positions}')
        if len(new) > len(old):
            raise ValueError('Replacement must fit original bytecode')
        for pos in positions:
            self.edit(start + pos, start + pos + len(old),
                      new + b'\x02' * (len(old) - len(new)), label)

    def patch(self):
        # Verification resolves File-typed signatures even in uncalled helper methods.
        # Alias the dormant AIR File QName to Object in every ABC block.
        for index, entry in enumerate(self.multinames[1:], 1):
            if entry[0] == 7 and self.strings[entry[2]] == 'File':
                ns = self.namespaces[entry[1]]
                if self.strings[ns[1]] == 'flash.filesystem':
                    obj = self.qname('', 'Object')
                    start, end = self.multiname_spans[index]
                    obj_start, obj_end = self.multiname_spans[obj]
                    self.edit(start, end, self.data[obj_start:obj_end],
                              'Remove AIR File type from dormant helper signatures')
        mains = [x for x in self.instances if self.name(x['name']) == 'Main']
        if not mains:
            return self.apply_edits()
        if len(mains) != 1:
            raise ValueError('Ambiguous Main class')
        main = mains[0]
        traits = {self.name(t['name']): t for t in main['traits']}
        for name in ('steamOn', 'trackingOn'):
            trait = traits[name]
            if trait['value_kind'] != 11:
                raise ValueError(f'Expected true default for {name}')
            p = trait['value_kind_pos']
            self.edit(p, p + 1, b'\x0a', f'{name}=false')
        trait = traits['basePath']
        if self.name(trait['type']) != 'File':
            raise ValueError('Expected AIR File type on Main.basePath')
        self.edit(trait['type_start'], trait['type_end'], b'\x00', 'basePath uses wildcard type')
        init = main['init']
        q = lambda n: u30(self.qname('', n))
        old = b'\x60' + q('SaveGameClass') + b'\x60' + q('SaveGameClass')
        old += b'\x46' + q('getOS') + b'\x00\x46' + q('getBaseFile') + b'\x01'
        self.replace_code(init, old, b'\x20', 'Skip AIR filesystem initialization')
        # Preserve onMobile=0 and the desktop UI. Only storage branch comparisons change.
        old = b'\xd0\x66' + q('onMobile') + b'\x24\x00\x14'
        new = b'\xd0\x66' + q('onMobile') + b'\x24\xff\x14'
        self.replace_code(init, old, new, 'Use existing SharedObject load path',
                          branch_tail=b'\xf0' + u30(135) + b'\xd0\x60' + q('SaveGameClass'))
        self.replace_code(traits['saveToDisk']['method'], old, new, 'Use existing SharedObject flush path')
        tracker = u30(self.qname('com.google.analytics', 'GATracker'))
        # Keep the enclosing receiver and initproperty; eliminate analytics construction.
        old = b'\x5d' + tracker + b'\xd0\x65\x01\x6c\x02\x2c'
        old += u30(self.strings.index('AS3')) + b'\x60' + q('DEBUG')
        old += b'\x4a' + tracker + b'\x04'
        self.replace_code(init, old, b'\x20', 'Do not construct analytics tracker', count=2)
        # Reuse the original mobile Back routine as a desktop right-click handler.
        # The runtime maps Switch B to right click; A and ZR stay left clicks.
        handler = self.methods.index('Main/$construct/onKeyDown')
        old = b'\xd0\x66' + q('onMobile') + b'\x24\x01\x14'
        new = b'\xd0\x66' + q('onMobile') + b'\x24\x00\x14'
        self.replace_code(init, old, new, 'Create original Back handler in desktop mode',
                          branch_tail=b'\xf0' + u30(158) + b'\x65\x01\x40' + u30(handler))
        params = self.method_params[handler]
        if len(params) != 1 or self.name(params[0][2]) != 'KeyboardEvent':
            raise ValueError('Unexpected Back handler signature')
        start, end, _ = params[0]
        self.edit(start, end, u30(self.qname('flash.events', 'MouseEvent')),
                  'Accept MouseEvent in Back handler')
        old = b'\xd1\x66' + q('keyCode') + b'\x60' + u30(self.qname('flash.ui', 'Keyboard'))
        old += b'\x66' + q('BACK')
        self.replace_code(handler, old, b'\x26\x26', 'Handle right click without AIR Back key constant')
        old = b'\x60' + u30(self.qname('flash.events', 'MouseEvent'))
        old += b'\x66' + q('RIGHT_CLICK') + b'\x65\x01\x6c\x01'
        new = old[:-1] + b'\x0a'
        self.replace_code(init, old, new, 'Bind right click to Back instead of empty handler')
        return self.apply_edits()

    def apply_edits(self):
        result = self.data
        for start, end, replacement, _ in sorted(self.edits, reverse=True):
            result = result[:start] + replacement + result[end:]
        ABC(result)  # Structural validation after all edits.
        return result, [label for _, _, _, label in self.edits]


def symbols(payload):
    count = int.from_bytes(payload[:2], 'little')
    p = 2
    result = []
    for _ in range(count):
        cid = int.from_bytes(payload[p:p+2], 'little')
        p += 2
        end = payload.index(0, p)
        result.append((cid, payload[p:end].decode('utf8')))
        p = end + 1
    if p != len(payload):
        raise ValueError('Unexpected SymbolClass bytes')
    return result


def symbol_bytes(entries):
    return struct.pack('<H', len(entries)) + b''.join(
        struct.pack('<H', cid) + name.encode('utf8') + b'\0' for cid, name in entries)


def preload_fonts(tags):
    wanted = {'Lettertype0', 'Lettertype1', 'Lettertype2',
              'Lettertype5', 'Lettertype10', 'Lettertype12'}
    bindings = [(cid, name) for tag, payload in tags if tag == 76
                for cid, name in symbols(payload) if name in wanted]
    if len(bindings) != 6 or {name for _, name in bindings} != wanted:
        raise ValueError('Expected six embedded font class linkages')
    ids = {cid for cid, _ in bindings}
    font_tags = []
    remaining = []
    for tag, payload in tags:
        if tag in (75, 73, 88) and int.from_bytes(payload[:2], 'little') in ids:
            font_tags.append((tag, payload))
            continue
        if tag == 76:
            entries = [(cid, name) for cid, name in symbols(payload) if name not in wanted]
            if not entries:
                continue
            payload = symbol_bytes(entries)
        remaining.append((tag, payload))
    if len(font_tags) != 18:
        raise ValueError('Expected definition/zones/name tags for all six fonts')
    roots = [i for i, (tag, payload) in enumerate(remaining)
             if tag == 76 and (0, 'Main') in symbols(payload)]
    if len(roots) != 1:
        raise ValueError('Expected one Main root linkage')
    at = roots[0]
    return remaining[:at] + font_tags + [(76, symbol_bytes(bindings))] + remaining[at:]


def read_swf(raw):
    if raw[:3] not in (b'CWS', b'FWS'):
        raise ValueError('Only CWS/FWS SWFs are supported')
    body = zlib.decompress(raw[8:]) if raw[:3] == b'CWS' else raw[8:]
    if len(body) + 8 != int.from_bytes(raw[4:8], 'little'):
        raise ValueError('SWF length mismatch')
    pos = (5 + (body[0] >> 3) * 4 + 7) // 8 + 4
    header = body[:pos]
    tags = []
    while pos + 2 <= len(body):
        value = int.from_bytes(body[pos:pos+2], 'little')
        pos += 2
        tag, size = value >> 6, value & 63
        if size == 63:
            size = int.from_bytes(body[pos:pos+4], 'little')
            pos += 4
        payload = body[pos:pos+size]
        if len(payload) != size:
            raise ValueError('Truncated SWF tag')
        pos += size
        tags.append((tag, payload))
        if tag == 0:
            if size != 0 or pos != len(body):
                raise ValueError('Invalid SWF End tag')
            return header, tags
    raise ValueError('Missing SWF End tag')


def verify_preservation(original, patched):
    old_header, old_tags = read_swf(original)
    new_header, new_tags = read_swf(patched)
    if old_header != new_header:
        raise ValueError('Movie dimensions/timing changed')
    assets = lambda tags: Counter((t, hashlib.sha256(p).digest())
                                  for t, p in tags if t not in (76, 82))
    if assets(old_tags) != assets(new_tags):
        raise ValueError('Non-code asset payloads changed')
    links = lambda tags: Counter(pair for t, p in tags if t == 76 for pair in symbols(p))
    if links(old_tags) != links(new_tags):
        raise ValueError('SymbolClass mappings changed')
    abcs = lambda tags: [ABC(p[p.index(0, 4)+1:]) for t, p in tags if t == 82]
    old_abcs, new_abcs = abcs(old_tags), abcs(new_tags)
    if len(old_abcs) != len(new_abcs):
        raise ValueError('ABC count changed')
    changed = []
    unchanged = 0
    for before, after in zip(old_abcs, new_abcs):
        if before.methods != after.methods or before.bodies.keys() != after.bodies.keys():
            raise ValueError('Method structure changed')
        for mid, (start, size) in before.bodies.items():
            after_start, after_size = after.bodies[mid]
            if before.data[start:start+size] == after.data[after_start:after_start+after_size]:
                unchanged += 1
            else:
                changed.append(before.methods[mid])
    if Counter(changed) != Counter(['Main/Main', 'Main/saveToDisk', 'Main/$construct/onKeyDown']):
        raise ValueError(f'Unexpected changed method bodies: {changed}')
    return {'asset_payloads_preserved': True, 'symbol_bindings_preserved': True,
            'movie_dimensions_and_timing_preserved': True,
            'changed_method_bodies': changed, 'unchanged_method_bodies': unchanged,
            'abc_blocks': len(old_abcs)}


def patch_swf(raw):
    if raw[:3] not in (b'CWS', b'FWS'):
        raise ValueError('Only CWS/FWS SWFs are supported')
    body = zlib.decompress(raw[8:]) if raw[:3] == b'CWS' else raw[8:]
    if len(body) + 8 != int.from_bytes(raw[4:8], 'little'):
        raise ValueError('SWF length mismatch')
    pos = (5 + (body[0] >> 3) * 4 + 7) // 8 + 4
    movie_header = body[:pos]
    tags = []
    changes = []
    while pos < len(body):
        header = int.from_bytes(body[pos:pos + 2], 'little')
        pos += 2
        tag, size = header >> 6, header & 63
        if size == 63:
            size = int.from_bytes(body[pos:pos + 4], 'little')
            pos += 4
        payload = body[pos:pos + size]
        if len(payload) != size:
            raise ValueError('Truncated SWF tag')
        pos += size
        if tag == 82:
            abc_start = payload.index(0, 4) + 1
            patched, labels = ABC(payload[abc_start:]).patch()
            payload = payload[:abc_start] + patched
            changes.extend(labels)
        tags.append((tag, payload))
        if tag == 0:
            if pos != len(body):
                raise ValueError('Unexpected bytes after End tag')
            break
    if len(changes) != 13:
        raise ValueError(f'Expected thirteen edits, got {changes}')
    tags = preload_fonts(tags)
    changes.append('Preload six original embedded fonts before Main construction')
    out = bytearray(movie_header)
    for tag, payload in tags:
        if len(payload) < 63:
            out += struct.pack('<H', (tag << 6) | len(payload))
        else:
            out += struct.pack('<HI', (tag << 6) | 63, len(payload))
        out += payload
    return b'CWS' + raw[3:4] + struct.pack('<I', len(out) + 8) + zlib.compress(out, 9), changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Original Paradise.swf')
    parser.add_argument('--out', type=Path, default=Path(__file__).parent / 'game')
    args = parser.parse_args()
    source = args.source.resolve()
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        raise SystemExit('Unrecognized source SWF; refusing to patch this build.')
    target = args.out.resolve()
    if target == source.parent:
        raise SystemExit('Output must not be the original game directory.')
    translated = source.parent / 'paradise-translations.xml'
    if not translated.is_file():
        raise SystemExit('Missing paradise-translations.xml next to source SWF.')
    patched, changes = patch_swf(raw)
    verification = verify_preservation(raw, patched)
    target.mkdir(parents=True, exist_ok=True)
    (target / 'Paradise.swf').write_bytes(patched)
    shutil.copy2(translated, target / translated.name)
    report = {'build': 'Paradise Steam 1.0.6 compatibility patch v0.3',
              'source_sha256': digest, 'patched_sha256': hashlib.sha256(patched).hexdigest(),
              'changes': changes, 'verification': verification,
              'status': 'UNVERIFIED ON SWITCH'}
    (target / 'build-report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
