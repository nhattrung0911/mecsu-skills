---
name: mecsu-pricelist-claude
description: Dùng khi người dùng đưa file Excel data sản phẩm (mã hãng, order id, giá Varin, cột thông số) và cần bảng giá Excel chuẩn Varin theo brand, hoặc gõ - làm bảng giá, tạo bảng giá, xuất bảng giá hãng Bosi/Stanley/Sata/FBJ, price list, cập nhật bảng giá, thêm ảnh vào bảng giá, chia card bảng giá, bảng giá A4 cho đối tác Varin.
---

# mecsu-pricelist-claude

Input: 1..n file Excel data (mỗi dòng 1 mã: Mã Hãng, Order ID, Varin Price, thông số; tên cột lệch
vẫn nhận). Output: `BẢNG GIÁ <HÃNG>.xlsx` A4 chuẩn Varin — header logo, card ảnh + bảng, giá
`VLOOKUP` Sheet2, footer đỏ, mã trang `XXX - 01` — kèm ảnh render từng trang để soát.

## Bốn nguyên tắc (lý do nằm sau mỗi dòng)
1. **Data của user là nguồn sự thật.** Tên card = `Tên Bảng Giá`/mô tả của user, không đặt lại theo
   web. Nghi data sai thì *báo*, chỉ sửa qua `--patches` có nguồn → `patch_log.md`. Bảng giá gửi đối
   tác: sai một con số là sai cam kết giá.
2. **Định dạng không tự chế.** Khung, font, màu, cỡ ảnh nằm trong `config/theme.json`; chia card/sắp
   dòng trong `config/families.json`. Cùng data → cùng kết quả mọi lần, mọi máy.
3. **Ảnh thật, đúng hãng.** Thư mục ảnh user → catalog chính thức theo order id → web đúng hãng.
   Không bao giờ tự vẽ ảnh. Card thiếu ảnh = lỗi QA.
4. **Leader điều phối, worker Sonnet làm việc nặng** — xem mục *Chạy theo đội*. Nhanh hơn, rẻ hơn,
   context leader sạch.

## Bước 0 — môi trường (một lần mỗi máy)
```bash
python "${CLAUDE_SKILL_DIR}/scripts/pl_doctor.py"
```
Exit 2 → in dòng `pip install ...` cho user chạy. Thiếu Excel chỉ mất bước render (vẫn ra xlsx).

## Chạy — một lệnh
```bash
python "${CLAUDE_SKILL_DIR}/scripts/run.py" <data1.xlsx> [data2.xlsx ...] --brand BOSI --code BSI
```
| Cờ | Khi nào |
|---|---|
| `--brand-filter Bosi` | file lẫn nhiều hãng — một bảng giá cho mỗi hãng, chạy lại cho hãng khác |
| `--images <thư mục>` | user có ảnh (tên file = mã hãng) |
| `--logo <png>` | logo hãng chưa có sẵn (bundled: varin, bsi, fbj, stanley, sata) |
| `--out <thư mục>` | mặc định `<thư mục data>/output/<code>` |
| `--patches a.json b.json` | sửa data có nguồn (định dạng: `pl_patch.py` docstring) |
| `--resume` | **sau mọi STOP**: chạy tiếp đúng từ bước đã dừng (mỗi STOP in sẵn dòng `RERUN: ...`) |
| `--from lint\|layout` | chạy lại từ một bước đã từng xong (vd sửa theme → `--from layout`) |
| `--accept-plan` / `--accept-data` / `--accept-images` | đã xem kế hoạch / cảnh báo data / ảnh catalog và chấp nhận |
| `--no-render` · `--offline` | máy không Excel · không mạng |

Hỏi user (chỉ khi thiếu): file data, tên hãng in title, mã trang 2–4 chữ in hoa.

