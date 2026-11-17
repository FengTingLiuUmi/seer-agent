#!/usr/bin/env python3
"""Minimal SWF/ABC reader + AVM2 disassembler (no deps).

usage: avm2.py <swf> list [substr]
       avm2.py <swf> dump <class-substr> [method-substr]
"""
import sys, struct, zlib

OPS = {
 0x00:('nop',''),0x01:('bkpt',''),0x02:('throw',''),0x03:('hasnext2','nn'),
 0x04:('getsuper','m'),0x05:('setsuper','m'),0x06:('dxns','F'),0x07:('dxnslate',''),
 0x08:('kill','n'),0x09:('label',''),
 0x0c:('ifnlt','s'),0x0d:('ifnle','s'),0x0e:('ifngt','s'),0x0f:('ifnge','s'),
 0x10:('jump','s'),0x11:('iftrue','s'),0x12:('iffalse','s'),0x13:('ifeq','s'),
 0x14:('ifne','s'),0x15:('iflt','s'),0x16:('ifle','s'),0x17:('ifgt','s'),
 0x18:('ifge','s'),0x19:('ifstricteq','s'),0x1a:('ifstrictne','s'),
 0x1b:('lookupswitch','W'),
 0x1c:('pushwith',''),0x1d:('popscope',''),0x1e:('nextname',''),0x1f:('hasnext',''),
 0x20:('pushnull',''),0x21:('pushundefined',''),0x23:('nextvalue',''),
 0x24:('pushbyte','i'),0x25:('pushshort','n'),0x26:('pushtrue',''),0x27:('pushfalse',''),
 0x28:('pushnan',''),0x29:('pop',''),0x2a:('dup',''),0x2b:('swap',''),
 0x2c:('pushstring','F'),0x2d:('pushint','I'),0x2e:('pushuint','U'),0x2f:('pushdouble','D'),
 0x30:('pushscope',''),0x31:('pushnamespace','N'),
 0x36:('findpropstrict','m'),0x37:('findproperty','m'),0x38:('finddef','m'),
 0x3a:('setproperty','m'),0x3b:('getlocal','n'),0x3c:('setlocal','n'),
 0x3d:('getglobalscope',''),0x3e:('getscopeobject','b'),0x3f:('getproperty','m'),
 0x40:('getouterscope','n'),0x41:('initproperty','m'),
 0x47:('returnvoid',''),0x48:('returnvalue',''),
 0x49:('constructsuper','n'),0x4a:('constructprop','mn'),0x4b:('callsuper','nn'),
 0x4c:('callproperty','mn'),0x4d:('callproplex','mn'),0x4e:('callsupervoid','nn'),
 0x4f:('callpropvoid','mn'),
 0x53:('applytype','n'),0x55:('newobject','n'),0x56:('newarray','n'),
 0x58:('newclass','n'),0x59:('newfunction','n'),
 0x60:('getlex','m'),0x61:('setproperty','m'),0x62:('getlocal','n'),0x63:('setlocal','n'),
 0x64:('getglobalscope',''),0x65:('getscopeobject','b'),0x66:('getproperty','m'),
 0x67:('getouterscope','n'),0x68:('initproperty','m'),0x6a:('deleteproperty','m'),
 0x6c:('getdescendants','m'),0x6d:('delete','m'),0x6e:('applytype','n'),
 0x6f:('checkfilter',''),0x70:('coerce','m'),0x71:('coerce_a',''),0x72:('coerce_s',''),
 0x73:('astype','m'),0x74:('astypelate',''),
 0x80:('coerce','m'),0x81:('coerce_a',''),0x82:('coerce_s',''),0x83:('astype','m'),
 0x84:('astypelate',''),0x85:('coerce','m'),0x86:('coerce_s',''),0x87:('astype','m'),
 0x90:('negate',''),0x91:('increment',''),0x92:('inclocal','n'),0x93:('decrement',''),
 0x94:('declocal','n'),0x95:('typeof',''),0x96:('not',''),0x97:('bitnot',''),
 0xa0:('add',''),0xa1:('subtract',''),0xa2:('multiply',''),0xa3:('divide',''),
 0xa4:('modulo',''),0xa5:('lshift',''),0xa6:('rshift',''),0xa7:('urshift',''),
 0xa8:('bitand',''),0xa9:('bitor',''),0xaa:('bitxor',''),0xab:('equals',''),
 0xac:('strictequals',''),0xad:('lessthan',''),0xae:('lessequals',''),
 0xaf:('greaterthan',''),0xb0:('greaterequals',''),0xb1:('instanceof',''),
 0xb2:('istype','m'),0xb3:('istypelate',''),0xb4:('in',''),
 0xc0:('increment_i',''),0xc1:('decrement_i',''),0xc2:('inclocal_i','n'),
 0xc3:('declocal_i','n'),0xc4:('negate_i',''),0xc5:('add_i',''),0xc6:('subtract_i',''),
 0xc7:('multiply_i',''),0xc8:('divide_i',''),0xc9:('modulo_i',''),
 0xd0:('getlocal_0',''),0xd1:('getlocal_1',''),0xd2:('getlocal_2',''),0xd3:('getlocal_3',''),
 0xd4:('setlocal_0',''),0xd5:('setlocal_1',''),0xd6:('setlocal_2',''),0xd7:('setlocal_3',''),
 0xef:('debug','bbbbn'),0xf0:('debugline','n'),0xf1:('debugfile','F'),
 0xf2:('bkptline','n'),0xf3:('timestamp',''),
}


