import pathlib
NL = chr(92) + 'n'          # hai ky tu: backslash + n
hong1 = "    return hashlib.sha256(('%s\n\n%s' % (he_thong, prompt)).encode('utf-8')).hexdigest()[:16]"
tot1 = "    return hashlib.sha256(('%s" + NL + NL + "%s' % (he_thong, prompt)).encode('utf-8')).hexdigest()[:16]"
hong2 = """    print('
CAN AGENT TRA LOI %d cau (buoc %s).
  1. Doc   %s
  2. Ghi   %s  dang {"<khoa>": "<cau tra loi>"}
  3. Chay lai DUNG lenh vua roi.'
          % (len(_PHIEN.dang_cho), buoc, cau_hoi, _PHIEN.thu_muc / 'tra_loi.json'))"""
tot2 = ("    print('" + NL + "CAN AGENT TRA LOI %d cau (buoc %s)." + NL + "'" + "\n"
        "          '  1. Doc   %s" + NL + "'" + "\n"
        '          \'  2. Ghi   %s  dang {"<khoa>": "<cau tra loi>"}' + NL + "'" + "\n"
        "          '  3. Chay lai DUNG lenh vua roi.'" + "\n"
        "          % (len(_PHIEN.dang_cho), buoc, cau_hoi, _PHIEN.thu_muc / 'tra_loi.json'))")
for ten in ('mecsu-category', 'mecsu-filter'):
    p = pathlib.Path('skills') / ten / 'scripts' / 'skill_env.py'
    t = p.read_text(encoding='utf-8')
    assert hong1 in t, ('1', ten)
    assert hong2 in t, ('2', ten)
    p.write_text(t.replace(hong1, tot1).replace(hong2, tot2), encoding='utf-8')
    print('fixed', p)
