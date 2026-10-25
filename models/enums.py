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
    FOOD_TECHNOLOGIST = "Food Technologist"


# Visual styling metadata mapped strictly to the Design System
STATUS_METADATA = {
    StatusEnum.PENDING: {
        "label": "Pending Review",
        "pill_class": "pill-pending",
        "color": "#92400E",
        "bg": "#FEF3C7",
        "dot": "#F59E0B",
        "description": "New record or awaiting management review."
    },
    StatusEnum.APPROVED: {
        "label": "Approved / Compliant",
        "pill_class": "pill-approved",
        "color": "#065F46",
        "bg": "#D1FAE5",
        "dot": "#10B981",
        "description": "Passed food safety standards, ready for next stage."
    },
    StatusEnum.HOLD: {
        "label": "On Hold / Quarantine",
        "pill_class": "pill-hold",
        "color": "#9A3412",
        "bg": "#FED7AA",
        "dot": "#F97316",
        "description": "Quarantined for microbial testing or pending additional inspection."
    },
    StatusEnum.REJECTED: {
        "label": "Rejected",
        "pill_class": "pill-rejected",
        "color": "#991B1B",
        "bg": "#FEE2E2",
        "dot": "#EF4444",
        "description": "Does not meet quality standards; return order issued or batch destroyed."
    }
}

# Role module access matrix defining persistent sidebar visibility
ROLE_MODULE_PERMISSIONS = {
    RoleEnum.ADMIN: ["procurement", "qc", "production", "warehouse", "traceability", "reports", "dashboard", "alerts", "admin"],
    RoleEnum.PROCUREMENT: ["procurement", "alerts"],
    RoleEnum.QC: ["qc", "alerts"],
    RoleEnum.PRODUCTION: ["production", "alerts"],
    RoleEnum.WAREHOUSE: ["warehouse", "traceability", "alerts"],
    RoleEnum.FOOD_TECHNOLOGIST: ["food_technologist", "traceability", "reports", "alerts", "dashboard"]
}

