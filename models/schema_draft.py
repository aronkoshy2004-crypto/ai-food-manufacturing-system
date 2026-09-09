"""
Base Schema Draft with Frozen Foreign Key Relationships
Phase 0 — Day 1-3 Foundation Schema
Frozen entities: RawMaterialLot, QCInspection, ProductionBatch, WarehouseItem, DispatchOrder
"""
import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from models import Base
from models.enums import StatusEnum

class RawMaterialLot(Base):
    """
    Procurement & Raw Materials intake table.
    FK: created_by_user_id -> users.id
    """
    __tablename__ = 'raw_material_lots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    lot_number = Column(String(50), unique=True, nullable=False, index=True)
    material_name = Column(String(150), nullable=False)
    category = Column(String(100), nullable=False)
    supplier_name = Column(String(150), nullable=False)
    quantity = Column(Float, nullable=False, default=0.0)
    unit = Column(String(30), nullable=False, default="Tons")
    storage_condition = Column(String(100), default="Cool storage 4-6°C")
    status = Column(String(20), nullable=False, default=StatusEnum.PENDING.value)
    
    # Foreign Key relationship
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    
    received_at = Column(DateTime, default=datetime.datetime.utcnow)
    notes = Column(Text, nullable=True)

    # Relationships
    qc_inspections = relationship("QCInspection", back_populates="raw_material_lot", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "lot_number": self.lot_number,
            "material_name": self.material_name,
            "category": self.category,
            "supplier_name": self.supplier_name,
            "quantity": self.quantity,
            "unit": self.unit,
            "storage_condition": self.storage_condition,
            "status": self.status,
            "received_at": self.received_at.strftime("%d/%m/%Y %H:%M") if self.received_at else None,
            "created_by": self.created_by.full_name if self.created_by else None
        }


from models.production import ProductionBatch


class QCInspection(Base):
    """
    Quality Control laboratory testing records.
    FK: inspector_id -> users.id
    FK: raw_material_lot_id -> raw_material_lots.id
    FK: production_batch_id -> production_batches.id
    """
    __tablename__ = 'qc_inspections'

    id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_code = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(150), nullable=False)
    sample_type = Column(String(50), default="Microbiological & Chemical")
    standards_applied = Column(String(100), default="QCVN 5-1:2010/BYT")
    
    # Foreign Keys
    raw_material_lot_id = Column(Integer, ForeignKey('raw_material_lots.id'), nullable=True)
    raw_material_lot = relationship("RawMaterialLot", back_populates="qc_inspections")

    production_batch_id = Column(Integer, ForeignKey('production_batches.id'), nullable=True)
    production_batch = relationship("ProductionBatch", back_populates="qc_inspections")

    inspector_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    inspector = relationship("User", foreign_keys=[inspector_id])

    status = Column(String(20), nullable=False, default=StatusEnum.PENDING.value)
    tested_params = Column(Text, nullable=True) # JSON / Text of Brix, pH, Coliform results
    inspected_at = Column(DateTime, default=datetime.datetime.utcnow)
    notes = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "inspection_code": self.inspection_code,
            "title": self.title,
            "sample_type": self.sample_type,
            "standards_applied": self.standards_applied,
            "status": self.status,
            "inspector": self.inspector.full_name if self.inspector else None,
            "lot_number": self.raw_material_lot.lot_number if self.raw_material_lot else (self.production_batch.batch_code if self.production_batch else "N/A"),
            "inspected_at": self.inspected_at.strftime("%d/%m/%Y %H:%M") if self.inspected_at else None
        }


class WarehouseItem(Base):
    """
    Warehouse inventory stock tracking.
    FK: production_batch_id -> production_batches.id
    FK: audited_by_user_id -> users.id
    """
    __tablename__ = 'warehouse_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_code = Column(String(50), unique=True, nullable=False, index=True)
    product_name = Column(String(150), nullable=False)
    location_bin = Column(String(100), nullable=False, default="Aisle A - Rack 04")
    pallet_count = Column(Float, default=1.0)
    quantity = Column(Float, nullable=False, default=0.0)
    unit = Column(String(30), default="Cartons")
    min_threshold = Column(Float, default=100.0)
    status = Column(String(20), nullable=False, default=StatusEnum.APPROVED.value)

    # Foreign Keys
    production_batch_id = Column(Integer, ForeignKey('production_batches.id'), nullable=True)
    batch = relationship("ProductionBatch", back_populates="warehouse_items")

    audited_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    audited_by = relationship("User", foreign_keys=[audited_by_user_id])

    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    dispatch_orders = relationship("DispatchOrder", back_populates="warehouse_item")

    def to_dict(self):
        return {
            "id": self.id,
            "sku_code": self.sku_code,
            "product_name": self.product_name,
            "location_bin": self.location_bin,
            "pallet_count": self.pallet_count,
            "quantity": self.quantity,
            "unit": self.unit,
            "min_threshold": self.min_threshold,
            "status": self.status,
            "batch_code": self.batch.batch_code if self.batch else "N/A",
            "audited_by": self.audited_by.full_name if self.audited_by else None
        }


class DispatchOrder(Base):
    """
    Outbound transport dispatch orders.
    FK: warehouse_item_id -> warehouse_items.id
    FK: dispatched_by_user_id -> users.id
    """
    __tablename__ = 'dispatch_orders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_code = Column(String(50), unique=True, nullable=False, index=True)
    destination = Column(String(150), nullable=False)
    carrier_name = Column(String(100), default="Factory Cold Chain Fleet")
    license_plate = Column(String(30), default="29C-881.99")
    driver_name = Column(String(100), default="Bui Van Hung")
    quantity = Column(Float, default=0.0)
    unit = Column(String(30), default="Cartons")
    temp_sensor_celsius = Column(Float, default=3.8)
    status = Column(String(20), nullable=False, default=StatusEnum.PENDING.value)

    # Foreign Keys
    warehouse_item_id = Column(Integer, ForeignKey('warehouse_items.id'), nullable=True)
    warehouse_item = relationship("WarehouseItem", back_populates="dispatch_orders")

    dispatched_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    dispatched_by = relationship("User", foreign_keys=[dispatched_by_user_id])

    scheduled_departure = Column(DateTime, default=datetime.datetime.utcnow)
    notes = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "order_code": self.order_code,
            "destination": self.destination,
            "carrier_name": self.carrier_name,
            "license_plate": self.license_plate,
            "driver_name": self.driver_name,
            "quantity": self.quantity,
            "unit": self.unit,
            "temp_sensor_celsius": self.temp_sensor_celsius,
            "status": self.status,
            "dispatched_by": self.dispatched_by.full_name if self.dispatched_by else None,
            "scheduled_departure": self.scheduled_departure.strftime("%d/%m/%Y %H:%M") if self.scheduled_departure else None
        }
