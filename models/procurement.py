"""
Procurement Domain Models: Suppliers, Raw Materials, Purchase Orders, Goods Receipts, and Lots
Phase 1 — PRD Implementation
"""
import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from models import Base
from models.enums import StatusEnum

class Supplier(Base):
    """
    Suppliers providing ingredients and packaging materials
    """
    __tablename__ = 'suppliers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    contact_name = Column(String(100), nullable=True)
    email = Column(String(120), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(String(255), nullable=True)
    rating = Column(Float, default=4.8)
    status = Column(String(20), default="APPROVED")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")
    raw_material_lots = relationship("RawMaterialLot", back_populates="supplier")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "contact_name": self.contact_name or "N/A",
            "email": self.email or "N/A",
            "phone": self.phone or "N/A",
            "address": self.address or "Vietnam",
            "rating": self.rating,
            "status": self.status,
            "po_count": len(self.purchase_orders)
        }


class RawMaterial(Base):
    """
    Catalog of raw materials and packaging specifications
    """
    __tablename__ = 'raw_materials'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    category = Column(String(100), nullable=False) # Fresh Milk, Aseptic Packaging, Sugar & Flavor, Fruit Concentrate
    standard_unit = Column(String(30), nullable=False, default="Tons")
    unit_weight = Column(String(50), default="1,000 kg / tank")
    storage_temp = Column(String(50), default="Cool storage 4-6°C")
    shelf_life_days = Column(Integer, default=180)
    min_stock_level = Column(Float, default=5.0)
    status = Column(String(20), default="APPROVED")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    lots = relationship("RawMaterialLot", back_populates="raw_material")
    po_items = relationship("PurchaseOrderItem", back_populates="raw_material")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "category": self.category,
            "standard_unit": self.standard_unit,
            "unit_weight": self.unit_weight,
            "storage_temp": self.storage_temp,
            "shelf_life_days": self.shelf_life_days,
            "min_stock_level": self.min_stock_level,
            "status": self.status
        }


class PurchaseOrder(Base):
    """
    Purchase Order (PO) with multi-line items
    """
    __tablename__ = 'purchase_orders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    po_number = Column(String(50), unique=True, nullable=False, index=True)
    
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    supplier = relationship("Supplier", back_populates="purchase_orders")

    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    expected_delivery_date = Column(DateTime, nullable=True)
    total_amount = Column(Float, default=0.0)
    currency = Column(String(10), default="VND")
    status = Column(String(20), default="PENDING") # PENDING, APPROVED, PARTIAL_RECEIVED, COMPLETED, CANCELLED
    notes = Column(Text, nullable=True)

    # Relationships
    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")
    goods_receipts = relationship("GoodsReceipt", back_populates="purchase_order")

    def to_dict(self):
        items_list = [item.to_dict() for item in self.items]
        return {
            "id": self.id,
            "po_number": self.po_number,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier.name if self.supplier else "N/A",
            "order_date": self.order_date.strftime("%d/%m/%Y") if self.order_date else "",
            "expected_delivery_date": self.expected_delivery_date.strftime("%d/%m/%Y") if self.expected_delivery_date else "This week",
            "total_amount": self.total_amount,
            "currency": self.currency,
            "status": self.status,
            "items_count": len(self.items),
            "items": items_list,
            "notes": self.notes or ""
        }


class PurchaseOrderItem(Base):
    """
    Line items within a Purchase Order
    """
    __tablename__ = 'purchase_order_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    purchase_order_id = Column(Integer, ForeignKey('purchase_orders.id'), nullable=False)
    purchase_order = relationship("PurchaseOrder", back_populates="items")

    raw_material_id = Column(Integer, ForeignKey('raw_materials.id'), nullable=False)
    raw_material = relationship("RawMaterial", back_populates="po_items")

    quantity_ordered = Column(Float, nullable=False)
    quantity_received = Column(Float, default=0.0)
    unit = Column(String(30), nullable=False)
    unit_price = Column(Float, default=0.0)
    subtotal = Column(Float, default=0.0)
    notes = Column(String(255), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "purchase_order_id": self.purchase_order_id,
            "raw_material_id": self.raw_material_id,
            "material_name": self.raw_material.name if self.raw_material else "N/A",
            "material_code": self.raw_material.code if self.raw_material else "N/A",
            "quantity_ordered": self.quantity_ordered,
            "quantity_received": self.quantity_received,
            "unit": self.unit,
            "unit_price": self.unit_price,
            "subtotal": self.subtotal,
            "is_fully_received": self.quantity_received >= self.quantity_ordered
        }


