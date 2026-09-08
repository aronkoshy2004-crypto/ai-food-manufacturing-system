# KỊCH BẢN DEMO THỰC THI TOÀN TRÌNH 13 BƯỚC (§12)
## HỆ THỐNG ĐIỀU HÀNH SẢN XUẤT & TRUY XUẤT NGUỒN GỐC THỰC PHẨM — FOOD MAN

---

### 1. Tổng Quan & Tài Khoản Trình Diễn

Hệ thống được thiết kế theo tiêu chuẩn công nghiệp hiện đại (**Theme Light #F5F6F8**, điểm nhấn **Navy #162B4E**, lưới thẻ 2 cột, và ngăn kéo trượt **Slide-in Detail Drawer** bên phải).

| Vai Trò | Người Dùng Demo | Email / Username | Quyền Hạn & Phân Hệ |
| :--- | :--- | :--- | :--- |
| **Admin** | Nguyễn Hoàng Minh | `admin@foodman.vn` | Toàn quyền kiểm soát toàn bộ 6 phân hệ |
| **Procurement** | Trần Văn Mua | `procurement@foodman.vn` | Nhà cung cấp, Nguyên liệu, Đơn mua PO, Nhập kho GRN |
| **QC Inspector** | Lê Thị Thử | `qc@foodman.vn` | Hàng chờ QC, Thử nghiệm Lab, Chứng thư COA, Khuyết tật AI |
| **Production** | Phạm Quốc Sản | `production@foodman.vn` | Đề xuất BOM, Khởi tạo mẻ, Tiến độ 5 công đoạn, Đóng gói |
| **Warehouse** | Đỗ Văn Kho | `warehouse@foodman.vn` | Tồn kho FEFO, Lệnh xuất xe lạnh, Cảm biến IoT, Khách hàng |

> **Truy cập nhanh Demo Login:**
> - `http://127.0.0.1:5000/demo-login/Admin`
> - `http://127.0.0.1:5000/demo-login/Procurement`
> - `http://127.0.0.1:5000/demo-login/QC`
> - `http://127.0.0.1:5000/demo-login/Production`
> - `http://127.0.0.1:5000/demo-login/Warehouse`

---

## 2. Kịch Bản Chi Tiết 13 Bước Chấp Nhận (§12)

```
[PO] -> [GRN] -> [QC & AI] -> [QC DUYỆT] -> [ĐỀ XUẤT BOM] -> [MẺ SX] -> [ĐÓNG GÓI] -> [KHO FEFO] -> [XUẤT KHO] -> [DASHBOARD] -> [TRUY XUẤT 7 TẦNG]
```

---

### BƯỚC 1: Phân Quyền & Đăng Nhập Vai Trò (Role-Based Access)
- **Mục tiêu:** Chứng minh phân quyền đa người dùng và điều hướng thích ứng.
- **Thao tác thực hiện:**
  1. Truy cập `http://127.0.0.1:5000/login`.
  2. Thử bấm vào từng nút đăng nhập nhanh: `Admin`, `Procurement`, `QC`, `Production`, `Warehouse`.
  3. Quan sát menu thanh bên trái (`Sidebar`):
     - Tài khoản *QC* chỉ thấy mục *Chất lượng & Phòng Lab*.
     - Tài khoản *Production* chỉ thấy *Sản xuất & Đóng gói*.
     - Tài khoản *Admin* nhìn thấy toàn bộ 6 phân hệ kèm số đếm huy hiệu (Badge count).
- **Điểm kiểm chứng:**
  - Sidebar hiển thị đúng các phân hệ được cấp phép theo bảng ma trận vai trò.
  - Profile góc dưới bên trái hiển thị tên và phòng ban tương ứng.

---

### BƯỚC 2: Đăng Ký Danh Mục Nhà Cung Cấp & Nguyên Liệu Thô
- **Mục tiêu:** Thiết lập thông tin nhà cung ứng chứng nhận VietGAP / Organic và nguyên liệu sữa tươi.
- **Thao tác thực hiện:**
  1. Đăng nhập vai trò **Procurement** hoặc **Admin**.
  2. Điều hướng đến: `http://127.0.0.1:5000/procurement?view=suppliers`.
  3. Quan sát danh sách nhà cung cấp dạng thẻ 2 cột: `Mộc Châu Farm Co.`, `Trang Trại Sữa Dalat Milk`. Bấm vào một thẻ để xem ngăn kéo chi tiết (chỉ số đánh giá tín nhiệm, chứng chỉ an toàn thực phẩm).
  4. Chuyển sang thẻ tab **"Danh mục nguyên liệu"** (`/procurement?view=raw-materials`):
     - Xem mã nguyên liệu `RAW-MILK-001` (Sữa bò tươi nguyên kem tiệt trùng).

---

### BƯỚC 3: Khởi Tạo Đơn Mua Hàng Đa Dòng (Multi-Line Purchase Order)
- **Mục tiêu:** Tạo đơn hàng mua nguyên liệu cho nhà cung cấp với nhiều mã hàng và tổng giá trị tự động.
- **Thao tác thực hiện:**
  1. Chọn tab **"Đơn mua PO"** (`/procurement?view=po`).
  2. Bấm nút **`+ Tạo đơn mua PO mới`** ở góc trên bên phải.
  3. Modal khởi tạo mở ra:
     - Chọn nhà cung cấp: *Nông trại Mộc Châu Farm Co.*.
     - Thêm dòng nguyên liệu: *Sữa tươi nguyên kem loại 1* — Số lượng: `25.0 Tấn` — Đơn giá: `18,500,000 VNĐ/Tấn`.
     - Thêm dòng 2: *Đường tinh luyện RE Biên Hòa* — Số lượng: `2.0 Tấn` — Đơn giá: `22,000,000 VNĐ/Tấn`.
     - Tổng tiền tự động tính: `506,500,000 VNĐ`.
  4. Bấm **Lưu & Phê duyệt Đơn PO**.
- **Điểm kiểm chứng:**
  - Thẻ PO xuất hiện ngay lập tức với mã `PO-2026-xxxx`, huy hiệu trạng thái `APPROVED` (xanh lá).

---

### BƯỚC 4: Nhập Kho Cổng Bồn GRN & Tự Động Sinh Mã Lô (`PENDING_QC`)
- **Mục tiêu:** Tiếp nhận xe bồn giao sữa, ghi nhận niêm phong chì và tự động tạo lô nguyên liệu chuyển sang trạng thái chờ kiểm định chất lượng.
- **Thao tác thực hiện:**
  1. Chọn tab **"Phiếu GRN"** (`/procurement?view=grn`).
  2. Bấm **`+ Tạo phiếu nhập GRN`**:
     - Chọn PO vừa tạo ở Bước 3.
     - Nhập số xe bồn: `29C-882.15`.
     - Số vận đơn: `BL-MC-0908`.
     - Ghi chú: *Niêm phong chì cửa van nguyên vẹn, nhiệt độ xe 3.8°C*.
  3. Bấm **Xác nhận nhập kho GRN**.
  4. Chuyển sang tab **"Lô nguyên liệu"** (`/procurement?view=lots`):
     - Quan sát lô nguyên liệu mới được sinh ra: `LOT-RM-2026-xxx`.
     - Huy hiệu trạng thái hiển thị màu hổ phách: `PENDING_QC`.
- **Điểm kiểm chứng:**
  - Số đếm huy hiệu hàng chờ QC trên sidebar nhảy tăng thêm +1.

---

### BƯỚC 5: Thử Nghiệm Phòng Lab, Chứng Thư COA & Thị Giác Máy Tính YOLO AI
- **Mục tiêu:** Kiểm nghiệm vi sinh, hóa lý, xác thực COA và quét khuyết tật ngoại quan bằng mô hình YOLOv8.
- **Thao tác thực hiện:**
  1. Đăng nhập vai trò **QC Inspector** (hoặc dùng Admin) và truy cập `http://127.0.0.1:5000/qc`.
  2. Quan sát hàng chờ kiểm định **QC Queue**: lô hàng mới ở Bước 4 đang hiển thị tại đây.
  3. Bấm vào thẻ lô hàng để mở **Ngăn kéo kiểm định tổng hợp (Wide Combined Review Drawer)**:
     - **Mục 1 (Thị giác máy tính YOLO AI):** Ảnh chụp niêm phong pallet hiển thị với các khung chữ nhật định vị khuyết tật (Bounding Boxes), nhãn khuyết tật (e.g. `Rách seal: 94.2%`, `Móp góc: 88.5%`), thời gian suy luận: `~48ms` bằng mô hình `YOLOv8x-FoodDefect-v2.1`.
     - **Mục 2 (Bảng chỉ tiêu Lab):** Độ Brix `12.3°Bx`, pH `6.68`, Vi sinh Coliform `0 CFU/ml`, Kháng sinh `Âm tính` (Tất cả đạt chuẩn).
     - **Mục 3 (Chứng thư COA):** Hiển thị chứng chỉ phòng thí nghiệm VILAS 102 / ISO 17025.
- **Điểm kiểm chứng:**
  - Thông báo cảnh báo màu vàng: *"KẾT QUẢ AI YOLO LÀ THAM KHẢO & KHÔNG TỰ ĐỘNG DUYỆT. BẮT BUỘC CHUYÊN VIÊN QC XÁC NHẬN."*

---

### BƯỚC 6: Cổng Phê Duyệt QC Của Chuyên Viên Con Người (Human-Only Decision)
- **Mục tiêu:** Đảm bảo tính pháp lý an toàn thực phẩm — máy móc và AI không thể tự phê duyệt mà phải do chuyên viên click nút xác nhận.
- **Thao tác thực hiện:**
  1. Ở chân ngăn kéo kiểm định, quan sát thanh công cụ hành động gồm 3 nút: **`Duyệt (Approve)`**, **`Tạm giữ (Hold)`**, **`Từ chối (Reject)`**.
  2. Nhập ghi chú: *Đối chiếu đạt chuẩn ISO 22000, cho phép chuyển sang sản xuất*.
  3. Bấm nút màu xanh **`Phê duyệt đạt chuẩn (Approve)`**.
  4. Thông báo xác nhận thành công xuất hiện. Thẻ chuyển trạng thái sang `APPROVED` (Xanh lá).
- **Điểm kiểm chứng:**
  - Lô hàng rời khỏi hàng chờ `QC Queue` và xuất hiện trong cổng chờ sản xuất (`/api/qc/production-ready-lots`).

---

### BƯỚC 7: Kiểm Tra Tồn Khẩu BOM & Khuyến Nghị Sản Xuất Tự Động
- **Mục tiêu:** Động cơ quy tắc (Rule engine) đối chiếu các lô đã đạt chuẩn QC với định mức công thức BOM.
- **Thao tác thực hiện:**
  1. Chuyển sang phân hệ **Sản xuất & Đóng gói**: `http://127.0.0.1:5000/production?view=recommendations`.
  2. Quan sát bảng đề xuất sản phẩm:
     - Thẻ sản phẩm *Sữa tiệt trùng Ít Đường 180ml UHT*: Huy hiệu xanh lá `PRODUCEABLE` (Đủ nguyên liệu).
     - Hiển thị số lượng mẻ tối đa có thể nấu: *2 - 3 Mẻ*.
     - Thẻ sản phẩm thiếu nguyên liệu hiển thị huy hiệu đỏ `LACKING_MATERIALS` kèm danh sách chi tiết thành phần thiếu hụt.

---

### BƯỚC 8: Khởi Tạo Mẻ Sản Xuất (Batch Creation Wizard) Tiêu Thụ Lô Đã Duyệt
- **Mục tiêu:** Cấp phát cụ thể các lô nguyên liệu đạt chuẩn vào bảng `batch_raw_materials` và sinh 5 công đoạn chế biến.
- **Thao tác thực hiện:**
  1. Tại thẻ sản phẩm đạt chuẩn, bấm **`+ Khởi tạo mẻ sản xuất`** (hoặc nút bấm trên thanh tiêu đề).
  2. Nhập thông số:
     - Sản lượng mục tiêu: `5,000 Thùng`.
     - Dây chuyền: `Line A1 - Tetra Pak Aseptic 250ml`.
  3. Bấm **Bắt đầu sản xuất**.
- **Điểm kiểm chứng:**
  - Mẻ sản xuất mới được tạo với mã định danh dạng `LOT-2026-xxx`.
  - Trạng thái ban đầu: `IN_PROGRESS` (Hổ phách), thanh tiến độ 20%.

---

### BƯỚC 9: Dòng Thời Gian 5 Công Đoạn (Stepper) & Chứng Nhận Đóng Gói
- **Mục tiêu:** Cập nhật mốc thời gian thực của 5 công đoạn và ghi nhận quy cách đóng gói vô trùng.
- **Thao tác thực hiện:**
  1. Chuyển sang tab **"Lô sản xuất"** (`/production?view=batches`).
  2. Bấm vào thẻ mẻ sản xuất vừa tạo để mở ngăn kéo trượt **Stepper Timeline**:
     - *Công đoạn 1: Chuẩn bị nguyên liệu (Material Prep)* [Hoàn tất]
     - *Công đoạn 2: Phối trộn & Đồng hóa (Mixing & Homogenization)* [Hoàn tất]
     - *Công đoạn 3: Tiệt trùng nhiệt UHT (UHT Pasteurization)* [Hoàn tất]
     - *Công đoạn 4: Chiết rót vô trùng (Aseptic Filling)* [Hoàn tất]
     - *Công đoạn 5: Đóng gói & Hoàn thiện (Packaging)* [Hoàn tất]
  3. Bấm **Chuyển công đoạn tiếp theo** cho đến khi đạt 100%.
  4. Nhập chứng chỉ bao bì: *5,000 Thùng carton 5 lớp + Màng tiệt trùng Tetra Brik*.
  5. Bấm **Xác nhận hoàn tất mẻ**.
- **Điểm kiểm chứng:**
  - Trạng thái mẻ chuyển sang `COMPLETE` (Xanh lá).
  - Hợp đồng đầu ra Module 4 (`/api/production/completed-batches`) được kích hoạt.

---

### BƯỚC 10: Đồng Bộ Tồn Kho Thành Phẩm & Thứ Tự Ưu Tiên FEFO
- **Mục tiêu:** Chỉ những mẻ có trạng thái `COMPLETE` mới được đồng bộ vào kho và tự động sắp xếp theo thứ tự cận hạn trước (FEFO).
- **Thao tác thực hiện:**
  1. Chuyển sang phân hệ **Kho bãi & Vận tải**: `http://127.0.0.1:5000/warehouse?view=inventory`.
  2. Quan sát lưới thẻ tồn kho:
     - Lô hàng vừa hoàn tất xuất hiện với mã SKU mới (e.g. `INV-SKU-xxx`), vị trí kệ lưu trữ (`Khu C - Kệ trượt Pallet`).
     - Danh sách thẻ được sắp xếp nghiêm ngặt theo ngày hết hạn tăng dần (`expiry_date ASC`).
     - Thẻ cận hạn trong vòng 15 ngày hiển thị huy hiệu viền đỏ nhấp nháy: `EXPIRING_SOON`.
- **Điểm kiểm chứng:**
  - Tuân thủ nguyên tắc First Expired, First Out (FEFO) ngăn chặn tuyệt đối tình trạng sữa hết hạn lưu cữu trong kho.

---

### BƯỚC 11: Lập Lệnh Xuất Kho Xe Lạnh & Giảm Trừ Tồn Kho Thời Gian Thực
- **Mục tiêu:** Tạo chuyến giao hàng VinMart / MM Mega Market, giám sát nhiệt độ xe lạnh và kiểm tra lượng tồn kho giảm trực tiếp.
- **Thao tác thực hiện:**
  1. Chuyển sang tab **"Lệnh xuất kho"** (`/warehouse?view=dispatches`).
  2. Bấm **`+ Tạo lệnh xuất kho mới`**:
     - Khách hàng: *Tập đoàn Bán lẻ VinCommerce (WinMart)*.
     - Chọn lô tồn kho thành phẩm ở Bước 10 (Số lượng ban đầu: `5,000 Thùng`).
     - Nhập số lượng xuất: `1,000 Thùng`.
     - Chọn đội xe: *Xe 29C-998.11 (Lái xe: Lê Văn Tiến)*.
  3. Bấm **Xác nhận xuất bến**.
  4. Quay lại tab **"Tồn kho FEFO"**:
     - Số lượng khả dụng của lô hàng giảm ngay lập tức: từ `5,000` xuống còn `4,000 Thùng`!
- **Điểm kiểm chứng:**
  - Lệnh xuất `DSP-2026-xxx` hiển thị nhiệt độ cảm biến thùng lạnh `❄ 3.8°C` (trong ngưỡng chuẩn `2.0°C - 6.0°C`).

---

### BƯỚC 12: Bảng Điều Hành Trung Tâm, Báo Cáo Phân Tích & Quét Cảnh Báo
- **Mục tiêu:** Tổng hợp số liệu KPI thời gian thực, trực quan hóa biểu đồ Chart.js và kích hoạt động cơ cảnh báo thông minh.
- **Thao tác thực hiện:**
  1. Truy cập **Bảng điều hành nhà máy** (`/dashboard`):
     - Quan sát 4 thẻ KPI: *Giá trị tồn kho (Tỷ VNĐ)*, *Hàng cận hạn FEFO*, *Chuyến xe xuất bến*, *Cảnh báo mở*.
     - Đồ thị đường kép Chart.js so sánh sản xuất vs. xuất kho trong 7 ngày.
     - Đồ thị Donut phân bổ cơ cấu nhóm hàng sữa.
  2. Chuyển sang trang **Báo cáo & Phân tích** (`/reports`):
     - Xem 3 biểu đồ nâng cao: *Năng suất Throughput 3 công đoạn*, *Tỷ lệ lỗi phế phẩm QC & AI*, *Xu hướng xuất kho & nhiệt độ xe lạnh*.
     - Bấm thử các nút thời gian: `7 Ngày`, `30 Ngày`, `90 Ngày`.
     - Bấm nút **"Xuất Báo Cáo"** để tải file CSV tóm tắt.
  3. Chuyển sang **Trung tâm cảnh báo** (`/alerts`):
     - Bấm nút **"Quét đánh giá hệ thống"** để kích hoạt bộ lọc tự động: Quét tồn kho thấp, quét lô cận hạn và hàng chờ QC tồn đọng.

---

### BƯỚC 13: Truy Xuất Nguồn Gốc 7 Tầng Toàn Trình (Flagship Traceability)
- **Mục tiêu:** Minh chứng mắt xích chuỗi giá trị unbroken không bị đứt đoạn từ nông trại đến siêu thị bán lẻ.
- **Thao tác thực hiện:**
  1. Nhập mã mẻ sản xuất (e.g. `LOT-2026-005` hoặc `LOT-2026-089`) vào thanh tìm kiếm trên cùng của Topbar rồi nhấn **Enter** (hoặc truy cập `/traceability`).
  2. Màn hình hiển thị đầy đủ sơ đồ **7 Mắt Xích Giá Trị**:
     ```
     [1. Nhà Cung Cấp] ──> [2. Lô Nguyên Liệu] ──> [3. Kiểm Định QC & AI] ──>
     [4. Chế Biến Mẻ]  ──> [5. Đóng Gói Vô Trùng] ──> [6. Tồn Kho FEFO] ──> [7. Xuất Bến Giao Hàng]
     ```
  3. Bấm vào từng nút mắt xích:
     - Bấm vào **Mắt xích 1**: Xem chứng nhận VietGAP của Nông trại Ba Vì / Mộc Châu.
     - Bấm vào **Mắt xích 3**: Xem kết quả Lab 0 CFU Coliform và ảnh quét AI YOLO.
     - Bấm vào **Mắt xích 4 & 5**: Xem mốc thời gian tiệt trùng UHT và màng Tetra Brik.
     - Bấm vào **Mắt xích 7**: Xem khách hàng WinMart và đồ thị nhiệt độ xe lạnh `3.8°C`.
- **Điểm kiểm chứng:**
  - Chuỗi dữ liệu liên kết 100% chính xác, không có mắt xích rỗng hay dữ liệu giả lập.

---

### BƯỚC PHỤ: Trải Nghiệm Trợ Lý AI Điều Hành (FoodMan AI Chatbot)
- **Mục tiêu:** Tương tác với trợ lý trí tuệ nhân tạo chuyên sâu về chuỗi cung ứng thực phẩm.
- **Thao tác thực hiện:**
  1. Bấm vào nút tròn màu Navy nổi ở góc dưới bên phải màn hình (`Trợ lý AI FoodMan`).
  2. Hộp thoại thông minh mở ra:
     - Bấm vào câu hỏi gợi ý: `⚡ Tồn kho FEFO` ➔ AI phản hồi ngay lập tức số lượng tồn kho khả dụng và các lô cận hạn.
     - Nhập câu hỏi: *"Truy xuất mẻ LOT-2026-005"* ➔ AI tóm tắt 7 tầng và cung cấp link bấm xem trực tiếp.
     - Nhập câu hỏi: *"Có bao nhiêu lô đang chờ QC?"* ➔ AI báo cáo tình hình hàng chờ và nguyên tắc kiểm định con người.
- **Điểm kiểm chứng:**
  - Trợ lý AI truy vấn cơ sở dữ liệu thời gian thực và trả về câu trả lời định dạng phong phú (Markdown, badge, link điều hướng).

---

## 3. Lệnh Kiểm Thử Tự Động Đầu Cuối

Để kiểm tra toàn bộ 13 bước trong 1 lần chạy tự động liên tục qua giao thức HTTP (không chỉnh sửa DB thủ công):

```powershell
python "C:\Users\L E N O V O\.gemini\antigravity-ide\brain\433255af-d683-47ef-8854-6576f05b1fcc\scratch\test_phase5_continuous_acceptance.py"
```

Kết quả kỳ vọng: **13/13 Acceptance Criteria (§12) PASSED CONTINUOUSLY WITH 100% SUCCESS!**