class R:
    def __init__(s, d, p=0): s.d = d; s.p = p
    def u8(s): v = s.d[s.p]; s.p += 1; return v
    def u16(s): v = struct.unpack_from('<H', s.d, s.p)[0]; s.p += 2; return v
    def u32(s): v = struct.unpack_from('<I', s.d, s.p)[0]; s.p += 4; return v
    def s32(s): v = struct.unpack_from('<i', s.d, s.p)[0]; s.p += 4; return v
    def d64(s): v = struct.unpack_from('<d', s.d, s.p)[0]; s.p += 8; return v
    def s24(s):
        b = s.d[s.p:s.p + 3]; s.p += 3
        v = b[0] | (b[1] << 8) | (b[2] << 16)
        return v - (1 << 24) if v & 0x800000 else v
    def i8(s):
        v = s.u8(); return v - 256 if v & 0x80 else v
    def u30(s):
        r = 0
        for i in range(4):
            b = s.u8()
            if i < 3:
                r |= (b & 0x7f) << (7 * i)
                if not (b & 0x80): return r
            else:
                return r | (b << 21)
    def raw(s, n): v = s.d[s.p:s.p + n]; s.p += n; return v


class ABC:
    def __init__(s, d):
        r = R(d)
        s.major = (r.u16(), r.u16())
        s.ints = [0]; n = r.u30()
        for _ in range(max(0, n - 1)): s.ints.append(r.s32())
        s.uints = [0]; n = r.u30()
        for _ in range(max(0, n - 1)): s.uints.append(r.u32())
        s.dbls = [0.0]; n = r.u30()
        for _ in range(max(0, n - 1)): s.dbls.append(r.d64())
        s.strs = [None]; n = r.u30()
        for _ in range(max(0, n - 1)): s.strs.append(r.raw(r.u30()).decode('utf-8', 'replace'))
        s.nss = [None]; n = r.u30()
        for _ in range(max(0, n - 1)):
            k = r.u8(); s.nss.append((k, r.u30()))
        s.nssets = [None]; n = r.u30()
        for _ in range(max(0, n - 1)):
            c = r.u30(); s.nssets.append([r.u30() for _ in range(c)])
        s.mns = [None]; n = r.u30()
        for _ in range(max(0, n - 1)):
            k = r.u8(); e = [k]
            if k in (0x07, 0x0d): e += [r.u30(), r.u30()]
            elif k in (0x0f, 0x10): e += [r.u30()]
            elif k in (0x11, 0x12): pass
            elif k in (0x09, 0x0e): e += [r.u30(), r.u30()]
            elif k in (0x1b, 0x1c): e += [r.u30()]
            elif k == 0x1d:
                e += [r.u30()]; c = r.u30(); e += [r.u30() for _ in range(c)]
            else: raise Exception('mn kind %x' % k)
            s.mns.append(e)
        s.methods = [None]; n = r.u30()
        for _ in range(max(0, n - 1)):
            pc = r.u30(); rt = r.u30(); pt = [r.u30() for _ in range(pc)]
            nm = r.u30(); fl = r.u8(); opt = []
            if fl & 0x08:
                oc = r.u30()
                for _ in range(oc): opt.append((r.u30(), r.u8()))
            s.methods.append({'name': nm, 'params': pt, 'ret': rt, 'flags': fl, 'opts': opt})
        n = r.u30()  # metadata count
        for _ in range(n):
            r.u30(); ic = r.u30()
            for _ in range(ic): r.u30(); r.u30()
        s.instances = []; n = r.u30()
        for _ in range(max(0, n - 1)):
            nm = r.u30(); sup = r.u30(); fl = r.u8()
            prot = r.u30() if fl & 0x08 else 0
            ic = r.u30(); ifaces = [r.u30() for _ in range(ic)]
            ii = r.u30(); tr = s.traits(r)
            s.instances.append({'name': nm, 'super': sup, 'iinit': ii, 'traits': tr,
                                'flags': fl, 'prot': prot, 'ifaces': ifaces})
        s.classes = []; n = r.u30()
        for _ in range(max(0, n - 1)):
            ci = r.u30(); tr = s.traits(r)
            s.classes.append({'cinit': ci, 'traits': tr})
        s.scripts = []; n = r.u30()
        for _ in range(n):
            si = r.u30(); tr = s.traits(r)
            s.scripts.append({'init': si, 'traits': tr})
        s.bodies = {}; n = r.u30()
        for _ in range(n):
            mi = r.u30(); ms = r.u30(); ml = r.u30(); isd = r.u30(); msd = r.u30()
            cl = r.u30(); code = r.raw(cl)
            ec = r.u30()
            for _ in range(ec):
                r.u30(); r.u30(); r.u30(); r.u30(); r.u30()
            tr = s.traits(r)
            s.bodies[mi] = {'code': code, 'maxstack': ms, 'maxlocals': ml, 'traits': tr}
        s.end = r.p

    def traits(s, r):
        out = []; n = r.u30()
        for _ in range(n):  # trait_count is exact (no dummy entry)
            nm = r.u30(); k = r.u8(); base = k & 0x0f
            t = {'name': nm, 'kind': base, 'meta': []}
            if base in (0, 6):
                t['slot'] = r.u30(); t['type'] = r.u30(); vi = r.u30()
                t['vindex'] = vi
                if vi: t['vkind'] = r.u8()
            elif base in (1, 2, 3):
                t['disp'] = r.u30(); t['method'] = r.u30()
            elif base == 4:
                t['slot'] = r.u30(); t['class'] = r.u30()
            elif base == 5:
                t['slot'] = r.u30(); t['function'] = r.u30()
            if k & 0x40:
                c = r.u30(); t['meta'] = [r.u30() for _ in range(c)]
            out.append(t)
        return out

    def s_(s, i): return s.strs[i] if 0 <= i < len(s.strs) and s.strs[i] is not None else '?'
    def ns_(s, i):
        if i <= 0 or i >= len(s.nss) or s.nss[i] is None: return ''
        return s.s_(s.nss[i][1])
    def mn_(s, i):
        if i <= 0 or i >= len(s.mns) or s.mns[i] is None: return '*'
        e = s.mns[i]; k = e[0]
        if k in (0x07, 0x0d, 0x09, 0x0e):
            nm = s.s_(e[2])
            if k in (0x07, 0x0d):
                ns = s.ns_(e[1])
                return (ns + '::' + nm) if ns else nm
            return nm + '{mn}'
        if k in (0x0f, 0x10): return s.s_(e[1]) + '{rt}'
        if k == 0x1d: return s.s_(e[1]) + '{T}'
        return '{}'


