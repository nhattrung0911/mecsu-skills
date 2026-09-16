---
name: mecsu-naming
description: Dat ten chuan tieng Viet va dien thong so ky thuat cho san pham chi co ma hang, moi gia tri kem URL nguon that. Use when file Excel chi co cot ma hang ma chua co ten hoac thong so.
---

# mecsu-naming

Input: file Excel/CSV sản phẩm. Output: tên chuẩn theo đúng quy ước của khách + thông số, mỗi giá
trị kèm căn cứ.

> **Trạng thái: cả bốn vòng đã chạy được trên dữ liệu thật**, và đã qua cả bốn cổng.

## Khi nào dùng

- File sản phẩm cần đặt tên hoặc chuẩn hoá tên theo một quy ước.
- File có dòng chỉ có mã, thiếu tên hoặc thiếu thông số.
- Người dùng gõ: *đặt tên từ mã*, *chuẩn hoá tên sản phẩm*, *điền thông số từ mã hãng*.

## Bốn vòng

| Vòng | Làm | Ra internet? |
|---|---|---|
| 0 | Đọc chính file, **rút ra quy ước đặt tên** của khách | không |
| 1 | Áp quy ước cho dòng **đã có** thông tin | không |
| 2 | Dòng **chỉ có mã**: tra web tìm loại + thông số | có |
| 3 | Mã khó: truy vấn hướng catalog/datasheet, đọc được cả PDF | có |
| cuối | Vẫn không ra: **ghi NOTE trung thực** cho người tự sửa | — |

Vòng 0 là chỗ quyết định chất lượng. Không hardcode bảng ánh xạ nào: file của khách đã có sẵn
hàng chục đến hàng nghìn tên đặt đúng kiểu của họ, và model đọc chúng để tự rút ra công thức, từ
vựng thông số, chỗ đặt hãng và mã.

## Cách chạy

```bash
python ${CLAUDE_SKILL_DIR}/scripts/run.py --input <file.xlsx> --job jobs/naming-01
```

Dừng sau vòng 0 để người soát `convention.json`: model rút ra quy ước gì, file đang tự mâu thuẫn
ở đâu. **Không bắt buộc điền gì** — chuẩn Mecsu nằm sẵn trong `references/naming_convention.md`.
Job nào muốn khác chuẩn thì điền `_quyet_dinh_cua_nguoi.cong_thuc_chuan`, nó thắng chuẩn.

```bash
python ${CLAUDE_SKILL_DIR}/scripts/run.py --input <file.xlsx> --job jobs/naming-01 --den-vong 1
python ${CLAUDE_SKILL_DIR}/scripts/run.py --input <file.xlsx> --job jobs/naming-01 --den-vong 2 --domain-cua-minh congty.vn
python ${CLAUDE_SKILL_DIR}/scripts/run.py --input <file.xlsx> --job jobs/naming-01 --den-vong 3 --domain-cua-minh congty.vn
```

`--den-vong 2` mới ra internet. `--domain-cua-minh` đánh dấu trang của chính công ty: nguồn đó
**không phải bằng chứng độc lập**, và bước tải sẽ ưu tiên nguồn khác.

Dò không ra cột mã thì dừng và in header thật kèm `--code-col` (đếm từ 0). Muốn học lại quy ước
thì thêm `--hoc-lai`. Kết quả ra `<job>/ket_qua.xlsx`, đổi chỗ bằng `--out`.

Chạy lẻ từng bước:

```bash
python ${CLAUDE_SKILL_DIR}/scripts/extract_codes.py --input <file.xlsx> --out codes.json
python ${CLAUDE_SKILL_DIR}/scripts/learn_convention.py --codes codes.json --out convention.json
python ${CLAUDE_SKILL_DIR}/scripts/apply_convention.py --codes codes.json --convention convention.json --out names.json
python ${CLAUDE_SKILL_DIR}/scripts/build_queries.py --codes codes.json --out queries.json
python ${CLAUDE_SKILL_DIR}/scripts/search_sources.py --codes codes.json --queries queries.json --out search.json
python ${CLAUDE_SKILL_DIR}/scripts/fetch_sources.py --sources search.json --out-dir web --limit 20
python ${CLAUDE_SKILL_DIR}/scripts/extract_from_web.py --sources-dir web --search search.json --convention convention.json --out web_facts.json
python ${CLAUDE_SKILL_DIR}/scripts/round3.py --job jobs/naming-01 --out round3.json
python ${CLAUDE_SKILL_DIR}/scripts/build_sheet.py --input <file.xlsx> --job jobs/naming-01 --out ket_qua.xlsx
```

Thêm `--dry-run` vào các bước gọi model để xem **số lần gọi dự kiến** trước khi tiêu tiền.

## Đọc được cả hai kiểu bố cục

| Kiểu | Dạng |
|---|---|
| Một dòng một sản phẩm | cột mã + cột mô tả trên cùng hàng |
| **Khối** | một hàng có mã, rồi N hàng chỉ có cột mô tả = các dòng thông số của nó |

Header không bắt buộc ở dòng đầu. Ô chứa nhiều dòng ngăn bằng ký tự xuống dòng cũng được tách ra.

## Luật không được phá

