"""
QC Domain Models: Samples, Tests, COA Documents, Inspection Images, AI YOLO Detections, and QC Decisions
Phase 2 — PRD Implementation
"""
import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from models import Base
from models.enums import StatusEnum

class QCSample(Base):
    """
    Samples drawn from raw material lots for laboratory testing
    """
    __tablename__ = 'qc_samples'

    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_code = Column(String(50), unique=True, nullable=False, index=True)
    
    raw_material_lot_id = Column(Integer, ForeignKey('raw_material_lots.id'), nullable=False)
    raw_material_lot = relationship("RawMaterialLot")

    sampler_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    sampler = relationship("User", foreign_keys=[sampler_user_id])

    sample_date = Column(DateTime, default=datetime.datetime.utcnow)
    storage_temp = Column(String(50), default="4°C")
    sample_size = Column(String(50), default="500ml / 5 mẫu ngẫu nhiên")
    notes = Column(Text, nullable=True)

    # Relationships
    tests = relationship("QCTest", back_populates="qc_sample", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "sample_code": self.sample_code,
            "raw_material_lot_id": self.raw_material_lot_id,
            "lot_number": self.raw_material_lot.lot_number if self.raw_material_lot else "N/A",
            "sampler_name": self.sampler.full_name if self.sampler else "Chuyên viên QC",
            "sample_date": self.sample_date.strftime("%d/%m/%Y %H:%M") if self.sample_date else "",
            "storage_temp": self.storage_temp,
            "sample_size": self.sample_size,
            "tests_count": len(self.tests),
            "all_passed": all(t.is_pass for t in self.tests) if self.tests else False
        }


class QCTest(Base):
    """
    Specific laboratory parameter testing results (range, result, pass/fail)
    """
    __tablename__ = 'qc_tests'

    id = Column(Integer, primary_key=True, autoincrement=True)
    qc_sample_id = Column(Integer, ForeignKey('qc_samples.id'), nullable=False)
    qc_sample = relationship("QCSample", back_populates="tests")

    parameter_name = Column(String(100), nullable=False) # e.g. Độ Brix, Chỉ số pH, Hàm lượng béo, Coliform, Cảm quan
    standard_spec = Column(String(100), nullable=False)  # e.g. "≥ 3.2%", "6.5 - 6.8 pH", "< 10 CFU/ml"
    measured_value = Column(String(100), nullable=False) # e.g. "3.45%", "6.65 pH", "Âm tính (0 CFU)"
    unit = Column(String(30), default="")
    is_pass = Column(Boolean, nullable=False, default=True)
    tested_at = Column(DateTime, default=datetime.datetime.utcnow)
    notes = Column(String(255), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "parameter_name": self.parameter_name,
            "standard_spec": self.standard_spec,
            "measured_value": self.measured_value,
            "unit": self.unit,
            "is_pass": self.is_pass,
            "tested_at": self.tested_at.strftime("%d/%m/%Y %H:%M") if self.tested_at else ""
        }


class COADocument(Base):
    """
    Certificate of Analysis (COA) documents provided by suppliers or independent labs
    """
    __tablename__ = 'coa_documents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_material_lot_id = Column(Integer, ForeignKey('raw_material_lots.id'), nullable=False)
    raw_material_lot = relationship("RawMaterialLot")

    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=True)
    supplier = relationship("Supplier")

    doc_number = Column(String(100), unique=True, nullable=False, index=True) # e.g. COA-VNM-2026-881
    filename = Column(String(255), nullable=False)
    file_url = Column(String(255), nullable=False)
    issued_date = Column(DateTime, default=datetime.datetime.utcnow)
    lab_accreditation = Column(String(100), default="VILAS 102 / ISO 17025")
    is_verified = Column(Boolean, default=True)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    notes = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "doc_number": self.doc_number,
            "filename": self.filename,
            "file_url": self.file_url,
            "supplier_name": self.supplier.name if self.supplier else "N/A",
            "issued_date": self.issued_date.strftime("%d/%m/%Y") if self.issued_date else "",
            "lab_accreditation": self.lab_accreditation,
            "is_verified": self.is_verified
        }


