---
name: mecsu-category
description: Use when an Excel workbook of products already carries category assignments and the question is which ones are wrong - finding mis-categorised SKUs, QC-ing a category export before it goes live, re-checking a category column, or when the user says soát danh mục, kiểm danh mục, gán sai danh mục, danh mục lá.
argument-hint: "[path/to/workbook.xlsx]"
license: MIT
---

# mecsu-category — kiểm tra danh mục đã gán

Kiểm tra mô tả sản phẩm có khớp danh mục nó đang mang không. Danh mục đang có **là bằng chứng**
— đi kiểm nó, đừng gán lại từ đầu.

Bổ trợ cho `mecsu-filter`: skill này trả lời *sản phẩm này thuộc danh mục nào*, `mecsu-filter`
trả lời *sản phẩm này có đủ và đúng thông số chưa*.

## Chạy

```bash
python ${CLAUDE_SKILL_DIR}/scripts/audit.py --input <file.xlsx> \
  --models ag/gemini-3.7-flash-medium ag/gemini-3.7-flash-high
```

Đó là cả pipeline: dò cột → lọc chữ (0 token) → một model chấm → model thứ hai đối chiếu →
dựng file cuối kèm tự kiểm tra. Nó dừng lại sau lô hiệu chuẩn 50 cặp; đọc lô đó xong mới
chạy lại kèm `--yes`.

**Layout cột nào cũng chạy.** `detect_schema.py` khớp tên cột miễn phí trước, chỉ gọi model
cho vai trò mà tên cột không quyết được. Cột nào pipeline không hiểu thì giữ nguyên, không
đụng. Chỉ cần ba vai trò có mặt: mô tả sản phẩm, danh mục đã gán, danh mục cấp 1.

Cứ chạy trước — bước dò cột và lọc chữ **không cần key**, và script tự dừng kèm đường dẫn
file cần điền nếu thiếu. Lúc đó mới hỏi người dùng endpoint 9router + key + model, đừng tự
đoán. Cần Python 3.11+ với `openpyxl`,
`requests`, `python-dotenv`.

## `.env` là tuỳ chọn

Endpoint trong `.env` mua thêm một model rẻ, **không phải điều kiện để chạy**. Không có nó thì
chính agent đang chạy làm phần việc đó: script ghi câu hỏi đã gộp lô ra `<thư mục out>/hoi_agent/
cau_hoi.json` rồi **thoát 4**; agent điền `tra_loi.json` rồi chạy lại đúng lệnh cũ. Câu trả lời của
agent đi qua **đúng đường đối chiếu ngược** như của model.

Có `.env` mà vẫn muốn tự làm: `MECSU_CHE_DO=agent`. Mã thoát: `3` chờ người soát · `4` chờ agent
trả lời · khác 0 còn lại là hỏng, không giao.

## Luật không được phá

1. **Không bao giờ gọi model theo từng dòng.** `rule_check.py` gộp trùng trước — bỏ token có
   chữ số (size, mã DIN, part number) khỏi mô tả để mọi biến thể của một sản phẩm thu về một
   cặp. Thấy mình đang lặp qua từng dòng để gọi model thì dừng.
2. **Không để model bịa danh mục.** Mỗi prompt mang theo nguyên danh sách leaf hợp lệ của
   nhóm đó, và mọi câu trả lời được đối chiếu lại với danh sách ấy. Đừng gỡ bước đó.
3. **Không giao thứ mình chưa kiểm.** `build_final.py` tự mở lại output của chính nó và exit
   khác 0 nếu số dòng, dòng không đụng tới, category id, hay bộ ba id/tên/depth không khớp.
   Exit khác 0 nghĩa là **không giao**, không phải "chạy lại kèm cờ khác".
4. **Không đoán qua chỗ bất đồng.** Chỗ hai model không thống nhất, dòng đó **giữ nguyên**
   danh mục đang có trừ khi có bằng chứng thật. Search đúng mã hàng, rồi chỉ ghi vào
   `dispute_resolution.json` cái mà bằng chứng đỡ được. Bỏ qua một cặp thì an toàn; phán sai
   một cặp là sai lan ra mọi dòng dùng chung cặp đó.
5. **Không cào máy tìm kiếm từ script.** Đã thử, IP bị chặn, 73/73 lượt tra về rỗng. Dùng web
   search của chính agent cho các cặp ảnh hưởng nhiều nhất — `list_disputes.py` in ra mỗi cặp
   phủ bao nhiêu dòng để biết lúc nào nên dừng.
6. **Không quote con số mình chưa đo.** `measure.py` sinh lại mọi con số trong tài liệu từ
   artifact trên đĩa. Chạy nó, đừng chép lại số nhớ được.

## Cái gì cần người

- `changelog.xlsx` — các thay đổi đề xuất. Phải có người duyệt trước khi giao.
- `disputes_to_research.json` — hai model bất đồng. Search phần này; chỉ ghi lại cái chứng
  minh được.
- `taxonomy_gaps.json` — không có danh mục hợp lệ nào cho những sản phẩm này. Đây không phải
  lỗi phân loại; đưa cho người quản lý taxonomy.

`deliver.py` từ chối ghi vào `delivered/` khi còn dispute chưa giải quyết. Sự từ chối đó
chính là tính năng.

---

Chi tiết từng bước, bảng verdict, định dạng bàn giao, quy tắc dọn dẹp, và mọi số đo:
[reference.md](reference.md)
