/**
 * FOOD MAN - INDUSTRIAL FOOD MANUFACTURING & SUPPLY CHAIN MANAGEMENT
 * Master-Detail Architecture & State Management
 */

// Global Application State
const appState = {
  currentDomain: 'production', // 'production' | 'qc' | 'raw-materials' | 'inventory' | 'dispatch'
  currentFilter: 'all',        // 'all' | 'attention' | 'ready'
  searchQuery: '',
  selectedCardId: null,
  activeItem: null
};

// Domain Metadata & Display Configurations
const domainConfigs = {
  production: {
    title: "Lô sản xuất & Đóng gói",
    breadcrumb: ["Trang chủ", "Nhà máy", "Lô sản xuất"],
    createBtnText: "+ Tạo lô sản xuất",
    counterLabel: "lô đang chạy",
    unit: "Thùng",
    dropdown1Label: "Trạng thái vận hành",
    dropdown1Options: [
      { value: "running", label: "Đang sản xuất", pill: "amber" },
      { value: "qc_hold", label: "Chờ duyệt QC", pill: "amber" },
      { value: "completed", label: "Đã hoàn thành", pill: "green" },
      { value: "scheduled", label: "Lên lịch ca tới", pill: "blue" }
    ],
    dropdown2Label: "Dây chuyền chiết rót",
    dropdown2Options: ["Line A1 - Tetra Pak 250ml", "Line A2 - Chai PET 350ml", "Line B1 - Lon Nhôm 330ml", "Line C - Đóng hộp tiệt trùng"],
    dropdown3Label: "Trưởng ca vận hành",
    dropdown3Options: ["Trần Minh Quân", "Lê Hải Đăng", "Nguyễn Thu Hà", "Vũ Hoàng Long"],
    dropdown4Label: "Khu vực lưu trữ tạm",
    dropdown4Options: ["Kho lạnh trung tâm (Block A)", "Kho đệm đóng gói (Zone 2)", "Silo chứa vô trùng #04", "Khu chờ xuất xưởng"]
  },
  qc: {
    title: "Kiểm tra chất lượng (QC Review)",
    breadcrumb: ["Trang chủ", "Quản lý", "Kiểm tra QC"],
    createBtnText: "+ Phiếu kiểm nghiệm mới",
    counterLabel: "mẫu cần duyệt",
    unit: "Chỉ số",
    dropdown1Label: "Kết luận kiểm định",
    dropdown1Options: [
      { value: "pending", label: "Đang kiểm nghiệm", pill: "amber" },
      { value: "passed", label: "Đạt chuẩn an toàn", pill: "green" },
      { value: "retest", label: "Cần test lại vi sinh", pill: "amber" },
      { value: "rejected", label: "Không đạt chỉ tiêu", pill: "red" }
    ],
    dropdown2Label: "Phòng Lab phân tích",
    dropdown2Options: ["Lab Vi sinh #01", "Lab Hóa lý #02", "Trạm kiểm tra cảm quan", "Phòng test độc chất"],
    dropdown3Label: "Chuyên viên kiểm định",
    dropdown3Options: ["ThS. Phạm Thu Trang", "KS. Đỗ Đức Minh", "Vũ Hoàng Long", "Trần Minh Quân"],
    dropdown4Label: "Tiêu chuẩn áp dụng",
    dropdown4Options: ["QCVN 5-1:2010/BYT", "ISO 22000:2018", "HACCP Tiêu chuẩn loại A", "FSSC 22000 v5.1"]
  },
  "raw-materials": {
    title: "Lô nguyên liệu đầu vào",
    breadcrumb: ["Trang chủ", "Quản lý", "Nguyên liệu thô"],
    createBtnText: "+ Nhập lô nguyên liệu",
    counterLabel: "lô trong kho",
    unit: "Tấn",
    dropdown1Label: "Trạng thái kiểm tra",
    dropdown1Options: [
      { value: "inspected", label: "Đạt chuẩn nhập kho", pill: "green" },
      { value: "sampling", label: "Đang lấy mẫu kiểm", pill: "amber" },
      { value: "quarantine", label: "Cách ly theo dõi", pill: "amber" },
      { value: "rejected", label: "Trả về nhà cung cấp", pill: "red" }
    ],
    dropdown2Label: "Kho nguyên liệu",
    dropdown2Options: ["Kho mát Silo A (18°C)", "Kho khô nguyên liệu C2", "Kho lạnh -18°C (Protein)", "Bồn chứa vô trùng B3"],
    dropdown3Label: "Nhân viên nhận hàng",
    dropdown3Options: ["Nguyễn Thu Hà", "Lê Hải Đăng", "Đỗ Đức Minh", "Trần Minh Quân"],
    dropdown4Label: "Nhà cung ứng",
    dropdown4Options: ["Fonterra New Zealand", "Mộc Châu Farm Co.", "Vinamilk Organic Dairy", "Cargill Agriculture"]
  },
  inventory: {
    title: "Tồn kho thành phẩm nhà máy",
    breadcrumb: ["Trang chủ", "Kho bãi", "Tồn kho thành phẩm"],
    createBtnText: "+ Điều chuyển tồn kho",
    counterLabel: "mã hàng lưu kho",
    unit: "Pallet",
    dropdown1Label: "Tình trạng tồn kho",
    dropdown1Options: [
      { value: "in_stock", label: "Tồn kho tối ưu", pill: "green" },
      { value: "low_stock", label: "Sắp chạm ngưỡng tối thiểu", pill: "amber" },
      { value: "reserved", label: "Đã giữ cho đơn hàng lớn", pill: "blue" },
      { value: "near_expiry", label: "Cận date xuất gấp", pill: "amber" }
    ],
    dropdown2Label: "Vị trí kệ kho",
    dropdown2Options: ["Dãy A - Kệ 04 (Tầng 3)", "Dãy B - Kho lạnh Pallet", "Dãy C - Kệ trượt FIFO", "Dãy D - Khu chờ xuất"],
    dropdown3Label: "Thủ kho phụ trách",
    dropdown3Options: ["Hoàng Đình Tuấn", "Nguyễn Thu Hà", "Lê Hải Đăng", "Vũ Hoàng Long"],
    dropdown4Label: "Chính sách xuất",
    dropdown4Options: ["FEFO (Hạn dùng trước xuất trước)", "FIFO (Nhập trước xuất trước)", "Ưu tiên hợp đồng lớn", "Lô biệt trữ theo yêu cầu"]
  },
  dispatch: {
    title: "Lệnh xuất kho & Vận chuyển",
    breadcrumb: ["Trang chủ", "Vận tải", "Lệnh xuất kho"],
    createBtnText: "+ Tạo lệnh điều phối",
    counterLabel: "lệnh xuất kho",
    unit: "Kiện",
    dropdown1Label: "Tiến độ điều phối",
    dropdown1Options: [
      { value: "dispatched", label: "Đang giao hàng", pill: "green" },
      { value: "loading", label: "Đang bốc hàng lên xe", pill: "amber" },
      { value: "ready", label: "Đã đóng gói chờ xe", pill: "green" },
      { value: "pending_doc", label: "Chờ kiểm duyệt chứng từ", pill: "amber" }
    ],
    dropdown2Label: "Đơn vị vận tải",
    dropdown2Options: ["Đội xe tải lạnh Nhà Máy (Xe 04)", "Đội xe container lạnh Nam Hà", "J&T Express Logistics Cold", "Đội vận chuyển Viettel Post"],
    dropdown3Label: "Tài xế / Phụ trách",
    dropdown3Options: ["Bác tài Bùi Văn Hùng", "Nguyễn Văn Thiện (Xe 29C-8819)", "Lê Văn Hùng", "Phạm Văn Tân"],
    dropdown4Label: "Điểm giao nhận",
    dropdown4Options: ["Tổng kho Mega Market Bình Phú", "Kho trung chuyển VinMart Hà Nội", "Cảng Cát Lái (Xuất khẩu)", "Siêu thị AEON Mall Long Biên"]
  }
};

