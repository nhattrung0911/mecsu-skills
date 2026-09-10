# lab/ — xưởng dựng skill (KHÔNG push)

Skill đang làm dở nằm ở đây. Chỉ file README này lên GitHub. `skills/` chỉ chứa **thành phẩm**:
đã có test, đã qua bốn cổng, đã lên web.

```
lab/
  <ten-skill>/        # bản nháp: SKILL.md, scripts, tests, ghi chú thử nghiệm
```

## Vòng đời một skill

```
lab/<ten>/  ──►  bốn cổng xanh  ──►  git mv lab/<ten> skills/<ten>  ──►  push
   nháp          test · lint ·           thành phẩm
   thử           validate · eval
```

## Dựng ở đây

Bám flow chuẩn ở `.kb/06-flow-build-skill.md`. Rút gọn:

1. **ĐỎ trước** — chạy tình huống thật khi *chưa có* skill, ghi nguyên văn agent làm sai gì.
2. Dựng `lab/<ten>/SKILL.md` + `scripts/` nhắm đúng cái sai đó.
3. Viết test cho từng chốt chặn. Tên file test phải **duy nhất toàn repo** (pytest gom theo tên
   file, không theo đường dẫn).
4. Chạy thử trên dữ liệu thật ở `jobs/inbox/`, hoặc file mẫu trong `samples/`.

## Ra thành phẩm

```bash
python -m pytest lab/<ten>/tests -q         # test riêng của bản nháp
git mv lab/<ten> skills/<ten>               # chuyển sang vùng push
python tools/sync_site.py                   # web tự có mục cho skill mới
claude plugin validate . && python -m pytest -q && python tools/lint_skills.py
```

Chưa qua đủ bốn cổng thì **để yên trong `lab/`**. Đẩy skill chưa test sang `skills/` là đẩy code
chưa test lên production.
