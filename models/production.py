"""
Production, Recipes, BOM & Packaging Models
PRD Phase 3
"""
import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from models import Base
from models.enums import StatusEnum

class Product(Base):
    """
    Finished Food & Beverage Products catalog
    """
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    category = Column(String(100), nullable=False, default="Sữa tiệt trùng")
    unit = Column(String(30), nullable=False, default="Thùng")
    shelf_life_days = Column(Integer, nullable=False, default=180) # days
    target_batch_size = Column(Float, nullable=False, default=5000.0) # standard units per batch
    storage_temp = Column(String(100), default="Nhiệt độ phòng (22-28°C)")
    description = Column(Text, nullable=True)
    image_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    recipes = relationship("Recipe", back_populates="product", cascade="all, delete-orphan")
    batches = relationship("ProductionBatch", back_populates="product")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "category": self.category,
            "unit": self.unit,
            "shelf_life_days": self.shelf_life_days,
            "target_batch_size": self.target_batch_size,
            "storage_temp": self.storage_temp,
            "description": self.description,
            "image_url": self.image_url,
            "active_recipe": self.active_recipe.to_dict() if self.active_recipe else None
        }

    @property
    def active_recipe(self):
        for r in self.recipes:
            if r.is_active:
                return r
        return self.recipes[0] if self.recipes else None


class Recipe(Base):
    """
    Manufacturing Recipe definition linking to BOM materials
    """
    __tablename__ = 'recipes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    recipe_code = Column(String(50), unique=True, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    version = Column(String(20), nullable=False, default="v1.0")
    standard_batch_yield = Column(Float, nullable=False, default=5000.0) # units produced per batch
    yield_unit = Column(String(30), nullable=False, default="Thùng")
    standard_prep_time_minutes = Column(Integer, default=240) # 4 hours
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="recipes")
    materials = relationship("RecipeMaterial", back_populates="recipe", cascade="all, delete-orphan")
    batches = relationship("ProductionBatch", back_populates="recipe")

    def to_dict(self):
        return {
            "id": self.id,
            "recipe_code": self.recipe_code,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else "N/A",
            "version": self.version,
            "standard_batch_yield": self.standard_batch_yield,
            "yield_unit": self.yield_unit,
            "standard_prep_time_minutes": self.standard_prep_time_minutes,
            "is_active": self.is_active,
            "notes": self.notes,
            "bom_items": [m.to_dict() for m in self.materials]
        }


class RecipeMaterial(Base):
    """
    Bill of Materials (BOM) linking Recipe to RawMaterial requirements
    """
    __tablename__ = 'recipe_materials'

    id = Column(Integer, primary_key=True, autoincrement=True)
    recipe_id = Column(Integer, ForeignKey('recipes.id'), nullable=False)
    raw_material_id = Column(Integer, ForeignKey('raw_materials.id'), nullable=False)
    required_quantity = Column(Float, nullable=False, default=1.0) # required per standard batch
    unit = Column(String(30), nullable=False, default="Tấn")
    tolerance_percent = Column(Float, default=2.0) # allowable variance +/- %
    notes = Column(Text, nullable=True)

    # Relationships
    recipe = relationship("Recipe", back_populates="materials")
    raw_material = relationship("RawMaterial")

    def to_dict(self):
        return {
            "id": self.id,
            "recipe_id": self.recipe_id,
            "raw_material_id": self.raw_material_id,
            "raw_material_code": self.raw_material.code if self.raw_material else "N/A",
            "raw_material_name": self.raw_material.name if self.raw_material else "N/A",
            "required_quantity": self.required_quantity,
            "unit": self.unit,
            "tolerance_percent": self.tolerance_percent
        }


