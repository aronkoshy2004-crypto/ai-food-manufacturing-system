"""
Database initialization and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from config import Config

Base = declarative_base()

_engine = None
_session_factory = None
db_session = None

def init_db(app=None):
    global _engine, _session_factory, db_session
    
    db_uri = Config.SQLALCHEMY_DATABASE_URI
    if app and 'SQLALCHEMY_DATABASE_URI' in app.config:
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']

    connect_args = {}
    if db_uri.startswith('sqlite'):
        connect_args = {'check_same_thread': False}

    _engine = create_engine(db_uri, connect_args=connect_args, pool_pre_ping=True)
    _session_factory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    db_session = scoped_session(_session_factory)

    # Import all models to register schema tables
    from models.user import User
    from models.schema_draft import (
        RawMaterialLot,
        QCInspection,
        ProductionBatch,
        WarehouseItem,
        DispatchOrder
    )
    import models.procurement
    import models.qc
    import models.production
    import models.warehouse

    Base.metadata.create_all(bind=_engine)

    if app:
        @app.teardown_appcontext
        def shutdown_session(exception=None):
            db_session.remove()

    return db_session

def get_db():
    return db_session
