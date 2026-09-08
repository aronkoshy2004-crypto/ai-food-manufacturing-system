"""
Shared Status Vocabulary and Role Definitions for Food Man
PRD Phase 0 Foundation
"""
from enum import Enum

class StatusEnum(str, Enum):
    """
    Shared status vocabulary frozen across the system:
    - PENDING: Initial state, awaiting review or processing
    - APPROVED: Passed QC, cleared for production/shipping, verified
    - HOLD: Quarantined, paused, awaiting bacterial reading or supervisor check
    - REJECTED: Failed quality control, out-of-spec, returned to supplier
    """
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    HOLD = "HOLD"
    REJECTED = "REJECTED"


class RoleEnum(str, Enum):
    """
    Role-based access control roles:
    - Procurement: Raw material intake, supplier tracking, purchase orders
    - QC: Quality inspection, lab test logs, microbiological checks, release approval
    - Production: Batch execution, packaging lines, shift planning
    - Warehouse: Finished goods inventory, bin/pallet tracking, dispatch orders
    - Admin: Full system access across all departments and user management
    """
    ADMIN = "Admin"
    PROCUREMENT = "Procurement"
    QC = "QC"
    PRODUCTION = "Production"
    WAREHOUSE = "Warehouse"


# Visual styling metadata mapped strictly to the Design System
STATUS_METADATA = {
    StatusEnum.PENDING: {
        "label": "Đang chờ duyệt",
        "pill_class": "pill-pending",
        "color": "#92400E",
        "bg": "#FEF3C7",
        "dot": "#F59E0B",
        "description": "Bản ghi mới hoặc đang chờ xác nhận từ cấp quản lý."
    },
    StatusEnum.APPROVED: {
        "label": "Đạt chuẩn / Đã duyệt",
        "pill_class": "pill-approved",
        "color": "#065F46",
        "bg": "#D1FAE5",
        "dot": "#10B981",
        "description": "Đạt chuẩn an toàn vệ sinh thực phẩm, sẵn sàng chuyển bước tiếp theo."
    },
    StatusEnum.HOLD: {
        "label": "Tạm dừng / Cách ly",
        "pill_class": "pill-hold",
        "color": "#9A3412",
        "bg": "#FED7AA",
        "dot": "#F97316",
        "description": "Đang cách ly kiểm định vi sinh hoặc cần kiểm tra bổ sung."
    },
    StatusEnum.REJECTED: {
        "label": "Không đạt / Từ chối",
        "pill_class": "pill-rejected",
        "color": "#991B1B",
        "bg": "#FEE2E2",
        "dot": "#EF4444",
        "description": "Không đáp ứng tiêu chuẩn chất lượng, đã xuất lệnh trả hàng hoặc hủy lô."
    }
}

# Role module access matrix defining persistent sidebar visibility
ROLE_MODULE_PERMISSIONS = {
    RoleEnum.ADMIN: ["procurement", "qc", "production", "warehouse", "reports"],
    RoleEnum.PROCUREMENT: ["procurement", "reports"],
    RoleEnum.QC: ["qc", "reports"],
    RoleEnum.PRODUCTION: ["production", "reports"],
    RoleEnum.WAREHOUSE: ["warehouse", "reports"]
}