// Rich Multi-Domain Datasets
const initialData = {
  production: [
    {
      id: "LOT-2026-089",
      category: "Dây chuyền sữa tươi",
      title: "Sữa tiệt trùng Ít Đường 180ml UHT",
      statValue: "4,500 / 5,000",
      statSub: "Thùng hoàn thành",
      progress: 90,
      progressColor: "fill-amber",
      miniGrid: [
        { label: "Ngày SX / Ca", value: "08/09/2026 - Ca 1" },
        { label: "Dây chuyền", value: "Line A1 - Tetra Pak" },
        { label: "Nhiệt độ UHT", value: "138.5°C / 4s" },
        { label: "HSD thành phẩm", value: "08/03/2027" }
      ],
      avatars: [
        { initial: "TM", bg: "#162B4E", name: "Trần Minh Quân" },
        { initial: "LH", bg: "#2563EB", name: "Lê Hải Đăng" },
        { initial: "NT", bg: "#059669", name: "Nguyễn Thu Hà" }
      ],
      status: "running",
      statusLabel: "Đang chiết rót",
      statusPill: "amber",
      dropdown1: "running",
      dropdown2: "Line A1 - Tetra Pak 250ml",
      dropdown3: "Trần Minh Quân",
      dropdown4: "Kho lạnh trung tâm (Block A)",
      readOnlySpecs: [
        { label: "Độ chuẩn Brix", value: "11.2 ± 0.2°Bx", icon: "flask" },
        { label: "Hàm lượng Protein", value: "3.1 g / 100ml", icon: "activity" },
        { label: "Độ chua chuẩn độ", value: "14.2°T", icon: "check-circle" },
        { label: "Mã QR Truy xuất", value: "LOT089-UHT-2026", icon: "qr-code", mono: true },
        { label: "Số mẻ nấu thanh trùng", value: "Mẻ #04/Bồn tiệt trùng B", icon: "database" }
      ],
      timeline: [
        { time: "06:30 AM", desc: "Vệ sinh CIP dây chuyền đạt chuẩn 100%" },
        { time: "07:15 AM", desc: "Bắt đầu bơm sữa nguyên liệu vào bồn ủ UHT" },
        { time: "08:00 AM", desc: "Chiết rót đạt 2,000 thùng đầu tiên" },
        { time: "10:45 AM", desc: "Lấy mẫu vi sinh kiểm tra giữa ca" }
      ],
      bannerType: "milk"
    },
    {
      id: "LOT-2026-090",
      category: "Dòng nước ép trái cây",
      title: "Nước cam ép tép Tự Nhiên 330ml Can",
      statValue: "12,000 / 12,000",
      statSub: "Lon đóng gói",
      progress: 100,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Ngày SX / Ca", value: "07/09/2026 - Ca 2" },
        { label: "Dây chuyền", value: "Line B1 - Lon Nhôm" },
        { label: "Độ Brix đo được", value: "12.8°Bx (Chuẩn)" },
        { label: "Chỉ số pH", value: "3.62 pH" }
      ],
      avatars: [
        { initial: "VH", bg: "#D97706", name: "Vũ Hoàng Long" },
        { initial: "PT", bg: "#7C3AED", name: "Phạm Thu Trang" }
      ],
      status: "completed",
      statusLabel: "Đạt chuẩn xuất xưởng",
      statusPill: "green",
      dropdown1: "completed",
      dropdown2: "Line B1 - Lon Nhôm 330ml",
      dropdown3: "Vũ Hoàng Long",
      dropdown4: "Khu chờ xuất xưởng",
      readOnlySpecs: [
        { label: "Hàm lượng tép cam", value: "15% thể tích", icon: "flask" },
        { label: "Áp suất đóng lon", value: "0.28 MPa CO2", icon: "activity" },
        { label: "Kiểm tra mí lon", value: "Kín 100% - Đạt", icon: "check-circle" },
        { label: "Mã QR Truy xuất", value: "ORANGE-330-LOT90", icon: "qr-code", mono: true },
        { label: "Chứng nhận", value: "HACCP & Halal Certified", icon: "shield" }
      ],
      timeline: [
        { time: "Hôm qua 14:00", desc: "Nhập tép cam nguyên liệu từ Mộc Châu" },
        { time: "Hôm qua 18:30", desc: "Hoàn tất đóng 12,000 lon" },
        { time: "Hôm nay 08:00", desc: "Phòng QC cấp phiếu xuất xưởng xanh" }
      ],
      bannerType: "juice"
    },
    {
      id: "LOT-2026-091",
      category: "Sữa chua lên men",
      title: "Sữa chua ăn Nha Đam 100g Hộp 4",
      statValue: "6,200 / 8,000",
      statSub: "Lốc sản xuất",
      progress: 77,
      progressColor: "fill-amber",
      miniGrid: [
        { label: "Thời gian ủ", value: "7.5 giờ / 42°C" },
        { label: "Men cấy", value: "L. Bulgaricus & S. Therm" },
        { label: "Dây chuyền", value: "Line C - Đóng hũ" },
        { label: "Hạn dùng", value: "45 ngày (Lạnh 4°C)" }
      ],
      avatars: [
        { initial: "TM", bg: "#162B4E", name: "Trần Minh Quân" },
        { initial: "ĐM", bg: "#0D9488", name: "Đỗ Đức Minh" }
      ],
      status: "qc_hold",
      statusLabel: "Chờ kiểm vi sinh ủ",
      statusPill: "amber",
      dropdown1: "qc_hold",
      dropdown2: "Line C - Đóng hộp tiệt trùng",
      dropdown3: "Trần Minh Quân",
      dropdown4: "Kho lạnh trung tâm (Block A)",
      readOnlySpecs: [
        { label: "Nhiệt độ bồn ủ", value: "42.0°C ổn định", icon: "activity" },
        { label: "Mật độ vi khuẩn sống", value: "≥ 10^7 CFU/g", icon: "flask" },
        { label: "Tỷ lệ thạch nha đam", value: "8.5% sạch xơ", icon: "check-circle" },
        { label: "Mã QR Truy xuất", value: "YOG-ALOE-091", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "04:00 AM", desc: "Nạp men Streptococcus thermophilus" },
        { time: "09:30 AM", desc: "Cắt đông mẻ ủ đạt pH 4.4" },
        { time: "10:15 AM", desc: "Trộn hạt nha đam tiệt trùng nhiệt" }
      ],
      bannerType: "yogurt"
    },
    {
      id: "LOT-2026-092",
      category: "Sữa hạt dinh dưỡng",
      title: "Sữa Hạt Óc Chó Yến Mạch 180ml hộp giấy",
      statValue: "8,000 / 8,000",
      statSub: "Thùng hoàn tất",
      progress: 100,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Tỷ lệ hạt", value: "14% Hạt óc chó Mỹ" },
        { label: "Đồng hóa", value: "200 Bar 2 cấp" },
        { label: "Dây chuyền", value: "Line A2 - Chai PET" },
        { label: "Đánh giá ca", value: "Tỷ lệ hao hụt < 0.4%" }
      ],
      avatars: [
        { initial: "LH", bg: "#2563EB", name: "Lê Hải Đăng" },
        { initial: "NT", bg: "#059669", name: "Nguyễn Thu Hà" }
      ],
      status: "completed",
      statusLabel: "Sẵn sàng lưu kho",
      statusPill: "green",
      dropdown1: "completed",
      dropdown2: "Line A2 - Chai PET 350ml",
      dropdown3: "Lê Hải Đăng",
      dropdown4: "Kho đệm đóng gói (Zone 2)",
      readOnlySpecs: [
        { label: "Độ mịn hạt nghiền", value: "< 25 micron", icon: "activity" },
        { label: "Chỉ tiêu Coliform", value: "Âm tính (Negative)", icon: "shield" },
        { label: "Hàm lượng Omega-3", value: "120mg / 100ml", icon: "flask" },
        { label: "Mã QR Truy xuất", value: "NUT-WALNUT-092", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "Hôm qua 07:00", desc: "Ngâm hạt óc chó và thủy phân enzyme yến mạch" },
        { time: "Hôm qua 16:00", desc: "Chiết rót vô trùng hoàn tất 8,000 thùng" },
        { time: "09:00 AM", desc: "Pallet đã bọc màng co chờ chuyển kho" }
      ],
      bannerType: "nuts"
    }
  ],

  qc: [
    {
      id: "QC-TEST-442",
      category: "Kiểm nghiệm vi sinh",
      title: "Mẫu Sữa chua nha đam Lô #LOT-2026-091",
      statValue: "18 / 20",
      statSub: "Tiêu chí đã đạt",
      progress: 90,
      progressColor: "fill-amber",
      miniGrid: [
        { label: "Người lấy mẫu", value: "KS. Đỗ Đức Minh" },
        { label: "Thời gian cấy", value: "08/09/2026 08:30" },
        { label: "Chỉ số Coliform", value: "< 10 CFU/ml (Âm tính)" },
        { label: "Kết quả sơ bộ", value: "Đang chờ đọc khuẩn lạc" }
      ],
      avatars: [
        { initial: "ĐM", bg: "#0D9488", name: "Đỗ Đức Minh" },
        { initial: "PT", bg: "#7C3AED", name: "Phạm Thu Trang" }
      ],
      status: "pending",
      statusLabel: "Đang ủ đọc khuẩn",
      statusPill: "amber",
      dropdown1: "pending",
      dropdown2: "Lab Vi sinh #01",
      dropdown3: "ThS. Phạm Thu Trang",
      dropdown4: "QCVN 5-1:2010/BYT",
      readOnlySpecs: [
        { label: "Đĩa cấy Petrifilm", value: "3M Aerobic Count Plate", icon: "flask" },
        { label: "Thời gian ủ nhiệt", value: "48 giờ ở 35°C ± 1°C", icon: "activity" },
        { label: "Khuẩn Salmonella", value: "Không phát hiện trong 25g", icon: "shield" },
        { label: "Mã phiếu Lab", value: "LAB-MIC-2026-898", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "08:15 AM", desc: "Lấy 5 mẫu ngẫu nhiên tại bồn rót số 2" },
        { time: "09:00 AM", desc: "Thực hiện pha loãng nồng độ 10^-1 đến 10^-3" },
        { time: "11:00 AM", desc: "Đưa vào tủ ấm Memmert 37°C" }
      ],
      bannerType: "qc"
    },
    {
      id: "QC-TEST-443",
      category: "Hóa lý & Dinh dưỡng",
      title: "Mẫu Nước ép cam tép Lô #LOT-2026-090",
      statValue: "100%",
      statSub: "Đạt 15/15 chỉ tiêu",
      progress: 100,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Hàm lượng Vitamin C", value: "48mg / 100ml" },
        { label: "Độ Brix chuẩn", value: "12.8° (Dải cho phép 12.5-13.0)" },
        { label: "Chất bảo quản", value: "Hoàn toàn không có" },
        { label: "Kết luận", value: "Cấp chứng thư xuất xưởng" }
      ],
      avatars: [
        { initial: "PT", bg: "#7C3AED", name: "Phạm Thu Trang" }
      ],
      status: "passed",
      statusLabel: "Đạt chuẩn an toàn 100%",
      statusPill: "green",
      dropdown1: "passed",
      dropdown2: "Lab Hóa lý #02",
      dropdown3: "ThS. Phạm Thu Trang",
      dropdown4: "ISO 22000:2018",
      readOnlySpecs: [
        { label: "Khúc xạ kế đo", value: "Atago Pocket PAL-1", icon: "activity" },
        { label: "Độ đục cảm quan", value: "Đồng nhất, tự nhiên", icon: "check-circle" },
        { label: "Kim loại nặng Pb", value: "< 0.02 mg/kg (Chuẩn)", icon: "shield" },
        { label: "Mã kiểm định Lab", value: "QC-CHEM-90-OK", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "Hôm qua 16:30", desc: "Nhận mẫu từ dây chuyền đóng lon" },
        { time: "Hôm qua 19:00", desc: "Kiểm tra HPLC sắc ký lỏng hàm lượng acid hữu cơ" },
        { time: "Sáng nay 08:30", desc: "Trưởng phòng ký duyệt đóng dấu ĐẠT" }
      ],
      bannerType: "juice"
    }
  ],

  "raw-materials": [
    {
      id: "RAW-LOT-512",
      category: "Sữa tươi thô",
      title: "Sữa bò tươi Organic nông trại Mộc Châu",
      statValue: "18.5 / 20",
      statSub: "Tấn xe bồn lạnh",
      progress: 92,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Nhiệt độ bồn xe", value: "3.2°C (Chuẩn < 4°C)" },
        { label: "Hàm lượng béo", value: "3.85% tự nhiên" },
        { label: "Chỉ số Resazurin", value: "Loại 1 (Rất tốt)" },
        { label: "Test kháng sinh", value: "Âm tính hoàn toàn" }
      ],
      avatars: [
        { initial: "NT", bg: "#059669", name: "Nguyễn Thu Hà" },
        { initial: "TM", bg: "#162B4E", name: "Trần Minh Quân" }
      ],
      status: "inspected",
      statusLabel: "Đạt chuẩn nhập bồn",
      statusPill: "green",
      dropdown1: "inspected",
      dropdown2: "Bồn chứa vô trùng B3",
      dropdown3: "Nguyễn Thu Hà",
      dropdown4: "Mộc Châu Farm Co.",
      readOnlySpecs: [
        { label: "Số xe bồn", value: "29H-439.12 (Bồn Inox 316)", icon: "truck" },
        { label: "Tỷ trọng ở 20°C", value: "1.029 g/cm3", icon: "activity" },
        { label: "Điểm đông đặc", value: "-0.528°C", icon: "flask" },
        { label: "COA nhà cung cấp", value: "COA-MC-2026-901", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "05:00 AM", desc: "Xe bồn cập cổng kiểm tra an ninh nhà máy" },
        { time: "05:30 AM", desc: "Lấy mẫu test nhanh kháng sinh Betalactam" },
        { time: "06:10 AM", desc: "Bơm chuyển vào Silo đệm vô trùng" }
      ],
      bannerType: "milk"
    },
    {
      id: "RAW-LOT-513",
      category: "Bao bì vô trùng",
      title: "Vỏ hộp tiệt trùng Tetra Brik Aseptic 250ml",
      statValue: "450,000",
      statSub: "Vỏ cuộn màng",
      progress: 100,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Nhà cung ứng", value: "Tetra Pak Thụy Điển" },
        { label: "Số lớp màng bảo vệ", value: "6 lớp tiêu chuẩn nhôm" },
        { label: "Chứng nhận FSC", value: "Gỗ tái sinh bền vững" },
        { label: "Tình trạng bao bì", value: "Niêm phong kín 100%" }
      ],
      avatars: [
        { initial: "LH", bg: "#2563EB", name: "Lê Hải Đăng" }
      ],
      status: "inspected",
      statusLabel: "Sẵn sàng cấp cho máy",
      statusPill: "green",
      dropdown1: "inspected",
      dropdown2: "Kho khô nguyên liệu C2",
      dropdown3: "Lê Hải Đăng",
      dropdown4: "Cargill Agriculture",
      readOnlySpecs: [
        { label: "Số cuộn màng", value: "90 cuộn x 5,000 hộp", icon: "database" },
        { label: "Độ dính lớp PE", value: "≥ 3.2 N/15mm", icon: "activity" },
        { label: "Kiểm tra độ ẩm kho", value: "Độ ẩm 52% (Đạt)", icon: "check-circle" },
        { label: "Mã lô nhà máy vỏ", value: "TP-SWED-884-26", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "03/09/2026", desc: "Cập cảng Hải Phòng" },
        { time: "06/09/2026", desc: "Vận chuyển về kho nguyên liệu số 2" },
        { time: "Hôm nay", desc: "Kiểm tra ngoại quan và chuyển lệnh cấp" }
      ],
      bannerType: "packages"
    }
  ],

  inventory: [
    {
      id: "INV-SKU-102",
      category: "Kho lạnh thành phẩm",
      title: "Sữa tươi tiệt trùng Nguyên Chất 1L (Thùng 12 hộp)",
      statValue: "1,850",
      statSub: "Thùng có sẵn",
      progress: 85,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Vị trí Pallet", value: "Kệ lạnh A3 - Tầng 2" },
        { label: "Nhiệt độ phòng", value: "4°C - 6°C" },
        { label: "Mức tồn an toàn", value: "Min 500 / Max 2,500" },
        { label: "Ngày sản xuất", value: "02/09/2026" }
      ],
      avatars: [
        { initial: "HT", bg: "#0284C7", name: "Hoàng Đình Tuấn" },
        { initial: "NT", bg: "#059669", name: "Nguyễn Thu Hà" }
      ],
      status: "in_stock",
      statusLabel: "Tồn kho dồi dào",
      statusPill: "green",
      dropdown1: "in_stock",
      dropdown2: "Dãy A - Kệ 04 (Tầng 3)",
      dropdown3: "Hoàng Đình Tuấn",
      dropdown4: "FEFO (Hạn dùng trước xuất trước)",
      readOnlySpecs: [
        { label: "Mã vạch EAN-13", value: "8935012345678", icon: "qr-code", mono: true },
        { label: "Trọng lượng Pallet", value: "780 kg / Pallet", icon: "database" },
        { label: "Hạn sử dụng còn lại", value: "174 ngày (FEFO Rank A)", icon: "activity" },
        { label: "Quy cách đóng thùng", value: "12 hộp x 1000ml", icon: "check-circle" }
      ],
      timeline: [
        { time: "02/09/2026", desc: "Nhập 2,000 thùng từ xưởng chế biến" },
        { time: "05/09/2026", desc: "Xuất 150 thùng cho hệ thống VinMart" }
      ],
      bannerType: "milk"
    },
    {
      id: "INV-SKU-108",
      category: "Nước uống giải khát",
      title: "Trà Xanh Mật Ong Đóng Chai 450ml (Thùng 24 chai)",
      statValue: "210 / 1,000",
      statSub: "Cần sản xuất bổ sung",
      progress: 21,
      progressColor: "fill-amber",
      miniGrid: [
        { label: "Vị trí Pallet", value: "Kệ khô D1 - Ô 09" },
        { label: "Mức tối thiểu", value: "300 Thùng" },
        { label: "Tình trạng", value: "Dưới ngưỡng an toàn" },
        { label: "Dự báo cạn", value: "Còn 2 ngày bán lẻ" }
      ],
      avatars: [
        { initial: "HT", bg: "#0284C7", name: "Hoàng Đình Tuấn" }
      ],
      status: "low_stock",
      statusLabel: "Sắp hết hàng (Low Stock)",
      statusPill: "amber",
      dropdown1: "low_stock",
      dropdown2: "Dãy C - Kệ trượt FIFO",
      dropdown3: "Hoàng Đình Tuấn",
      dropdown4: "FIFO (Nhập trước xuất trước)",
      readOnlySpecs: [
        { label: "Mã vạch EAN-13", value: "8935098765432", icon: "qr-code", mono: true },
        { label: "Số Pallet hiện tại", value: "3.5 Pallet", icon: "database" },
        { label: "Đơn đặt hàng chờ", value: "500 thùng (Mega Market)", icon: "activity" },
        { label: "Đề xuất phòng kế hoạch", value: "Đẩy lịch Line A2 ngày mai", icon: "shield" }
      ],
      timeline: [
        { time: "07/09/2026", desc: "Xuất 600 thùng cho chuỗi Circle K" },
        { time: "Hôm nay 08:30", desc: "Cảnh báo tự động gửi Quản đốc ca" }
      ],
      bannerType: "juice"
    }
  ],

  dispatch: [
    {
      id: "DISP-2026-192",
      category: "Đơn vận chuyển lạnh",
      title: "Phân phối 800 thùng sữa tiệt trùng tới Mega Market",
      statValue: "800 / 800",
      statSub: "Thùng đã bốc xe",
      progress: 100,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Xe lạnh vận tải", value: "Xe Inox 29C-8819" },
        { label: "Nhiệt độ thùng", value: "3.8°C (Đo trực tiếp GPS)" },
        { label: "Thời gian rời kho", value: "10:30 AM (Hôm nay)" },
        { label: "Dự kiến giao", value: "12:00 PM (Trưa nay)" }
      ],
      avatars: [
        { initial: "BH", bg: "#475569", name: "Bác tài Bùi Văn Hùng" },
        { initial: "LH", bg: "#2563EB", name: "Lê Hải Đăng" }
      ],
      status: "dispatched",
      statusLabel: "Đang lăn bánh trên đường",
      statusPill: "green",
      dropdown1: "dispatched",
      dropdown2: "Đội xe container lạnh Nam Hà",
      dropdown3: "Bác tài Bùi Văn Hùng",
      dropdown4: "Tổng kho Mega Market Bình Phú",
      readOnlySpecs: [
        { label: "Biển số phương tiện", value: "29C-881.99 (ThermoKing)", icon: "truck" },
        { label: "Cảm biến nhiệt IoT", value: "Online 4G - 3.8°C chuẩn", icon: "activity" },
        { label: "Số vận đơn Logistics", value: "LOG-MM-2026-992", icon: "qr-code", mono: true },
        { label: "Biên bản bàn giao", value: "Đầy đủ phiếu kiểm dịch BYT", icon: "check-circle" }
      ],
      timeline: [
        { time: "09:30 AM", desc: "Bốc hàng từ kệ lạnh A3 lên xe" },
        { time: "10:15 AM", desc: "Kẹp chì niêm phong seal an toàn #9942" },
        { time: "10:30 AM", desc: "Xe lăn bánh rời cổng số 1" }
      ],
      bannerType: "truck"
    },
    {
      id: "DISP-2026-193",
      category: "Điều phối nội bộ",
      title: "Điều chuyển 350 thùng nước cam sang Kho trung chuyển",
      statValue: "120 / 350",
      statSub: "Đang xếp Pallet",
      progress: 34,
      progressColor: "fill-amber",
      miniGrid: [
        { label: "Xe tiếp nhận", value: "Xe tải 5 tấn (Nhà xe 04)" },
        { label: "Cửa xuất kho", value: "Dock số 3 (Kho B)" },
        { label: "Độ ưu tiên", value: "Gấp - Khách cần lúc 14:00" },
        { label: "Người kiểm đếm", value: "Nguyễn Văn Thiện" }
      ],
      avatars: [
        { initial: "NT", bg: "#059669", name: "Nguyễn Văn Thiện" }
      ],
      status: "loading",
      statusLabel: "Đang bốc dỡ tại Dock",
      statusPill: "amber",
      dropdown1: "loading",
      dropdown2: "Đội xe tải lạnh Nhà Máy (Xe 04)",
      dropdown3: "Nguyễn Văn Thiện (Xe 29C-8819)",
      dropdown4: "Kho trung chuyển VinMart Hà Nội",
      readOnlySpecs: [
        { label: "Dock xuất hàng", value: "Dock Gate #03", icon: "database" },
        { label: "Kiểm tra ngoại quan", value: "Thùng nguyên seal không móp", icon: "shield" },
        { label: "Vận tốc xe quy định", value: "Tối đa 60 km/h (Hàng chất lỏng)", icon: "activity" },
        { label: "Mã chuyến xe", value: "TRUCK-4T-0809", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "10:30 AM", desc: "Xe cập dock chuẩn bị mở cửa sau" },
        { time: "10:45 AM", desc: "Xe nâng bắt đầu đưa 4 pallet đầu tiên lên sàn" }
      ],
      bannerType: "juice"
    }
  ]
};

