"""Bounded static PE32+ import-name inspection; never loads or executes an image."""
import re
import struct

MAX_BYTES=16777216
DLL=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\.dll',re.IGNORECASE)


def inspect(data):
    def need(value):
        if not value: raise ValueError('unsupported_or_invalid_pe_image')
    def u16(offset):
        need(0<=offset<=len(data)-2); return struct.unpack_from('<H',data,offset)[0]
    def u32(offset):
        need(0<=offset<=len(data)-4); return struct.unpack_from('<I',data,offset)[0]
    need(type(data) is bytes and 64<=len(data)<=MAX_BYTES and data[:2]==b'MZ')
    pe=u32(0x3c); need(64<=pe<=len(data)-24 and data[pe:pe+4]==b'PE\0\0')
    coff=pe+4; machine=u16(coff); count=u16(coff+2); optional_size=u16(coff+16); flags=u16(coff+18)
    need(machine in (0x8664,0xaa64) and 1<=count<=96 and flags&2)
    optional=coff+20; need(112<=optional_size<=4096 and optional+optional_size+40*count<=len(data))
    need(u16(optional)==0x20b)
    directories=u32(optional+108); need(2<=directories<=16 and 112+8*directories<=optional_size)
    headers=u32(optional+60); need(optional+optional_size+40*count<=headers<=len(data))
    sections=[]
    for index in range(count):
        section=optional+optional_size+index*40
        virtual_size=u32(section+8); virtual=u32(section+12); raw_size=u32(section+16); raw=u32(section+20)
        if raw_size: need(raw>=headers and raw+raw_size<=len(data))
        need(virtual+max(virtual_size,raw_size)<=0x100000000)
        sections.append((virtual,max(virtual_size,raw_size),raw,raw_size))
    def offset(rva,size):
        need(size>=0 and rva+size<=0x100000000)
        if rva<headers:
            need(rva+size<=headers); return rva
        matches=[(virtual,raw,raw_size) for virtual,span,raw,raw_size in sections if virtual<=rva and rva+size<=virtual+span]
        need(len(matches)==1)
        virtual,raw,raw_size=matches[0]; relative=rva-virtual
        need(relative+size<=raw_size and raw+relative+size<=len(data)); return raw+relative
    # Delay-load imports are deliberately outside this first profile.
    if directories>13: need(u32(optional+112+13*8)==0 and u32(optional+116+13*8)==0)
    rva=u32(optional+120); size=u32(optional+124)
    names=[]
    if rva or size:
        need(rva and 20<=size<=65536)
        offset(rva,size); terminated=False
        for index in range(min(129,size//20)):
            item=offset(rva+index*20,20); fields=struct.unpack_from('<IIIII',data,item)
            if fields==(0,0,0,0,0): terminated=True; break
            need(index<128 and fields[3])
            letters=[]
            for position in range(121):
                value=data[offset(fields[3]+position,1)]
                if value==0: break
                need(33<=value<=126); letters.append(value)
            else: need(False)
            name=bytes(letters).decode('ascii').lower()
            need(DLL.fullmatch(name) and '..' not in name and name not in names)
            names.append(name)
        need(terminated)
    return dict(architecture='x86_64' if machine==0x8664 else 'arm64',isDll=bool(flags&0x2000),imports=sorted(names),
                inspection='static-import-directory-only',dynamicLoadsVerified=False)
