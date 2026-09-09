# -*- coding: utf-8 -*-
with open('app.js', 'r', encoding='utf-8') as f:
    code = f.read()

cleanup = [
    ('"Le Van Hùng"', '"Le Van Hung"'),
    ('{ label: "Dây chuyền",', '{ label: "Line",'),
    ('name: "Phạm Thu Trang"', 'name: "Pham Thu Trang"'),
    ('{ initial: "ĐM",', '{ initial: "DM",'),
    ('{ label: "Incubation Time nhiệt",', '{ label: "Incubation Period",'),
    ('time: "Sáng nay 08:30",', 'time: "This morning 08:30",'),
    ('Không tìm thấy bản ghi nào', 'No records found'),
    ('// Editable Dropdown 2 (Dây chuyền / Kho / Lab)', '// Editable Dropdown 2 (Line / Warehouse / Lab)'),
    ('// Editable Dropdown 3 (Phụ trách / Người kiểm)', '// Editable Dropdown 3 (Lead / Inspector)'),
    ('// Editable Dropdown 4 (Vị trí lưu / Tiêu chuẩn)', '// Editable Dropdown 4 (Storage / Standard)'),
    ('Không có thông số đặc thù.', 'No technical specifications registered.'),
    ('// Timeline / Nhật ký', '// Timeline / Audit Log'),
    ('Chưa có nhật ký ghi nhận.', 'No activity log recorded.'),
    ('Cập nhật trạng thái: "${opt1 ? opt1.label : val1}" bởi Tran Minh Quan', 'Status updated: "${opt1 ? opt1.label : val1}" by Tran Minh Quan')
]

for src, dst in cleanup:
    code = code.replace(src, dst)

with open('app.js', 'w', encoding='utf-8') as f:
    f.write(code)

print("Second pass cleanup completed!")