class ProductionBatch(Base):
    """
    Production Batch execution on manufacturing lines.
    Replaces draft model with complete PRD Phase 3 schema.
    """
    __tablename__ = 'production_batches'

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_code = Column(String(50), unique=True, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)
    recipe_id = Column(Integer, ForeignKey('recipes.id'), nullable=True)
    product_name = Column(String(150), nullable=False)
    line_name = Column(String(100), nullable=False, default="Line A1 - Tetra Pak 250ml")
    target_quantity = Column(Float, nullable=False, default=5000.0)
    actual_quantity = Column(Float, nullable=False, default=0.0)
    unit = Column(String(30), nullable=False, default="Thùng")
    temperature_spec = Column(String(50), default="138.5°C / 4s UHT")
    
    # Batch status: IN_PROGRESS, COMPLETE, HOLD, CANCELLED
    status = Column(String(30), nullable=False, default="IN_PROGRESS")
    current_stage = Column(String(100), default="Chuẩn bị nguyên liệu")
    stage_progress_percent = Column(Integer, default=20)
    
    shift_manager_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    shift_manager = relationship("User", foreign_keys=[shift_manager_id])

    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    mfg_date = Column(DateTime, default=datetime.datetime.utcnow)
    expiry_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    product = relationship("Product", back_populates="batches")
    recipe = relationship("Recipe", back_populates="batches")
    consumed_materials = relationship("BatchRawMaterial", back_populates="production_batch", cascade="all, delete-orphan")
    process_records = relationship("ProductionProcessRecord", back_populates="production_batch", cascade="all, delete-orphan", order_by="ProductionProcessRecord.stage_order")
    packaging_records = relationship("PackagingRecord", back_populates="production_batch", cascade="all, delete-orphan")
    qc_inspections = relationship("QCInspection", back_populates="production_batch", cascade="all, delete-orphan")
    warehouse_items = relationship("WarehouseItem", back_populates="batch")

    def to_dict(self):
        progress = self.stage_progress_percent or (int((self.actual_quantity / self.target_quantity * 100)) if self.target_quantity > 0 else 0)
        return {
            "id": self.id,
            "batch_code": self.batch_code,
            "product_id": self.product_id,
            "recipe_id": self.recipe_id,
            "product_name": self.product_name,
            "line_name": self.line_name,
            "target_quantity": self.target_quantity,
            "actual_quantity": self.actual_quantity,
            "unit": self.unit,
            "progress": min(progress, 100),
            "temperature_spec": self.temperature_spec,
            "status": self.status,
            "current_stage": self.current_stage,
            "shift_manager": self.shift_manager.full_name if self.shift_manager else "Trần Minh Quân",
            "started_at": self.started_at.strftime("%d/%m/%Y %H:%M") if self.started_at else None,
            "completed_at": self.completed_at.strftime("%d/%m/%Y %H:%M") if self.completed_at else None,
            "mfg_date": self.mfg_date.strftime("%d/%m/%Y") if self.mfg_date else None,
            "expiry_date": self.expiry_date.strftime("%d/%m/%Y") if self.expiry_date else None,
            "consumed_materials": [cm.to_dict() for cm in self.consumed_materials],
            "process_stages": [pr.to_dict() for pr in self.process_records],
            "packaging": self.packaging_records[0].to_dict() if self.packaging_records else None
        }


class BatchRawMaterial(Base):
    """
    Specific raw material lots consumed by a production batch for complete traceability
    """
    __tablename__ = 'batch_raw_materials'

    id = Column(Integer, primary_key=True, autoincrement=True)
    production_batch_id = Column(Integer, ForeignKey('production_batches.id'), nullable=False)
    raw_material_lot_id = Column(Integer, ForeignKey('raw_material_lots.id'), nullable=False)
    quantity_consumed = Column(Float, nullable=False, default=0.0)
    unit = Column(String(30), nullable=False, default="Tấn")
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    production_batch = relationship("ProductionBatch", back_populates="consumed_materials")
    raw_material_lot = relationship("RawMaterialLot")

    def to_dict(self):
        return {
            "id": self.id,
            "production_batch_id": self.production_batch_id,
            "raw_material_lot_id": self.raw_material_lot_id,
            "lot_number": self.raw_material_lot.lot_number if self.raw_material_lot else "N/A",
            "material_name": self.raw_material_lot.material_name if self.raw_material_lot else "N/A",
            "quantity_consumed": self.quantity_consumed,
            "unit": self.unit,
            "recorded_at": self.recorded_at.strftime("%d/%m/%Y %H:%M") if self.recorded_at else None
        }


