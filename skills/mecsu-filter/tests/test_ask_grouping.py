# -*- coding: utf-8 -*-
"""Khoa gom cau hoi phai mang ca nhan doc duoc tu TEN san pham.

Loi that: `M14x1.5 Ren Nhuyen` va `M14` ren tho bi gom vao CUNG mot cau hoi vi
khoa gom dung `known` (filter tho) thay vi `ctx_known` (filter + nhan doc tu ten).
Model tra ve mot gia tri, `apply_fills.py` trai no cho ca hai -> ren nhuyen bi
dien buoc ren cua ren tho. Day dung la ca `M14x1.5 Ren Nhuyen -> Buoc Ren 2 mm`
trong bang chot chan cua SKILL.md, moi va o nhanh corpus.
"""
import json
import pickle
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))


def _row(ten, filter_goc, can_tra_cuu='', part_id=0, ma=''):
    return {'group': 'Bulong', 'ten': ten, 'filter_goc': filter_goc,
            'filter_bo_sung': '', 'can_tra_cuu': can_tra_cuu,
            'part_id': part_id, 'ma': ma}


def _fixtures(tmp_path: Path):
    res = [
        # Hai dong nay chi de von tu cua nhom co thuoc tinh `Loai Ren`.
        _row('Bulong M16x2x40 Ren Tho', 'Size Ren: M16 | Loai Ren: Ren Tho | Buoc Ren: 2 mm'),
        _row('Bulong M16x1.5x40 Ren Nhuyen',
             'Size Ren: M16 | Loai Ren: Ren Nhuyen | Buoc Ren: 1.5 mm'),
        # Hai dong can hoi: cung `Size Ren: M14`, khac nhau DUY NHAT o ten.
        _row('Bulong DIN912 M14x1.5x35 Ren Nhuyen', 'Size Ren: M14', 'Buoc Ren', 10, 'A'),
        _row('Bulong DIN912 M14x35', 'Size Ren: M14', 'Buoc Ren', 11, 'B'),
    ]
    audit = tmp_path / 'audit.pkl'
    with open(audit, 'wb') as handle:
        pickle.dump((res, {}), handle)

    # Quan he cu the dung truoc quan he tong quat; `keys`/`table` rong nen corpus
    # khong tra duoc gi, moi o deu phai thanh cau hoi.
    deps = tmp_path / 'deps.json'
    deps.write_text(json.dumps({'Bulong': [
        {'target': 'Buoc Ren', 'det': ['Size Ren', 'Loai Ren'],
         'keys': {}, 'table': {}, 'consistency': 1.0, 'support': 2},
        {'target': 'Buoc Ren', 'det': ['Size Ren'],
         'keys': {}, 'table': {}, 'consistency': 0.9, 'support': 2},
    ]}, ensure_ascii=False), encoding='utf-8')
    return audit, deps


def test_nhan_doc_tu_ten_phai_tach_cau_hoi(tmp_path):
    audit, deps = _fixtures(tmp_path)
    out = tmp_path / 'queue.json'
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / 'build_ai_queue.py'),
         '--audit', str(audit), '--deps', str(deps), '--out', str(out)],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    asks = json.loads(out.read_text(encoding='utf-8'))['asks']
    assert len(asks) == 2, 'ren nhuyen va ren tho bi gom chung 1 cau hoi: %s' % asks
    nhuyen = [a for a in asks if 'Ren Nhuyen' in json.dumps(a['context'], ensure_ascii=False)]
    assert len(nhuyen) == 1, 'khoa gom khong mang nhan `Loai Ren` doc tu ten: %s' % asks
    assert nhuyen[0]['rows'] == [2], 'cau hoi ren nhuyen phai chi phu dong ren nhuyen'