## Mã thoát — đọc dòng đầu tiên của output
| Dòng đầu | Nghĩa | Leader làm gì |
|---|---|---|
| `STOP 4 plan` | nhóm lạ / quá lớn chưa có luật chia | đọc `plan.md`; sửa `plan.json` (split/sort) hoặc thêm họ vào `config/families.json`; `--resume` (hoặc `--accept-plan`) |
| `STOP 4 data` | data nghi sai (`items_warnings.txt`) | ≥ 3 mã → **worker A**, ít hơn tự tra; có nguồn → chạy lại lệnh gốc + `--patches team/patches_A.json --resume`; không nguồn → KHÔNG sửa, ghi vào báo cáo cho user, `--accept-data --resume` |
| `STOP 4 lint` | nội dung vi phạm `references/content_rules.md` | ≥ 10 card → **worker C**; `pl_docedit.py` gộp → `--resume` |
| `STOP 4 images` | thiếu ảnh sau thư mục + catalog | mỗi `img_work/sheet_*.png` → 1 **worker B**; run.py tự gộp `team/picks_*.json` → `--resume` |
| `STOP 4 images-review` | ảnh lấy từ catalog — có thể là ảnh quảng cáo/hãng khác | xem `img_work/chosen_sheet*.png` (1 ảnh/≤30 card, leader tự xem hoặc **worker B**); ảnh xấu → ghi `reject.json` = [card_id…] → `--resume`; ổn hết → `--accept-images --resume` |
| `FAIL qa` (exit 1) | lỗi QA (thiếu ảnh, chồng card…) | đọc `qa_report.md`, sửa đúng chỗ, chạy dòng `RERUN` |
| exit 0 | xong | soát render (dưới) rồi bàn giao |
| exit 2 | sai cờ / bước hỏng | đọc lỗi, sửa lệnh; không lặp lại mù |

Gộp sửa nội dung của worker: `python "${CLAUDE_SKILL_DIR}/scripts/pl_docedit.py" <out>/doc.json <out>/team/edits_1.json`
(từ chối đổi tiêu đề lấy từ data, từ chối hai file sửa cùng ô → exit 2).

## Chạy theo đội (điểm mấu chốt)
Leader = phiên đang nói với user: chạy `run.py`, đọc STOP, quyết định, chấm. Worker = Agent tool với
`model: "sonnet"`, gửi **cùng một lượt** để chạy song song, mỗi worker một file riêng trong
`<out>/team/`, trả lời ≤ 120 từ. Worker không sửa `doc.json`/data, không chạy `run.py`. Leader gộp
bằng script và để lint + QA làm trọng tài — không đọc lại từng file của worker.
Mẫu giao việc A (tra catalog) · B (chọn ảnh) · C (sửa card) · D (soát trang): `references/team.md`.
Dưới ngưỡng ở bảng trên thì leader tự làm — khởi động worker cũng tốn.

## Soát cuối (exit 0)
- Leader tự xem `renders/page_01.png` + trang cuối theo `references/qa_checklist.md`.
- Trên 4 trang: `run.py` ghi `team/review_batches.json` → mỗi lô một **worker D**; leader chỉ mở
  trang có lỗi mức "chặn". Sửa qua `doc.json`/theme rồi `--from layout`; tối đa 3 vòng.
- Script tự viết thêm (kiểm tra nhanh…) phải `sys.stdout.reconfigure(encoding="utf-8")` hoặc chạy `python -X utf8` — console Windows là cp1252.
- Render là ảnh chụp Excel 2007: chữ méo cục bộ có thể là lỗi chụp — kiểm giá trị ô trước khi sửa.

## Linh hoạt — yêu cầu mới, theo thứ tự
1. Đổi được bằng `config/theme.json` / `families.json` / trường card (`references/doc_schema.md`) → sửa dữ liệu.
2. Một lần cho một bảng → `doc.json` (`pl_docedit.py`) hoặc `plan.json`.
3. Lặp lại ≥ 2 lần → sửa script + thêm test trong `tests/` (`python -m pytest -q` ở gốc plugin).
4. User đưa bảng giá chuẩn mới → `pl_extract.py <file.xlsx> --pages 1 --reflow -o learned.json --work <dir>`
   để học bố cục + từ vựng, cập nhật `references/content_rules.md`.

## Dữ liệu của người dùng (không nằm trong plugin)
`$MECSU_PRICELIST_HOME` (mặc định `~/.mecsu-pricelist`): `kb/<CODE>.json` (tên/ảnh đã duyệt theo
mã — cùng mã luôn ra cùng kết quả) và `logos/`. Cập nhật plugin không mất dữ liệu này.
Duyệt kho: `python "${CLAUDE_SKILL_DIR}/scripts/pl_kb.py" list --brand BSI --status review`.

## Bàn giao cho user
Đường dẫn xlsx + 1–2 ảnh render; số trang/card/mã; những gì đã sửa (`patch_log.md`, `edit_log.md`);
những gì cần user quyết (ảnh web `review`, data nghi sai chưa xác minh, tên card chung chung).

## Tham chiếu
- `references/team.md` — mẫu giao việc cho worker A/B/C/D, luật gộp.
- `references/content_rules.md` — tiêu đề, dòng mô tả, nhãn cột, legend, note.
- `references/qa_checklist.md` — checklist soát trang.
- `references/format_spec.md` — số đo khung Varin.
- `references/doc_schema.md` — các trường của `doc.json` và cột tuỳ chọn trong data.