Mỗi luật sinh từ một lỗi đã đo, ghi trong `.kb/specs/2026-09-11-mecsu-naming-buoc-do.md`.

1. **Không có text nguồn thì không hỏi model.** Mã không mã hoá loại sản phẩm.
2. **Quyết định của người thắng suy luận của model.** Chuẩn Mecsu thắng thứ model tự rút ra;
   `_quyet_dinh_cua_nguoi` của job thắng cả hai. `convention.json` ghi lại đủ ba tầng.
3. **Đối chiếu ngược mọi thứ model trả về.** Tên mới phải chứa **đúng mã hãng**, và **không được
   chứa tiền tố nội bộ**. Đã đo: model đổi `C-1 450x16x21` thành `C1-450x16x21` (4/20 dòng); và
   để lọt `SATA SAT-70303A` ra tên bán hàng (99/200 dòng, tất cả đều đang chấm OK).
4. **Ba mức, không phải hai.** `OK` · `REVIEW` (có nghi ngờ, ghi rõ vì sao) · trống.
5. **Chạy đồng bộ, tự kết thúc.** Không giao điều phối cho agent con.
6. **Tóm tắt của công cụ tìm kiếm không phải nguồn.** Nguồn hợp lệ chỉ là text tải về từ URL thật.
7. **Không sửa thứ người dùng không yêu cầu sửa.** Xuất xứ, nhãn thông số: giữ nguyên, chỉ báo chỗ
   lệch.

## Chốt chặn

| Chốt | Vì sao |
|---|---|
| Dừng sau vòng 0 cho người soát quy ước | áp một công thức sai cho cả file là hỏng cả file |
| Chuẩn nằm trong skill, không hỏi lại mỗi job | người dùng không cần biết công thức trước |
| Tên mới không chứa đúng mã gốc → `REVIEW` | model từng tự viết lại mã |
| Bước nào exit ≠ 0 thì dừng cả dây | báo xong trong khi chưa kiểm gì |
| Bước sau kiểm **nội dung** file, không kiểm sự tồn tại | file rỗng cũng là thất bại |

## Nặng bao nhiêu

Đo trên file thật 20 sản phẩm, 2026-09-11:

| | |
|---|---|
| Cả tầng 0 token chạy lại | **~1 giây** |
| Thư viện ngoài stdlib | chỉ `ddgs`, nạp khi cần |
| Nguồn tải về, mỗi trang | HTML thô ~366 KB → **text nén ~7 KB** |
| Cả job 20 sản phẩm | **128 KB** |

Mặc định lưu **text đã lọc, nén gzip** — 1,2% HTML thô. Suy ra file 5.730 sản phẩm: ~24 MB thay vì
~2 GB. Cần cấu trúc bảng (trang hãng SATA/Anex) thì `fetch_sources.py --luu html`.

Cache giữ lại vì bỏ nó là trả bằng giờ: 5.730 trang × 1 giây nghỉ ≈ 1,6 tiếng mỗi lần chạy lại.

## Vòng 3 nhận nguồn thế nào

Một trang chỉ **nhắc tới mã** thì chưa đủ. Ba điều kiện, cả ba đều sinh từ một thành công giả đã
đo được:

| Điều kiện | Lỗi nó chặn |
|---|---|
| Mã phải có trong **URL** | `S23052` khớp trang của `S23055` — trang catalog liệt kê nhiều mã |
| Text phải có **≥2 số đo** | trang bán lẻ tên đúng nhưng không một số liệu nào |
| Số đo phải **gần chỗ nhắc mã** | `12V 18V 20V` lấy từ menu danh mục máy pin của website |

Không nguồn nào đạt thì model viết **ghi chú bàn giao**: đã tìm ở đâu, thiếu gì, người cần làm gì.
Ghi chú đó là **kết quả**, không phải lỗi.

## Nhánh trang hãng — có sẵn, chưa nối vào `run.py`

Dùng cho file mà **mã suy thẳng ra URL trang hãng** (đo 2026-09-11: SATA 62,1% và Anex 3,1% của
một file 5.730 mã). Rẻ và chính xác hơn tìm kiếm, nhưng chỉ áp được khi hãng có mẫu URL.

```bash
python ${CLAUDE_SKILL_DIR}/scripts/vendor_url.py --codes codes.json --out sources.json --check 12
python ${CLAUDE_SKILL_DIR}/scripts/fetch_sources.py --sources sources.json --out-dir sources --luu html
python ${CLAUDE_SKILL_DIR}/scripts/parse_vendor.py --sources-dir sources --codes codes.json --out facts.json
python ${CLAUDE_SKILL_DIR}/scripts/ai_extract.py --facts facts.json --out ai.json
```

`--check` thử thật bằng HTTP xem mẫu URL còn đúng không — nó là **giả định về một trang web bên
ngoài**, gãy lúc nào không ai báo. `--luu html` vì bước này cần cấu trúc bảng, không chỉ chữ.

`skill_env.py` là lớp dùng chung: đọc `.env` ở gốc plugin và gọi model. Không script nào giữ key
riêng. Nó parse **SSE** vì endpoint luôn stream kể cả khi không xin — `json.load()` chết ngay.
