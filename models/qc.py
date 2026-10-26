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
    sample_size = Column(String(50), default="500ml / 5 random samples")
    notes = Column(Text, nullable=True)

    # Relationships
    tests = relationship("QCTest", back_populates="qc_sample", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "sample_code": self.sample_code,
            "raw_material_lot_id": self.raw_material_lot_id,
            "lot_number": self.raw_material_lot.lot_number if self.raw_material_lot else "N/A",
            "sampler_name": self.sampler.full_name if self.sampler else "QC Specialist",
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

    parameter_name = Column(String(100), nullable=False) # e.g. Brix Level, pH Index, Fat Content, Coliform, Sensory
    standard_spec = Column(String(100), nullable=False)  # e.g. "≥ 3.2%", "6.5 - 6.8 pH", "< 10 CFU/ml"
    measured_value = Column(String(100), nullable=False) # e.g. "3.45%", "6.65 pH", "Negative (0 CFU)"
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
    Physical inspection photos captured for AI and visual evaluation,
    linkable to Raw Material Lots, Products, or Production Batches.
    """
    __tablename__ = 'inspection_images'

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_material_lot_id = Column(Integer, ForeignKey('raw_material_lots.id'), nullable=True)
    raw_material_lot = relationship("RawMaterialLot")

    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)
    product = relationship("Product")

    production_batch_id = Column(Integer, ForeignKey('production_batches.id'), nullable=True)
    production_batch = relationship("ProductionBatch")

    image_url = Column(String(255), nullable=False)
    annotated_image_url = Column(String(255), nullable=True)
    image_type = Column(String(100), default="Raw Material / Food Product Visual Scan")
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    ai_inspections = relationship("AIInspection", back_populates="inspection_image", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "raw_material_lot_id": self.raw_material_lot_id,
            "product_id": self.product_id,
            "production_batch_id": self.production_batch_id,
            "target_type": "lot" if self.raw_material_lot_id else ("product" if self.product_id else ("batch" if self.production_batch_id else "general")),
            "target_identifier": (self.raw_material_lot.lot_number if self.raw_material_lot else 
                                 (self.product.code if self.product else 
                                 (self.production_batch.batch_code if self.production_batch else "N/A"))),
            "target_name": (self.raw_material_lot.material_name if self.raw_material_lot else 
                           (self.product.name if self.product else 
                           (self.production_batch.product_name if self.production_batch else "N/A"))),
            "image_url": self.image_url,
            "annotated_image_url": self.annotated_image_url or self.image_url,
            "image_type": self.image_type,
            "uploaded_at": self.uploaded_at.strftime("%d/%m/%Y %H:%M") if self.uploaded_at else ""
        }


class AIInspection(Base):
    """
    YOLOv8 AI inference inspection record with defect classification,
    bounding box coordinates, confidence scores, and model diagnostic status.
    """
    __tablename__ = 'ai_inspections'

    id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_image_id = Column(Integer, ForeignKey('inspection_images.id'), nullable=False)
    inspection_image = relationship("InspectionImage", back_populates="ai_inspections")

    raw_material_lot_id = Column(Integer, ForeignKey('raw_material_lots.id'), nullable=True)
    raw_material_lot = relationship("RawMaterialLot")

    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)
    product = relationship("Product")

    production_batch_id = Column(Integer, ForeignKey('production_batches.id'), nullable=True)
    production_batch = relationship("ProductionBatch")

    model_version = Column(String(100), default="YOLOv8")
    model_status = Column(String(50), default="READY") # READY, MODEL_NOT_FOUND, NO_DEFECTS, DEFECTS_DETECTED
    inference_time_ms = Column(Float, default=0.0)
    total_defects_count = Column(Integer, default=0)
    summary = Column(String(255), default="No defects detected")
    status_message = Column(Text, nullable=True)
    annotated_image_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Material mismatch warning attributes
    material_mismatch = Column(Boolean, default=False, nullable=True)
    mismatch_warning = Column(String(255), nullable=True)
    detected_material = Column(String(50), nullable=True)
    lot_material = Column(String(50), nullable=True)
    avg_confidence = Column(Float, default=0.0, nullable=True)

    # Relationships
    detected_defects = relationship("DetectedDefect", back_populates="ai_inspection", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "inspection_image_id": self.inspection_image_id,
            "raw_material_lot_id": self.raw_material_lot_id,
            "product_id": self.product_id,
            "production_batch_id": self.production_batch_id,
            "target_label": (self.raw_material_lot.lot_number if self.raw_material_lot else 
                            (self.product.name if self.product else 
                            (self.production_batch.batch_code if self.production_batch else "Unlinked"))),
            "model_version": self.model_version,
            "model_status": self.model_status,
            "inference_time_ms": round(self.inference_time_ms, 1),
            "total_defects_count": self.total_defects_count,
            "summary": self.summary,
            "status_message": self.status_message,
            "raw_image_url": self.inspection_image.image_url if self.inspection_image else "",
            "annotated_image_url": self.annotated_image_url or (self.inspection_image.annotated_image_url if self.inspection_image else ""),
            "defects": [d.to_dict() for d in self.detected_defects],
            "material_mismatch": bool(self.material_mismatch) if self.material_mismatch is not None else False,
            "mismatch_warning": self.mismatch_warning,
            "detected_material": self.detected_material,
            "lot_material": self.lot_material,
            "avg_confidence": round(self.avg_confidence, 3) if self.avg_confidence is not None else 0.0,
            "created_at": self.created_at.strftime("%d/%m/%Y %H:%M:%S") if self.created_at else ""
        }


class DetectedDefect(Base):
    """
    Individual defect instances detected by YOLOv8 with bounding box and confidence score
    """
    __tablename__ = 'detected_defects'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ai_inspection_id = Column(Integer, ForeignKey('ai_inspections.id'), nullable=False)
    ai_inspection = relationship("AIInspection", back_populates="detected_defects")

    defect_class = Column(String(100), nullable=False) # e.g. "Mold/Fungal Spot", "Broken/Cracked Seed", "Foreign Matter", "Packaging Tear"
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
    raw_material_lot_id = Column(Integer, ForeignKey('raw_material_lots.id'), nullable=True)
    raw_material_lot = relationship("RawMaterialLot")

    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)
    product = relationship("Product")

    production_batch_id = Column(Integer, ForeignKey('production_batches.id'), nullable=True)
    production_batch = relationship("ProductionBatch")

    decided_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    decided_by = relationship("User", foreign_keys=[decided_by_user_id])

    final_status = Column(String(30), nullable=False) # APPROVED, HOLD, REJECTED
    reason = Column(String(255), nullable=True)
    action_notes = Column(Text, nullable=True)
    decided_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        target_name = (self.raw_material_lot.lot_number if self.raw_material_lot else 
                      (self.product.name if self.product else 
                      (self.production_batch.batch_code if self.production_batch else "N/A")))
        return {
            "id": self.id,
            "raw_material_lot_id": self.raw_material_lot_id,
            "product_id": self.product_id,
            "production_batch_id": self.production_batch_id,
            "target_identifier": target_name,
            "inspector_name": self.decided_by.full_name if self.decided_by else "QC Specialist",
            "final_status": self.final_status,
            "reason": self.reason or "Verified Lab tests, COA and AI visual inspection",
            "action_notes": self.action_notes or "",
            "decided_at": self.decided_at.strftime("%d/%m/%Y %H:%M:%S") if self.decided_at else ""
        }


class AIFeedback(Base):
    """
    Feedback loop for continuous model improvement.
    Stores QC inspector confirmation or corrections of YOLOv8 defect classifications.
    Enables iterative dataset refinement and model retraining.
    """
    __tablename__ = 'ai_feedbacks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ai_inspection_id = Column(Integer, ForeignKey('ai_inspections.id'), nullable=False)
    ai_inspection = relationship("AIInspection")

    inspector_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    inspector = relationship("User", foreign_keys=[inspector_user_id])

    feedback_type = Column(String(50), nullable=False)  # CONFIRMED_ACCURATE, FALSE_POSITIVE, MISCLASSIFIED, NEEDS_RETRAINING
    corrected_class = Column(String(100), nullable=True)
    inspector_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "ai_inspection_id": self.ai_inspection_id,
            "inspector_name": self.inspector.full_name if self.inspector else "QC Inspector",
            "feedback_type": self.feedback_type,
            "corrected_class": self.corrected_class,
            "inspector_notes": self.inspector_notes or "",
            "created_at": self.created_at.strftime("%d/%m/%Y %H:%M:%S") if self.created_at else ""
        }


class LiveSession(Base):
    """
    Live mobile inspection sessions for QR pairing and real-time camera streaming.
    Phase 1 — Live Inspection sessions
    """
    __tablename__ = 'live_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    lot_id = Column(Integer, ForeignKey('raw_material_lots.id'), nullable=True)
    lot = relationship("RawMaterialLot")
    status = Column(String(30), nullable=False, default="ACTIVE") # ACTIVE, CLOSED, EXPIRED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    locked_result_json = Column(Text, nullable=True)
    ai_inspection_id = Column(Integer, ForeignKey('ai_inspections.id'), nullable=True)
    ai_inspection = relationship("AIInspection")

    # Relationships
    frames = relationship("LiveFrame", back_populates="session", cascade="all, delete-orphan", order_by="LiveFrame.id.asc()")

    def is_active(self) -> bool:
        if self.status != "ACTIVE":
            return False
        if self.expires_at and datetime.datetime.utcnow() > self.expires_at:
            return False
        return True

    def to_dict(self):
        import json
        locked_parsed = None
        if self.locked_result_json:
            try:
                locked_parsed = json.loads(self.locked_result_json)
            except Exception:
                locked_parsed = None

        return {
            "id": self.id,
            "token": self.token,
            "lot_id": self.lot_id,
            "lot_number": self.lot.lot_number if self.lot else None,
            "lot_material": self.lot.material_name if self.lot else None,
            "status": self.status,
            "created_at": self.created_at.strftime("%d/%m/%Y %H:%M:%S") if self.created_at else "",
            "created_at_iso": self.created_at.isoformat() if self.created_at else "",
            "expires_at": self.expires_at.strftime("%d/%m/%Y %H:%M:%S") if self.expires_at else "",
            "expires_at_iso": self.expires_at.isoformat() if self.expires_at else "",
            "closed_at": self.closed_at.strftime("%d/%m/%Y %H:%M:%S") if self.closed_at else None,
            "is_active": self.is_active(),
            "frames_count": len(self.frames) if self.frames else 0,
            "locked_result": locked_parsed,
            "ai_inspection_id": self.ai_inspection_id
        }


class LiveFrame(Base):
    """
    Individual frame captures uploaded from phone camera during a live inspection session.
    Stores raw detection results, bounding boxes, counts, and image paths.
    """
    __tablename__ = 'live_frames'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('live_sessions.id'), nullable=False)
    session = relationship("LiveSession", back_populates="frames")

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    image_path = Column(String(255), nullable=False)
    annotated_path = Column(String(255), nullable=True)
    material = Column(String(50), nullable=True)
    good_count = Column(Integer, default=0)
    defect_count = Column(Integer, default=0)
    avg_confidence = Column(Float, default=0.0)
    status = Column(String(50), nullable=True) # e.g. "NO_DEFECTS", "DEFECTS_DETECTED"
    is_locked = Column(Boolean, default=False, nullable=False)
    raw_json = Column(Text, nullable=True)

    def to_dict(self):
        import json
        raw_parsed = None
        if self.raw_json:
            try:
                raw_parsed = json.loads(self.raw_json)
            except Exception:
                raw_parsed = self.raw_json

        return {
            "id": self.id,
            "session_id": self.session_id,
            "created_at": self.created_at.strftime("%H:%M:%S") if self.created_at else "",
            "created_at_iso": self.created_at.isoformat() if self.created_at else "",
            "image_path": self.image_path,
            "annotated_path": (
                (self.annotated_path or self.image_path or '').replace(
                    '/static/uploads/annotated/annotated_live_',
                    '/static/uploads/live_frames/annotated/annotated_live_'
                )
            ),
            "material": self.material,
            "good_count": self.good_count or 0,
            "defect_count": self.defect_count or 0,
            "total_count": (self.good_count or 0) + (self.defect_count or 0),
            "avg_confidence": round(self.avg_confidence, 3) if self.avg_confidence is not None else 0.0,
            "status": self.status,
            "is_locked": bool(self.is_locked),
            "raw_json": raw_parsed
        }