class InspectionImage(Base):
    """
    Physical lot inspection photos captured for AI and visual evaluation
    """
    __tablename__ = 'inspection_images'

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_material_lot_id = Column(Integer, ForeignKey('raw_material_lots.id'), nullable=False)
    raw_material_lot = relationship("RawMaterialLot")

    image_url = Column(String(255), nullable=False)
    image_type = Column(String(50), default="Bao bì ngoài & Niêm phong seal")
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    ai_inspections = relationship("AIInspection", back_populates="inspection_image", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "raw_material_lot_id": self.raw_material_lot_id,
            "image_url": self.image_url,
            "image_type": self.image_type,
            "uploaded_at": self.uploaded_at.strftime("%d/%m/%Y %H:%M") if self.uploaded_at else ""
        }


class AIInspection(Base):
    """
    YOLO AI inference inspection record
    """
    __tablename__ = 'ai_inspections'

    id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_image_id = Column(Integer, ForeignKey('inspection_images.id'), nullable=False)
    inspection_image = relationship("InspectionImage", back_populates="ai_inspections")

    raw_material_lot_id = Column(Integer, ForeignKey('raw_material_lots.id'), nullable=False)
    raw_material_lot = relationship("RawMaterialLot")

    model_version = Column(String(50), default="YOLOv8x-FoodDefect-v2.1")
    inference_time_ms = Column(Float, default=48.5)
    total_defects_count = Column(Integer, default=0)
    summary = Column(String(255), default="Không phát hiện khuyết tật")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    detected_defects = relationship("DetectedDefect", back_populates="ai_inspection", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "model_version": self.model_version,
            "inference_time_ms": self.inference_time_ms,
            "total_defects_count": self.total_defects_count,
            "summary": self.summary,
            "defects": [d.to_dict() for d in self.detected_defects],
            "created_at": self.created_at.strftime("%d/%m/%Y %H:%M:%S") if self.created_at else ""
        }


class DetectedDefect(Base):
    """
    Individual defect instances detected by YOLO with bounding box and confidence score
    """
    __tablename__ = 'detected_defects'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ai_inspection_id = Column(Integer, ForeignKey('ai_inspections.id'), nullable=False)
    ai_inspection = relationship("AIInspection", back_populates="detected_defects")

    defect_class = Column(String(100), nullable=False) # e.g. "Rách bao bì", "Hở seal niêm phong", "Vết ố bẩn", "Móp góc thùng"
    confidence = Column(Float, nullable=False)          # e.g. 0.942 (94.2%)
    
    # Bounding box coordinates in percentage of image dimensions (0 to 100%)
    bbox_x = Column(Float, nullable=False) # left
    bbox_y = Column(Float, nullable=False) # top
    bbox_w = Column(Float, nullable=False) # width
    bbox_h = Column(Float, nullable=False) # height

    def to_dict(self):
        return {
            "id": self.id,
            "defect_class": self.defect_class,
            "confidence": round(self.confidence, 3),
            "confidence_percent": f"{self.confidence * 100:.1f}%",
            "bbox": {
                "x": self.bbox_x,
                "y": self.bbox_y,
                "w": self.bbox_w,
                "h": self.bbox_h
            }
        }


class QCDecision(Base):
    """
    HUMAN-ONLY final decision.
    AI output is advisory-only and NEVER auto-approves.
    Only a verified human inspector click records a decision here.
    """
    __tablename__ = 'qc_decisions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_material_lot_id = Column(Integer, ForeignKey('raw_material_lots.id'), nullable=False)
    raw_material_lot = relationship("RawMaterialLot")

    decided_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    decided_by = relationship("User", foreign_keys=[decided_by_user_id])

    final_status = Column(String(30), nullable=False) # APPROVED, HOLD, REJECTED
    reason = Column(String(255), nullable=True)
    action_notes = Column(Text, nullable=True)
    decided_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "raw_material_lot_id": self.raw_material_lot_id,
            "lot_number": self.raw_material_lot.lot_number if self.raw_material_lot else "N/A",
            "inspector_name": self.decided_by.full_name if self.decided_by else "Chuyên viên QC",
            "final_status": self.final_status,
            "reason": self.reason or "Đã đối chiếu kết quả Lab, COA và AI ngoại quan",
            "action_notes": self.action_notes or "",
            "decided_at": self.decided_at.strftime("%d/%m/%Y %H:%M:%S") if self.decided_at else ""
        }
