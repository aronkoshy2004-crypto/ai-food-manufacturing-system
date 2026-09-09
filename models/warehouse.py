"""
Warehouse, Inventory, Dispatch, Traceability & Alerts Models
PRD Phase 4
"""
import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from models import Base
from models.enums import StatusEnum

class WarehouseInventory(Base):
    """
    Warehouse inventory stock synced ONLY from approved finished batches.
    Sorted by FEFO (First Expired, First Out: nearest expiry first).
    """
    __tablename__ = 'warehouse_inventory'

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_code = Column(String(50), unique=True, nullable=False, index=True)
    production_batch_id = Column(Integer, ForeignKey('production_batches.id'), nullable=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)
    batch_code = Column(String(50), nullable=False, index=True)
    product_name = Column(String(150), nullable=False)
    
    # Quantities
    initial_quantity = Column(Float, nullable=False, default=0.0)
    available_quantity = Column(Float, nullable=False, default=0.0) # live decrements on dispatch
    allocated_quantity = Column(Float, nullable=False, default=0.0)
    unit = Column(String(30), nullable=False, default="Cartons")
    unit_price = Column(Float, default=240000.0) # VND per unit for stock valuation
    
    # Storage specs
    storage_bin = Column(String(100), nullable=False, default="Zone A - Rack 04 Shelf 2")
    pallet_code = Column(String(50), default="PLT-2026-081")
    storage_temperature = Column(String(50), default="20-25°C Ambient Dry")
    
    # Dates for FEFO
    mfg_date = Column(DateTime, default=datetime.datetime.utcnow)
    expiry_date = Column(DateTime, nullable=False, index=True) # FEFO primary index
    received_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Status: NORMAL, EXPIRING_SOON, EXPIRED, QUARANTINED
    status = Column(String(30), nullable=False, default="NORMAL")
    
    # Audited by
    audited_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    audited_by = relationship("User", foreign_keys=[audited_by_user_id])

    # Relationships
    batch = relationship("ProductionBatch")
    product = relationship("Product")
    dispatch_items = relationship("DispatchItem", back_populates="inventory")

    @property
    def days_to_expiry(self):
        if not self.expiry_date:
            return 999
        now = datetime.datetime.utcnow()
        delta = (self.expiry_date - now).total_seconds() / 86400
        return int(delta)

    @property
    def expiry_urgency(self):
        days = self.days_to_expiry
        if days <= 0:
            return "EXPIRED" # Red
        elif days <= 15:
            return "EXPIRING_SOON" # Red-orange
        elif days <= 45:
            return "ATTENTION" # Amber
        else:
            return "FRESH" # Green

    def to_dict(self):
        days = self.days_to_expiry
        urgency = self.expiry_urgency
        return {
            "id": self.id,
            "sku_code": self.sku_code,
            "production_batch_id": self.production_batch_id,
            "product_id": self.product_id,
            "batch_code": self.batch_code,
            "product_name": self.product_name,
            "initial_quantity": self.initial_quantity,
            "available_quantity": self.available_quantity,
            "allocated_quantity": self.allocated_quantity,
            "unit": self.unit,
            "unit_price": self.unit_price,
            "total_value": self.available_quantity * self.unit_price,
            "storage_bin": self.storage_bin,
            "pallet_code": self.pallet_code,
            "storage_temperature": self.storage_temperature,
            "mfg_date": self.mfg_date.strftime("%d/%m/%Y") if self.mfg_date else None,
            "expiry_date": self.expiry_date.strftime("%d/%m/%Y") if self.expiry_date else None,
            "days_to_expiry": days,
            "expiry_urgency": urgency,
            "status": self.status,
            "audited_by": self.audited_by.full_name if self.audited_by else "Hoang Dinh Tuan",
            "received_at": self.received_at.strftime("%d/%m/%Y %H:%M") if self.received_at else None
        }


class Customer(Base):
    """
    Retail distribution chains, supermarkets, export partners
    """
    __tablename__ = 'customers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    tax_id = Column(String(50), nullable=True)
    contact_person = Column(String(100), default="Tran Thanh Nga")
    phone = Column(String(30), default="0903.112.334")
    email = Column(String(100), default="purchasing@retailchain.vn")
    delivery_address = Column(String(200), default="VinMart Central DC Northern Division, Hanoi")
    city = Column(String(100), default="Hanoi")
    status = Column(String(20), default="ACTIVE")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    dispatches = relationship("Dispatch", back_populates="customer")

    def to_dict(self):
        return {
            "id": self.id,
            "customer_code": self.customer_code,
            "name": self.name,
            "tax_id": self.tax_id,
            "contact_person": self.contact_person,
            "phone": self.phone,
            "email": self.email,
            "delivery_address": self.delivery_address,
            "city": self.city,
            "status": self.status
        }


