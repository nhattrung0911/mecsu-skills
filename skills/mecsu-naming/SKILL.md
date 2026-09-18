---
name: mecsu-naming
description: Dung khi file Excel chi co cot ma hang ma chua co ten hoac thong so ky thuat, hoac khi nguoi dung go: dat ten tu ma, chuan hoa ten san pham, dien thong so tu ma hang, tra thong so theo ma, tao ma.
---

# mecsu-naming

Input: file Excel/CSV sản phẩm. Output: tên chuẩn theo đúng quy ước của khách + thông số, mỗi giá
trị kèm căn cứ.

> **Trạng thái: cả bốn vòng đã chạy được trên dữ liệu thật**, và đã qua cả năm cổng.

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

## `.env` là tuỳ chọn, không bắt buộc

| `.env` | Ai làm phần việc của model | Agent làm gì |
|---|---|---|
| có endpoint | model rẻ trong `.env` | **giám sát**: mỗi bước xong, đọc 10 dòng mẫu trong artifact vừa sinh, đối chiếu với nguồn, báo số |
| không có | **chính agent đang chạy** | tự trả lời, rồi vẫn tự soát như trên |

Có `.env` mà vẫn muốn tự làm thì đặt `MECSU_CHE_DO=agent`. Có key không có nghĩa là bị bắt xài key.

Chế độ agent bàn giao qua file: script ghi câu hỏi **đã gộp lô** ra `<job>/hoi_agent/cau_hoi.json`
rồi **thoát 4**; agent điền `tra_loi.json` rồi chạy lại **đúng lệnh cũ**. Câu trả lời của agent đi
qua đúng đường đối chiếu ngược như của model. Mã thoát: `3` = chờ **người** soát · `4` = chờ
**agent** trả lời · khác 0 còn lại = hỏng, không giao.

Chi tiết: [`references/che_do_agent.md`](references/che_do_agent.md).

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

**Nâng `--den-vong` không tính tiền lại.** Bước nào mà đầu vào không đổi và đầu ra còn nội dung
thì bỏ qua, in `bo qua: dau vao khong doi`. Khoá theo **nội dung** đầu vào: sửa `convention.json`
là vòng 1 chạy lại ngay. File hoặc thư mục rỗng tính là chưa có kết quả, nên một thất bại đã cache
không bao giờ được dùng. `--lam-lai` ép chạy lại tất cả.

> Trước khi có chỗ này (đo 2026-09-17, 100 mã): đi vòng 1 → 2 → 3 trả tiền vòng 1 **ba lần**, bước
> tìm kiếm chạy lại **33 phút mỗi lượt**, và vòng 3 tải lại từ đầu làm **21 OK tụt còn 19** — chạy
> thêm để tốt hơn lại tệ hơn.

Chạy lẻ từng bước để soi một bước cụ thể khi tìm lỗi: [`references/chay_le_tung_buoc.md`](references/chay_le_tung_buoc.md).

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

Đo trên file thật 20 sản phẩm (2026-09-11): cả tầng 0 token chạy lại **~1 giây**, cả job
**128 KB** vì lưu text đã lọc nén gzip — 1,2% HTML thô. Chi tiết và lý do giữ cache:
[`references/chi_phi.md`](references/chi_phi.md).

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

## Nhánh trang hãng

Dùng cho file mà **mã suy thẳng ra URL trang hãng** (đo 2026-09-11: SATA 62,1% và Anex 3,1%
của một file 5.730 mã). Rẻ và chính xác hơn tìm kiếm, nhưng chỉ áp được khi hãng có mẫu URL.
Chưa nối vào `run.py`; bốn lệnh và lý do ở
[`references/nhanh_trang_hang.md`](references/nhanh_trang_hang.md).