def read_swf(path):
    d = open(path, 'rb').read()
    if d[:3] == b'CWS': body = zlib.decompress(d[8:])
    elif d[:3] == b'FWS': body = d[8:]
    else: raise SystemExit('bad magic %r' % d[:3])
    nbits = body[0] >> 3
    p = (5 + 4 * nbits + 7) // 8 + 4
    abcs = []
    while p < len(body) - 1:
        th = struct.unpack_from('<H', body, p)[0]; p += 2
        code = th >> 6; ln = th & 0x3f
        if ln == 0x3f:
            ln = struct.unpack_from('<I', body, p)[0]; p += 4
        data = body[p:p + ln]; p += ln
        if code == 82:
            i = data.find(b'\0', 4)
            abcs.append(data[i + 1:])
    return abcs


def dis(code, abc):
    out = []; p = 0; n = len(code)
    while p < n:
        start = p; r = R(code, p)
        op = r.u8()
        if op not in OPS:
            out.append(('op_%02x' % op, '', start)); return out, p
        name, spec = OPS[op]
        args = []
        for ch in spec:
            if ch == 'b': args.append('#%d' % r.u8())
            elif ch == 'i': args.append(str(r.i8()))
            elif ch == 's': args.append('+%d' % r.s24())
            elif ch == 'n': args.append('%d' % r.u30())
            elif ch == 'm': args.append(abc.mn_(r.u30()))
            elif ch == 'F': args.append('"%s"' % abc.s_(r.u30()))
            elif ch == 'I': args.append('%d' % abc.ints[r.u30()])
            elif ch == 'U': args.append('%d' % abc.uints[r.u30()])
            elif ch == 'D': args.append('%r' % abc.dbls[r.u30()])
            elif ch == 'N': args.append(abc.ns_(r.u30()))
            elif ch == 'W':
                dflt = r.s24(); c = r.u30()
                args.append('default+%d/%s' % (dflt, ','.join('+%d' % r.s24() for _ in range(c))))
        out.append((name, ' '.join(args), start))
        p = r.p
    return out, p