// Application Database
let appData = JSON.parse(JSON.stringify(initialData));

// SVG Vector Banners for Detail Panel
function getBannerSvg(type, title, stat) {
  const backgrounds = {
    milk: 'linear-gradient(135deg, #1E293B 0%, #0F172A 50%, #1E3A8A 100%)',
    juice: 'linear-gradient(135deg, #78350F 0%, #451A03 50%, #B45309 100%)',
    yogurt: 'linear-gradient(135deg, #064E3B 0%, #022C22 50%, #047857 100%)',
    nuts: 'linear-gradient(135deg, #312E81 0%, #1E1B4B 50%, #4338CA 100%)',
    qc: 'linear-gradient(135deg, #134E4A 0%, #042F2E 50%, #0F766E 100%)',
    truck: 'linear-gradient(135deg, #18181B 0%, #09090B 50%, #27272A 100%)',
    packages: 'linear-gradient(135deg, #1E1B4B 0%, #0F172A 50%, #3730A3 100%)'
  };

  const bg = backgrounds[type] || backgrounds.milk;

  return `
    <div style="width:100%;height:100%;background:${bg};position:relative;display:flex;align-items:center;padding:0 24px;overflow:hidden;">
      <svg style="position:absolute;right:-20px;bottom:-20px;opacity:0.12;width:180px;height:180px;" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.5">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <div style="position:relative;z-index:2;">
        <div style="display:inline-block;padding:3px 8px;background:rgba(255,255,255,0.15);backdrop-filter:blur(4px);border-radius:4px;font-size:11px;font-weight:700;color:#FFFFFF;margin-bottom:6px;letter-spacing:0.5px;text-transform:uppercase;">
          FOOD MAN • HACCP APPROVED
        </div>
        <div style="color:#FFFFFF;font-size:18px;font-weight:800;letter-spacing:-0.3px;max-width:340px;line-height:1.3;">${title}</div>
        <div style="color:#93C5FD;font-size:12px;font-weight:600;margin-top:4px;font-family:'JetBrains Mono',monospace;">${stat}</div>
      </div>
    </div>
  `;
}