class GoodsReceipt(Base):
    """
    Goods Receipt Note (GRN) created upon arrival and intake of PO items
    """
    __tablename__ = 'goods_receipts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    grn_number = Column(String(50), unique=True, nullable=False, index=True)

    purchase_order_id = Column(Integer, ForeignKey('purchase_orders.id'), nullable=False)
    purchase_order = relationship("PurchaseOrder", back_populates="goods_receipts")

    receiver_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    receiver = relationship("User", foreign_keys=[receiver_user_id])

    received_date = Column(DateTime, default=datetime.datetime.utcnow)
    delivery_note_ref = Column(String(100), nullable=True) # Delivery Note / Bill of Lading
    truck_plate = Column(String(50), default="29C-438.12")
    status = Column(String(20), default="COMPLETED")
    notes = Column(Text, nullable=True)

    # Relationships
    items = relationship("GoodsReceiptItem", back_populates="goods_receipt", cascade="all, delete-orphan")
    generated_lots = relationship("RawMaterialLot", back_populates="goods_receipt")

    def to_dict(self):
        return {
            "id": self.id,
            "grn_number": self.grn_number,
            "purchase_order_id": self.purchase_order_id,
            "po_number": self.purchase_order.po_number if self.purchase_order else "N/A",
            "supplier_name": self.purchase_order.supplier.name if (self.purchase_order and self.purchase_order.supplier) else "N/A",
            "received_date": self.received_date.strftime("%d/%m/%Y %H:%M") if self.received_date else "",
            "delivery_note_ref": self.delivery_note_ref or "N/A",
            "truck_plate": self.truck_plate or "N/A",
            "status": self.status,
            "items_count": len(self.items),
            "receiver": self.receiver.full_name if self.receiver else "Warehouse Custodian"
        }


class GoodsReceiptItem(Base):
    """
    Line items received in a GRN
    """
    __tablename__ = 'goods_receipt_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    goods_receipt_id = Column(Integer, ForeignKey('goods_receipts.id'), nullable=False)
    goods_receipt = relationship("GoodsReceipt", back_populates="items")

    purchase_order_item_id = Column(Integer, ForeignKey('purchase_order_items.id'), nullable=True)
    purchase_order_item = relationship("PurchaseOrderItem")

    raw_material_id = Column(Integer, ForeignKey('raw_materials.id'), nullable=False)
    raw_material = relationship("RawMaterial")

    quantity_received = Column(Float, nullable=False)
    unit = Column(String(30), nullable=False)
    unit_weight = Column(String(50), nullable=True)
    notes = Column(String(255), nullable=True)


# Update RawMaterialLot integration with procurement foreign keys
from models.schema_draft import RawMaterialLot

# Add foreign key columns dynamically if not present or define model relationships
RawMaterialLot.raw_material_id = Column(Integer, ForeignKey('raw_materials.id'), nullable=True)
RawMaterialLot.raw_material = relationship("RawMaterial", back_populates="lots")

RawMaterialLot.supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=True)
RawMaterialLot.supplier = relationship("Supplier", back_populates="raw_material_lots")

RawMaterialLot.purchase_order_id = Column(Integer, ForeignKey('purchase_orders.id'), nullable=True)
RawMaterialLot.purchase_order = relationship("PurchaseOrder")

RawMaterialLot.goods_receipt_id = Column(Integer, ForeignKey('goods_receipts.id'), nullable=True)
RawMaterialLot.goods_receipt = relationship("GoodsReceipt", back_populates="generated_lots")

RawMaterialLot.qc_status = Column(String(30), default="PENDING_QC") # PENDING_QC, APPROVED, REJECTED, HOLD
RawMaterialLot.unit_weight = Column(String(50), default="Standard spec")