def main():
    swf = sys.argv[1]; mode = sys.argv[2] if len(sys.argv) > 2 else 'list'
    abcs = read_swf(swf)
    pat = (sys.argv[3].lower() if len(sys.argv) > 3 else '')
    mpat = (sys.argv[4].lower() if len(sys.argv) > 4 else '')
    print('ABC blocks:', len(abcs))
    for bi, raw in enumerate(abcs):
        try:
            a = ABC(raw)
        except Exception as e:
            continue
        if mode == 'list':
            for ins in a.instances:
                nm = a.mn_(ins['name'])
                if pat and pat not in nm.lower(): continue
                print('class', nm, '<-', a.mn_(ins['super']))
                for t in ins['traits']:
                    print('   ', {0:'var',1:'method',2:'get',3:'set',4:'class',5:'func',6:'const'}[t['kind']],
                          a.s_(t['name']), 'method=%s' % t.get('method'))
        else:
            for ins in a.instances:
                nm = a.mn_(ins['name'])
                if pat not in nm.lower(): continue
                print('=== class', nm, '(abc %d)' % bi)
                for t in ins['traits']:
                    mi = t.get('method')
                    if mi is None or mi not in a.bodies: continue
                    mn = a.s_(t['name'])
                    if mpat and mpat not in mn.lower(): continue
                    code = a.bodies[mi]['code']
                    lines, end = dis(code, a)
                    print('--- %s (%dB, decoded %d)' % (mn, len(code), end))
                    for l in lines: print('  %04x %-16s %s' % (l[2], l[0], l[1]))


if __name__ == '__main__':
    main()