// Icon Helper for Technical Specs
function getIconSvg(name) {
  switch (name) {
    case 'flask':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 2v7.31L4.65 19.4c-.65.98.05 2.6 1.35 2.6h12c1.3 0 2-1.62 1.35-2.6L14 9.31V2m-4 0h4" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    case 'activity':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    case 'check-circle':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" stroke-linecap="round" stroke-linejoin="round"/><polyline points="22 4 12 14.01 9 11.01" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    case 'qr-code':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>`;
    case 'database':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>`;
    case 'shield':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>`;
    case 'truck':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>`;
    default:
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
  }
}

// Render Master Card List (2-Column Grid)
function renderCardList() {
  const cardContainer = document.getElementById('cardGridContainer');
  const items = appData[appState.currentDomain] || [];

  // Filter items
  const filteredItems = items.filter(item => {
    const matchesFilter = 
      appState.currentFilter === 'all' ||
      (appState.currentFilter === 'attention' && item.statusPill === 'amber') ||
      (appState.currentFilter === 'ready' && item.statusPill === 'green');

    const q = appState.searchQuery.toLowerCase().trim();
    const matchesSearch = !q || 
      item.id.toLowerCase().includes(q) ||
      item.title.toLowerCase().includes(q) ||
      item.category.toLowerCase().includes(q);

    return matchesFilter && matchesSearch;
  });

  // Update page counts
  const totalCountEl = document.getElementById('pageTotalCount');
  if (totalCountEl) {
    const config = domainConfigs[appState.currentDomain];
    totalCountEl.textContent = `${items.length} ${config.counterLabel}`;
  }

  // Update Filter Pill Counts
  const countAll = items.length;
  const countAttention = items.filter(i => i.statusPill === 'amber').length;
  const countReady = items.filter(i => i.statusPill === 'green').length;

  document.getElementById('filterCountAll').textContent = countAll;
  document.getElementById('filterCountAttention').textContent = countAttention;
  document.getElementById('filterCountReady').textContent = countReady;

  if (filteredItems.length === 0) {
    cardContainer.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 60px 20px; text-align: center; background: #FFFFFF; border-radius: 12px; border: 1px dashed var(--border-subtle);">
        <div style="width: 48px; height: 48px; margin: 0 auto 12px; border-radius: 50%; background: var(--accent-navy-light); display: flex; align-items: center; justify-content: center; color: var(--accent-navy);">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        </div>
        <h3 style="font-size: 16px; font-weight: 700; color: var(--text-main); margin-bottom: 4px;">Không tìm thấy bản ghi nào</h3>
        <p style="font-size: 13px; color: var(--text-muted);">Vui lòng thử tìm kiếm với từ khóa khác hoặc xóa bộ lọc.</p>
      </div>
    `;
    return;
  }

  // Generate 2-Column Cards
  cardContainer.innerHTML = filteredItems.map(item => {
    const isSelected = item.id === appState.selectedCardId;

    // Build 2x2 mini-grid cells
    const miniGridHtml = item.miniGrid.map(cell => `
      <div class="mini-grid-cell">
        <span class="mini-grid-label">${cell.label}</span>
        <span class="mini-grid-value" title="${cell.value}">${cell.value}</span>
      </div>
    `).join('');

    // Build avatar stack
    const avatarsHtml = item.avatars.map(av => `
      <div class="avatar-stack-item" style="background-color: ${av.bg};" title="${av.name}">
        ${av.initial}
      </div>
    `).join('');

    // Build progress bar if available
    const progressHtml = item.progress !== undefined ? `
      <div class="card-progress-wrapper">
        <div class="card-progress-header">
          <span>Tiến độ hoàn thành</span>
          <span style="font-family:'JetBrains Mono',monospace;">${item.progress}%</span>
        </div>
        <div class="progress-track">
          <div class="progress-bar-fill ${item.progressColor || ''}" style="width: ${item.progress}%;"></div>
        </div>
      </div>
    ` : '';

    return `
      <div class="master-card ${isSelected ? 'active-selected' : ''}" data-id="${item.id}" onclick="handleCardSelect('${item.id}')">
        <!-- Header Row: ID/Title + secondary stat top-right -->
        <div class="card-header-row">
          <div class="card-title-group">
            <div class="card-id-tag">
              <span class="card-code">${item.id}</span>
              <span class="card-category-label">${item.category}</span>
            </div>
            <h3 class="card-item-title">${item.title}</h3>
          </div>
          <div class="card-stat-box">
            <span class="card-stat-value">${item.statValue}</span>
            <span class="card-stat-sub">${item.statSub}</span>
          </div>
        </div>

        <!-- 2x2 label/value mini-grid -->
        <div class="card-mini-grid">
          ${miniGridHtml}
        </div>

        <!-- Progress bar where relevant -->
        ${progressHtml}

        <!-- Card Footer: Avatar stack + Status pill bottom-right -->
        <div class="card-footer-row">
          <div class="avatar-stack">
            ${avatarsHtml}
          </div>
          <div class="status-pill pill-${item.statusPill}">
            <span class="status-dot"></span>
            <span>${item.statusLabel}</span>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// Master-Detail Selection Handler
function handleCardSelect(cardId) {
  appState.selectedCardId = cardId;
  const items = appData[appState.currentDomain] || [];
  const item = items.find(i => i.id === cardId);

  if (!item) return;

  appState.activeItem = JSON.parse(JSON.stringify(item)); // Clone for editing

  // Re-render card grid to reflect active navy border
  renderCardList();

  // Populate and open slide-in panel
  populateDetailPanel(appState.activeItem);
  openDetailPanel();
}

// Open / Close Slide-in Panel
function openDetailPanel() {
  const panel = document.getElementById('detailSlidePanel');
  const backdrop = document.getElementById('slidePanelBackdrop');
  panel.classList.add('open');
  backdrop.classList.add('active');
}

function closeDetailPanel() {
  const panel = document.getElementById('detailSlidePanel');
  const backdrop = document.getElementById('slidePanelBackdrop');
  panel.classList.remove('open');
  backdrop.classList.remove('active');
  appState.selectedCardId = null;
  renderCardList();
}

// Populate Right-hand Slide-in Panel with Selected Card Data
function populateDetailPanel(item) {
  const config = domainConfigs[appState.currentDomain];

  // Set ID
  document.getElementById('panelRecordId').textContent = item.id;

  // Visual Banner at top
  const bannerContainer = document.getElementById('panelVisualBanner');
  bannerContainer.innerHTML = getBannerSvg(item.bannerType, item.title, `${item.statValue} ${item.statSub}`);

  // Editable Dropdown 1 (Trạng thái)
  const lbl1 = document.getElementById('labelDropdown1');
  lbl1.textContent = config.dropdown1Label;
  const sel1 = document.getElementById('selectDropdown1');
  sel1.innerHTML = config.dropdown1Options.map(opt => `
    <option value="${opt.value}" ${item.dropdown1 === opt.value ? 'selected' : ''}>${opt.label}</option>
  `).join('');

  // Editable Dropdown 2 (Dây chuyền / Kho / Lab)
  const lbl2 = document.getElementById('labelDropdown2');
  lbl2.textContent = config.dropdown2Label;
  const sel2 = document.getElementById('selectDropdown2');
  sel2.innerHTML = config.dropdown2Options.map(opt => `
    <option value="${opt}" ${item.dropdown2 === opt ? 'selected' : ''}>${opt}</option>
  `).join('');

  // Editable Dropdown 3 (Phụ trách / Người kiểm)
  const lbl3 = document.getElementById('labelDropdown3');
  lbl3.textContent = config.dropdown3Label;
  const sel3 = document.getElementById('selectDropdown3');
  sel3.innerHTML = config.dropdown3Options.map(opt => `
    <option value="${opt}" ${item.dropdown3 === opt ? 'selected' : ''}>${opt}</option>
  `).join('');

  // Editable Dropdown 4 (Vị trí lưu / Tiêu chuẩn)
  const lbl4 = document.getElementById('labelDropdown4');
  lbl4.textContent = config.dropdown4Label;
  const sel4 = document.getElementById('selectDropdown4');
  sel4.innerHTML = config.dropdown4Options.map(opt => `
    <option value="${opt}" ${item.dropdown4 === opt ? 'selected' : ''}>${opt}</option>
  `).join('');

  // Read-only technical info list below
  const specsContainer = document.getElementById('panelReadonlySpecs');
  if (item.readOnlySpecs && item.readOnlySpecs.length > 0) {
    specsContainer.innerHTML = item.readOnlySpecs.map(spec => `
      <div class="readonly-info-row">
        <span class="readonly-label">
          ${getIconSvg(spec.icon)}
          ${spec.label}
        </span>
        <span class="readonly-value ${spec.mono ? 'mono' : ''}">${spec.value}</span>
      </div>
    `).join('');
  } else {
    specsContainer.innerHTML = `<div style="padding: 12px 14px; font-size: 12px; color: var(--text-muted);">Không có thông số đặc thù.</div>`;
  }

  // Timeline / Nhật ký
  const timelineContainer = document.getElementById('panelTimelineList');
  if (item.timeline && item.timeline.length > 0) {
    timelineContainer.innerHTML = item.timeline.map(tl => `
      <div class="timeline-entry">
        <span class="timeline-time">${tl.time}</span>
        <span class="timeline-desc">${tl.desc}</span>
      </div>
    `).join('');
  } else {
    timelineContainer.innerHTML = `<div style="font-size: 12px; color: var(--text-muted);">Chưa có nhật ký ghi nhận.</div>`;
  }
}

// Save Changes from Slide-in Panel
function saveDetailPanelChanges() {
  if (!appState.activeItem) return;

  const config = domainConfigs[appState.currentDomain];
  const cardId = appState.activeItem.id;
  const items = appData[appState.currentDomain];
  const index = items.findIndex(i => i.id === cardId);

  if (index === -1) return;

  // Read updated dropdowns
  const val1 = document.getElementById('selectDropdown1').value;
  const val2 = document.getElementById('selectDropdown2').value;
  const val3 = document.getElementById('selectDropdown3').value;
  const val4 = document.getElementById('selectDropdown4').value;

  const opt1 = config.dropdown1Options.find(o => o.value === val1);
  if (opt1) {
    items[index].status = val1;
    items[index].statusLabel = opt1.label;
    items[index].statusPill = opt1.pill;
  }

  items[index].dropdown1 = val1;
  items[index].dropdown2 = val2;
  items[index].dropdown3 = val3;
  items[index].dropdown4 = val4;

  // Update relevant mini-grid value if matches
  if (items[index].miniGrid[1]) {
    items[index].miniGrid[1].value = val2;
  }

  // Add an entry to timeline
  const now = new Date();
  const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  items[index].timeline.unshift({
    time: `Hôm nay ${timeStr}`,
    desc: `Cập nhật trạng thái: "${opt1 ? opt1.label : val1}" bởi Trần Minh Quân`
  });

  // Re-render
  renderCardList();
  populateDetailPanel(items[index]);
  showToast("Thành công!", `Đã lưu cập nhật cho bản ghi ${cardId}`, "success");
}

// Delete Record Action
function deleteCurrentRecord() {
  if (!appState.selectedCardId) return;
  const cardId = appState.selectedCardId;

  if (confirm(`Bạn có chắc chắn muốn xóa bản ghi ${cardId} khỏi hệ thống?`)) {
    appData[appState.currentDomain] = appData[appState.currentDomain].filter(i => i.id !== cardId);
    closeDetailPanel();
    renderCardList();
    showToast("Đã xóa bản ghi", `Bản ghi ${cardId} đã được xóa thành công.`, "danger");
  }
}

// Switch Active Navigation Domain
function switchDomain(domainKey) {
  if (!domainConfigs[domainKey]) return;

  appState.currentDomain = domainKey;
  appState.selectedCardId = null;
  appState.searchQuery = '';
  appState.currentFilter = 'all';

  // Update Sidebar active classes
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.domain === domainKey);
  });

  // Update Filter buttons
  document.querySelectorAll('.filter-tab').forEach(el => {
    el.classList.toggle('active', el.dataset.filter === 'all');
  });

  // Update Breadcrumb & Header Title
  const config = domainConfigs[domainKey];
  const breadcrumbEl = document.getElementById('pageBreadcrumb');
  breadcrumbEl.innerHTML = config.breadcrumb.map((crumb, idx) => {
    if (idx === config.breadcrumb.length - 1) {
      return `<span class="breadcrumb-active">${crumb}</span>`;
    }
    return `<a href="javascript:void(0)">${crumb}</a><span class="breadcrumb-separator">/</span>`;
  }).join('');

  document.getElementById('pageMainTitle').textContent = config.title;
  document.getElementById('btnPrimaryActionText').textContent = config.createBtnText;

  // Clear search input
  const searchInput = document.getElementById('globalSearchInput');
  if (searchInput) searchInput.value = '';

  // Close detail panel if open
  closeDetailPanel();

  // Render cards for domain
  renderCardList();
}

