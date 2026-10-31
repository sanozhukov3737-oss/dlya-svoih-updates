"""Prepare a compact, reproducible transfer of the exact reviewed catalog ZIP."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib
from restore_catalog199_candidate import ROOT, EXPECTED_BYTES, EXPECTED_SHA256

def make(archive):
    assert archive.stat().st_size == EXPECTED_BYTES
    with archive.open('rb') as stream:
        assert hashlib.file_digest(stream,'sha256').hexdigest() == EXPECTED_SHA256
    output = ROOT/'content/releases/catalog199'
    output.mkdir(parents=True,exist_ok=True)
    payload = bytearray()
    segments = []
    reused = 0
    def literal(data):
        offset = len(payload)
        payload.extend(data)
        if segments and segments[-1][0]=='literal' and segments[-1][1]+segments[-1][2]==offset:
            segments[-1][2] += len(data)
        else:
            segments.append(['literal',offset,len(data)])
    with archive.open('rb') as source, zipfile.ZipFile(archive) as pack:
        cursor = 0
        for info in pack.infolist():
            assert cursor == info.header_offset
            source.seek(cursor)
            fixed = source.read(30)
            name_length,extra_length = struct.unpack_from('<HH',fixed,26)
            header = fixed+source.read(name_length+extra_length)
            raw = source.read(info.compress_size)
            cursor += len(header)+len(raw)
            literal(header)
            local = ROOT/'app/src/main/assets'/info.filename
            matches = False
            if info.filename.startswith(('images/','thumbs/')) and local.is_file():
                encoder = zlib.compressobj(9,zlib.DEFLATED,-15)
                data = encoder.compress(local.read_bytes())+encoder.flush()
                matches = data == raw
            if matches:
                segments.append(['asset',info.filename,len(raw),hashlib.sha256(raw).hexdigest()])
                reused += 1
            else:
                literal(raw)
        source.seek(cursor)
        literal(source.read())
    parts = []
    size = 512*1024
    for number,offset in enumerate(range(0,len(payload),size)):
        data = payload[offset:offset+size]
        path = output/f'part-{number:03d}.bin'
        path.write_bytes(data)
        parts.append(dict(path=path.name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    recipe = dict(formatVersion=1,baselineCommit='17afade25fcaea88fdd50e0e936bfaa17b0da4c6',
        bytes=EXPECTED_BYTES,sha256=EXPECTED_SHA256,parts=parts,segments=segments)
    (output/'recipe.json').write_text(json.dumps(recipe,separators=(',',':'))+'\n')
    print(json.dumps(dict(reusedFiles=reused,payloadBytes=len(payload),parts=len(parts))))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    make(parser.parse_args().candidate)
