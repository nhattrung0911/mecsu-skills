# -*- coding: utf-8 -*-
"""Chot chan cho duong chay chinh cua run.py.

Loi that: moi batch that bai -> ai_values_*.json van duoc ghi ra (rong `{}`),
run.py chi kiem tra file CO TON TAI nen chay tiep verify/apply/build_review roi
in "Xong." sau khi dien 0 o.
"""
import json
import os
import pickle
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

DEAD_ENDPOINT = 'http://127.0.0.1:1/v1'


def _queue(tmp_path: Path) -> Path:
    queue = {
        'asks': [
            {
                'ask_id': 1,
                'key_hash': 'abc123',
                'group': 'Bulong',
                'attr': 'Buoc Ren',
                'context': {'Duong Kinh Ren': 'M14'},
                'sample_name': 'Bulong M14x1.5 Ren Nhuyen',
                'sample_known': {},
                'rows': [0],
            }
        ]
    }
    path = tmp_path / 'queue.json'
    path.write_text(json.dumps(queue, ensure_ascii=False), encoding='utf-8')
    return path


def _audit_pkl(tmp_path: Path) -> Path:
    path = tmp_path / 'audit.pkl'
    with open(path, 'wb') as handle:
        pickle.dump(([], {}), handle)
    return path


def test_ai_fill_bao_loi_khi_moi_batch_that_bai(tmp_path):
    """Endpoint chet ma exit 0 -> run.py di tiep va bao "Xong." sau khi dien 0 o."""
    env = dict(
        os.environ,
        MECSU_BASE_URL=DEAD_ENDPOINT,
        MECSU_API_KEY='khong-can-that',
        MECSU_MODELS='fake-model',
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / 'ai_fill.py'),
            '--queue', str(_queue(tmp_path)),
            '--audit', str(_audit_pkl(tmp_path)),
            '--output-dir', str(tmp_path),
        ],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=env,
        timeout=120,
    )
    assert proc.returncode != 0, 'exit 0 du moi batch that bai:\n%s' % proc.stdout[-2000:]


def _two_value_files(tmp_path: Path):
    files = []
    for slug in ('model-a', 'model-b'):
        path = tmp_path / ('ai_values_' + slug + '.json')
        path.write_text('{}', encoding='utf-8')
        files.append(str(path))
    return files


def test_verify_values_nhan_nhieu_file_values(tmp_path):
    """run.py splat `*ai_values(job)`; chay 2 model = 2 file -> argparse exit 2, gay ca pipeline."""
    proc = subprocess.run(
        [
            sys.executable, str(SCRIPTS / 'verify_values.py'),
            '--audit', str(_audit_pkl(tmp_path)),
            '--queue', str(_queue(tmp_path)),
            '--values', *_two_value_files(tmp_path),
            '--out', str(tmp_path / 'verify.json'),
        ],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    assert 'unrecognized arguments' not in proc.stderr, proc.stderr


def test_gop_hai_model_bat_dong_thi_bo_o_do(tmp_path):
    """Cung luat nhu apply_fills.py: hai model tra khac nhau -> it nhat mot cai sai,
    khong biet cai nao -> bo ca hai, khong duoc chon bua mot cai."""
    import verify_values as vv

    a = tmp_path / 'ai_values_model-a.json'
    b = tmp_path / 'ai_values_model-b.json'
    a.write_text(json.dumps({'k1': {'value': '1.5 mm'}, 'k2': {'value': '2 mm'}}), encoding='utf-8')
    b.write_text(json.dumps({'k1': {'value': '1.5 mm'}, 'k2': {'value': '2.5 mm'}}), encoding='utf-8')

    merged, conflicts = vv.merge_values([a, b])
    assert merged['k1']['value'] == '1.5 mm'
    assert 'k2' not in merged
    assert conflicts == 1


def test_build_review_nhan_nhieu_file_values(tmp_path):
    """Cung loi splat, o buoc dung bang cham diem."""
    empty = tmp_path / 'empty.json'
    empty.write_text('{}', encoding='utf-8')
    proc = subprocess.run(
        [
            sys.executable, str(SCRIPTS / 'build_review.py'),
            '--audit', str(_audit_pkl(tmp_path)),
            '--queue', str(_queue(tmp_path)),
            '--corpus-filled', str(empty),
            '--ai-values', *_two_value_files(tmp_path),
            '--ai-verify', str(empty),
            '--out', str(tmp_path / 'cham_diem.xlsx'),
        ],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    assert 'unrecognized arguments' not in proc.stderr, proc.stderr