// Open Quick Create Modal
function openQuickCreateModal(domainKey) {
  const targetDomain = domainKey || appState.currentDomain;
  const config = domainConfigs[targetDomain];

  document.getElementById('modalTargetDomain').value = targetDomain;
  document.getElementById('modalTitleText').textContent = `Tạo mới: ${config.title}`;
  document.getElementById('newRecordCategory').value = config.dropdown2Options[0] || 'Chung';
  document.getElementById('newRecordTitle').value = '';
  document.getElementById('newRecordStat').value = `1,000 ${config.unit}`;

  const modal = document.getElementById('quickCreateModal');
  modal.classList.add('active');
}

function closeQuickCreateModal() {
  const modal = document.getElementById('quickCreateModal');
  modal.classList.remove('active');
}

function submitQuickCreate() {
  const targetDomain = document.getElementById('modalTargetDomain').value;
  const title = document.getElementById('newRecordTitle').value.trim();
  const category = document.getElementById('newRecordCategory').value.trim();
  const stat = document.getElementById('newRecordStat').value.trim();

  if (!title) {
    alert("Vui lòng nhập tên / tiêu đề bản ghi!");
    return;
  }

  const config = domainConfigs[targetDomain];
  const prefix = targetDomain === 'production' ? 'LOT' :
                 targetDomain === 'qc' ? 'QC' :
                 targetDomain === 'raw-materials' ? 'RAW' :
                 targetDomain === 'inventory' ? 'INV' : 'DISP';

  const randomNum = Math.floor(100 + Math.random() * 900);
  const newId = `${prefix}-2026-${randomNum}`;

  const newItem = {
    id: newId,
    category: category || "Sản xuất chung",
    title: title,
    statValue: stat || `500 ${config.unit}`,
    statSub: "Mới tạo",
    progress: 10,
    progressColor: "fill-amber",
    miniGrid: [
      { label: "Ngày tạo", value: "Hôm nay 11:00" },
      { label: "Đơn vị phụ trách", value: config.dropdown2Options[0] },
      { label: "Người duyệt", value: "Trần Minh Quân" },
      { label: "Trạng thái", value: "Đang khởi tạo" }
    ],
    avatars: [
      { initial: "TM", bg: "#162B4E", name: "Trần Minh Quân" }
    ],
    status: config.dropdown1Options[0].value,
    statusLabel: config.dropdown1Options[0].label,
    statusPill: config.dropdown1Options[0].pill,
    dropdown1: config.dropdown1Options[0].value,
    dropdown2: config.dropdown2Options[0],
    dropdown3: "Trần Minh Quân",
    dropdown4: config.dropdown4Options[0],
    readOnlySpecs: [
      { label: "Mã khởi tạo hệ thống", value: newId, icon: "qr-code", mono: true },
      { label: "Tiêu chuẩn ban hành", value: "QCVN 5-1:2010/BYT", icon: "shield" }
    ],
    timeline: [
      { time: "Vừa xong", desc: "Khởi tạo bản ghi mới trên hệ thống Food Man" }
    ],
    bannerType: targetDomain === 'qc' ? 'qc' : targetDomain === 'dispatch' ? 'truck' : 'milk'
  };

  appData[targetDomain].unshift(newItem);
  closeQuickCreateModal();

  if (appState.currentDomain === targetDomain) {
    renderCardList();
    handleCardSelect(newId);
  } else {
    switchDomain(targetDomain);
    handleCardSelect(newId);
  }

  showToast("Tạo mới thành công!", `Đã thêm ${newId} vào danh mục ${config.title}`, "success");
}