class ProductionProcessRecord(Base):
    """
    Stage tracking with start/end timestamps per stage in place of static dropdowns
    """
    __tablename__ = 'production_process_records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    production_batch_id = Column(Integer, ForeignKey('production_batches.id'), nullable=False)
    stage_name = Column(String(100), nullable=False)
    stage_order = Column(Integer, nullable=False, default=1)
    status = Column(String(30), nullable=False, default="PENDING") # PENDING, IN_PROGRESS, COMPLETED
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    operator_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    operator = relationship("User", foreign_keys=[operator_id])
    parameters_log = Column(Text, nullable=True) # e.g. "Brix: 12.4, Nhiệt độ tiệt trùng: 138.5°C"
    notes = Column(Text, nullable=True)

    # Relationships
    production_batch = relationship("ProductionBatch", back_populates="process_records")

    def to_dict(self):
        duration_mins = None
        if self.started_at and self.ended_at:
            duration_mins = int((self.ended_at - self.started_at).total_seconds() / 60)
        return {
            "id": self.id,
            "production_batch_id": self.production_batch_id,
            "stage_name": self.stage_name,
            "stage_order": self.stage_order,
            "status": self.status,
            "started_at": self.started_at.strftime("%d/%m/%Y %H:%M:%S") if self.started_at else None,
            "ended_at": self.ended_at.strftime("%d/%m/%Y %H:%M:%S") if self.ended_at else None,
            "duration_minutes": duration_mins,
            "operator": self.operator.full_name if self.operator else "Kỹ thuật viên ca",
            "parameters_log": self.parameters_log,
            "notes": self.notes
        }


class PackagingMaterial(Base):
    """
    Packaging consumables: Cartons, Tetra Pak rolls, film, shrink wrap
    """
    __tablename__ = 'packaging_materials'

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_code = Column(String(50), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    unit = Column(String(30), nullable=False, default="Thùng carton")
    stock_quantity = Column(Float, nullable=False, default=10000.0)
    specifications = Column(String(150), default="Carton 5 lớp in Flexo chống ẩm")

    def to_dict(self):
        return {
            "id": self.id,
            "material_code": self.material_code,
            "name": self.name,
            "unit": self.unit,
            "stock_quantity": self.stock_quantity,
            "specifications": self.specifications
        }


class PackagingRecord(Base):
    """
    Packaging records and output inspection for a finished batch
    """
    __tablename__ = 'packaging_records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    production_batch_id = Column(Integer, ForeignKey('production_batches.id'), nullable=False)
    carton_boxes_used = Column(Integer, nullable=False, default=0)
    packaging_seal_rolls_used = Column(Float, nullable=False, default=0.0)
    packages_completed = Column(Integer, nullable=False, default=0) # units produced
    waste_count = Column(Integer, default=0)
    inspected_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    inspected_by = relationship("User", foreign_keys=[inspected_by_user_id])
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow)
    notes = Column(Text, nullable=True)

    # Relationships
    production_batch = relationship("ProductionBatch", back_populates="packaging_records")

    def to_dict(self):
        return {
            "id": self.id,
            "production_batch_id": self.production_batch_id,
            "carton_boxes_used": self.carton_boxes_used,
            "packaging_seal_rolls_used": self.packaging_seal_rolls_used,
            "packages_completed": self.packages_completed,
            "waste_count": self.waste_count,
            "inspected_by": self.inspected_by.full_name if self.inspected_by else "Tổ trưởng Đóng gói",
            "recorded_at": self.recorded_at.strftime("%d/%m/%Y %H:%M") if self.recorded_at else None,
            "notes": self.notes
        }
