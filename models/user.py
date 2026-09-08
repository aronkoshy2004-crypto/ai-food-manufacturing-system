"""
User Model with Role-Based Authentication
"""
import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from werkzeug.security import generate_password_hash, check_password_hash
from models import Base
from models.enums import RoleEnum

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False, default=RoleEnum.PRODUCTION.value)
    avatar_initials = Column(String(10), default="FM")
    department = Column(String(100), default="Vận hành")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def has_role(self, *roles) -> bool:
        if not roles:
            return True
        allowed_roles = [r.value if isinstance(r, RoleEnum) else str(r) for r in roles]
        return self.role in allowed_roles or self.role == RoleEnum.ADMIN.value

    def is_admin(self) -> bool:
        return self.role == RoleEnum.ADMIN.value

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "avatar_initials": self.avatar_initials,
            "department": self.department,
            "is_active": self.is_active
        }

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