// Toast System
function showToast(title, msg, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast-item toast-${type}`;

  const iconSvg = type === 'success' ? 
    `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>` :
    type === 'danger' ?
    `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>` :
    `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;

  toast.innerHTML = `
    ${iconSvg}
    <div class="toast-content">
      <div class="toast-title">${title}</div>
      <div class="toast-msg">${msg}</div>
    </div>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.25s ease';
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

// Live Topbar Clock (Date & Time chips)
function startLiveClock() {
  function updateTime() {
    const now = new Date();
    
    // Days in Vietnamese
    const days = ["Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];
    const dayName = days[now.getDay()];
    const dateFormatted = `${String(now.getDate()).padStart(2, '0')}/${String(now.getMonth() + 1).padStart(2, '0')}/${now.getFullYear()}`;
    const timeFormatted = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

    const dateChip = document.getElementById('liveDateChip');
    const timeChip = document.getElementById('liveTimeChip');

    if (dateChip) dateChip.textContent = `${dayName}, ${dateFormatted}`;
    if (timeChip) timeChip.textContent = timeFormatted;
  }

  updateTime();
  setInterval(updateTime, 1000);
}

// Attach Event Listeners on Page Load
document.addEventListener('DOMContentLoaded', () => {
  // Start live date/time chips
  startLiveClock();

  // Initial render
  switchDomain('production');

  // Search input listener
  const searchInput = document.getElementById('globalSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      appState.searchQuery = e.target.value;
      renderCardList();
    });
  }

  // Filter Tabs
  document.querySelectorAll('.filter-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      appState.currentFilter = tab.dataset.filter;
      renderCardList();
    });
  });

  // Global Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Esc closes panels
    if (e.key === 'Escape') {
      closeDetailPanel();
      closeQuickCreateModal();
    }
    // Ctrl+K / Cmd+K focuses search
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      searchInput.focus();
    }
  });
});