class Dispatch(Base):
    """
    Outbound shipping dispatch order with live inventory decrement and cold-chain logging
    """
    __tablename__ = 'dispatches'

    id = Column(Integer, primary_key=True, autoincrement=True)
    dispatch_code = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    dispatched_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    destination = Column(String(200), nullable=False)
    carrier_name = Column(String(100), default="FoodMan Cold Chain Fleet")
    license_plate = Column(String(30), default="29C-881.99")
    driver_name = Column(String(100), default="Bui Van Hung")
    driver_phone = Column(String(30), default="0978.555.234")
    
    temp_sensor_celsius = Column(Float, default=4.2)
    temp_spec_range = Column(String(50), default="2.0°C - 6.0°C")
    
    # Status: PENDING, IN_TRANSIT, DELIVERED, CANCELLED
    status = Column(String(30), nullable=False, default="IN_TRANSIT")
    total_packages = Column(Float, default=0.0)
    total_amount = Column(Float, default=0.0)
    
    scheduled_departure = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    customer = relationship("Customer", back_populates="dispatches")
    dispatched_by = relationship("User", foreign_keys=[dispatched_by_id])
    items = relationship("DispatchItem", back_populates="dispatch", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "dispatch_code": self.dispatch_code,
            "customer_id": self.customer_id,
            "customer_name": self.customer.name if self.customer else "N/A",
            "destination": self.destination,
            "carrier_name": self.carrier_name,
            "license_plate": self.license_plate,
            "driver_name": self.driver_name,
            "driver_phone": self.driver_phone,
            "temp_sensor_celsius": self.temp_sensor_celsius,
            "temp_spec_range": self.temp_spec_range,
            "status": self.status,
            "total_packages": self.total_packages,
            "total_amount": self.total_amount,
            "scheduled_departure": self.scheduled_departure.strftime("%d/%m/%Y %H:%M") if self.scheduled_departure else None,
            "completed_at": self.completed_at.strftime("%d/%m/%Y %H:%M") if self.completed_at else None,
            "dispatched_by": self.dispatched_by.full_name if self.dispatched_by else "Warehouse Coordinator",
            "notes": self.notes,
            "items": [item.to_dict() for item in self.items]
        }


class DispatchItem(Base):
    """
    Line items in a dispatch order linking directly to inventory & production batch
    """
    __tablename__ = 'dispatch_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    dispatch_id = Column(Integer, ForeignKey('dispatches.id'), nullable=False)
    inventory_id = Column(Integer, ForeignKey('warehouse_inventory.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)
    batch_code = Column(String(50), nullable=False)
    quantity = Column(Float, nullable=False, default=1.0)
    unit = Column(String(30), default="Cartons")
    unit_price = Column(Float, default=240000.0)
    subtotal = Column(Float, default=240000.0)

    # Relationships
    dispatch = relationship("Dispatch", back_populates="items")
    inventory = relationship("WarehouseInventory", back_populates="dispatch_items")
    product = relationship("Product")

    def to_dict(self):
        return {
            "id": self.id,
            "dispatch_id": self.dispatch_id,
            "inventory_id": self.inventory_id,
            "product_id": self.product_id,
            "product_name": self.inventory.product_name if self.inventory else (self.product.name if self.product else "N/A"),
            "batch_code": self.batch_code,
            "quantity": self.quantity,
            "unit": self.unit,
            "unit_price": self.unit_price,
            "subtotal": self.subtotal
        }


class AlertRule(Base):
    """
    Automated notification rules (Low stock, FEFO expiry, Temp excursion, QC Rejection)
    """
    __tablename__ = 'alert_rules'

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_code = Column(String(50), unique=True, nullable=False)
    rule_name = Column(String(150), nullable=False)
    rule_type = Column(String(50), nullable=False) # LOW_STOCK, EXPIRING_SOON, TEMP_EXCURSION, QC_REJECTION
    threshold_value = Column(Float, default=15.0) # e.g. 15 days or 100 units or 6.5 C
    severity = Column(String(20), default="WARNING") # INFO, WARNING, CRITICAL
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    notifications = relationship("NotificationAlert", back_populates="rule")

    def to_dict(self):
        return {
            "id": self.id,
            "rule_code": self.rule_code,
            "rule_name": self.rule_name,
            "rule_type": self.rule_type,
            "threshold_value": self.threshold_value,
            "severity": self.severity,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%d/%m/%Y") if self.created_at else None
        }


class NotificationAlert(Base):
    """
    Central alerts/notifications for topbar bell and alerts list
    """
    __tablename__ = 'notification_alerts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey('alert_rules.id'), nullable=True)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    module = Column(String(50), default="Warehouse") # Procurement, QC, Production, Warehouse
    severity = Column(String(20), default="WARNING") # INFO, WARNING, CRITICAL
    is_read = Column(Boolean, default=False)
    reference_type = Column(String(50), nullable=True) # lot, batch, inventory, dispatch
    reference_id = Column(String(50), nullable=True) # e.g. LOT-2026-089 or RAW-LOT-512
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    rule = relationship("AlertRule", back_populates="notifications")

    def to_dict(self):
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "title": self.title,
            "message": self.message,
            "module": self.module,
            "severity": self.severity,
            "is_read": self.is_read,
            "reference_type": self.reference_type,
            "reference_id": self.reference_id,
            "created_at": self.created_at.strftime("%d/%m/%Y %H:%M") if self.created_at else None
        }
