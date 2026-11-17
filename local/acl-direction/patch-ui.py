#!/usr/bin/env python3
"""Apply the local device-policy direction UI to the verified v1.7.0 asset.

Only the two device-policy forms are changed. All other feature checks remain.
A changed upstream asset must be reviewed before updating this checksum.
"""
import hashlib
from pathlib import Path
import sys

EXPECTED = '6ae17ea46f71e00090b27c7608dd02f89547be088e6408f825678fd8929a1eb7'

def patch(data: bytes) -> bytes:
    if hashlib.sha256(data).hexdigest() != EXPECTED:
        raise ValueError('Unexpected UI asset: refusing to patch an unreviewed build')
    text = data.decode()
    def replace(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise ValueError('UI patch anchor is not unique: ' + old[:90])
        text = text.replace(old, new)

    # Preserve the chosen direction when the CE service defaults are initialized.
    replace(',E(1))},[x,Ee,ae,p?.service])', ')},[x,Ee,ae,p?.service])')
    replace(',r.useEffect(()=>{x||E(1)},[x])', '')
    replace('r.useEffect(()=>{U||x(1)},[U]);', '')

    forms = [
        ('x', 'S', 'E', 'O', 'if(!x)return;'),
        ('U', 'g', 'x', 'j', 'if(!U)return void x(1);'),
    ]
    for ee, state, setter, flag, guard in forms:
        old = ('a.jsx(N,{title:'+ee+'?"":"Changing direction is only available on Pro",children:a.jsx("img",{onClick:()=>{'+guard+
               'const e=0==='+state+'?1:0;'+setter+'(e),'+flag+'(0===e)},src:$M,className:`w-full scale-110 ${'+ee+
               '?"cursor-pointer":"cursor-not-allowed"} ${'+ee+'&&0==='+state+'?"opacity-30":""}`,alt:"Left arrow"})})')
        new = ('a.jsxs("div",{className:"w-full flex flex-col gap-2",children:['
               'a.jsx("img",{src:$M,className:`w-full scale-110 ${0==='+state+'?"opacity-30":""}`,alt:"Left arrow"}),'
               'a.jsxs("select",{"aria-label":"Traffic direction",value:'+state+',onChange:t=>{const e=Number(t.target.value);'+setter+'(e),'+flag+'(0===e)},'
               'className:"w-full rounded border border-stroke-default bg-bg-default px-1 py-2 text-xs text-text-primary",'
               'children:[a.jsx("option",{value:1,children:"Two-way"}),a.jsx("option",{value:0,children:"One-way: source to destination"})]})]})')
        replace(old, new)
    return ('/* Local device-policy direction UI, 2026-11-17. */\n'+text).encode()

if __name__ == '__main__':
    source, destination = map(Path, sys.argv[1:])
    output = patch(source.read_bytes())
    destination.write_bytes(output)
    print(hashlib.sha256(output).hexdigest(), destination)
