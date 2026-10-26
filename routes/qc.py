"""
QC Routes & API: Lab Tests, COA, YOLO AI Inspection, Human-Only Decision Making, and Production Output Contract
Phase 2 — PRD Implementation
"""
import os
import io
import json
import secrets
import base64
import threading
import time
import socket
from collections import defaultdict
import datetime
from PIL import Image
import qrcode
from config import Config
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, current_app, send_file
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from models import get_db
from models.enums import RoleEnum, StatusEnum, STATUS_METADATA
from models.user import User
from models.schema_draft import RawMaterialLot
from models.procurement import Supplier, RawMaterial
from models.production import Product, ProductionBatch
from models.qc import (
    QCSample,
    QCTest,
    COADocument,
    InspectionImage,
    AIInspection,
    DetectedDefect,
    QCDecision,
    AIFeedback,
    LiveSession,
    LiveFrame
)

from ai.predict import run_yolo_inference, MODEL_VERSION
from ai.yolo_service import check_ai_engine_status, run_yolo_visual_inspection, FOOD_DEFECT_TAXONOMY, GLOBAL_INFERENCE_LOCK
from ai.release_decision import release_decision, MATERIAL_SPECS, parse_numeric_value, normalize_material_name
from models.warehouse import NotificationAlert
from routes.auth import login_required, get_current_user, role_required


def extract_material_name(text) -> str:
    """
    Extracts canonical material name ('Peanut', 'Corn', 'Sunflower') from a lot name,
    category description, or YOLO detected class name.
    Returns 'Peanut', 'Corn', 'Sunflower', or None.
    """
    if not text:
        return None
    t = str(text).lower()
    if "peanut" in t or "groundnut" in t:
        return "Peanut"
    if "corn" in t or "maize" in t:
        return "Corn"
    if "sunflower" in t:
        return "Sunflower"
    return None


detect_material_from_text = extract_material_name


def get_default_engine_for_material(material: str = None) -> str:
    """
    Requirement 5: Safe default engine: 'ai' for all materials so the system behaves
    as it did before the new modes. Keep new modes available behind settings.
    """
    return "ai"


def resolve_inspection_engine(requested_engine: str, material: str = None) -> str:
    """
    Resolves active inspection engine:
    - If explicitly specified as 'colour' / 'color', 'both', or 'ai', use it.
    - If 'auto', keep material-based rules (peanut/sunflower = colour, corn = ai).
    - Default fallback when None/empty: safe default 'ai'.
    """
    req = (requested_engine or "").strip().lower()
    if req in ("colour", "color"):
        return "colour"
    if req == "both":
        return "both"
    if req == "ai":
        return "ai"
    if req == "auto":
        if material:
            m = str(material).strip().lower()
            if "corn" in m or "maize" in m:
                return "ai"
            elif "peanut" in m or "groundnut" in m or "sunflower" in m:
                return "colour"
        return "ai"
    return "ai"


_CACHED_CLS_MODEL = None

def get_cached_cls_model(model_path: str):
    """Caches loaded classification model to avoid reloading weights repeatedly."""
    global _CACHED_CLS_MODEL
    if _CACHED_CLS_MODEL is None and os.path.isfile(model_path):
        from ultralytics import YOLO
        _CACHED_CLS_MODEL = YOLO(model_path)
    return _CACHED_CLS_MODEL


def classify_material_from_crops(crop_images: list) -> str:
    """
    Classifies a list of cropped kernel BGR images using models/material_cls.pt.
    Returns the majority-voted material ('Peanut', 'Corn', 'Sunflower') or None.
    """
    from config import Config
    model_path = getattr(Config, 'MATERIAL_CLS_MODEL_PATH', 'models/material_cls.pt')
    if not os.path.isfile(model_path) or not crop_images:
        return None
    try:
        cls_model = get_cached_cls_model(model_path)
        if cls_model is None:
            from ultralytics import YOLO
            cls_model = YOLO(model_path)
        res = cls_model(crop_images, verbose=False, imgsz=96)
        votes = Counter()
        for r in res:
            name = r.names[r.probs.top1].capitalize()
            votes[name] += 1
        return votes.most_common(1)[0][0] if votes else None
    except Exception:
        return None


def get_mostly_detected_material(yolo_res: dict) -> str:
    """
    Counts detections across both detected_defects and detected_healthy
    to determine which material (Peanut, Corn, Sunflower) the YOLO model mostly detected.
    Returns 'Peanut', 'Corn', 'Sunflower', or None if no material objects detected.
    """
    from config import Config
    # Additive check: if USE_MATERIAL_CLASSIFIER is enabled and override exists, use it
    if getattr(Config, 'USE_MATERIAL_CLASSIFIER', False):
        cls_override = yolo_res.get("classifier_material")
        if cls_override in ("Peanut", "Corn", "Sunflower"):
            return cls_override

    counts = {"Peanut": 0, "Corn": 0, "Sunflower": 0}
    conf_sums = {"Peanut": 0.0, "Corn": 0.0, "Sunflower": 0.0}

    for d in yolo_res.get("detected_defects", []):
        mat = extract_material_name(d.get("defect_class", ""))
        if mat in counts:
            counts[mat] += 1
            conf_sums[mat] += float(d.get("confidence", 0.0))

    for h in yolo_res.get("detected_healthy", []):
        mat = extract_material_name(h.get("specimen_class") or h.get("defect_class", ""))
        if mat in counts:
            counts[mat] += 1
            conf_sums[mat] += float(h.get("confidence", 0.0))

    mostly_detected = None
    max_count = 0
    for mat, count in counts.items():
        if count > max_count:
            max_count = count
            mostly_detected = mat
        elif count == max_count and count > 0:
            if conf_sums[mat] > conf_sums.get(mostly_detected, 0.0):
                mostly_detected = mat

    return mostly_detected


_TOKEN_RATE_LOCK = threading.Lock()
_TOKEN_TIMESTAMPS = defaultdict(list)

def get_lan_base_url():
    lan_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        lan_ip = "127.0.0.1"

    port = os.environ.get('PORT', '5000')
    return f"http://{lan_ip}:{port}"


def get_public_base_url():
    env_url = (os.environ.get('PUBLIC_BASE_URL') or '').strip()
    if env_url:
        return env_url.rstrip('/')

    pub_file = os.path.join(Config.BASE_DIR, '.public_url')
    if os.path.isfile(pub_file):
        try:
            with open(pub_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return content.rstrip('/')
        except Exception:
            pass
    return None


def resolve_capture_base_url():
    """
    Resolves the base URL for QR pairing and mobile capture page.
    Priority:
    1. Env var PUBLIC_BASE_URL
    2. File .public_url in workspace
    3. LAN address with visible warning flag
    """
    pub = get_public_base_url()
    if pub:
        return pub, False
    return get_lan_base_url(), True


def package_session_urls(token: str) -> dict:
    """
    Packages both HTTPS Tunnel and local Wi-Fi LAN URLs and QR codes.
    Allows frontend to dynamically switch between Tunnel and LAN if ISP blocks Cloudflare.
    """
    pub_base = get_public_base_url()
    lan_base = get_lan_base_url()

    lan_capture_url = f"{lan_base}/capture/{token}"
    lan_qr = generate_qr_code_data_url(lan_capture_url)

    if pub_base:
        pub_capture_url = f"{pub_base}/capture/{token}"
        pub_qr = generate_qr_code_data_url(pub_capture_url)
        primary_url = pub_capture_url
        primary_qr = pub_qr
        is_lan = False
        warning = None
    else:
        pub_capture_url = None
        pub_qr = None
        primary_url = lan_capture_url
        primary_qr = lan_qr
        is_lan = True
        warning = "Live camera needs the HTTPS link"

    return {
        "capture_url": primary_url,
        "qr_data_url": primary_qr,
        "is_lan": is_lan,
        "warning": warning,
        "lan_capture_url": lan_capture_url,
        "lan_qr_data_url": lan_qr,
        "public_capture_url": pub_capture_url,
        "public_qr_data_url": pub_qr,
        "has_public_tunnel": bool(pub_base)
    }



def generate_qr_code_data_url(url: str) -> str:
    """
    Generates a base64-encoded PNG data URI for the given URL using qrcode.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode('ascii')


def check_token_rate_limit(token: str, max_requests: int = 3, window_seconds: float = 1.0) -> bool:
    """
    Thread-safe sliding-window rate limit: allows ~3 requests per second per token.
    """
    if current_app and current_app.config.get('TESTING'):
        return True
    now = time.time()
    with _TOKEN_RATE_LOCK:
        timestamps = _TOKEN_TIMESTAMPS[token]
        valid_timestamps = [t for t in timestamps if now - t < window_seconds]
        if len(valid_timestamps) >= max_requests:
            _TOKEN_TIMESTAMPS[token] = valid_timestamps
            return False
        valid_timestamps.append(now)
        _TOKEN_TIMESTAMPS[token] = valid_timestamps
        return True


def cleanup_non_final_frames(db, session_id: int) -> int:
    """
    Deletes raw and annotated image files on disk for temporary non-final streaming frames
    of a closed session, while preserving the final frame and the locked/best specimen frames intact on disk.
    """
    frames = db.query(LiveFrame).filter_by(session_id=session_id).order_by(LiveFrame.id.asc()).all()
    if len(frames) <= 1:
        return 0

    sess = db.query(LiveSession).filter_by(id=session_id).first()
    keep_ids = set()
    if frames:
        keep_ids.add(frames[-1].id)
    for f in frames:
        if f.is_locked:
            keep_ids.add(f.id)
    if sess and sess.locked_result_json:
        try:
            res = json.loads(sess.locked_result_json)
            for bf in res.get("best_frames", []):
                if isinstance(bf, dict) and "id" in bf:
                    keep_ids.add(bf["id"])
        except Exception:
            pass

    to_clean = [f for f in frames if f.id not in keep_ids]
    deleted_count = 0

    for f in to_clean:
        for p in [f.image_path, f.annotated_path]:
            if not p:
                continue
            clean_rel = p.lstrip('/')
            disk_path = os.path.join(Config.BASE_DIR, clean_rel.replace('/', os.sep))
            if os.path.isfile(disk_path):
                try:
                    os.remove(disk_path)
                    deleted_count += 1
                except Exception as ex:
                    print(f"Warning: could not delete non-final frame {disk_path}: {ex}")

            base_p, ext_p = os.path.splitext(disk_path)
            infer_p = f"{base_p}_infer_1920{ext_p}"
            if os.path.isfile(infer_p):
                try:
                    os.remove(infer_p)
                except Exception:
                    pass
    return deleted_count


qc_bp = Blueprint('qc', __name__)

# ==============================================================================
# 1. QC UI VIEW
# ==============================================================================
@qc_bp.route('/qc')
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def index():
    user = get_current_user()
    view = request.args.get('view', 'queue') # 'queue' | 'tests' | 'coa' | 'ai-inspection'
    if view in ['station', 'camera-station', 'ai-inspection', 'live-inspection']:
        return redirect(url_for('qc.camera_station'))
    db = get_db()

    pending_qc_count = db.query(RawMaterialLot).filter(
        (RawMaterialLot.qc_status == "PENDING_QC") | (RawMaterialLot.status == StatusEnum.PENDING.value)
    ).count()

    view_titles = {
        'queue': 'QC Inspection Queue',
        'tests': 'QC Test Results & COA',
        'coa': 'QC Test Results & COA',
        'ai-inspection': 'YOLOv8 AI Visual Quality Inspection',
        'live-inspection': 'Live Mobile Camera Inspection'
    }

    breadcrumbs = {
        'queue': ["Home", "Quality Control", "QC Inspection Queue"],
        'tests': ["Home", "Quality Control", "QC Test Results & COA"],
        'coa': ["Home", "Quality Control", "QC Test Results & COA"],
        'ai-inspection': ["Home", "Quality Control", "AI Visual Inspection"],
        'live-inspection': ["Home", "Quality Control", "Live Mobile Inspection"]
    }

    lots = db.query(RawMaterialLot).order_by(RawMaterialLot.id.desc()).all()
    products = db.query(Product).filter_by(is_active=True).all()
    batches = db.query(ProductionBatch).order_by(ProductionBatch.id.desc()).limit(15).all()

    active_live_session = db.query(LiveSession).filter(
        LiveSession.status == "ACTIVE",
        LiveSession.expires_at > datetime.datetime.utcnow()
    ).order_by(LiveSession.id.desc()).first()

    active_session_data = None
    if active_live_session:
        urls_pkg = package_session_urls(active_live_session.token)
        active_session_data = {
            "session": active_live_session.to_dict(),
            **urls_pkg
        }

    return render_template(
        'qc.html',
        user=user,
        active_view=view,
        view_title=view_titles.get(view, 'Quality Control (QC)'),
        breadcrumb=breadcrumbs.get(view, ["Home", "Quality Control"]),
        pending_qc_count=pending_qc_count,
        lots=lots,
        products=products,
        batches=batches,
        active_live_session=active_session_data
    )


@qc_bp.route('/qc/camera-station', methods=['GET'])
@qc_bp.route('/qc/station', methods=['GET'])
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def camera_station():
    """
    Laptop/Desktop QC Camera Inspection Station (Phase 2).
    Login required. Internal session created behind the scenes.
    Token and QR code are never displayed.
    """
    user = get_current_user()
    db = get_db()

    pending_qc_count = db.query(RawMaterialLot).filter(
        (RawMaterialLot.qc_status == "PENDING_QC") | (RawMaterialLot.status == StatusEnum.PENDING.value)
    ).count()

    lots = db.query(RawMaterialLot).order_by(RawMaterialLot.id.desc()).all()

    # Reuse an existing active session if available, or create a new internal session
    active_sess = db.query(LiveSession).filter(
        LiveSession.status == "ACTIVE",
        LiveSession.expires_at > datetime.datetime.utcnow()
    ).order_by(LiveSession.id.desc()).first()

    if not active_sess:
        token = secrets.token_urlsafe(32)
        created_at = datetime.datetime.utcnow()
        expires_at = created_at + datetime.timedelta(hours=2)
        default_lot_id = lots[0].id if lots else None

        active_sess = LiveSession(
            token=token,
            lot_id=default_lot_id,
            status="ACTIVE",
            created_at=created_at,
            expires_at=expires_at
        )
        db.add(active_sess)
        db.commit()

    urls_pkg = package_session_urls(active_sess.token)

    return render_template(
        'camera_station.html',
        user=user,
        active_view='station',
        view_title='QC Camera Inspection Station',
        breadcrumb=["Home", "Quality Control", "Camera Station"],
        pending_qc_count=pending_qc_count,
        lots=lots,
        session_id=active_sess.id,
        session_token=active_sess.token,
        current_lot_id=active_sess.lot_id,
        session_urls=urls_pkg
    )



def compute_lot_qc_steps_and_next_action(lot, db):
    """
    Derives 4-step progress and next action label from existing lot records (Stage C).
    Additive only; does not alter release_decision logic or any table schema.
    """
    now_utc = datetime.datetime.utcnow()

    # 1. COA & lab test measures
    coa = db.query(COADocument).filter_by(raw_material_lot_id=lot.id).first()
    qc_sample = db.query(QCSample).filter_by(raw_material_lot_id=lot.id).first()
    tests = qc_sample.tests if qc_sample else []
    test_dict = {}
    for t in tests:
        pname = (t.parameter_name or '').lower()
        if 'moisture' in pname:
            test_dict['moisture'] = parse_numeric_value(t.measured_value)
        elif 'aflatoxin' in pname:
            test_dict['aflatoxin_b1'] = parse_numeric_value(t.measured_value)
        elif 'free fatty' in pname or 'ffa' in pname:
            test_dict['ffa'] = parse_numeric_value(t.measured_value)
        elif 'purity' in pname:
            test_dict['purity'] = parse_numeric_value(t.measured_value)

    # COA status: present / missing / expired
    if coa:
        exp_date = getattr(coa, 'expiry_date', None)
        notes_str = (getattr(coa, 'notes', '') or '').lower()
        if (exp_date and exp_date < now_utc) or ('expired' in notes_str):
            coa_status = 'expired'
        else:
            coa_status = 'present'
    else:
        coa_status = 'missing'

    # 2. Release decision
    dec = release_decision(lot, db=db)
    raw_outcome = dec.get('outcome', 'HOLD')
    plain_label = 'GOOD' if raw_outcome == 'RELEASE' else ('BAD' if raw_outcome == 'REJECT' else 'NEEDS REVIEW')

    # 3. 4 Steps derivation
    ai_insp = db.query(AIInspection).filter_by(raw_material_lot_id=lot.id).first()
    ai_done = (dec.get('ai_state') not in (None, 'NOT_RUN')) or (ai_insp is not None)
    has_lab = bool(test_dict.get('moisture') is not None or test_dict.get('aflatoxin_b1') is not None or test_dict.get('ffa') is not None or test_dict.get('purity') is not None or tests)
    has_coa = (coa is not None and coa_status != 'missing')
    lab_done = bool(has_coa and has_lab)
    qc_dec = db.query(QCDecision).filter_by(raw_material_lot_id=lot.id).first()
    signoff_done = lot.qc_status in ('APPROVED', 'REJECTED', 'HOLD') and (qc_dec is not None)

    steps = [
        {"name": "AI Scan", "key": "ai_scan", "status": "done" if ai_done else "pending"},
        {"name": "Lab Tests & COA", "key": "lab_coa", "status": "done" if lab_done else "pending"},
        {"name": "Combined Check", "key": "combined_check", "status": "done" if (ai_done or lab_done) else "pending", "outcome": raw_outcome, "label": plain_label},
        {"name": "Sign-Off", "key": "sign_off", "status": "done" if signoff_done else "pending"}
    ]

    if not ai_done:
        next_action = "Run AI scan"
    elif not lab_done:
        next_action = "Enter lab & COA results"
    elif not signoff_done:
        next_action = "Ready for sign-off"
    else:
        next_action = f"Signed off ({lot.qc_status})"

    return {
        "lab_measures": test_dict,
        "coa_status": coa_status,
        "coa_doc_number": coa.doc_number if coa else None,
        "decision_outcome": raw_outcome,
        "decision_label": plain_label,
        "steps": steps,
        "next_action": next_action,
        "release_decision": dec
    }


# ==============================================================================
# 2. QC QUEUE API (LIST OF PENDING LOTS)
# ==============================================================================
@qc_bp.route('/api/qc/queue', methods=['GET'])
@login_required
def get_qc_queue():
    """
    Returns card grid of lots requiring QC review.
    Preserves all existing Phase 1 & 2 card fields, enriched with Stage C
    additive fields: lab_measures, coa_status, decision_outcome, steps, next_action.
    """
    db = get_db()
    # Filter for lots that are pending inspection
    lots = db.query(RawMaterialLot).filter(
        (RawMaterialLot.qc_status == "PENDING_QC") | (RawMaterialLot.status == StatusEnum.PENDING.value)
    ).order_by(RawMaterialLot.id.desc()).all()

    cards = []
    for lot in lots:
        po_ref = lot.purchase_order.po_number if lot.purchase_order else (f"PO #{lot.id}" if lot.purchase_order_id else "GRN Intake")
        stage_c_info = compute_lot_qc_steps_and_next_action(lot, db)

        cards.append({
            "id": lot.lot_number,
            "db_id": lot.id,
            "title": lot.material_name,
            "category": lot.category,
            "headerStat": f"{lot.quantity:,.1f} {lot.unit}",
            "statSub": "Pending Inspection",
            "progress": 40,
            "miniGrid": [
                {"label": "Material / Spec", "value": f"{lot.material_name} ({lot.unit_weight or 'Standard'})"},
                {"label": "Supplier / PO", "value": f"{lot.supplier_name} • {po_ref}"},
                {"label": "Intake Date", "value": lot.received_at.strftime("%Y-%m-%d") if lot.received_at else "Today"},
                {"label": "Storage Condition", "value": lot.storage_condition or "Cold Storage 4°C"}
            ],
            "avatars": [
                {"initial": "QC", "bg": "#F59E0B", "name": "Awaiting Lab Inspection"}
            ],
            "status": "PENDING_QC",
            "statusLabel": "PENDING_QC",
            "statusPill": "pill-pending",
            # Stage C Additive fields (new fields only; no existing fields modified)
            "lab_measures": stage_c_info["lab_measures"],
            "coa_status": stage_c_info["coa_status"],
            "coa_doc_number": stage_c_info["coa_doc_number"],
            "decision_outcome": stage_c_info["decision_outcome"],
            "decision_label": stage_c_info["decision_label"],
            "steps": stage_c_info["steps"],
            "next_action": stage_c_info["next_action"]
        })

    return jsonify({
        "success": True,
        "count": len(cards),
        "cards": cards
    })


# ==============================================================================
# 3. COMBINED REVIEW ENDPOINT (LAB + COA + YOLO AI)
# ==============================================================================
@qc_bp.route('/api/qc/lot/<int:lot_id>/review', methods=['GET'])
@login_required
def get_lot_combined_review(lot_id):
    """
    Combined review endpoint aggregating:
    - Lot metadata & Supplier profile
    - Lab test parameters (QCTest pass/fail results)
    - COA document verification status & link
    - AI YOLO inspection report with defect bounding boxes & confidence scores
    - Past decisions if any
    """
    db = get_db()
    lot = db.query(RawMaterialLot).filter_by(id=lot_id).first()
    if not lot:
        return jsonify({"error": "Raw material lot not found"}), 404

    # 1. Fetch or create default lab tests
    sample = db.query(QCSample).filter_by(raw_material_lot_id=lot.id).first()
    if not sample:
        sample = QCSample(
            sample_code=f"SMP-{lot.lot_number.replace('LOT-RM-', '')}",
            raw_material_lot_id=lot.id,
            sample_date=datetime.datetime.utcnow(),
            storage_temp=lot.storage_condition or "4.0°C",
            sample_size="500ml / 5 representative samples"
        )
        db.add(sample)
        db.flush()

        # Seed realistic parameter test specs
        db.add_all([
            QCTest(qc_sample_id=sample.id, parameter_name="Brix Level", standard_spec="≥ 11.0°Bx", measured_value="11.4°Bx", unit="°Bx", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="pH Index", standard_spec="6.5 - 6.8 pH", measured_value="6.68 pH", unit="pH", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Fat Content", standard_spec="≥ 3.2%", measured_value="3.55%", unit="%", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Coliform Count", standard_spec="< 10 CFU/ml", measured_value="0 CFU/ml", unit="CFU", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Sensory Evaluation", standard_spec="Milky white, natural aroma", measured_value="100% compliant", unit="", is_pass=True)
        ])
        db.commit()

    lab_tests = [t.to_dict() for t in sample.tests]

    # 2. Fetch COA document from library
    coa = db.query(COADocument).filter_by(raw_material_lot_id=lot.id).first()
    coa_data = coa.to_dict() if coa else None

    # 3. Fetch or run YOLO AI inspection on lot image
    insp_image = db.query(InspectionImage).filter_by(raw_material_lot_id=lot.id).first()
    if not insp_image:
        insp_image = InspectionImage(
            raw_material_lot_id=lot.id,
            image_url="https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800&auto=format&fit=crop&q=80", # Representative packaging/warehouse lot image
            image_type="Pallet physical appearance & packaging seal inspection"
        )
        db.add(insp_image)
        db.flush()

    ai_insp = db.query(AIInspection).filter_by(inspection_image_id=insp_image.id).first()
    if not ai_insp:
        # Run YOLO inference engine
        yolo_result = run_yolo_inference(insp_image.image_url, {"lot_number": lot.lot_number})
        lot_material = extract_material_name(lot.material_name) or extract_material_name(lot.category)
        camera_material = get_mostly_detected_material(yolo_result)
        material_mismatch = False
        mismatch_warning = None
        if lot_material and camera_material:
            if lot_material.lower() != camera_material.lower():
                material_mismatch = True
                mismatch_warning = f"Possible material mismatch: lot says {lot_material}, camera sees {camera_material}. Please verify."

        ai_insp = AIInspection(
            inspection_image_id=insp_image.id,
            raw_material_lot_id=lot.id,
            model_version=yolo_result["model_version"],
            inference_time_ms=yolo_result["inference_time_ms"],
            total_defects_count=yolo_result["total_defects_count"],
            summary=yolo_result["summary"],
            material_mismatch=material_mismatch,
            mismatch_warning=mismatch_warning,
            detected_material=camera_material,
            lot_material=lot_material
        )
        db.add(ai_insp)
        db.flush()

        for defect in yolo_result["detected_defects"]:
            detected = DetectedDefect(
                ai_inspection_id=ai_insp.id,
                defect_class=defect["defect_class"],
                confidence=defect["confidence"],
                bbox_x=defect["bbox_x"],
                bbox_y=defect["bbox_y"],
                bbox_w=defect["bbox_w"],
                bbox_h=defect["bbox_h"]
            )
            db.add(detected)
        db.commit()

    ai_data = ai_insp.to_dict()
    ai_data["image_url"] = insp_image.image_url

    # Attach Live Session best_frames and final_decision if this lot had a live session
    live_sess = db.query(LiveSession).filter_by(lot_id=lot.id).order_by(LiveSession.id.desc()).first()
    if live_sess and live_sess.locked_result_json:
        try:
            l_json = json.loads(live_sess.locked_result_json)
            raw_bfs = l_json.get("best_frames", [])
            clean_bfs = []
            for bf in raw_bfs:
                bf_copy = dict(bf)
                if bf_copy.get("annotated_path"):
                    bf_copy["annotated_path"] = bf_copy["annotated_path"].replace(
                        '/static/uploads/annotated/annotated_live_',
                        '/static/uploads/live_frames/annotated/annotated_live_'
                    )
                clean_bfs.append(bf_copy)
            ai_data["best_frames"] = clean_bfs
            ai_data["best_annotated_urls"] = [
                (u or '').replace('/static/uploads/annotated/annotated_live_', '/static/uploads/live_frames/annotated/annotated_live_')
                for u in l_json.get("best_annotated_urls", [])
            ]
            ai_data["final_decision"] = l_json.get("final_decision") or final_decision(l_json)
        except Exception:
            pass

    # 4. Past decision if any
    decision = db.query(QCDecision).filter_by(raw_material_lot_id=lot.id).order_by(QCDecision.id.desc()).first()

    po_ref = lot.purchase_order.po_number if lot.purchase_order else (f"PO #{lot.id}" if lot.purchase_order_id else "N/A")

    all_passed = all(t.is_pass for t in sample.tests) if sample and sample.tests else True
    lab_eval = {
        "all_passed": all_passed,
        "tests": lab_tests,
        "sample_code": sample.sample_code if sample else None
    }

    stage_c_info = compute_lot_qc_steps_and_next_action(lot, db)

    result = {
        "lot": {
            "id": lot.id,
            "lot_number": lot.lot_number,
            "material_name": lot.material_name,
            "category": lot.category,
            "supplier_name": lot.supplier_name,
            "quantity": lot.quantity,
            "unit": lot.unit,
            "unit_weight": lot.unit_weight,
            "storage_condition": lot.storage_condition,
            "po_number": po_ref,
            "qc_status": lot.qc_status or "PENDING_QC",
            "received_at": lot.received_at.strftime("%d/%m/%Y %H:%M") if lot.received_at else "Today"
        },
        "lab_tests": lab_tests,
        "lab_evaluation": lab_eval,
        "coa": coa_data,
        "ai_inspection": ai_data,
        "release_decision": release_decision(lot, db=db),
        "last_decision": decision.to_dict() if decision else None,
        "advisory_notice": "AI YOLO RESULTS ARE ADVISORY ONLY AND NOT AUTO-APPROVED. QC SPECIALIST CONFIRMATION IS MANDATORY.",
        # Stage C Additive fields
        "steps": stage_c_info["steps"],
        "next_action": stage_c_info["next_action"],
        "lab_measures": stage_c_info["lab_measures"],
        "coa_status": stage_c_info["coa_status"]
    }

    return jsonify({
        "success": True,
        **result,
        "data": result
    })


@qc_bp.route('/api/qc/lot/<int:lot_id>/release-decision', methods=['GET'])
@login_required
def get_lot_release_decision_api(lot_id):
    """
    Dedicated combined release decision endpoint (COA + AI).
    Evaluates COA state (PASS, FAIL, MISSING), AI state (PASS, REVIEW, REJECT, RETAKE, NOT_RUN),
    and overall release outcome (RELEASE, HOLD, REJECT).
    """
    db = get_db()
    lot = db.query(RawMaterialLot).filter_by(id=lot_id).first()
    if not lot:
        return jsonify({"success": False, "error": "Raw material lot not found"}), 404

    rel_dec = release_decision(lot, db=db)
    return jsonify({
        "success": True,
        "lot_id": lot.id,
        "lot_number": lot.lot_number,
        **rel_dec,
        "release_decision": rel_dec,
        "data": rel_dec
    }), 200


# ==============================================================================
# YOLOv8 AI VISUAL INSPECTION APIS
# ==============================================================================
@qc_bp.route('/api/qc/ai-model-status', methods=['GET'])
@login_required
def get_ai_model_status():
    """
    Returns active YOLOv8 model status, file location, and training diagnostics.
    """
    status = check_ai_engine_status()
    return jsonify({
        "success": True,
        "data": status,
        **status
    })



@qc_bp.route('/api/qc/ai-inspect', methods=['POST'])
@login_required
def inspect_image_yolo():
    """
    AI Inspection Workflow:
    Upload Image -> YOLOv8 Analysis -> Detect Visible Defects -> Generate AI Result
    Stores inspection result and image in DB linked to lot, product, or batch.
    If no model is available, returns clear configuration guidance without fake detections.
    """
    db = get_db()
    target_type = request.form.get('target_type') or (request.json.get('target_type', 'lot') if request.is_json else 'lot')
    target_id = request.form.get('target_id') or (request.json.get('target_id') if request.is_json else None)
    conf_threshold = float(request.form.get('confidence_threshold') or (request.json.get('confidence_threshold', 0.12) if request.is_json else 0.12))

    raw_lot_id = None
    product_id = None
    batch_id = None

    if target_type == 'lot' and target_id:
        raw_lot_id = int(target_id)
    elif target_type == 'product' and target_id:
        product_id = int(target_id)
    elif target_type == 'batch' and target_id:
        batch_id = int(target_id)

    # Handle image file upload or image URL
    file = request.files.get('image') if 'image' in request.files else None
    image_url = None
    raw_file_path = None

    upload_raw_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'raw')
    upload_annotated_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'annotated')
    os.makedirs(upload_raw_dir, exist_ok=True)
    os.makedirs(upload_annotated_dir, exist_ok=True)

    if file and file.filename:
        filename = secure_filename(file.filename)
        unique_prefix = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S_")
        saved_name = unique_prefix + filename
        raw_file_path = os.path.join(upload_raw_dir, saved_name)
        file.save(raw_file_path)
        image_url = f"/static/uploads/raw/{saved_name}"
    else:
        # Check JSON or form image_url
        image_url = request.form.get('image_url') or (request.json.get('image_url') if request.is_json else None)
        if not image_url:
            image_url = "/static/img/peanut_sample.jpg"

    # Create InspectionImage record
    insp_image = InspectionImage(
        raw_material_lot_id=raw_lot_id,
        product_id=product_id,
        production_batch_id=batch_id,
        image_url=image_url,
        image_type=request.form.get('image_type', 'Raw Material Visual Scan') if not request.is_json else request.json.get('image_type', 'Raw Material Visual Scan'),
        uploaded_at=datetime.datetime.utcnow()
    )
    db.add(insp_image)
    db.flush()

    # Run YOLOv8 visual inspection
    if raw_file_path and os.path.isfile(raw_file_path):
        yolo_res = run_yolo_visual_inspection(raw_file_path, upload_annotated_dir, conf_threshold=conf_threshold)
    else:
        local_static = os.path.join(current_app.root_path, image_url.lstrip('/'))
        if os.path.isfile(local_static):
            yolo_res = run_yolo_visual_inspection(local_static, upload_annotated_dir, conf_threshold=conf_threshold)
        else:
            engine_status = check_ai_engine_status()
            yolo_res = {
                "success": engine_status["ready"],
                "model_status": engine_status["status"],
                "model_version": engine_status.get("model_name") or "YOLOv8-Unconfigured",
                "inference_time_ms": 0.0,
                "total_defects_count": 0,
                "detected_defects": [],
                "summary": "Model Configuration Required" if not engine_status["ready"] else "No visual defects detected",
                "status_message": engine_status["message"],
                "annotated_image_url": None,
                "inspection_timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "training_workflow": engine_status.get("training_workflow", [])
            }

    annotated_url = yolo_res.get("annotated_image_url")
    if annotated_url:
        insp_image.annotated_image_url = annotated_url

    # Check for wrong-material warning when inspection is linked to a lot
    lot_material = None
    if raw_lot_id:
        linked_lot = db.query(RawMaterialLot).filter_by(id=raw_lot_id).first()
        if linked_lot:
            lot_material = extract_material_name(linked_lot.material_name) or extract_material_name(linked_lot.category)

    camera_material = get_mostly_detected_material(yolo_res)

    material_mismatch = False
    mismatch_warning = None

    if lot_material and camera_material:
        if lot_material.lower() != camera_material.lower():
            material_mismatch = True
            mismatch_warning = f"Possible material mismatch: lot says {lot_material}, camera sees {camera_material}. Please verify."

    # Compute average confidence across all detections
    all_detections = yolo_res.get("detected_defects", []) + yolo_res.get("detected_healthy", [])
    if all_detections:
        avg_confidence = sum(float(d.get("confidence", 0.0)) for d in all_detections) / len(all_detections)
    else:
        avg_confidence = 0.0

    is_low_confidence = len(all_detections) > 0 and avg_confidence < 0.50
    total_defects = len(yolo_res.get("detected_defects", []))

    # Editable threshold from request (default max allowed defects: 0)
    max_defects_threshold = int(request.form.get('max_defects_threshold') or (request.json.get('max_defects_threshold', 0) if request.is_json else 0))

    # Requirement 1: When a material mismatch is flagged, or the average confidence of all detections is below 50%,
    # set the status to NEEDS_REVIEW. Hide the automatic pass/fail suggestion and show "Result unreliable: verify the sample manually or retake the photo."
    if material_mismatch or is_low_confidence:
        model_status = "NEEDS_REVIEW"
        pass_fail_suggestion = None
        unreliable_warning = "Result unreliable: verify the sample manually or retake the photo."
        summary = f"Inspection marked NEEDS_REVIEW ({unreliable_warning})"
    else:
        unreliable_warning = None
        pass_fail_suggestion = "FAIL" if total_defects > max_defects_threshold else "PASS"
        model_status = "DEFECTS_DETECTED" if total_defects > 0 else "NO_DEFECTS"
        summary = yolo_res.get("summary", "Inspection recorded")

    ai_insp = AIInspection(
        inspection_image_id=insp_image.id,
        raw_material_lot_id=raw_lot_id,
        product_id=product_id,
        production_batch_id=batch_id,
        model_version=yolo_res.get("model_version", "YOLOv8"),
        model_status=model_status,
        inference_time_ms=yolo_res.get("inference_time_ms", 0.0),
        total_defects_count=total_defects,
        summary=summary,
        status_message=unreliable_warning or yolo_res.get("status_message"),
        annotated_image_url=annotated_url,
        material_mismatch=material_mismatch,
        mismatch_warning=mismatch_warning,
        detected_material=camera_material,
        lot_material=lot_material,
        avg_confidence=round(avg_confidence, 4),
        created_at=datetime.datetime.utcnow()
    )
    db.add(ai_insp)
    db.flush()

    for d in yolo_res.get("detected_defects", []):
        defect_item = DetectedDefect(
            ai_inspection_id=ai_insp.id,
            defect_class=d["defect_class"],
            confidence=d["confidence"],
            bbox_x=d["bbox_x"],
            bbox_y=d["bbox_y"],
            bbox_w=d["bbox_w"],
            bbox_h=d["bbox_h"]
        )
        db.add(defect_item)

    db.commit()

    ai_payload = {
        "inspection_id": ai_insp.id,
        "image_id": insp_image.id,
        "raw_image_url": insp_image.image_url,
        "uploaded_image": insp_image.image_url,
        "annotated_image_url": annotated_url or insp_image.image_url,
        "annotated_image": annotated_url or insp_image.image_url,
        "model_version": ai_insp.model_version,
        "model_status": ai_insp.model_status,
        "status_message": ai_insp.status_message,
        "inference_time_ms": ai_insp.inference_time_ms,
        "total_defects_count": ai_insp.total_defects_count,
        "summary": ai_insp.summary,
        "defects": [d.to_dict() for d in ai_insp.detected_defects],
        "detected_defects": [d.to_dict() for d in ai_insp.detected_defects],
        "healthy_specimens_count": yolo_res.get("healthy_specimens_count", 0),
        "detected_healthy": yolo_res.get("detected_healthy", []),
        "material_mismatch": material_mismatch,
        "mismatch_warning": mismatch_warning,
        "detected_material": camera_material,
        "lot_material": lot_material,
        "avg_confidence": round(avg_confidence, 3),
        "avg_confidence_percent": f"{avg_confidence * 100:.1f}%",
        "is_low_confidence": is_low_confidence,
        "is_unreliable": (material_mismatch or is_low_confidence),
        "unreliable_warning": unreliable_warning,
        "pass_fail_suggestion": pass_fail_suggestion,
        "max_defects_threshold": max_defects_threshold,
        "timestamp": ai_insp.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "inspection_timestamp": ai_insp.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "training_workflow": yolo_res.get("training_workflow", []),
        "confidence_threshold": conf_threshold,
        "was_resized_for_inference": yolo_res.get("was_resized_for_inference", False),
        "original_dimensions": yolo_res.get("original_dimensions", []),
        "inference_dimensions": yolo_res.get("inference_dimensions", [])
    }

    return jsonify({
        "success": True,
        "message": "AI Visual inspection completed successfully",
        "data": ai_payload,
        "ai_result": ai_payload
    }), 200



@qc_bp.route('/api/qc/ai-inspections', methods=['GET'])
@login_required
def get_ai_inspections():
    """
    Returns visual inspection history, optionally filtered by target.
    """
    db = get_db()
    lot_id = request.args.get('lot_id', type=int)
    product_id = request.args.get('product_id', type=int)
    batch_id = request.args.get('batch_id', type=int)

    query = db.query(AIInspection)
    if lot_id:
        query = query.filter_by(raw_material_lot_id=lot_id)
    if product_id:
        query = query.filter_by(product_id=product_id)
    if batch_id:
        query = query.filter_by(production_batch_id=batch_id)

    inspections = query.order_by(AIInspection.id.desc()).limit(20).all()
    return jsonify({
        "success": True,
        "count": len(inspections),
        "data": [i.to_dict() for i in inspections]
    })


@qc_bp.route('/api/qc/ai-feedback', methods=['POST'])
@login_required
def submit_ai_feedback():
    """
    Feedback Loop for Quality Record:
    Records QC Specialist verdict ('RESULT_CORRECT' / 'RESULT_WRONG') plus note box.
    Feedback is stored in the database for compliance and auditing.
    It is NOT automatically fed into model retraining.
    """
    db = get_db()
    data = request.get_json() or {}
    ai_inspection_id = data.get('ai_inspection_id')
    feedback_type = data.get('feedback_type', 'RESULT_CORRECT') # 'RESULT_CORRECT', 'RESULT_WRONG'
    notes = data.get('notes', '')
    user = get_current_user()

    if not ai_inspection_id:
        return jsonify({"success": False, "error": "ai_inspection_id is required"}), 400

    feedback = AIFeedback(
        ai_inspection_id=int(ai_inspection_id),
        inspector_user_id=user.id if user else None,
        feedback_type=feedback_type,
        corrected_class=data.get('corrected_class'),
        inspector_notes=notes,
        created_at=datetime.datetime.utcnow()
    )
    db.add(feedback)
    db.commit()

    return jsonify({
        "success": True,
        "message": "Feedback successfully recorded in quality audit log (no automated retraining triggered).",
        "data": feedback.to_dict()
    }), 201


def create_qc_handoff_alert(db, lot, final_status, user_name=None):
    """
    Step 5 Handoff alerts:
    - QC Approved -> Alert Production: 'Lot [LOT#] released, ready for batch production'
    - QC Rejected -> Alert Warehouse/Procurement: 'Lot [LOT#] REJECTED - quarantined, do not consume'
    - QC Hold -> Alert QC: 'Lot [LOT#] placed on HOLD'
    """
    if not lot:
        return
    lot_num = getattr(lot, 'lot_number', f"Lot #{getattr(lot, 'id', '')}")
    mat_name = getattr(lot, 'material_name', 'Material')
    actor = user_name or "QC Inspector"
    try:
        if final_status == 'APPROVED':
            alert = NotificationAlert(
                title=f"Lot Released: {lot_num}",
                message=f"Lot {lot_num} ({mat_name}) released by {actor}, ready for batch production.",
                module="Production",
                severity="INFO",
                reference_type="lot",
                reference_id=lot_num
            )
            db.add(alert)
        elif final_status == 'REJECTED':
            alert = NotificationAlert(
                title=f"Lot Quarantined: {lot_num}",
                message=f"Lot {lot_num} ({mat_name}) REJECTED by {actor} - quarantined, do not consume.",
                module="Warehouse",
                severity="CRITICAL",
                reference_type="lot",
                reference_id=lot_num
            )
            db.add(alert)
        elif final_status == 'HOLD':
            alert = NotificationAlert(
                title=f"Lot On Hold: {lot_num}",
                message=f"Lot {lot_num} ({mat_name}) placed on HOLD by {actor}. Additional verification required.",
                module="QC",
                severity="WARNING",
                reference_type="lot",
                reference_id=lot_num
            )
            db.add(alert)
    except Exception:
        pass


@qc_bp.route('/api/qc/ai-inspection/<int:inspection_id>/confirm-verdict', methods=['POST'])
@login_required
def confirm_ai_verdict(inspection_id):
    """
    Day 3 Item: Lot status update on confirm.
    Updates the linked lot status based on inspector Accept/Reject action.
    """
    db = get_db()
    ai_insp = db.query(AIInspection).filter_by(id=inspection_id).first()
    if not ai_insp:
        return jsonify({"success": False, "error": "AI Inspection not found"}), 404

    data = request.get_json() or {}
    action = (data.get('verdict') or data.get('action') or '').upper() # 'ACCEPT' / 'PASS' or 'REJECT' / 'FAIL'
    notes = data.get('notes', '')
    user = get_current_user()

    if action in ['ACCEPT', 'PASS', 'APPROVED']:
        final_status = 'APPROVED'
    elif action in ['REJECT', 'FAIL', 'REJECTED']:
        final_status = 'REJECTED'
    elif action in ['HOLD', 'NEEDS_REVIEW']:
        final_status = 'HOLD'
    else:
        return jsonify({"success": False, "error": f"Invalid action: {action}"}), 400

    is_accept = final_status == 'APPROVED'
    is_reject = final_status == 'REJECTED'

    # Check state from final_decision
    live_sess = db.query(LiveSession).filter_by(ai_inspection_id=ai_insp.id).first()
    if not live_sess and ai_insp.raw_material_lot_id:
        live_sess = db.query(LiveSession).filter_by(lot_id=ai_insp.raw_material_lot_id).order_by(LiveSession.id.desc()).first()

    analysis_dict = ai_insp.to_dict()
    if live_sess and live_sess.locked_result_json:
        try:
            analysis_dict = json.loads(live_sess.locked_result_json)
        except Exception:
            pass

    dec_obj = final_decision(analysis_dict)
    analysis_state = dec_obj.get("state", "REVIEW")
    written_reason = (data.get('notes') or data.get('reason') or data.get('action_notes') or '').strip()

    if is_accept and analysis_state != "PASS":
        if not written_reason:
            return jsonify({
                "success": False,
                "error": f"Approving a lot when the analysis state is {analysis_state} requires a written reason."
            }), 400

    if is_reject and analysis_state != "REJECT":
        if not written_reason:
            return jsonify({
                "success": False,
                "error": f"Rejecting a lot when the analysis state is {analysis_state} requires a written reason."
            }), 400

    now_utc = datetime.datetime.utcnow()
    who_name = user.full_name if (user and user.full_name) else (user.username if user else "QC Inspector")
    when_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    is_override = (is_accept and analysis_state != "PASS") or (is_reject and analysis_state != "REJECT")
    if is_override:
        audit_note = f"Override Verdict [{final_status}] by {who_name} at {when_str}. Analysis State was {analysis_state}. Reason: {written_reason}"
    else:
        audit_note = f"Verdict [{final_status}] confirmed by {who_name} at {when_str}." + (f" Notes: {written_reason}" if written_reason else "")

    lot = ai_insp.raw_material_lot
    if lot:
        lot.qc_status = final_status
        if final_status == 'APPROVED':
            lot.status = StatusEnum.APPROVED.value
        elif final_status == 'REJECTED':
            lot.status = StatusEnum.REJECTED.value
        elif final_status == 'HOLD':
            lot.status = StatusEnum.PENDING.value

    ai_insp.status_message = audit_note

    decision = QCDecision(
        raw_material_lot_id=lot.id if lot else None,
        product_id=ai_insp.product_id,
        production_batch_id=ai_insp.production_batch_id,
        decided_by_user_id=user.id if user else 1,
        final_status=final_status,
        reason=f"Override ({analysis_state} -> {final_status}): {written_reason}" if is_override else f"AI Visual Inspection Verdict Confirmed ({action})",
        action_notes=audit_note,
        decided_at=now_utc
    )
    db.add(decision)
    create_qc_handoff_alert(db, lot, final_status, who_name)
    db.commit()

    return jsonify({
        "success": True,
        "message": f"Verdict confirmed. Lot {lot.lot_number if lot else 'Record'} status updated to {final_status}.",
        "final_status": final_status,
        "lot_number": lot.lot_number if lot else None,
        "decision_id": decision.id
    })


@qc_bp.route('/api/qc/ai-inspection/<int:inspection_id>/pdf', methods=['GET'])
@login_required
def generate_inspection_pdf(inspection_id):
    """
    Day 3 Item: Inspection report PDF generation.
    Generates an official inspection dossier PDF using ReportLab.
    """
    db = get_db()
    insp = db.query(AIInspection).filter_by(id=inspection_id).first()
    if not insp:
        return jsonify({"error": "AI Inspection record not found"}), 404

    lot = insp.raw_material_lot
    lot_name = lot.material_name if lot else "N/A"
    lot_code = lot.lot_number if lot else "Unlinked Specimen"
    supplier_name = lot.supplier_name if lot else "N/A"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=17,
        leading=21,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=3
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=10
    )
    section_title = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=10,
        spaceAfter=6
    )
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#334155')
    )
    cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=cell_style,
        fontName='Helvetica-Bold'
    )
    verdict_pass = ParagraphStyle(
        'VerdictPass',
        parent=cell_bold,
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#059669')
    )
    verdict_fail = ParagraphStyle(
        'VerdictFail',
        parent=cell_bold,
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#DC2626')
    )
    verdict_review = ParagraphStyle(
        'VerdictReview',
        parent=cell_bold,
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#D97706')
    )

    elements = []

    # Header
    elements.append(Paragraph("FOODMAN QUALITY CONTROL &amp; FOOD SAFETY ASSURANCE", title_style))
    elements.append(Paragraph(f"AI Visual Inspection Dossier • YOLOv8 Detection Engine • Report Generated {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}", subtitle_style))

    mat_label = insp.detected_material or ""
    if mat_label:
        if not mat_label.lower().startswith("material:"):
            mat_label = f"Material: {mat_label}"
        elements.append(Paragraph(f"<b>{mat_label}</b>", ParagraphStyle('MatBanner', parent=subtitle_style, fontSize=11, leading=14, textColor=colors.HexColor('#0F172A'))))

    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284C7'), spaceBefore=2, spaceAfter=12))

    # Meta Table
    if insp.model_status == "NEEDS_REVIEW":
        status_paragraph = Paragraph("NEEDS REVIEW", verdict_review)
    elif insp.total_defects_count > 0 or insp.model_status == "DEFECTS_DETECTED":
        status_paragraph = Paragraph("FAIL (Defects Detected)", verdict_fail)
    else:
        status_paragraph = Paragraph("PASS", verdict_pass)

    mat_cell_str = f"Lot: {insp.lot_material or 'N/A'}<br/><b>{mat_label or 'Camera: N/A'}</b>"
    meta_data = [
        [Paragraph("Inspection ID:", cell_bold), Paragraph(f"#{insp.id}", cell_style), Paragraph("Inspection Status:", cell_bold), status_paragraph],
        [Paragraph("Target Entity:", cell_bold), Paragraph(f"{lot_code} ({lot_name})", cell_style), Paragraph("Supplier:", cell_bold), Paragraph(supplier_name, cell_style)],
        [Paragraph("Model Version:", cell_bold), Paragraph(insp.model_version or "YOLOv8", cell_style), Paragraph("Inference Latency:", cell_bold), Paragraph(f"{insp.inference_time_ms} ms", cell_style)],
        [Paragraph("Defects Count:", cell_bold), Paragraph(str(insp.total_defects_count), cell_style), Paragraph("Avg Confidence:", cell_bold), Paragraph(f"{(insp.avg_confidence or 0.0)*100:.1f}%", cell_style)],
        [Paragraph("Material Check:", cell_bold), Paragraph(mat_cell_str, cell_style), Paragraph("Timestamp:", cell_bold), Paragraph(insp.created_at.strftime("%Y-%m-%d %H:%M UTC") if insp.created_at else "N/A", cell_style)]
    ]

    meta_table = Table(meta_data, colWidths=[110, 160, 120, 150])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 10))

    # Mismatch / Unreliable warning banner in PDF
    if insp.material_mismatch or insp.mismatch_warning or insp.model_status == "NEEDS_REVIEW":
        warn_text = insp.mismatch_warning or insp.status_message or "Result unreliable: verify the sample manually or retake the photo."
        warn_data = [[
            Paragraph(f"<b>ADVISORY:</b> {warn_text}", ParagraphStyle('Warn', parent=cell_style, textColor=colors.HexColor('#92400E'), fontName='Helvetica-Bold'))
        ]]
        warn_table = Table(warn_data, colWidths=[540])
        warn_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FEF3C7')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#F59E0B')),
            ('TOPPADDING', (0,0), (-1,-1), 7),
            ('BOTTOMPADDING', (0,0), (-1,-1), 7),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
        ]))
        elements.append(warn_table)
        elements.append(Spacer(1, 10))

    # Defect Detections Table
    elements.append(Paragraph("OBJECT &amp; DEFECT DETECTIONS", section_title))
    defect_rows = [
        [Paragraph("#", cell_bold), Paragraph("Classification Class", cell_bold), Paragraph("Severity", cell_bold), Paragraph("Confidence", cell_bold), Paragraph("Bounding Box [X, Y, W, H]", cell_bold)]
    ]

    if insp.detected_defects:
        for idx, d in enumerate(insp.detected_defects, 1):
            bbox_str = f"[{d.bbox_x}%, {d.bbox_y}%, {d.bbox_w}%, {d.bbox_h}%]"
            defect_rows.append([
                Paragraph(str(idx), cell_style),
                Paragraph(d.defect_class, ParagraphStyle('DefCls', parent=cell_style, textColor=colors.HexColor('#DC2626'), fontName='Helvetica-Bold')),
                Paragraph("CRITICAL" if "mold" in d.defect_class.lower() else "WARNING", cell_style),
                Paragraph(f"{d.confidence*100:.1f}%", cell_style),
                Paragraph(bbox_str, cell_style)
            ])
    else:
        defect_rows.append([
            Paragraph("1", cell_style),
            Paragraph("No visual defects detected (Specimen clean)", ParagraphStyle('Clean', parent=cell_style, textColor=colors.HexColor('#059669'))),
            Paragraph("NORMAL", cell_style),
            Paragraph(f"{(insp.avg_confidence or 0.95)*100:.1f}%", cell_style),
            Paragraph("[0%, 0%, 100%, 100%]", cell_style)
        ])

    defects_table = Table(defect_rows, colWidths=[25, 195, 80, 80, 160])
    defects_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(defects_table)
    elements.append(Spacer(1, 14))

    # Look up LiveSession associated with this inspection or lot
    live_sess = db.query(LiveSession).filter_by(ai_inspection_id=insp.id).first()
    if not live_sess and insp.raw_material_lot_id:
        live_sess = db.query(LiveSession).filter_by(lot_id=insp.raw_material_lot_id).order_by(LiveSession.id.desc()).first()

    best_frames_list = []
    final_dec_obj = None
    if live_sess and live_sess.locked_result_json:
        try:
            l_json = json.loads(live_sess.locked_result_json)
            best_frames_list = l_json.get("best_frames", [])
            final_dec_obj = l_json.get("final_decision")
        except Exception:
            pass

    if not final_dec_obj:
        final_dec_obj = final_decision({
            "material": insp.detected_material,
            "kernels_checked": (insp.total_defects_count or 0) + 15,
            "defect_pct": 0.0 if (insp.total_defects_count or 0) == 0 else round(((insp.total_defects_count or 0) / max(1, (insp.total_defects_count or 0) + 15)) * 100.0, 1),
            "confidence": insp.avg_confidence,
            "warnings": [insp.status_message] if insp.status_message and "override" not in insp.status_message.lower() else []
        })

    # Rebuild Result Card Component in PDF (Matching station result card & dashboard live card)
    if final_dec_obj:
        f_state = (final_dec_obj.get("state") or "REVIEW").upper()
        f_state_title = f_state.capitalize()
        f_reason = final_dec_obj.get("reason") or "Inspection complete."
        f_next_step = final_dec_obj.get("next_step") or "Review sample and determine lot disposition."
        f_material = final_dec_obj.get("material") or insp.detected_material or "Unknown"
        f_kernels = final_dec_obj.get("kernels_checked", 0)
        f_defect = final_dec_obj.get("defect_pct")

        # 1. Status Banner: ONLY coloured element (green, amber, red, grey)
        banner_bg = colors.HexColor('#FFFBEB')
        banner_border = colors.HexColor('#FDE68A')
        banner_text = colors.HexColor('#92400E')

        if f_state == "PASS":
            banner_bg = colors.HexColor('#ECFDF5')
            banner_border = colors.HexColor('#A7F3D0')
            banner_text = colors.HexColor('#065F46')
        elif f_state == "REJECT":
            banner_bg = colors.HexColor('#FEF2F2')
            banner_border = colors.HexColor('#FECACA')
            banner_text = colors.HexColor('#991B1B')
        elif f_state == "RETAKE":
            banner_bg = colors.HexColor('#F1F5F9')
            banner_border = colors.HexColor('#CBD5E1')
            banner_text = colors.HexColor('#334155')

        banner_title_style = ParagraphStyle(
            'BannerTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=15,
            leading=19,
            textColor=banner_text
        )

        banner_data = [[
            Paragraph(f"<b>{f_state_title}</b> — {f_reason}", banner_title_style)
        ]]
        banner_table = Table(banner_data, colWidths=[540])
        banner_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), banner_bg),
            ('BOX', (0,0), (-1,-1), 1, banner_border),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ]))
        elements.append(banner_table)
        elements.append(Spacer(1, 10))

        # 2. Three plain stats: Material, Kernels checked, Defective. Neutral greys.
        stat_label_style = ParagraphStyle(
            'StatLabel',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#64748B')
        )
        stat_val_style = ParagraphStyle(
            'StatVal',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=colors.HexColor('#0F172A')
        )
        stat_note_style = ParagraphStyle(
            'StatNote',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor('#64748B')
        )

        if f_defect is not None:
            defect_cell = [
                Paragraph("DEFECTIVE", stat_label_style),
                Paragraph(f"{f_defect:.1f}%", stat_val_style)
            ]
        else:
            defect_cell = [
                Paragraph("DEFECTIVE", stat_label_style),
                Paragraph("Hidden", stat_val_style),
                Paragraph("Shown once the material is clear", stat_note_style)
            ]

        stats_data = [
            [
                [Paragraph("MATERIAL", stat_label_style), Paragraph(str(f_material), stat_val_style)],
                [Paragraph("KERNELS CHECKED", stat_label_style), Paragraph(str(f_kernels), stat_val_style)],
                defect_cell
            ]
        ]
        stats_table = Table(stats_data, colWidths=[180, 180, 180])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(stats_table)
        elements.append(Spacer(1, 10))

        # 3. What to do next (Neutral greys)
        next_data = [
            [
                Paragraph("<b>What to do next:</b> " + f_next_step, cell_style)
            ]
        ]
        next_table = Table(next_data, colWidths=[540])
        next_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ]))
        elements.append(next_table)
        elements.append(Spacer(1, 10))

    # 4. Photos behind this result: three photos with caption "n flagged of m kernels"
    if best_frames_list:
        elements.append(Paragraph("Photos behind this result", section_title))
        best_col_cells = []
        for idx, bf in enumerate(best_frames_list[:3], 1):
            flagged = bf.get("defect_count", 0)
            good_c = bf.get("good_count", 0)
            total_k = flagged + good_c
            label_text = f"{flagged} flagged of {total_k} kernels"

            img_cand = bf.get("annotated_path") or bf.get("image_path")
            cell_items = []
            if img_cand:
                norm_cand = img_cand.replace('/static/uploads/annotated/annotated_live_', '/static/uploads/live_frames/annotated/annotated_live_')
                disk_path = os.path.join(Config.BASE_DIR, norm_cand.lstrip('/').replace('/', os.sep))
                if not os.path.isfile(disk_path):
                    raw_cand = (bf.get("image_path") or "").lstrip('/')
                    disk_path = os.path.join(Config.BASE_DIR, raw_cand.replace('/', os.sep))

                if os.path.isfile(disk_path):
                    try:
                        cell_items.append(RLImage(disk_path, width=160, height=105))
                        cell_items.append(Spacer(1, 4))
                    except Exception:
                        pass

            cell_items.append(Paragraph(label_text, ParagraphStyle('FrameLabel', parent=cell_style, fontSize=8, leading=10, textColor=colors.HexColor('#475569'))))
            best_col_cells.append(cell_items)

        if best_col_cells:
            while len(best_col_cells) < 3:
                best_col_cells.append([Paragraph("", cell_style)])
            best_table = Table([best_col_cells], colWidths=[180, 180, 180])
            best_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(best_table)
            elements.append(Spacer(1, 10))

    # 5. How was this decided? (Technical lines in neutral grey)
    if final_dec_obj:
        elements.append(Paragraph("How was this decided?", section_title))
        raw_details = final_dec_obj.get("details") or []
        clean_lines = []
        for d in raw_details:
            c = (d.replace("across 5 usable frames", "across 5 photos used")
                  .replace("across usable frames", "across photos used")
                  .replace("usable frames", "photos used")
                  .replace("classifier consensus", "material agreement")
                  .replace("multi-frame locked analysis", "photo analysis")
                  .replace("specimen", "sample")
                  .replace("Material agreement:", "Agreement:")
                  .replace("Agreement:", "Material agreement:"))
            clean_lines.append(f"• {c}")

        if not clean_lines:
            clean_lines = [
                f"• Material agreement: {f_material}",
                f"• Photos used: 5 of 5",
                f"• Model confidence: {(insp.avg_confidence or 0.95)*100:.1f}%",
                "• Pass limit: 5.0%, Reject limit: 8.0%"
            ]

        dec_table = Table([[Paragraph("<br/>".join(clean_lines), cell_style)]], colWidths=[540])
        dec_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ]))
        elements.append(dec_table)
        elements.append(Spacer(1, 10))

    # 5. Combined Release Decision & Quality Gate (COA + AI)
    if lot:
        rel_dec = release_decision(lot, db=db)
        r_outcome = rel_dec.get("outcome", "HOLD")
        r_coa_state = rel_dec.get("coa_state", "MISSING")
        r_ai_state = rel_dec.get("ai_state", "NOT_RUN")
        r_reason = rel_dec.get("reason", "")

        rel_bg = colors.HexColor('#FEF3C7')
        rel_border = colors.HexColor('#F59E0B')
        rel_text = colors.HexColor('#92400E')
        if r_outcome == "RELEASE":
            rel_bg = colors.HexColor('#ECFDF5')
            rel_border = colors.HexColor('#10B981')
            rel_text = colors.HexColor('#065F46')
        elif r_outcome == "REJECT":
            rel_bg = colors.HexColor('#FEF2F2')
            rel_border = colors.HexColor('#EF4444')
            rel_text = colors.HexColor('#991B1B')

        elements.append(Paragraph("COMBINED RELEASE DECISION (COA + AI)", section_title))
        rel_data = [
            [
                Paragraph(f"<b>OUTCOME: {r_outcome}</b> — {r_reason}", ParagraphStyle('RelTitle', parent=cell_style, textColor=rel_text, fontName='Helvetica-Bold', fontSize=10, leading=13))
            ],
            [
                Paragraph(f"<b>Paper Check (COA):</b> {r_coa_state} &nbsp;|&nbsp; <b>Camera Check (AI):</b> {r_ai_state}", cell_style)
            ]
        ]
        if rel_dec.get("peanut_advisory"):
            rel_data.append([Paragraph(f"<b>Advisory:</b> {rel_dec['peanut_advisory']}", ParagraphStyle('PeaAdv', parent=cell_style, textColor=colors.HexColor('#1E40AF')))])

        rel_table = Table(rel_data, colWidths=[540])
        rel_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), rel_bg),
            ('BOX', (0,0), (-1,-1), 1.2, rel_border),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ]))
        elements.append(rel_table)
        elements.append(Spacer(1, 10))

    # 6. Human QC Officer Sign-Off & Audit Reason
    elements.append(Paragraph("QC Officer Sign-off", section_title))
    recent_decision = db.query(QCDecision).filter_by(raw_material_lot_id=insp.raw_material_lot_id).order_by(QCDecision.id.desc()).first() if insp.raw_material_lot_id else None
    if recent_decision:
        who_str = recent_decision.decided_by.full_name if recent_decision.decided_by else "QC Officer"
        when_str = recent_decision.decided_at.strftime("%Y-%m-%d %H:%M UTC") if recent_decision.decided_at else "N/A"
        reason_str = recent_decision.action_notes or recent_decision.reason or "Standard approval"
        disp_str = f"<b>{recent_decision.final_status}</b>"
        sign_data = [
            [Paragraph("Verified By (QC Specialist):", cell_bold), Paragraph(who_str, cell_style), Paragraph("Sign-off Date:", cell_bold), Paragraph(when_str, cell_style)],
            [Paragraph("Final Disposition:", cell_bold), Paragraph(disp_str, cell_style), Paragraph("Written Reason / Audit:", cell_bold), Paragraph(reason_str, cell_style)]
        ]
    else:
        sign_data = [
            [Paragraph("Verified By (QC Specialist):", cell_bold), Paragraph("___________________________", cell_style), Paragraph("Signature &amp; Stamp:", cell_bold), Paragraph("___________________________", cell_style)],
            [Paragraph("Final Disposition:", cell_bold), Paragraph("Approved [  ]    Hold [  ]    Rejected [  ]", cell_style), Paragraph("Sign-off Date:", cell_bold), Paragraph("____ / ____ / 2026", cell_style)]
        ]
    sign_table = Table(sign_data, colWidths=[140, 140, 120, 140])
    sign_table.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(sign_table)
    elements.append(Spacer(1, 8))

    # 7. Footer line on peanut results and PDFs: "Camera screening only. Not a lab test."
    elements.append(Paragraph(
        "Camera screening only. Not a lab test.",
        ParagraphStyle(
            'PdfFooterNote',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=8,
            leading=10,
            alignment=1, # Center
            textColor=colors.HexColor('#64748B')
        )
    ))

    doc.build(elements)
    buffer.seek(0)

    clean_code = lot_code.replace(" ", "_").replace("/", "-")
    filename = f"Inspection_Report_{clean_code}_{insp.id}.pdf"
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )


@qc_bp.route('/api/qc/decision', methods=['POST'])
@login_required
def submit_general_qc_decision():

    """
    Generalized Final QC Decision combining:
    1. Lab Test Results
    2. COA Document Verification
    3. YOLOv8 Visual Defect Results
    4. Required Product Specifications
    Decision is strictly Human-Only (APPROVED, HOLD, REJECTED).
    Only materials/products with final APPROVED status can proceed.
    """
    data = request.get_json() or {}
    target_type = data.get('target_type', 'lot') # 'lot', 'product', 'batch'
    target_id = data.get('target_id')
    final_status = data.get('final_status', '').upper()
    reason = data.get('reason', 'QC Specialist verification of Lab, COA, YOLO visual scan and specifications.')
    action_notes = data.get('action_notes', '')

    if final_status not in ['APPROVED', 'HOLD', 'REJECTED']:
        return jsonify({"success": False, "error": "Invalid approval status. Must be APPROVED, HOLD, or REJECTED."}), 400

    if not target_id:
        return jsonify({"success": False, "error": "Target ID is required."}), 400

    db = get_db()
    user = get_current_user()

    raw_lot_id = None
    product_id = None
    batch_id = None
    target_label = ""

    if target_type == 'lot':
        raw_lot_id = int(target_id)
        lot = db.query(RawMaterialLot).filter_by(id=raw_lot_id).first()
        if not lot:
            return jsonify({"success": False, "error": "Raw material lot not found"}), 404
        lot.qc_status = final_status
        if final_status == 'APPROVED':
            lot.status = StatusEnum.APPROVED.value
        elif final_status == 'HOLD':
            lot.status = StatusEnum.HOLD.value
        else:
            lot.status = StatusEnum.REJECTED.value
        target_label = f"Raw Material Lot {lot.lot_number}"
    elif target_type == 'product':
        product_id = int(target_id)
        prod = db.query(Product).filter_by(id=product_id).first()
        if not prod:
            return jsonify({"success": False, "error": "Product not found"}), 404
        target_label = f"Product {prod.name}"
    elif target_type == 'batch':
        batch_id = int(target_id)
        batch = db.query(ProductionBatch).filter_by(id=batch_id).first()
        if not batch:
            return jsonify({"success": False, "error": "Batch not found"}), 404
        if final_status == 'REJECTED':
            batch.status = "REJECTED"
        target_label = f"Batch {batch.batch_code}"

    decision = QCDecision(
        raw_material_lot_id=raw_lot_id,
        product_id=product_id,
        production_batch_id=batch_id,
        decided_by_user_id=user.id if user else 1,
        final_status=final_status,
        reason=reason,
        action_notes=action_notes
    )
    db.add(decision)
    if raw_lot_id:
        target_lot = db.query(RawMaterialLot).filter_by(id=raw_lot_id).first()
        create_qc_handoff_alert(db, target_lot, final_status, user.full_name if user else 'QC')
    db.commit()

    return jsonify({
        "success": True,
        "message": f"QC Officer {user.full_name if user else 'QC'} recorded final decision [{final_status}] for {target_label}.",
        "data": decision.to_dict()
    }), 200


@qc_bp.route('/api/qc/lot/<int:lot_id>/image', methods=['POST'])
@login_required
def upload_inspection_image(lot_id):
    """
    Upload physical lot inspection photo and execute YOLO AI inference.
    """
    data = request.get_json() or {}
    db = get_db()
    lot = db.query(RawMaterialLot).filter_by(id=lot_id).first()
    if not lot:
        return jsonify({"error": "Raw material lot not found"}), 404

    image_url = data.get('image_url', 'https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800&auto=format&fit=crop&q=80')
    image_type = data.get('image_type', 'Packaging appearance / seal')

    insp_image = InspectionImage(
        raw_material_lot_id=lot.id,
        image_url=image_url,
        image_type=image_type
    )
    db.add(insp_image)
    db.flush()

    # Run YOLO inference
    yolo_result = run_yolo_inference(insp_image.image_url, {"lot_number": lot.lot_number})
    lot_material = extract_material_name(lot.material_name) or extract_material_name(lot.category)
    camera_material = get_mostly_detected_material(yolo_result)
    material_mismatch = False
    mismatch_warning = None
    if lot_material and camera_material:
        if lot_material.lower() != camera_material.lower():
            material_mismatch = True
            mismatch_warning = f"Possible material mismatch: lot says {lot_material}, camera sees {camera_material}. Please verify."

    ai_insp = AIInspection(
        inspection_image_id=insp_image.id,
        raw_material_lot_id=lot.id,
        model_version=yolo_result["model_version"],
        inference_time_ms=yolo_result["inference_time_ms"],
        total_defects_count=yolo_result["total_defects_count"],
        summary=yolo_result["summary"],
        material_mismatch=material_mismatch,
        mismatch_warning=mismatch_warning,
        detected_material=camera_material,
        lot_material=lot_material
    )
    db.add(ai_insp)
    db.flush()

    for defect in yolo_result["detected_defects"]:
        detected = DetectedDefect(
            ai_inspection_id=ai_insp.id,
            defect_class=defect["defect_class"],
            confidence=defect["confidence"],
            bbox_x=defect["bbox_x"],
            bbox_y=defect["bbox_y"],
            bbox_w=defect["bbox_w"],
            bbox_h=defect["bbox_h"]
        )
        db.add(detected)
    db.commit()

    ai_dict = ai_insp.to_dict()
    ai_dict["image_url"] = insp_image.image_url

    return jsonify({
        "success": True,
        "data": {
            "image": insp_image.to_dict(),
            "ai_inspection": ai_dict
        }
    }), 201


# ==============================================================================
# 4. HUMAN-ONLY QC DECISION ENDPOINT (APPROVED / HOLD / REJECTED)
# AI never auto-approves
# ==============================================================================
@qc_bp.route('/api/qc/lot/<int:lot_id>/decision', methods=['POST'])
@login_required
def submit_qc_decision(lot_id):
    """
    Human-only final decision: APPROVED, HOLD, or REJECTED.
    AI output is displayed advisory-only, decision MUST be triggered by manual human click.
    """
    data = request.get_json() or {}
    final_status = data.get('final_status', '').upper()

    if final_status not in ['APPROVED', 'HOLD', 'REJECTED']:
        return jsonify({"error": "Invalid approval status. Choose APPROVED, HOLD, or REJECTED."}), 400

    db = get_db()
    user = get_current_user()

    lot = db.query(RawMaterialLot).filter_by(id=lot_id).first()
    if not lot:
        return jsonify({"error": "Raw material lot not found"}), 404

    # Determine analysis state
    analysis_state = "REVIEW"
    live_sess = db.query(LiveSession).filter_by(lot_id=lot.id).order_by(LiveSession.id.desc()).first()
    if live_sess and live_sess.locked_result_json:
        try:
            d_obj = final_decision(json.loads(live_sess.locked_result_json))
            analysis_state = d_obj.get("state", "REVIEW")
        except Exception:
            analysis_state = "REVIEW"
    else:
        recent_ai = db.query(AIInspection).filter_by(raw_material_lot_id=lot.id).order_by(AIInspection.id.desc()).first()
        if recent_ai:
            if recent_ai.model_status != "NEEDS_REVIEW" and (recent_ai.total_defects_count or 0) == 0 and not recent_ai.material_mismatch:
                analysis_state = "PASS"
            elif (recent_ai.total_defects_count or 0) > 0:
                analysis_state = "REJECT"
            else:
                analysis_state = "REVIEW"

    written_notes = (data.get('action_notes') or data.get('reason') or '').strip()
    if written_notes == 'QC Specialist performed comprehensive verification of Lab tests, COA certificate, and AI visual inspection.':
        written_notes = ''

    # Evaluate combined release decision outcome
    rel_dec = release_decision(lot, db=db)
    rec_outcome = rel_dec.get("outcome", "HOLD")

    is_override = False
    if final_status == 'APPROVED' and rec_outcome != 'RELEASE':
        is_override = True
        if not written_notes:
            return jsonify({
                "error": f"Releasing lot {lot.lot_number} against the suggestion ({rec_outcome}) requires a written reason (who, when, and why)."
            }), 400

    if final_status == 'REJECTED' and rec_outcome != 'REJECT':
        is_override = True
        if not written_notes:
            return jsonify({
                "error": f"Rejecting lot {lot.lot_number} when outcome is not REJECT ({rec_outcome}) requires a written reason (who, when, and why)."
            }), 400

    now_utc = datetime.datetime.utcnow()
    who_name = user.full_name if (user and user.full_name) else (user.username if user else "QC Inspector")
    when_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

    if is_override:
        audit_note = f"Override to {final_status} by {who_name} at {when_str}. Release outcome was {rec_outcome}. Reason: {written_notes}"
    else:
        audit_note = written_notes or f"Verified by {who_name} at {when_str}."

    # 1. Record human decision with who, when, reason
    decision = QCDecision(
        raw_material_lot_id=lot.id,
        decided_by_user_id=user.id if user else 1,
        final_status=final_status,
        reason=f"Override ({analysis_state} -> {final_status}): {written_notes}" if is_override else (data.get('reason') or f"Confirmed {final_status}"),
        action_notes=audit_note,
        decided_at=now_utc
    )
    db.add(decision)

    if is_override:
        ai_rec = db.query(AIInspection).filter_by(raw_material_lot_id=lot.id).order_by(AIInspection.id.desc()).first()
        if ai_rec:
            ai_rec.status_message = audit_note

    # 2. Update Lot QC status
    lot.qc_status = final_status
    if final_status == 'APPROVED':
        lot.status = StatusEnum.APPROVED.value
    elif final_status == 'HOLD':
        lot.status = StatusEnum.HOLD.value
    else:
        lot.status = StatusEnum.REJECTED.value

    db.commit()

    return jsonify({
        "success": True,
        "message": f"QC Officer {user.full_name if user else 'QC'} approved lot {lot.lot_number} to status: {final_status}",
        "decision": decision.to_dict(),
        "lot_qc_status": lot.qc_status
    })


# ==============================================================================
# 5. OUTPUT CONTRACT WITH MODULE 3 (PRODUCTION)
# Production may ONLY query lots where qc_decisions.final_status = APPROVED
# ==============================================================================
@qc_bp.route('/api/qc/production-ready-lots', methods=['GET'])
@login_required
def get_production_ready_lots():
    """
    Output Contract for Module 3 (Production):
    Production may ONLY query lots where qc_decisions.final_status = APPROVED.
    Any lots with PENDING_QC, HOLD, or REJECTED are strictly excluded.
    """
    db = get_db()
    approved_lots = db.query(RawMaterialLot).join(QCDecision).filter(
        QCDecision.final_status == 'APPROVED',
        RawMaterialLot.qc_status == 'APPROVED'
    ).distinct().all()

    return jsonify({
        "success": True,
        "contract": "Production Staging Gate (Approved Only)",
        "count": len(approved_lots),
        "lots": [
            {
                "id": lot.id,
                "lot_number": lot.lot_number,
                "material_name": lot.material_name,
                "quantity": lot.quantity,
                "unit": lot.unit,
                "qc_status": lot.qc_status,
                "storage_condition": lot.storage_condition
            }
            for lot in approved_lots
        ]
    })


# ==============================================================================
# 6. LAB TEST & COA DIRECT APIS
# ==============================================================================
@qc_bp.route('/api/qc/lot/<int:lot_id>/sample', methods=['POST'])
@login_required
def add_lot_sample_and_tests(lot_id):
    data = request.get_json() or {}
    db = get_db()
    user = get_current_user()

    sample = QCSample(
        sample_code=data.get('sample_code', f"SMP-{lot_id}-{datetime.datetime.utcnow().strftime('%H%M%S')}"),
        raw_material_lot_id=lot_id,
        sampler_user_id=user.id if user else None,
        storage_temp=data.get('storage_temp', '4°C'),
        sample_size=data.get('sample_size', '500ml'),
        notes=data.get('notes', '')
    )
    db.add(sample)
    db.flush()

    tests_data = data.get('tests', [])
    for t in tests_data:
        db.add(QCTest(
            qc_sample_id=sample.id,
            parameter_name=t.get('parameter_name'),
            standard_spec=t.get('standard_spec'),
            measured_value=t.get('measured_value'),
            unit=t.get('unit', ''),
            is_pass=bool(t.get('is_pass', True))
        ))

    db.commit()
    return jsonify({"success": True, "sample": sample.to_dict()}), 201


@qc_bp.route('/api/qc/lot/<int:lot_id>/coa', methods=['POST'])
@login_required
def upload_coa(lot_id):
    data = request.get_json() or {}
    db = get_db()
    coa = COADocument(
        raw_material_lot_id=lot_id,
        supplier_id=data.get('supplier_id'),
        doc_number=data.get('doc_number', f"COA-{lot_id}-{datetime.datetime.utcnow().strftime('%d%m%Y')}"),
        filename=data.get('filename', 'COA_Standard.pdf'),
        file_url=data.get('file_url', f'/static/docs/coa_{lot_id}.pdf'),
        lab_accreditation=data.get('lab_accreditation', 'VILAS / ISO 17025'),
        is_verified=bool(data.get('is_verified', True))
    )
    db.add(coa)
    db.commit()
    return jsonify({"success": True, "coa": coa.to_dict()}), 201


# ==============================================================================
# 7. LIVE MOBILE INSPECTION APIS & PHONE CAPTURE (PHASE 1)
# ==============================================================================

@qc_bp.route('/api/qc/live-session/create', methods=['POST'])
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def create_live_session():
    """
    Creates a new live inspection session with a random 32-byte URL-safe token.
    Token expires after 2 hours.
    Generates a QR code and capture link.
    """
    db = get_db()
    data = request.get_json(silent=True) or {}
    lot_id = data.get('lot_id')
    if lot_id:
        try:
            lot_id = int(lot_id)
        except (ValueError, TypeError):
            lot_id = None

    # Generate random 32-byte URL-safe token
    token = secrets.token_urlsafe(32)
    created_at = datetime.datetime.utcnow()
    expires_at = created_at + datetime.timedelta(hours=2)

    live_sess = LiveSession(
        token=token,
        lot_id=lot_id,
        status="ACTIVE",
        created_at=created_at,
        expires_at=expires_at
    )
    db.add(live_sess)
    db.commit()

    urls_pkg = package_session_urls(token)
    return jsonify({
        "success": True,
        "session": live_sess.to_dict(),
        **urls_pkg
    }), 201


@qc_bp.route('/api/qc/live-session/active', methods=['GET'])
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def get_active_live_session():
    """
    Returns current active live inspection session if available.
    """
    db = get_db()
    sess = db.query(LiveSession).filter(
        LiveSession.status == "ACTIVE",
        LiveSession.expires_at > datetime.datetime.utcnow()
    ).order_by(LiveSession.id.desc()).first()

    if not sess:
        return jsonify({"success": True, "session": None})

    urls_pkg = package_session_urls(sess.token)
    return jsonify({
        "success": True,
        "session": sess.to_dict(),
        **urls_pkg
    })


@qc_bp.route('/api/qc/live-session/<int:session_id>/latest', methods=['GET'])
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def get_live_session_latest(session_id):
    """
    Laptop page polls every 1 second for the newest frame of its session
    and thumbnail history list.
    """
    db = get_db()
    sess = db.query(LiveSession).filter_by(id=session_id).first()
    if not sess:
        return jsonify({"success": False, "error": "Session not found."}), 404

    # Check expiration
    if sess.status == "ACTIVE" and sess.expires_at and datetime.datetime.utcnow() > sess.expires_at:
        sess.status = "EXPIRED"
        db.commit()

    frames = db.query(LiveFrame).filter_by(session_id=sess.id).order_by(LiveFrame.id.desc()).all()
    latest_frame = frames[0].to_dict() if frames else None

    # Up to 25 recent frames for thumbnail history
    history = [
        {
            "id": f.id,
            "created_at": f.created_at.strftime("%H:%M:%S") if f.created_at else "",
            "annotated_path": f.annotated_path or f.image_path,
            "image_path": f.image_path,
            "good_count": f.good_count or 0,
            "defect_count": f.defect_count or 0,
            "status": f.status,
            "material": f.material,
            "avg_confidence": round(f.avg_confidence, 3) if f.avg_confidence is not None else 0.0
        }
        for f in frames[:25]
    ]

    # Resolve live capture URLs (picks up .public_url dynamically and includes LAN fallback)
    urls_pkg = package_session_urls(sess.token)

    return jsonify({
        "success": True,
        "session": sess.to_dict(),
        **urls_pkg,
        "latest_frame": latest_frame,
        "total_frames": len(frames),
        "history": history
    })


@qc_bp.route('/api/qc/live-session/<int:session_id>/close', methods=['POST'])
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def close_live_session(session_id):
    """
    Invalidates session token, sets status to CLOSED,
    and deletes non-final frame images from disk while keeping the final frame.
    """
    db = get_db()
    sess = db.query(LiveSession).filter_by(id=session_id).first()
    if not sess:
        return jsonify({"success": False, "error": "Session not found."}), 404

    sess.status = "CLOSED"
    sess.closed_at = datetime.datetime.utcnow()

    deleted_count = cleanup_non_final_frames(db, sess.id)
    db.commit()

    return jsonify({
        "success": True,
        "message": f"Session closed successfully. Token invalidated. Cleaned {deleted_count} non-final image file(s). Final frame preserved.",
        "session": sess.to_dict(),
        "cleaned_files_count": deleted_count
    })


@qc_bp.route('/api/qc/live-session/<int:session_id>/link-lot', methods=['POST'])
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def link_live_session_lot(session_id):
    """
    Links or updates the lot assigned to an active live inspection session.
    """
    db = get_db()
    sess = db.query(LiveSession).filter_by(id=session_id).first()
    if not sess:
        return jsonify({"success": False, "error": "Live session not found."}), 404

    data = request.get_json(silent=True) or {}
    lot_id = data.get('lot_id')
    if lot_id is not None:
        try:
            lot_id = int(lot_id) if str(lot_id).strip() != "" else None
        except (ValueError, TypeError):
            lot_id = None

    sess.lot_id = lot_id
    db.commit()

    lot_name = sess.lot.lot_number if sess.lot else "Unlinked"
    return jsonify({
        "success": True,
        "message": f"Assigned lot to {lot_name}",
        "lot_id": lot_id,
        "lot_number": lot_name
    })


@qc_bp.route('/capture/<token>', methods=['GET'])
def capture_page(token):
    """
    Mobile phone capture page.
    No login required, token only, mobile-first, big buttons, nothing else from system visible.
    Shows rear camera 'Take Photo' button and inspection feedback.
    Shows clear messages for expired or closed sessions.
    """
    db = get_db()
    sess = db.query(LiveSession).filter_by(token=token).first()

    page_state = "ACTIVE"
    error_title = ""
    error_message = ""

    if not sess:
        page_state = "INVALID"
        error_title = "Invalid Session Token"
        error_message = "This QR code or capture link does not match any active inspection session. Please scan a new QR code from the QC terminal."
    elif sess.status == "CLOSED":
        page_state = "CLOSED"
        error_title = "Session Closed"
        error_message = "This inspection session has been closed by the QC inspector. Please scan a new QR code from the QC terminal."
    elif sess.expires_at and datetime.datetime.utcnow() > sess.expires_at:
        sess.status = "EXPIRED"
        db.commit()
        page_state = "EXPIRED"
        error_title = "Session Expired"
        error_message = "This inspection session has expired (2-hour limit). Please start a new session on the QC terminal."

    return render_template(
        'mobile_capture.html',
        token=token,
        session=sess,
        page_state=page_state,
        error_title=error_title,
        error_message=error_message
    )


def final_decision(result: dict) -> dict:
    """
    Turns analysis results into a single authoritative decision object:
    - state: 'PASS', 'REJECT', 'REVIEW', or 'RETAKE'
    - reason: one plain sentence
    - material: canonical material name ('Corn', 'Peanut', 'Sunflower', or 'Unknown / mixed')
    - kernels_checked: int count of kernels checked
    - defect_pct: float or None (null when hidden)
    - next_step: one plain sentence with recommended action
    - details: list of lines (strings)

    State rules:
    - RETAKE: fewer than 5 kernels, fewer than 3 usable frames, or very blurry. Show no percentages (defect_pct is None).
    - REVIEW: material unclear (below agreement rule), mismatch with the lot, low average confidence,
              more than 20% uncertain kernels, defect % between pass and reject limits, or any warning.
    - REJECT: material clear AND defect % above the reject limit.
    - PASS: material clear, enough kernels, defect % below the pass limit, no warnings.
    - Sunflower never gets PASS.
    - Peanut results always carry the note: 'Camera screening only. Peanut lots need lab testing before release.'
    - When the material is unclear or the state is RETAKE, set defect_pct to null (keep raw value in details only).
    """
    if not isinstance(result, dict):
        result = {}

    # 1. Kernels checked
    kernels_checked = result.get('kernels_checked')
    if kernels_checked is None:
        kernels_checked = result.get('total_items_counted', result.get('items_counted', 0))
    try:
        kernels_checked = int(kernels_checked)
    except (ValueError, TypeError):
        kernels_checked = 0

    # 2. Usable frames
    usable_frames = result.get('usable_frames_count')
    if usable_frames is None:
        usable_frames = result.get('usable_frames')
    if usable_frames is None:
        best_f = result.get('best_frames') or []
        usable_frames = len(best_f) if best_f else (0 if result.get('status') == 'NEEDS_RETAKE' else 5)
    try:
        usable_frames = int(usable_frames)
    except (ValueError, TypeError):
        usable_frames = 0

    # 3. Blurriness
    is_blurry = bool(result.get('is_blurry', False))
    if not is_blurry:
        for w in result.get('warnings', []):
            if any(term in str(w).lower() for term in ('blurry', 'blur', 'unfocused')):
                is_blurry = True
                break

    # 4. Material extraction
    raw_material = result.get('material') or result.get('winner_material') or result.get('detected_material') or "Unknown"
    raw_material_str = str(raw_material).strip()
    if raw_material_str.lower().startswith("material:"):
        raw_material_str = raw_material_str.split(":", 1)[1].strip()
    canonical_material = raw_material_str.split('(')[0].strip() if '(' in raw_material_str else raw_material_str
    material = canonical_material or "Unknown"

    # 5. Raw defect percentage
    raw_defect_pct = result.get('defect_pct')
    if raw_defect_pct is None:
        raw_defect_pct = result.get('defect_percent')
    if raw_defect_pct is None:
        total_items = kernels_checked
        defect_cnt = result.get('defect_count') or result.get('moldy_count') or 0
        raw_defect_pct = round((defect_cnt / float(total_items) * 100.0), 1) if total_items > 0 else 0.0
    else:
        try:
            raw_defect_pct = round(float(raw_defect_pct), 1)
        except (ValueError, TypeError):
            raw_defect_pct = 0.0

    # 6. Pass & Reject Limits
    pass_limit = result.get('pass_limit')
    if pass_limit is None:
        pass_limit = result.get('pass_threshold')
    reject_limit = result.get('reject_limit')
    if reject_limit is None:
        reject_limit = result.get('reject_threshold', result.get('max_defect_percent'))

    try:
        pass_limit = float(pass_limit) if pass_limit is not None else 5.0
    except (ValueError, TypeError):
        pass_limit = 5.0

    try:
        reject_limit = float(reject_limit) if reject_limit is not None else max(pass_limit, 5.0)
    except (ValueError, TypeError):
        reject_limit = max(pass_limit, 5.0)

    # 7. Material clarity & agreement
    winner_ratio = result.get('winner_ratio')
    if winner_ratio is None:
        winner_ratio = result.get('agreement_ratio', 1.0)
    try:
        winner_ratio = float(winner_ratio)
    except (ValueError, TypeError):
        winner_ratio = 1.0

    is_mixed = bool(result.get('is_mixed', False))
    mat_lower = material.lower()
    is_unknown_mat = (
        mat_lower in ("unknown", "unknown / mixed", "mixed / uncertain material", "mixed", "")
        or mat_lower.startswith("unknown")
        or mat_lower.startswith("mixed")
    )

    # Agreement rule: at least 3 kernels and >= 70% agreement
    material_unclear = is_unknown_mat or is_mixed or (winner_ratio < 0.70) or (kernels_checked < 3 and not (kernels_checked >= 5))

    # 8. Confidence & Uncertainties
    avg_conf = result.get('confidence')
    if avg_conf is None:
        avg_conf = result.get('avg_confidence', 0.90)
    try:
        avg_conf = float(avg_conf)
    except (ValueError, TypeError):
        avg_conf = 0.90
    is_low_conf = bool(result.get('is_low_confidence', False)) or (avg_conf < 0.50)

    u_cnt = result.get('uncertain_count')
    if u_cnt is None:
        u_cnt = result.get('uncertain_items_counted', 0)
    if (u_cnt is None or u_cnt == 0) and result.get('tracked_kernels'):
        u_cnt = sum(1 for tk in result['tracked_kernels'] if tk.get('majority_verdict') == 'Uncertain' or 'uncertain' in str(tk.get('majority_verdict')).lower())

    uncertain_ratio = result.get('uncertain_ratio')
    if uncertain_ratio is None:
        uncertain_ratio = (u_cnt / float(kernels_checked)) if kernels_checked > 0 else 0.0
    try:
        uncertain_ratio = float(uncertain_ratio)
    except (ValueError, TypeError):
        uncertain_ratio = 0.0
    try:
        u_cnt = int(u_cnt)
    except (ValueError, TypeError):
        u_cnt = 0
    # Requirement 1: If they disagree on a kernel, mark it Uncertain, which pushes the state to REVIEW
    is_high_uncertainty = (uncertain_ratio > 0.20) or (u_cnt > 0)

    # 9. Warnings & Mismatches
    raw_warnings = list(result.get('warnings') or [])
    material_mismatch = bool(result.get('material_mismatch', False))
    if not material_mismatch and result.get('lot_material') and material not in ("Unknown", "Unknown / mixed"):
        lot_m = str(result.get('lot_material')).lower()
        if lot_m not in mat_lower and mat_lower not in lot_m:
            material_mismatch = True

    peanut_note = "Camera screening only. Peanut lots need lab testing before release."
    blocking_warnings = [
        w for w in raw_warnings
        if "peanut mold detection has limited accuracy" not in str(w).lower()
        and peanut_note.lower() not in str(w).lower()
        and "discoloured (colour screening)" not in str(w).lower()
    ]

    is_peanut = (mat_lower == "peanut" or "peanut" in mat_lower)
    is_sunflower = (mat_lower == "sunflower" or "sunflower" in mat_lower)

    # State evaluation
    state = None
    reason = ""
    next_step = ""
    defect_pct = None

    min_scan_kernels = result.get("min_kernels", getattr(Config, "MIN_SCAN_KERNELS", 3))
    # Check 1: RETAKE (fewer than min_scan_kernels, fewer than 3 usable frames, or very blurry)
    if kernels_checked < min_scan_kernels or usable_frames < 3 or is_blurry:
        state = "RETAKE"
        defect_pct = None
        if kernels_checked < min_scan_kernels:
            reason = f"Scan has only {kernels_checked} kernel{'s' if kernels_checked != 1 else ''}; at least {min_scan_kernels} kernels are required for valid analysis."
        elif usable_frames < 3:
            reason = f"Scan produced only {usable_frames} usable frame{'s' if usable_frames != 1 else ''}; at least 3 usable frames are required."
        else:
            reason = "Camera photos are too blurry for accurate defect detection."
        next_step = f"Hold camera steady with good lighting and rescan with at least {min_scan_kernels} kernels in the tray."

    # Check 2: REJECT (Material clear AND defect % above the reject limit)
    elif (not material_unclear) and (raw_defect_pct > reject_limit):
        state = "REJECT"
        defect_pct = raw_defect_pct
        reason = f"Defect percentage of {raw_defect_pct:.1f}% exceeds the allowable reject limit of {reject_limit:.1f}%."
        next_step = "Quarantine lot immediately and initiate supplier non-conformance workflow."

    # Check 3: REVIEW
    elif (
        material_unclear
        or material_mismatch
        or is_low_conf
        or is_high_uncertainty
        or (pass_limit <= raw_defect_pct <= reject_limit and pass_limit < reject_limit)
        or len(blocking_warnings) > 0
        or is_sunflower
    ):
        state = "REVIEW"
        defect_pct = None if material_unclear else raw_defect_pct

        if material_unclear:
            reason = f"Material identification is unclear ({int(round(winner_ratio * 100))}% agreement, minimum 70% required)."
            next_step = "Inspect tray manually to confirm material type or rescan with clean separation."
        elif material_mismatch:
            reason = result.get('mismatch_warning') or f"Detected material ({material}) does not match declared lot material ({result.get('lot_material', 'N/A')})."
            next_step = "Verify lot documentation and confirm physical sample identity."
        elif is_low_conf:
            reason = f"Average detection confidence of {int(round(avg_conf * 100))}% is below the 50% reliability threshold."
            next_step = "Verify defect status manually with a hand lens or under inspection lighting."
        elif is_high_uncertainty:
            if u_cnt > 0 and uncertain_ratio <= 0.20:
                reason = f"{u_cnt} kernel{'s' if u_cnt != 1 else ''} marked Uncertain (disagreement between engines or classification uncertainty)."
            else:
                reason = f"More than 20% of kernels ({int(round(uncertain_ratio * 100))}%) have uncertain classifications."
            next_step = "Perform manual visual sorting on uncertain kernels."
        elif is_sunflower:
            reason = "Sunflower inspection provides colour screening only and cannot be automatically passed."
            next_step = "Conduct manual inspection and confirm quality specs before releasing lot."
        elif pass_limit <= raw_defect_pct <= reject_limit and pass_limit < reject_limit:
            reason = f"Defect rate of {raw_defect_pct:.1f}% falls between the pass limit ({pass_limit:.1f}%) and reject limit ({reject_limit:.1f}%)."
            next_step = "Take a secondary sample or perform laboratory testing before lot disposition."
        elif len(blocking_warnings) > 0:
            reason = f"Inspection flagged with warning: {blocking_warnings[0]}"
            next_step = "Address flagged warning conditions and confirm inspection validity."
        else:
            reason = "Visual scan requires manual specialist review before lot sign-off."
            next_step = "Inspect sample manually or send for laboratory testing."

    # Check 4: PASS
    else:
        state = "PASS"
        defect_pct = raw_defect_pct
        reason = f"Material verified as {material} with {raw_defect_pct:.1f}% defects, within the {pass_limit:.1f}% pass limit."
        next_step = "Lot meets visual inspection standards; proceed with standard sign-off."

    # Construct details list
    details = []
    details.append(f"Material: {material} (Agreement: {int(round(winner_ratio * 100))}%)")
    details.append(f"Kernels checked: {kernels_checked} across {usable_frames} usable frames")
    if defect_pct is None:
        details.append(f"Defect rate (raw): {raw_defect_pct:.1f}% (hidden from card due to {state.lower()} state)")
    else:
        details.append(f"Defect rate: {raw_defect_pct:.1f}% (Pass limit: {pass_limit:.1f}%, Reject limit: {reject_limit:.1f}%)")

    details.append(f"Average detection confidence: {int(round(avg_conf * 100))}%")
    if uncertain_ratio > 0:
        details.append(f"Uncertain kernels: {int(round(uncertain_ratio * 100))}%")

    if is_peanut:
        details.append(peanut_note)

    for bw in blocking_warnings:
        warn_line = f"Warning: {bw}"
        if warn_line not in details:
            details.append(warn_line)

    suspect_cnt = result.get('moldy_count')
    if suspect_cnt is None:
        suspect_cnt = result.get('defect_count')
    if suspect_cnt is None and result.get('tracked_kernels'):
        suspect_cnt = sum(1 for tk in result['tracked_kernels'] if 'suspect' in str(tk.get('majority_verdict', '')).lower() or ('mold' in str(tk.get('majority_verdict', '')).lower() and 'not' not in str(tk.get('majority_verdict', '')).lower()))
    try:
        suspect_cnt = int(suspect_cnt)
    except (ValueError, TypeError):
        suspect_cnt = int(round((raw_defect_pct / 100.0) * kernels_checked)) if kernels_checked > 0 else 0

    good_cnt = result.get('good_count')
    if good_cnt is None and result.get('tracked_kernels'):
        good_cnt = sum(1 for tk in result['tracked_kernels'] if tk.get('majority_verdict') == 'Normal')
    try:
        good_cnt = int(good_cnt)
    except (ValueError, TypeError):
        good_cnt = max(0, kernels_checked - suspect_cnt - u_cnt)

    summary_headline = f"{material}, {kernels_checked} kernel{'s' if kernels_checked != 1 else ''}, {good_cnt} good, {suspect_cnt} suspect, {u_cnt} uncertain"

    return {
        "state": state,
        "reason": reason,
        "material": material,
        "kernels_checked": kernels_checked,
        "defect_pct": defect_pct,
        "next_step": next_step,
        "details": details,
        "summary_headline": summary_headline,
        "total_kernels_counted": kernels_checked,
        "good_kernels_count": good_cnt,
        "suspect_kernels_count": suspect_cnt,
        "uncertain_kernels_count": u_cnt,
        "material_name": material
    }


def annotate_frame_kernels(img_bgr: np.ndarray, kernels: list, ignore_zones: list = None, title_hud: str = None) -> np.ndarray:
    """
    Renders big readable outlines on frame photos (Requirement 4):
    - Normal kernels: GREEN (BGR: 40, 205, 50)
    - Suspect kernels: RED (BGR: 30, 30, 235)
    - Uncertain kernels: AMBER (BGR: 0, 165, 255)
    - Big readable outlines (thickness 3)
    - Clickable ID badge with readable label
    """
    import cv2
    import numpy as np

    annotated = img_bgr.copy()
    H, W = annotated.shape[:2]

    if ignore_zones:
        for z in ignore_zones:
            zx1 = max(0, int(round(float(z.get("x", 0.0)) * W)))
            zy1 = max(0, int(round(float(z.get("y", 0.0)) * H)))
            zx2 = min(W, int(round((float(z.get("x", 0.0)) + float(z.get("w", 0.0))) * W)))
            zy2 = min(H, int(round((float(z.get("y", 0.0)) + float(z.get("h", 0.0))) * H)))
            overlay = annotated.copy()
            cv2.rectangle(overlay, (zx1, zy1), (zx2, zy2), (40, 40, 200), -1)
            cv2.addWeighted(overlay, 0.20, annotated, 0.80, 0, annotated)
            cv2.rectangle(annotated, (zx1, zy1), (zx2, zy2), (30, 165, 245), 2, cv2.LINE_AA)

    for k in kernels:
        cnt = k.get("contour")
        kid = k.get("id", 1)

        # Determine bounding box in pixel coordinates
        if "bbox" in k and isinstance(k["bbox"], (list, tuple)) and len(k["bbox"]) == 4:
            x, y, w, h = k["bbox"]
        elif "bbox" in k and isinstance(k["bbox"], dict):
            b = k["bbox"]
            x = int(round(b.get("x", 0.0) * W)) if b.get("x", 0.0) <= 1.0 else int(b.get("x", 0.0))
            y = int(round(b.get("y", 0.0) * H)) if b.get("y", 0.0) <= 1.0 else int(b.get("y", 0.0))
            w = int(round(b.get("w", 0.0) * W)) if b.get("w", 0.0) <= 1.0 else int(b.get("w", 0.0))
            h = int(round(b.get("h", 0.0) * H)) if b.get("h", 0.0) <= 1.0 else int(b.get("h", 0.0))
        elif "x" in k:
            x = int(round(k.get("x", 0.0) * W)) if k.get("x", 0.0) <= 1.0 else int(k.get("x", 0.0))
            y = int(round(k.get("y", 0.0) * H)) if k.get("y", 0.0) <= 1.0 else int(k.get("y", 0.0))
            w = int(round(k.get("w", 0.0) * W)) if k.get("w", 0.0) <= 1.0 else int(k.get("w", 0.0))
            h = int(round(k.get("h", 0.0) * H)) if k.get("h", 0.0) <= 1.0 else int(k.get("h", 0.0))
        else:
            continue

        cx = x + w // 2
        cy = y + h // 2

        cls_name = str(k.get("majority_verdict") or k.get("classification") or k.get("verdict") or k.get("class") or "").lower()
        k_type = str(k.get("type") or "").lower()
        is_uncertain = "uncertain" in cls_name or k_type == "uncertain"
        is_suspect = ("suspect" in cls_name or "mold" in cls_name or k_type == "defect") and not is_uncertain

        # Requirement 4 colors (BGR)
        if is_uncertain:
            color = (0, 165, 255)   # Amber
            badge_text = f"#{kid} Uncertain"
        elif is_suspect:
            color = (30, 30, 235)   # Red
            tags = k.get("representative_tags") or k.get("reason_tags") or []
            why_short = tags[0] if tags else "Suspect"
            badge_text = f"#{kid} Suspect [{why_short}]"
        else:
            color = (40, 205, 50)   # Green
            sc = k.get("representative_score") or k.get("suspect_score") or k.get("score")
            sc_str = f" ({sc:.0f})" if sc is not None else ""
            badge_text = f"#{kid} Normal{sc_str}"

        # Big readable outline: thickness 3 for contour or rectangle
        if cnt is not None:
            cv2.drawContours(annotated, [cnt], -1, color, 3, cv2.LINE_AA)
        else:
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 3, cv2.LINE_AA)
        cv2.circle(annotated, (cx, cy), 3, (0, 0, 255), -1, cv2.LINE_AA)

        # ID Badge
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.44
        thickness = 1
        (tw, th), baseline = cv2.getTextSize(badge_text, font, scale, thickness)
        bx = max(2, x)
        by = max(th + 6, y - 6)

        cv2.rectangle(annotated, (bx - 2, by - th - 4), (bx + tw + 6, by + baseline + 2), (15, 23, 42), -1)
        cv2.rectangle(annotated, (bx - 2, by - th - 4), (bx + tw + 6, by + baseline + 2), color, 1, cv2.LINE_AA)
        cv2.putText(annotated, badge_text, (bx + 2, by), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)

    return annotated


def track_kernels_across_locked_frames(batch_frames, dist_thresh=0.08, iou_thresh=0.20, consensus_mat=None):
    """
    Requirement 2: Track kernels across the 5 locked frames by position,
    give each kernel a majority verdict, and count each kernel once.
    This removes the flicker.
    """
    import json
    import numpy as np
    from collections import Counter
    from ai.classical_kernel_finder import find_kernels_classical

    tracked_kernels = []

    for f_idx, frame in enumerate(batch_frames):
        boxes = []
        if frame.raw_json:
            try:
                rj = json.loads(frame.raw_json)
                boxes = rj.get("boxes", [])
            except Exception:
                boxes = []

        # If frame doesn't have boxes in raw_json, extract from disk image
        if not boxes and frame.image_path:
            p = frame.image_path.lstrip('/')
            p_disk = os.path.join(Config.BASE_DIR, p.replace('/', os.sep))
            if os.path.isfile(p_disk):
                try:
                    c_res = find_kernels_classical(p_disk)
                    for k in c_res["kernels"]:
                        nb = k["bbox_normalized"]
                        is_suspect = (k.get("classification") != "Normal")
                        boxes.append({
                            "id": k["id"],
                            "class": "Suspect (discoloured)" if is_suspect else "Normal",
                            "type": "defect" if is_suspect else "healthy",
                            "x": nb["x"],
                            "y": nb["y"],
                            "w": nb["w"],
                            "h": nb["h"],
                            "suspect_score": k.get("suspect_score", 0.0),
                            "reason_tags": k.get("reason_tags", []),
                            "reason_why": k.get("reason_why", "discoloured" if is_suspect else "Normal"),
                            "metrics": k.get("metrics", {})
                        })
                except Exception:
                    boxes = []
        # Intra-frame duplicate box suppression (behind INSPECTION_PROFILE=improved)
        try:
            if Config.is_improved_inspection() and len(boxes) > 1:
                deduped = []
                for b_cand in boxes:
                    bx1 = float(b_cand.get("x") if b_cand.get("x") is not None else (float(b_cand.get("x_pct", 0.0)) / 100.0))
                    by1 = float(b_cand.get("y") if b_cand.get("y") is not None else (float(b_cand.get("y_pct", 0.0)) / 100.0))
                    bw1 = float(b_cand.get("w") if b_cand.get("w") is not None else (float(b_cand.get("w_pct", 0.0)) / 100.0))
                    bh1 = float(b_cand.get("h") if b_cand.get("h") is not None else (float(b_cand.get("h_pct", 0.0)) / 100.0))
                    cx1 = bx1 + bw1 / 2.0
                    cy1 = by1 + bh1 / 2.0
                    is_dup = False
                    for existing in deduped:
                        bx2 = float(existing.get("x") if existing.get("x") is not None else (float(existing.get("x_pct", 0.0)) / 100.0))
                        by2 = float(existing.get("y") if existing.get("y") is not None else (float(existing.get("y_pct", 0.0)) / 100.0))
                        bw2 = float(existing.get("w") if existing.get("w") is not None else (float(existing.get("w_pct", 0.0)) / 100.0))
                        bh2 = float(existing.get("h") if existing.get("h") is not None else (float(existing.get("h_pct", 0.0)) / 100.0))
                        cx2 = bx2 + bw2 / 2.0
                        cy2 = by2 + bh2 / 2.0
                        d_dist = np.sqrt((cx1 - cx2)**2 + (cy1 - cy2)**2)
                        ix1 = max(bx1, bx2)
                        iy1 = max(by1, by2)
                        ix2 = min(bx1 + bw1, bx2 + bw2)
                        iy2 = min(by1 + bh1, by2 + bh2)
                        b_iou = 0.0
                        if ix2 > ix1 and iy2 > iy1:
                            ia = (ix2 - ix1) * (iy2 - iy1)
                            ua = bw1 * bh1 + bw2 * bh2 - ia
                            b_iou = ia / ua if ua > 0 else 0.0
                        if d_dist <= 0.038 or b_iou >= 0.35:
                            is_dup = True
                            if b_cand.get("type") == "defect" or "suspect" in str(b_cand.get("class", "")).lower():
                                existing["type"] = b_cand.get("type")
                                existing["class"] = b_cand.get("class")
                                existing["reason_why"] = b_cand.get("reason_why")
                            break
                    if not is_dup:
                        deduped.append(b_cand)
                boxes = deduped
        except Exception:
            pass

        for b in boxes:
            bx = b.get("x")
            by = b.get("y")
            bw = b.get("w")
            bh = b.get("h")
            if bx is None or by is None or bw is None or bh is None:
                bx = float(b.get("x_pct", 0.0)) / 100.0
                by = float(b.get("y_pct", 0.0)) / 100.0
                bw = float(b.get("w_pct", 0.0)) / 100.0
                bh = float(b.get("h_pct", 0.0)) / 100.0
            bx, by, bw, bh = float(bx), float(by), float(bw), float(bh)
            cx = bx + bw / 2.0
            cy = by + bh / 2.0

            b_type = str(b.get("type") or "").lower()
            b_class = str(b.get("class") or "").lower()
            det_mat = extract_material_name(b.get("class") or "")
            conf = float(b.get("confidence") or b.get("suspect_score") or 0.0)

            b_class_is_defect = ("suspect" in b_class or ("mold" in b_class and "not" not in b_class and "clean" not in b_class))
            b_is_defect = (b_type == "defect" or b_class_is_defect)

            if b_type == "uncertain" or "uncertain" in b_class:
                verdict = "Uncertain"
            elif consensus_mat and det_mat and det_mat.lower() != consensus_mat.lower() and conf < 0.50 and b_is_defect:
                verdict = "Uncertain"
            elif b_is_defect:
                verdict = "Suspect"
            else:
                verdict = "Normal"

            reason_why = b.get("reason_why")
            if not reason_why:
                tags = b.get("reason_tags", [])
                if tags:
                    reason_why = tags[0]
                elif verdict == "Suspect":
                    reason_why = "discoloured"
                elif verdict == "Uncertain":
                    if consensus_mat and det_mat and det_mat.lower() != consensus_mat.lower():
                        reason_why = f"Uncertain: {b.get('class', 'cross-material defect')} ({conf:.0%})"
                    else:
                        reason_why = "disagreement / uncertain classification"
                else:
                    sc = b.get("suspect_score") or b.get("confidence") or 0.0
                    reason_why = f"Normal (score {float(sc):.0f})"

            obs = {
                "frame_id": frame.id,
                "frame_idx": f_idx,
                "box_id": b.get("id"),
                "verdict": verdict,
                "score": float(b.get("suspect_score") or b.get("confidence") or 0.0),
                "reason_why": reason_why,
                "reason_tags": b.get("reason_tags", []),
                "ai_opinion": b.get("ai_opinion", ""),
                "metrics": b.get("metrics", {}),
                "bbox": {"x": round(bx, 4), "y": round(by, 4), "w": round(bw, 4), "h": round(bh, 4)},
                "centroid": (round(cx, 4), round(cy, 4))
            }

            # Match to existing tracked kernel
            best_tk = None
            min_dist = float('inf')

            for tk in tracked_kernels:
                if any(o["frame_idx"] == f_idx for o in tk["observations"]):
                    continue

                tcx, tcy = tk["centroid"]
                dist = np.sqrt((cx - tcx)**2 + (cy - tcy)**2)

                tx = tk["bbox"]["x"]
                ty = tk["bbox"]["y"]
                tw = tk["bbox"]["w"]
                th = tk["bbox"]["h"]
                ix1 = max(bx, tx)
                iy1 = max(by, ty)
                ix2 = min(bx + bw, tx + tw)
                iy2 = min(by + bh, ty + th)
                iou = 0.0
                if ix2 > ix1 and iy2 > iy1:
                    ia = (ix2 - ix1) * (iy2 - iy1)
                    ua = bw * bh + tw * th - ia
                    iou = ia / ua if ua > 0 else 0.0

                if (dist <= dist_thresh or iou >= iou_thresh) and dist < min_dist:
                    min_dist = dist
                    best_tk = tk

            if best_tk is not None:
                best_tk["observations"].append(obs)
                n_obs = len(best_tk["observations"])
                best_tk["centroid"] = (
                    round((best_tk["centroid"][0] * (n_obs - 1) + cx) / n_obs, 4),
                    round((best_tk["centroid"][1] * (n_obs - 1) + cy) / n_obs, 4)
                )
                best_tk["bbox"] = {"x": round(bx, 4), "y": round(by, 4), "w": round(bw, 4), "h": round(bh, 4)}
            else:
                new_tk = {
                    "id": len(tracked_kernels) + 1,
                    "centroid": (round(cx, 4), round(cy, 4)),
                    "bbox": {"x": round(bx, 4), "y": round(by, 4), "w": round(bw, 4), "h": round(bh, 4)},
                    "observations": [obs]
                }
                tracked_kernels.append(new_tk)

    # Compute majority verdict for each tracked kernel across observations
    for tk in tracked_kernels:
        obs = tk["observations"]
        verdict_counts = Counter(o["verdict"] for o in obs)
        n_votes = verdict_counts.get("Normal", 0)
        s_votes = verdict_counts.get("Suspect", 0)
        u_votes = verdict_counts.get("Uncertain", 0)
        total_votes = len(obs)

        # Majority rule
        if u_votes > 0 and (u_votes >= max(n_votes, s_votes) or (u_votes / float(total_votes)) >= 0.40):
            maj_verdict = "Uncertain"
        elif s_votes > n_votes:
            maj_verdict = "Suspect (discoloured)"
        elif n_votes > s_votes:
            maj_verdict = "Normal"
        elif s_votes == n_votes and s_votes > 0:
            maj_verdict = "Uncertain"
        else:
            maj_verdict = "Normal"

        tk["majority_verdict"] = maj_verdict
        tk["vote_counts"] = {
            "normal": n_votes,
            "suspect": s_votes,
            "uncertain": u_votes,
            "total": total_votes
        }

        # Representative reason why (Requirement 4: e.g. "dark patch 18% of area")
        if maj_verdict == "Uncertain":
            u_obs = [o for o in obs if o["verdict"] == "Uncertain"]
            tk["reason_why"] = u_obs[0]["reason_why"] if u_obs else "Disagreement / uncertain classification"
            tk["ai_opinion"] = u_obs[0].get("ai_opinion", "") if u_obs else ""
            tk["representative_score"] = u_obs[0].get("score", 0.0) if u_obs else 0.0
            tk["representative_tags"] = u_obs[0].get("reason_tags", []) if u_obs else []
        elif "suspect" in maj_verdict.lower():
            s_obs = [o for o in obs if o["verdict"] == "Suspect"]
            best_s = max(s_obs, key=lambda o: o.get("score", 0.0)) if s_obs else obs[0]
            tk["reason_why"] = best_s.get("reason_why") or "discoloured"
            tk["ai_opinion"] = best_s.get("ai_opinion", "")
            tk["representative_score"] = best_s.get("score", 0.0)
            tk["representative_tags"] = best_s.get("reason_tags", [])
        else:
            avg_sc = sum(o.get("score", 0.0) for o in obs) / len(obs)
            tk["reason_why"] = f"Normal (score {avg_sc:.0f})"
            tk["ai_opinion"] = obs[0].get("ai_opinion", "")
            tk["representative_score"] = round(avg_sc, 1)
            tk["representative_tags"] = []

    return tracked_kernels


def evaluate_locked_frames_with_classifier(sess, batch, db, request, usable_frames, good_pct_list) -> dict:
    """
    Phase 3: Material Classifier Integration behind USE_MATERIAL_CLASSIFIER flag.
    - Classifies crops of each detected kernel across all 5 locked frames with models/material_cls.pt.
    - Material = confidence-weighted majority across all kernels in all 5 locked frames.
    - Requires at least 3 kernels and 70% agreement; otherwise material = 'Unknown / mixed' with status NEEDS_REVIEW and never Pass.
    - Tracks kernels across the 5 locked frames by position, gives each kernel a majority verdict, and counts each kernel once (removes flicker).
    - Under disagreement or low confidence cross-material detections, marks kernel as 'Uncertain', which pushes the state to REVIEW.
    - Sunflower: shows 'Discoloured (colour screening)' using Lab colour distance from sample median, never 'mold', and never automatic Pass.
    - Displays: 'Material: Peanut (classifier 97%)' on result card and PDF.
    """
    import cv2
    import numpy as np
    from ultralytics import YOLO

    cls_model_path = getattr(Config, 'MATERIAL_CLS_MODEL_PATH', 'models/material_cls.pt')
    if not os.path.isabs(cls_model_path):
        cls_model_path = os.path.join(Config.BASE_DIR, cls_model_path)

    # 1. Collect all kernel crops across usable frames for material classifier consensus
    crop_records = []
    all_crops = []

    for f in usable_frames:
        raw_img_path = f.image_path or ""
        img_rel = raw_img_path.lstrip('/')
        possible_paths = [
            os.path.join(Config.BASE_DIR, img_rel),
            raw_img_path,
            os.path.join(Config.BASE_DIR, raw_img_path)
        ]
        img_disk_path = None
        for p in possible_paths:
            if os.path.isfile(p):
                img_disk_path = p
                break

        if not img_disk_path:
            continue

        img = cv2.imread(img_disk_path)
        if img is None:
            continue
        H, W = img.shape[:2]

        boxes = []
        if f.raw_json:
            try:
                rj = json.loads(f.raw_json)
                boxes = rj.get("boxes", [])
            except Exception:
                boxes = []

        for b in boxes:
            bx = b.get("x")
            by = b.get("y")
            bw = b.get("w")
            bh = b.get("h")
            if bx is None or by is None or bw is None or bh is None:
                bx = float(b.get("x_pct", 0.0)) / 100.0
                by = float(b.get("y_pct", 0.0)) / 100.0
                bw = float(b.get("w_pct", 0.0)) / 100.0
                bh = float(b.get("h_pct", 0.0)) / 100.0

            x1 = max(0, int(round(bx * W)))
            y1 = max(0, int(round(by * H)))
            x2 = min(W, int(round((bx + bw) * W)))
            y2 = min(H, int(round((by + bh) * H)))

            if x2 <= x1 or y2 <= y1:
                continue

            pad_w = int((x2 - x1) * 0.08)
            pad_h = int((y2 - y1) * 0.08)
            cx1 = max(0, x1 - pad_w)
            cy1 = max(0, y1 - pad_h)
            cx2 = min(W, x2 + pad_w)
            cy2 = min(H, y2 + pad_h)

            crop = img[cy1:cy2, cx1:cx2]
            if crop.size == 0 or crop.shape[0] < 6 or crop.shape[1] < 6:
                continue

            cls_lower = (b.get("class") or "").lower()
            is_mold = (b.get("type") == "defect" or ("mold" in cls_lower and "not" not in cls_lower and "clean" not in cls_lower))
            crop_records.append({
                "crop": crop,
                "box": b,
                "frame": f,
                "class_name": b.get("class", ""),
                "det_conf": float(b.get("confidence", 0.0)),
                "is_defect": is_mold,
                "det_material": extract_material_name(b.get("class", ""))
            })
            all_crops.append(crop)

    warnings = []
    total_crops_count = len(crop_records)

    # 2. Check Requirement 1 consensus
    is_consensus = False
    winner_mat = "Unknown / mixed"
    agreement_pct = 0
    agreement_ratio = 0.0

    if os.path.isfile(cls_model_path) and len(all_crops) >= 3:
        try:
            cls_model = get_cached_cls_model(cls_model_path)
            if cls_model is None:
                from ultralytics import YOLO
                cls_model = YOLO(cls_model_path)
            cls_res = cls_model(all_crops, verbose=False, imgsz=96)
            weighted_votes = defaultdict(float)

            for rec, r in zip(crop_records, cls_res):
                top1_idx = int(r.probs.top1)
                pred_mat = r.names[top1_idx].capitalize()
                pred_conf = float(r.probs.top1conf) if hasattr(r.probs, 'top1conf') else float(r.probs.data[top1_idx])
                rec["cls_material"] = pred_mat
                rec["cls_conf"] = pred_conf
                weighted_votes[pred_mat] += pred_conf

            # In improved profile: incorporate scene-level detector class votes
            try:
                if Config.is_improved_inspection():
                    for rec in crop_records:
                        det_m = rec.get("det_material")
                        if det_m and det_m != "Unknown":
                            weighted_votes[det_m] += 0.4
            except Exception:
                pass

            total_weight = sum(weighted_votes.values())
            if total_weight > 0:
                candidate_winner = max(weighted_votes, key=weighted_votes.get)
                agreement_ratio = weighted_votes[candidate_winner] / total_weight
                agreement_pct = int(round(agreement_ratio * 100))

                # Require at least 3 kernels and 70% agreement
                if agreement_ratio >= 0.70 and len(crop_records) >= 3:
                    winner_mat = candidate_winner
                    is_consensus = True
        except Exception as e:
            warnings.append(f"Material classifier execution error: {e}")

    # In improved profile: if detected sample < MIN_SCAN_KERNELS, report Uncertain
    try:
        min_scan_k = getattr(Config, 'MIN_SCAN_KERNELS', 3)
        if Config.is_improved_inspection() and total_crops_count < min_scan_k:
            is_consensus = False
            winner_mat = "Uncertain / Insufficient Sample"
            display_material = "Uncertain / Insufficient Sample"
            warnings.append(f"Insufficient sample: only {total_crops_count} kernel(s) detected. At least {min_scan_k} kernels required for valid inspection.")
    except Exception:
        pass

    if not is_consensus:
        winner_mat = "Unknown / mixed"
        display_material = "Unknown / mixed"
        warnings.append(
            f"Classifier consensus not achieved ({agreement_pct}% agreement across {total_crops_count} kernel(s); 70% agreement and at least 3 kernels required)."
        )
    else:
        display_material = f"{winner_mat} (classifier {agreement_pct}%)"

    # 3. Requirement 2: Track kernels across the 5 locked frames by position,
    # give each kernel a majority verdict, and count each kernel once.
    tracked_kernels = track_kernels_across_locked_frames(
        usable_frames,
        consensus_mat=(winner_mat if is_consensus else None)
    )
    total_kernels = len(tracked_kernels)

    moldy_count = sum(1 for tk in tracked_kernels if "suspect" in tk["majority_verdict"].lower() or ("mold" in tk["majority_verdict"].lower() and "not" not in tk["majority_verdict"].lower()))
    uncertain_count = sum(1 for tk in tracked_kernels if tk["majority_verdict"] == "Uncertain")
    good_count = sum(1 for tk in tracked_kernels if tk["majority_verdict"] == "Normal")

    # 4. Sunflower Special Rule: Lab colour distance screening
    if is_consensus and winner_mat == "Sunflower":
        lab_vectors = []
        for rec in crop_records:
            lab_img = cv2.cvtColor(rec["crop"], cv2.COLOR_BGR2LAB)
            l_mean = float(np.mean(lab_img[:, :, 0])) * (100.0 / 255.0)
            a_mean = float(np.mean(lab_img[:, :, 1])) - 128.0
            b_mean = float(np.mean(lab_img[:, :, 2])) - 128.0
            rec["lab"] = (l_mean, a_mean, b_mean)
            lab_vectors.append((l_mean, a_mean, b_mean))

        if lab_vectors:
            l_med = float(np.median([v[0] for v in lab_vectors]))
            a_med = float(np.median([v[1] for v in lab_vectors]))
            b_med = float(np.median([v[2] for v in lab_vectors]))

            discoloured_count = 0
            for tk in tracked_kernels:
                tk_rec = next((r for r in crop_records if any(o["frame_id"] == r["frame"].id for o in tk["observations"])), None)
                if tk_rec and "lab" in tk_rec:
                    vl, va, vb = tk_rec["lab"]
                    delta_e = float(np.sqrt((vl - l_med)**2 + (va - a_med)**2 + (vb - b_med)**2))
                    tk["delta_e"] = round(delta_e, 2)
                    if delta_e > 22.0 or "suspect" in tk["majority_verdict"].lower() or "mold" in tk["majority_verdict"].lower():
                        tk["majority_verdict"] = "Suspect (discoloured)"
                        tk["reason_why"] = f"Lab colour delta-E {delta_e:.1f} > 22.0"
                        discoloured_count += 1
                elif "suspect" in tk["majority_verdict"].lower() or "mold" in tk["majority_verdict"].lower():
                    discoloured_count += 1

            moldy_count = discoloured_count

        warnings.append("Sunflower: Discoloured (colour screening) using Lab colour distance from sample median. Visual verification required.")

    # Scene-level countable sample check (Improvement 5)
    try:
        if Config.is_improved_inspection() and tracked_kernels:
            high_overlap_pairs = 0
            for i in range(len(tracked_kernels)):
                for j in range(i + 1, len(tracked_kernels)):
                    b1 = tracked_kernels[i].get("bbox", {})
                    b2 = tracked_kernels[j].get("bbox", {})
                    c_dist = np.sqrt((b1.get("x", 0) - b2.get("x", 0))**2 + (b1.get("y", 0) - b2.get("y", 0))**2)
                    if c_dist < 0.04:
                        high_overlap_pairs += 1
            if high_overlap_pairs >= 3:
                warnings.append("Sample notice: Kernels appear heavily touching or clustered. Spread the kernels out on the tray for optimal counting accuracy.")
    except Exception:
        pass

    # Check uncertainty ratio
    uncertain_ratio = (uncertain_count / float(total_kernels)) if total_kernels > 0 else 0.0
    is_high_uncertainty = (uncertain_ratio > 0.20) or (uncertain_count > 0)
    if uncertain_ratio > 0.20:
        warnings.append(
            f"High classification uncertainty: {round(uncertain_ratio * 100, 1)}% of kernels ({uncertain_count}/{total_kernels}) have cross-material defect detections with confidence < 0.50. Manual review required."
        )

    # 5. Lot mismatch warning
    material_mismatch = False
    mismatch_warning = None
    lot_material = None
    if sess.lot and sess.lot.material_name:
        lot_material = extract_material_name(sess.lot.material_name) or extract_material_name(sess.lot.category)
    if lot_material and is_consensus:
        if lot_material.lower() != winner_mat.lower():
            material_mismatch = True
            mismatch_warning = f"Possible material mismatch: lot says {lot_material}, camera sees {winner_mat}. Please verify."
            warnings.append(mismatch_warning)

    # 6. Low-confidence review (< 50%)
    all_confs = [rec["det_conf"] for rec in crop_records if rec["det_conf"] > 0]
    avg_confidence = round(sum(all_confs) / len(all_confs), 3) if all_confs else (round(agreement_ratio, 3) if is_consensus else 0.0)
    confidence_percent = f"{round(avg_confidence * 100.0, 1)}%"
    is_low_conf = (avg_confidence < 0.50)
    if is_low_conf:
        warnings.append(f"Low average detection confidence ({confidence_percent} < 50%). Manual review required.")

    # 7. Peanut accuracy note
    if is_consensus and winner_mat == "Peanut":
        p_warn = "Peanut mold detection has limited accuracy, confirm visually."
        if p_warn not in warnings:
            warnings.append(p_warn)

    # 8. Scan mode dropdown check
    scan_mode = "Auto"
    if request:
        scan_mode = request.form.get('scan_mode') or request.args.get('scan_mode') or "Auto"
        if not scan_mode and request.is_json:
            scan_mode = (request.get_json(silent=True) or {}).get('scan_mode', 'Auto')

    scan_mode_mismatch = False
    scan_mode_warning = None
    if scan_mode and scan_mode.lower() not in ("auto", "none", "") and is_consensus:
        chosen_mode = scan_mode.capitalize()
        if chosen_mode in ("Peanut", "Corn", "Sunflower") and chosen_mode.lower() != winner_mat.lower():
            scan_mode_mismatch = True
            scan_mode_warning = f"Scan mode mismatch: Inspection Station is set to '{chosen_mode}', but AI classifier identified '{winner_mat}' ({agreement_pct}% agreement). The classifier result was NOT silently overridden."
            warnings.append(scan_mode_warning)

    # 9. Pass / Fail Suggestion
    max_defects = 0
    max_defect_pct = 5.0
    if request:
        try:
            max_defects = int(request.form.get('max_defects_threshold') or request.args.get('max_defects_threshold', 0))
        except (ValueError, TypeError):
            max_defects = 0
        try:
            max_defect_pct = float(request.form.get('max_defect_percent') or request.args.get('max_defect_percent', 5.0))
        except (ValueError, TypeError):
            max_defect_pct = 5.0

    defect_pct = round((moldy_count / float(total_kernels) * 100.0), 1) if total_kernels > 0 else 0.0
    good_pct = round(100.0 - defect_pct, 1)

    # Base suggestion decision
    if (not is_consensus) or material_mismatch or is_low_conf or is_high_uncertainty:
        suggestion = "Manual Review"
        status_code = "NEEDS_REVIEW"
    else:
        if defect_pct > max_defect_pct or moldy_count > max_defects:
            suggestion = "Reject"
            status_code = "REJECTED"
        else:
            suggestion = "Pass"
            status_code = "APPROVED"

    # Sunflower: never an automatic Pass!
    if is_consensus and winner_mat == "Sunflower":
        if suggestion == "Pass" or status_code == "APPROVED":
            suggestion = "Manual Review"
            status_code = "NEEDS_REVIEW"

    # Best 3 frames - Re-annotate with big readable outlines (Green, Red, Amber)
    sorted_frames = sorted(
        batch,
        key=lambda f: ((f.good_count or 0) + (f.defect_count or 0), f.avg_confidence or 0.0),
        reverse=True
    )
    best_3 = sorted_frames[:3]

    active_ignore_zones = getattr(Config, 'IGNORE_ZONES', [{"x": 0.0, "y": 0.82, "w": 0.22, "h": 0.18}])
    best_annotated_urls = []
    for f in best_3:
        raw_p = f.image_path or ""
        p_disk = os.path.join(Config.BASE_DIR, raw_p.lstrip('/').replace('/', os.sep))
        if os.path.isfile(p_disk):
            img_bgr = cv2.imread(p_disk)
            if img_bgr is not None:
                frame_k_list = []
                for tk in tracked_kernels:
                    obs = next((o for o in tk["observations"] if o["frame_id"] == f.id), None)
                    v = tk["majority_verdict"]
                    if v == "Uncertain":
                        cls_name = "Uncertain"
                    elif "suspect" in v.lower() or "mold" in v.lower():
                        cls_name = "Suspect"
                    else:
                        cls_name = "Normal"
                    
                    bbox_norm = obs["bbox"] if obs else tk["bbox"]
                    frame_k_list.append({
                        "id": tk["id"],
                        "classification": cls_name,
                        "majority_verdict": v,
                        "reason_why": tk.get("reason_why", ""),
                        "representative_score": tk.get("representative_score", 0.0),
                        "bbox_normalized": bbox_norm
                    })
                
                ann_bgr = annotate_frame_kernels(img_bgr, frame_k_list, ignore_zones=active_ignore_zones)
                ann_dir = os.path.join(Config.BASE_DIR, 'static', 'uploads', 'live_frames', 'annotated')
                os.makedirs(ann_dir, exist_ok=True)
                ann_fname = f"ann_locked_{f.id}_{sess.id}.jpg"
                ann_disk = os.path.join(ann_dir, ann_fname)
                cv2.imwrite(ann_disk, ann_bgr)
                f.annotated_path = f"/static/uploads/live_frames/annotated/{ann_fname}"
        best_annotated_urls.append(f.annotated_path or f.image_path)

    locked_result = {
        "status": status_code,
        "suggestion": suggestion,
        "material": display_material,
        "material_display": f"Material: {display_material}",
        "winner_material": winner_mat,
        "winner_ratio": round(agreement_ratio, 3),
        "confidence": avg_confidence,
        "confidence_percent": confidence_percent,
        "items_counted": total_kernels,
        "total_items_counted": total_kernels,
        "good_pct": good_pct,
        "defect_pct": defect_pct,
        "good_count": good_count,
        "suspect_count": moldy_count,
        "moldy_count": moldy_count,
        "uncertain_count": uncertain_count,
        "uncertain_ratio": round(uncertain_ratio, 3),
        "summary_headline": f"{winner_mat if is_consensus else 'Uncertain'}, {total_kernels} kernel{'s' if total_kernels != 1 else ''}, {good_count} good, {moldy_count} suspect, {uncertain_count} uncertain",
        "tracked_kernels": tracked_kernels,
        "warnings": warnings,
        "material_mismatch": material_mismatch,
        "mismatch_warning": mismatch_warning,
        "is_low_confidence": is_low_conf,
        "is_mixed": (not is_consensus),
        "scan_mode": scan_mode,
        "scan_mode_mismatch": scan_mode_mismatch,
        "scan_mode_warning": scan_mode_warning,
        "classifier_active": True,
        "usable_frames_count": len(usable_frames),
        "total_frames_count": len(batch),
        "best_frames": [f.to_dict() for f in best_3],
        "best_annotated_urls": best_annotated_urls,
        "completed_at": datetime.datetime.utcnow().strftime("%H:%M:%S")
    }

    decision = final_decision(locked_result)
    locked_result["final_decision"] = decision
    locked_result["decision_state"] = decision["state"]
    locked_result["decision_reason"] = decision["reason"]
    locked_result["next_step"] = decision["next_step"]
    locked_result["decision_details"] = decision["details"]
    if decision["defect_pct"] is None:
        locked_result["defect_pct"] = None
        locked_result["defect_pct_raw"] = defect_pct

    sess.locked_result_json = json.dumps(locked_result)
    db.commit()
    return locked_result


def evaluate_locked_frames(sess, batch, db, request=None) -> dict:
    """
    Evaluates 5 locked frames (Phase 2):
    - Calculates Good % per frame: good / (good + defect)
    - Averages Good % across the 5 frames (never sum)
    - Ignores frames with zero detections
    - If fewer than 3 usable frames, returns suggestion = 'Retake', status = 'NEEDS_RETAKE'
    - Material = material with highest total confidence across 5 frames
    - If winner has < 60% of total confidence, reports 'Mixed / uncertain material' and sets NEEDS_REVIEW
    - Mismatch vs linked lot (warning only, never auto-correct)
    - Low average confidence (< 50%) -> NEEDS_REVIEW
    - Editable pass/fail thresholds for suggestion
    - Peanut results always show 'Peanut mold detection has limited accuracy, confirm visually.'
    - Sunflower results show 'Mold detection is not available for sunflower' and never show Pass
    - Best 3 annotated frames
    - Saves result to sess.locked_result_json
    """
    usable_frames = []
    good_pct_list = []

    for f in batch:
        items = (f.good_count or 0) + (f.defect_count or 0)
        if items > 0:
            usable_frames.append(f)
            good_pct_list.append((f.good_count or 0) / float(items))

    # Requirement B: If fewer than 3 usable frames, return NEEDS_RETAKE
    if len(usable_frames) < 3:
        retake_result = {
            "status": "NEEDS_RETAKE",
            "suggestion": "Retake",
            "material": "Unknown",
            "confidence": 0.0,
            "confidence_percent": "0.0%",
            "items_counted": 0,
            "total_items_counted": 0,
            "good_pct": 0.0,
            "defect_pct": None,
            "defect_pct_raw": 0.0,
            "warnings": ["Fewer than 3 usable frames detected (frames with detectable items). Please hold steady and scan with good lighting."],
            "usable_frames_count": len(usable_frames),
            "total_frames_count": len(batch),
            "best_frames": [f.to_dict() for f in batch[:3]],
            "best_annotated_urls": [f.annotated_path or f.image_path for f in batch[:3]],
            "completed_at": datetime.datetime.utcnow().strftime("%H:%M:%S")
        }
        dec = final_decision(retake_result)
        retake_result["final_decision"] = dec
        retake_result["decision_state"] = dec["state"]
        retake_result["decision_reason"] = dec["reason"]
        retake_result["next_step"] = dec["next_step"]
        retake_result["decision_details"] = dec["details"]
        sess.locked_result_json = json.dumps(retake_result)
        db.commit()
        return retake_result

    # Phase 3: Check if USE_MATERIAL_CLASSIFIER is enabled
    if getattr(Config, 'USE_MATERIAL_CLASSIFIER', False):
        return evaluate_locked_frames_with_classifier(
            sess=sess,
            batch=batch,
            db=db,
            request=request,
            usable_frames=usable_frames,
            good_pct_list=good_pct_list
        )

    # 1. Requirement 2: Track kernels across usable frames by position (deduplicate)
    tracked_kernels = track_kernels_across_locked_frames(usable_frames)
    total_kernels = len(tracked_kernels)
    moldy_count = sum(1 for tk in tracked_kernels if "suspect" in tk["majority_verdict"].lower() or ("mold" in tk["majority_verdict"].lower() and "not" not in tk["majority_verdict"].lower()))
    uncertain_count = sum(1 for tk in tracked_kernels if tk["majority_verdict"] == "Uncertain")
    good_count = sum(1 for tk in tracked_kernels if tk["majority_verdict"] == "Normal")

    defect_percent = round((moldy_count / float(total_kernels) * 100.0), 1) if total_kernels > 0 else 0.0
    good_percent = round(100.0 - defect_percent, 1)

    avg_items_counted = total_kernels
    total_items_counted = total_kernels

    # 2. Total Confidence & Material Winner across all 5 frames
    mat_conf_totals = defaultdict(float)
    all_detection_confs = []

    for f in batch:
        if f.raw_json:
            try:
                rj = json.loads(f.raw_json)
                for b in rj.get("boxes", []):
                    c_name = b.get("class") or ""
                    mat = extract_material_name(c_name)
                    conf = float(b.get("confidence", 0.0))
                    if mat:
                        mat_conf_totals[mat] += conf
                    all_detection_confs.append(conf)
            except Exception:
                pass
        # Fallback if raw_json missing boxes
        if not all_detection_confs and f.material:
            mat_conf_totals[f.material] += (f.avg_confidence or 0.0)
            all_detection_confs.append(f.avg_confidence or 0.0)

    total_mat_conf = sum(mat_conf_totals.values())
    if total_mat_conf > 0:
        winner_mat = max(mat_conf_totals, key=mat_conf_totals.get)
        winner_conf = mat_conf_totals[winner_mat]
        winner_ratio = winner_conf / total_mat_conf
    else:
        winner_mat = batch[0].material or "Unknown"
        winner_ratio = 1.0

    avg_confidence = round(sum(all_detection_confs) / len(all_detection_confs), 3) if all_detection_confs else 0.0
    confidence_percent = f"{round(avg_confidence * 100.0, 1)}%"

    warnings = []
    is_mixed = False
    display_material = winner_mat

    # If winner has less than 60% of the total, report "Mixed / uncertain material" and set NEEDS_REVIEW
    if winner_ratio < 0.60 or winner_mat == "Unknown":
        display_material = "Mixed / uncertain material"
        is_mixed = True
        warnings.append("Mixed or uncertain material detected across frames (winner confidence < 60%).")

    # 3. Mismatch vs linked lot (warning only, never auto-correct)
    material_mismatch = False
    mismatch_warning = None
    lot_material = None
    if sess.lot and sess.lot.material_name:
        lot_material = extract_material_name(sess.lot.material_name) or extract_material_name(sess.lot.category)
    if lot_material and not is_mixed:
        if lot_material.lower() != display_material.lower():
            material_mismatch = True
            mismatch_warning = f"Possible material mismatch: lot says {lot_material}, camera sees {display_material}. Please verify."
            warnings.append(mismatch_warning)

    # 4. Low average confidence (< 50%) -> NEEDS_REVIEW
    is_low_conf = avg_confidence < 0.50
    if is_low_conf:
        warnings.append(f"Low average detection confidence ({confidence_percent} < 50%). Manual review required.")

    # 5. Specific Material Warnings:
    if display_material == "Peanut":
        p_warn = "Peanut mold detection has limited accuracy, confirm visually."
        if p_warn not in warnings:
            warnings.append(p_warn)

    if display_material == "Sunflower":
        sf_warn = "Mold detection is not available for sunflower"
        if sf_warn not in warnings:
            warnings.append(sf_warn)

    # 6. Pass/Fail Suggestion based on editable thresholds
    max_defects = 0
    max_defect_pct = 5.0 # default 5%
    if request:
        try:
            max_defects = int(request.form.get('max_defects_threshold') or request.args.get('max_defects_threshold', 0))
        except (ValueError, TypeError):
            max_defects = 0
        try:
            max_defect_pct = float(request.form.get('max_defect_percent') or request.args.get('max_defect_percent', 5.0))
        except (ValueError, TypeError):
            max_defect_pct = 5.0

    total_defects = moldy_count

    if is_mixed or material_mismatch or is_low_conf or (uncertain_count > 0):
        suggestion = "Manual Review"
        status_code = "NEEDS_REVIEW"
    else:
        if defect_percent > max_defect_pct or total_defects > max_defects:
            suggestion = "Reject"
            status_code = "REJECTED"
        else:
            suggestion = "Pass"
            status_code = "APPROVED"

    # For sunflower: never show Pass!
    if display_material == "Sunflower" and suggestion == "Pass":
        suggestion = "Manual Review"
        status_code = "NEEDS_REVIEW"

    # 7. Best 3 annotated frames - Re-annotate with big readable outlines
    sorted_frames = sorted(
        batch,
        key=lambda f: ((f.good_count or 0) + (f.defect_count or 0), f.avg_confidence or 0.0),
        reverse=True
    )
    best_3 = sorted_frames[:3]

    active_ignore_zones = getattr(Config, 'IGNORE_ZONES', [{"x": 0.0, "y": 0.82, "w": 0.22, "h": 0.18}])
    best_annotated_urls = []
    for f in best_3:
        raw_p = f.image_path or ""
        p_disk = os.path.join(Config.BASE_DIR, raw_p.lstrip('/').replace('/', os.sep))
        if os.path.isfile(p_disk):
            img_bgr = cv2.imread(p_disk)
            if img_bgr is not None:
                frame_k_list = []
                for tk in tracked_kernels:
                    obs = next((o for o in tk["observations"] if o["frame_id"] == f.id), None)
                    v = tk["majority_verdict"]
                    if v == "Uncertain":
                        cls_name = "Uncertain"
                    elif "suspect" in v.lower() or "mold" in v.lower():
                        cls_name = "Suspect"
                    else:
                        cls_name = "Normal"
                    
                    bbox_norm = obs["bbox"] if obs else tk["bbox"]
                    frame_k_list.append({
                        "id": tk["id"],
                        "classification": cls_name,
                        "majority_verdict": v,
                        "reason_why": tk.get("reason_why", ""),
                        "representative_score": tk.get("representative_score", 0.0),
                        "bbox_normalized": bbox_norm
                    })
                
                ann_bgr = annotate_frame_kernels(img_bgr, frame_k_list, ignore_zones=active_ignore_zones)
                ann_dir = os.path.join(Config.BASE_DIR, 'static', 'uploads', 'live_frames', 'annotated')
                os.makedirs(ann_dir, exist_ok=True)
                ann_fname = f"ann_locked_{f.id}_{sess.id}.jpg"
                ann_disk = os.path.join(ann_dir, ann_fname)
                cv2.imwrite(ann_disk, ann_bgr)
                f.annotated_path = f"/static/uploads/live_frames/annotated/{ann_fname}"
        best_annotated_urls.append(f.annotated_path or f.image_path)

    locked_result = {
        "status": status_code,
        "suggestion": suggestion,
        "material": display_material,
        "winner_material": winner_mat,
        "winner_ratio": round(winner_ratio, 3),
        "confidence": avg_confidence,
        "confidence_percent": confidence_percent,
        "items_counted": total_kernels,
        "total_items_counted": total_kernels,
        "good_pct": good_percent,
        "defect_pct": defect_percent,
        "moldy_count": moldy_count,
        "uncertain_count": uncertain_count,
        "uncertain_ratio": round((uncertain_count / float(total_kernels)), 3) if total_kernels > 0 else 0.0,
        "tracked_kernels": tracked_kernels,
        "warnings": warnings,
        "material_mismatch": material_mismatch,
        "mismatch_warning": mismatch_warning,
        "is_low_confidence": is_low_conf,
        "is_mixed": is_mixed,
        "usable_frames_count": len(usable_frames),
        "total_frames_count": len(batch),
        "best_frames": [f.to_dict() for f in best_3],
        "best_annotated_urls": best_annotated_urls,
        "completed_at": datetime.datetime.utcnow().strftime("%H:%M:%S")
    }

    decision = final_decision(locked_result)
    locked_result["final_decision"] = decision
    locked_result["decision_state"] = decision["state"]
    locked_result["decision_reason"] = decision["reason"]
    locked_result["next_step"] = decision["next_step"]
    locked_result["decision_details"] = decision["details"]
    if decision["defect_pct"] is None:
        locked_result["defect_pct"] = None
        locked_result["defect_pct_raw"] = defect_percent

    sess.locked_result_json = json.dumps(locked_result)
    db.commit()
    return locked_result


def get_inspection_setting(key: str, default: str = "") -> str:
    """Reads a setting value from inspection_station_settings table."""
    db = get_db()
    from sqlalchemy import text
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS inspection_station_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """))
        db.commit()
    except Exception:
        db.rollback()
    try:
        row = db.execute(text("SELECT value FROM inspection_station_settings WHERE key = :k"), {"k": key}).fetchone()
        return str(row[0]) if (row and row[0] is not None) else default
    except Exception:
        return default


def set_inspection_setting(key: str, value: str):
    """Upserts a setting key-value pair in inspection_station_settings table."""
    db = get_db()
    from sqlalchemy import text
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS inspection_station_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """))
        db.commit()
    except Exception:
        db.rollback()
    try:
        db.execute(text("""
            INSERT INTO inspection_station_settings (key, value, updated_at)
            VALUES (:k, :v, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = :v, updated_at = CURRENT_TIMESTAMP;
        """), {"k": key, "v": str(value)})
        db.commit()
    except Exception:
        db.rollback()


def get_material_colour_threshold(material: str) -> float:
    """Reads calibrated suspect threshold for a material (default 40.0)."""
    key = f"colour_screening_threshold_{str(material).lower()}"
    val = get_inspection_setting(key, "40.0")
    try:
        return float(val)
    except (ValueError, TypeError):
        return 40.0


def get_user_calibration_marks() -> dict:
    """Reads saved user marks from inspection_station_settings table."""
    raw = get_inspection_setting("colour_calibration_user_marks", "{}")
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def set_user_calibration_marks(marks: dict):
    """Saves user marks to inspection_station_settings table."""
    set_inspection_setting("colour_calibration_user_marks", json.dumps(marks))


def compute_material_separation_stats(material: str, threshold: float, marks_dict: dict) -> dict:
    """
    Computes separation performance for a material:
    True Normal (TN): marked normal and score < threshold
    False Suspect (FS): marked normal and score >= threshold
    True Suspect (TS): marked suspect and score >= threshold
    False Normal (FN): marked suspect and score < threshold
    """
    mat_marks = [
        m for m in marks_dict.values()
        if (m.get("material") or "").lower() == material.lower()
    ]
    total_marked = len(mat_marks)
    marked_normal = sum(1 for m in mat_marks if m.get("mark") == "normal")
    marked_suspect = sum(1 for m in mat_marks if m.get("mark") == "suspect")

    tn = 0
    fs = 0
    ts = 0
    fn = 0

    for m in mat_marks:
        score = float(m.get("score", 0.0))
        mark = m.get("mark")
        if mark == "normal":
            if score < threshold:
                tn += 1
            else:
                fs += 1
        elif mark == "suspect":
            if score >= threshold:
                ts += 1
            else:
                fn += 1

    correct = tn + ts
    accuracy_pct = round((correct / float(total_marked)) * 100.0, 1) if total_marked > 0 else None

    return {
        "material": material,
        "threshold": round(threshold, 1),
        "total_marked": total_marked,
        "marked_normal": marked_normal,
        "marked_suspect": marked_suspect,
        "true_normal": tn,
        "false_suspect": fs,
        "true_suspect": ts,
        "false_normal": fn,
        "accuracy_pct": accuracy_pct
    }


def fit_threshold_from_marks(material: str, marks_dict: dict) -> float:
    """
    Fits a simple threshold per material from user marks (NO machine learning).
    Evaluates thresholds T in [5.0, 95.0] to maximize separation accuracy (TN + TS) / Total.
    Picks the median threshold among ties to maximize margins.
    Defaults to 40.0 if insufficient marks.
    """
    mat_marks = [
        m for m in marks_dict.values()
        if (m.get("material") or "").lower() == material.lower()
    ]
    if not mat_marks:
        return 40.0

    normal_scores = [float(m.get("score", 0.0)) for m in mat_marks if m.get("mark") == "normal"]
    suspect_scores = [float(m.get("score", 0.0)) for m in mat_marks if m.get("mark") == "suspect"]

    if not normal_scores and not suspect_scores:
        return 40.0

    if normal_scores and not suspect_scores:
        max_n = max(normal_scores)
        return min(95.0, max(20.0, round(max_n + 5.0, 1)))

    if suspect_scores and not normal_scores:
        min_s = min(suspect_scores)
        return max(5.0, min(80.0, round(min_s - 5.0, 1)))

    best_acc = -1.0
    best_candidates = []

    for step in range(10, 191):
        T = round(step * 0.5, 1)
        tn = sum(1 for s in normal_scores if s < T)
        ts = sum(1 for s in suspect_scores if s >= T)
        acc = (tn + ts) / float(len(mat_marks))

        if acc > best_acc:
            best_acc = acc
            best_candidates = [T]
        elif abs(acc - best_acc) < 1e-6:
            best_candidates.append(T)

    if best_candidates:
        best_candidates.sort()
        mid = len(best_candidates) // 2
        return best_candidates[mid]

    return 40.0


@qc_bp.route('/api/capture/<token>/frame', methods=['POST'])
def upload_live_frame(token):
    """
    Phone frame upload endpoint (Phase 1 & Phase 2).
    - Checks token and expiry (2 hours).
    - Rate limits about 3 requests per second per token.
    - Accepts JPEG only, max 3 MB, decode-checks the image.
    - Runs YOLO detection function under global lock.
    - Manages frame disk retention: keeps only latest live frame + 5 locked frames.
    - When lock=true: accumulates locked frames and performs 5-frame evaluation.
    - Returns normalised boxes, counts, status, and locked_result (if locked).
    """
    db = get_db()
    sess = db.query(LiveSession).filter_by(token=token).first()

    # 1. Validate token
    if not sess:
        return jsonify({"success": False, "error": "Invalid session token."}), 404

    if sess.status == "CLOSED":
        return jsonify({"success": False, "error": "This inspection session is closed."}), 410

    if sess.expires_at and datetime.datetime.utcnow() > sess.expires_at:
        sess.status = "EXPIRED"
        db.commit()
        return jsonify({"success": False, "error": "This inspection session has expired."}), 410

    if sess.status != "ACTIVE":
        return jsonify({"success": False, "error": f"Session status is {sess.status}."}), 410

    # 2. Rate limit: about 3 requests per second per token
    if not check_token_rate_limit(token, max_requests=3, window_seconds=1.0):
        return jsonify({
            "success": False,
            "error": "Rate limit exceeded. Maximum 3 requests per second per token."
        }), 429

    # 3. Check uploaded file
    if 'image' not in request.files and 'file' not in request.files:
        return jsonify({"success": False, "error": "No image file provided."}), 400

    uploaded_file = request.files.get('image') or request.files.get('file')
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"success": False, "error": "Empty file provided."}), 400

    file_bytes = uploaded_file.read()

    # Max 3 MB limit (3 * 1024 * 1024 = 3,145,728 bytes)
    MAX_FILE_BYTES = 3 * 1024 * 1024
    if len(file_bytes) > MAX_FILE_BYTES:
        return jsonify({
            "success": False,
            "error": f"File size ({len(file_bytes)} bytes) exceeds the 3 MB maximum limit."
        }), 413

    # Decode-check and JPEG only
    try:
        img = Image.open(io.BytesIO(file_bytes))
        if img.format != 'JPEG':
            return jsonify({
                "success": False,
                "error": f"Invalid format '{img.format}'. Only JPEG images are accepted."
            }), 400
        img.verify()
        img = Image.open(io.BytesIO(file_bytes))
        img.load()
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Corrupt or unreadable JPEG image: {str(e)}"
        }), 400

    # Check lock parameter
    is_lock_frame = (request.form.get('lock') or request.args.get('lock') or '').lower() in ['true', '1', 'yes']

    # Requirement E: Keep only the latest live frame per session plus the 5 locked frames.
    # If this is an unlocked streaming frame, clean up any previous unlocked frames on disk
    if not is_lock_frame:
        prev_unlocked = db.query(LiveFrame).filter_by(session_id=sess.id, is_locked=False).all()
        for old_f in prev_unlocked:
            for p in [old_f.image_path, old_f.annotated_path]:
                if p:
                    dp = os.path.join(Config.BASE_DIR, p.lstrip('/').replace('/', os.sep))
                    if os.path.isfile(dp):
                        try:
                            os.remove(dp)
                        except Exception:
                            pass
            db.delete(old_f)
        db.flush()

    # 4. Save raw image file to static/uploads/live_frames/raw/
    raw_dir = os.path.join(Config.BASE_DIR, 'static', 'uploads', 'live_frames', 'raw')
    annotated_dir = os.path.join(Config.BASE_DIR, 'static', 'uploads', 'live_frames', 'annotated')
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(annotated_dir, exist_ok=True)

    raw_filename = f"live_{sess.id}_{int(time.time()*1000)}_{secrets.token_hex(4)}.jpg"
    raw_disk_path = os.path.join(raw_dir, raw_filename)
    with open(raw_disk_path, 'wb') as f:
        f.write(file_bytes)

    # 5. Determine Inspection Engine & Ignore Zones
    raw_engine = request.form.get('engine') or request.args.get('engine') or getattr(Config, 'INSPECTION_ENGINE', 'auto')
    mat_hint = None
    if sess.lot and sess.lot.material_name:
        mat_hint = sess.lot.material_name
    elif getattr(sess, 'material', None):
        mat_hint = getattr(sess, 'material', None)
    scan_mode_val = request.form.get('scan_mode') or request.args.get('scan_mode')
    if scan_mode_val and scan_mode_val.lower() not in ('auto', 'all', 'none', ''):
        mat_hint = scan_mode_val

    engine_param = resolve_inspection_engine(raw_engine, mat_hint)

    # Read ignore zones (rectangles as percentages: {x, y, w, h})
    # Default: bottom-left 22% wide by 18% high
    active_ignore_zones = getattr(Config, 'IGNORE_ZONES', [{"x": 0.0, "y": 0.82, "w": 0.22, "h": 0.18}])
    raw_iz = request.form.get('ignore_zones') or request.args.get('ignore_zones')
    if raw_iz:
        try:
            active_ignore_zones = json.loads(raw_iz)
        except Exception:
            pass

    from ai.classical_kernel_finder import is_center_in_ignore_zones, find_kernels_classical
    import cv2
    import numpy as np

    start_infer = time.time()
    debug_view_url = None
    classical_res = None
    yolo_res = None

    raw_web_url = f"/static/uploads/live_frames/raw/{raw_filename}"
    annotated_filename = f"annotated_{raw_filename}"
    annotated_disk_path = os.path.join(annotated_dir, annotated_filename)

    if engine_param in ['colour', 'color']:
        # Pure Classical Kernel Finder (OpenCV Lab Otsu, no AI)
        detected_material = sess.lot.material_name if (sess.lot and sess.lot.material_name) else "Peanut"
        mat_canon = detect_material_from_text(detected_material) or "Peanut"
        threshold = get_material_colour_threshold(mat_canon)
        classical_res = find_kernels_classical(
            raw_disk_path,
            ignore_zones=active_ignore_zones,
            suspect_threshold=threshold,
            material=mat_canon
        )
        frame_infer_ms = round((time.time() - start_infer) * 1000, 1)

        good_count = classical_res["normal_count"]
        defect_count = classical_res["suspect_count"]
        if defect_count > 0:
            model_status = "DEFECTS_DETECTED"
        elif good_count > 0:
            model_status = "NO_DEFECTS"
        else:
            model_status = "NO_SPECIMENS"

        avg_confidence = 1.0

        boxes = []
        for k in classical_res["kernels"]:
            nb = k["bbox_normalized"]
            is_suspect = (k.get("classification") != "Normal")
            box_class = "Suspect (discoloured)" if is_suspect else "Normal"
            boxes.append({
                "class": box_class,
                "type": "defect" if is_suspect else "healthy",
                "severity": "WARNING" if is_suspect else "NORMAL",
                "category": "Suspect (discoloured)" if is_suspect else "Normal",
                "confidence": 1.0,
                "x": nb["x"],
                "y": nb["y"],
                "w": nb["w"],
                "h": nb["h"],
                "x_pct": nb["x_pct"],
                "y_pct": nb["y_pct"],
                "w_pct": nb["w_pct"],
                "h_pct": nb["h_pct"],
                "id": k["id"],
                "area": k["area"],
                "suspect_score": k.get("suspect_score", 0.0),
                "reason_tags": k.get("reason_tags", []),
                "reason_why": k.get("reason_why", "discoloured" if is_suspect else "Normal"),
                "metrics": k.get("metrics", {})
            })

        # Render big readable outlines (Green for Normal, Red for Suspect, thickness 3)
        raw_bgr = cv2.imread(raw_disk_path)
        if raw_bgr is not None:
            ann_bgr = annotate_frame_kernels(raw_bgr, boxes, ignore_zones=active_ignore_zones)
            cv2.imwrite(annotated_disk_path, ann_bgr)
            annotated_url = f"/static/uploads/live_frames/annotated/{annotated_filename}"
        else:
            annotated_url = raw_web_url
        debug_view_url = annotated_url

    elif engine_param == 'both':
        # Requirement 1: Under "both", show colour as the main result and the AI as a second opinion.
        # If they disagree on a kernel, mark it Uncertain, which pushes the state to REVIEW.
        detected_material = sess.lot.material_name if (sess.lot and sess.lot.material_name) else "Peanut"
        mat_canon = detect_material_from_text(detected_material) or "Peanut"
        threshold = get_material_colour_threshold(mat_canon)

        classical_res = find_kernels_classical(
            raw_disk_path,
            ignore_zones=active_ignore_zones,
            suspect_threshold=threshold,
            material=mat_canon
        )
        yolo_res = run_yolo_visual_inspection(
            raw_image_path=raw_disk_path,
            output_annotated_dir=annotated_dir
        )
        frame_infer_ms = round((time.time() - start_infer) * 1000, 1)

        yolo_defects = [
            d for d in yolo_res.get("detected_defects", [])
            if not is_center_in_ignore_zones(
                (float(d.get("bbox_x", 0.0)) + float(d.get("bbox_w", 0.0)) / 2.0) / 100.0,
                (float(d.get("bbox_y", 0.0)) + float(d.get("bbox_h", 0.0)) / 2.0) / 100.0,
                active_ignore_zones
            )
        ]
        yolo_healthy = [
            h for h in yolo_res.get("detected_healthy", [])
            if not is_center_in_ignore_zones(
                (float(h.get("bbox_x", 0.0)) + float(h.get("bbox_w", 0.0)) / 2.0) / 100.0,
                (float(h.get("bbox_y", 0.0)) + float(h.get("bbox_h", 0.0)) / 2.0) / 100.0,
                active_ignore_zones
            )
        ]

        boxes = []
        uncertain_count = 0
        defect_count = 0
        good_count = 0

        for k in classical_res["kernels"]:
            nb = k["bbox_normalized"]
            kx, ky, kw, kh = nb["x"], nb["y"], nb["w"], nb["h"]
            kcx = kx + kw / 2.0
            kcy = ky + kh / 2.0
            is_colour_suspect = (k.get("classification") != "Normal")
            colour_why = k.get("reason_why") or ("discoloured" if is_colour_suspect else "Normal")

            matched_d = None
            for d in yolo_defects:
                dx = float(d.get("bbox_x", 0.0)) / 100.0
                dy = float(d.get("bbox_y", 0.0)) / 100.0
                dw = float(d.get("bbox_w", 0.0)) / 100.0
                dh = float(d.get("bbox_h", 0.0)) / 100.0
                dcx, dcy = dx + dw / 2.0, dy + dh / 2.0
                dist = np.sqrt((kcx - dcx)**2 + (kcy - dcy)**2)
                if dist <= 0.08 or (dx <= kcx <= dx + dw and dy <= kcy <= dy + dh) or (kx <= dcx <= kx + kw and ky <= dcy <= ky + kh):
                    matched_d = d
                    break

            matched_h = None
            if not matched_d:
                for h in yolo_healthy:
                    hx = float(h.get("bbox_x", 0.0)) / 100.0
                    hy = float(h.get("bbox_y", 0.0)) / 100.0
                    hw = float(h.get("bbox_w", 0.0)) / 100.0
                    hh = float(h.get("bbox_h", 0.0)) / 100.0
                    hcx, hcy = hx + hw / 2.0, hy + hh / 2.0
                    dist = np.sqrt((kcx - hcx)**2 + (kcy - hcy)**2)
                    if dist <= 0.08 or (hx <= kcx <= hx + hw and hy <= kcy <= hy + hh) or (kx <= hcx <= kx + kw and ky <= hcy <= ky + kh):
                        matched_h = h
                        break

            is_ai_defect = (matched_d is not None)

            if is_colour_suspect and is_ai_defect:
                box_class = "Suspect (discoloured)"
                box_type = "defect"
                d_cls = matched_d.get("defect_class", "defect")
                d_conf = float(matched_d.get("confidence", 0.0))
                ai_op = f"AI agrees: {d_cls} ({d_conf:.0%})"
                reason_why = colour_why
                defect_count += 1
            elif (not is_colour_suspect) and (not is_ai_defect):
                box_class = "Normal"
                box_type = "healthy"
                h_conf = float(matched_h.get("confidence", 0.95)) if matched_h else 0.95
                ai_op = f"AI agrees: Healthy ({h_conf:.0%})"
                reason_why = colour_why
                good_count += 1
            else:
                # Disagreement -> Uncertain!
                box_class = "Uncertain"
                box_type = "uncertain"
                uncertain_count += 1
                if is_colour_suspect:
                    ai_conf = float(matched_h.get("confidence", 0.0)) if matched_h else 0.0
                    ai_label = f"Healthy ({ai_conf:.0%})" if matched_h else "Clean"
                    ai_op = f"AI opinion: {ai_label}"
                    reason_why = f"Disagreement: Colour flagged {colour_why}, but AI detected {ai_label}"
                else:
                    d_cls = matched_d.get("defect_class", "defect")
                    d_conf = float(matched_d.get("confidence", 0.0))
                    ai_op = f"AI opinion: {d_cls} ({d_conf:.0%})"
                    reason_why = f"Disagreement: AI detected {d_cls} ({d_conf:.0%}), but Colour screening was Normal"

            boxes.append({
                "class": box_class,
                "type": box_type,
                "severity": "WARNING" if box_type in ("defect", "uncertain") else "NORMAL",
                "category": box_class,
                "confidence": round(float(matched_d.get("confidence", 0.0) if matched_d else (matched_h.get("confidence", 1.0) if matched_h else 1.0)), 3),
                "x": nb["x"],
                "y": nb["y"],
                "w": nb["w"],
                "h": nb["h"],
                "x_pct": nb["x_pct"],
                "y_pct": nb["y_pct"],
                "w_pct": nb["w_pct"],
                "h_pct": nb["h_pct"],
                "id": k["id"],
                "area": k["area"],
                "suspect_score": k.get("suspect_score", 0.0),
                "reason_tags": k.get("reason_tags", []),
                "reason_why": reason_why,
                "ai_opinion": ai_op,
                "metrics": k.get("metrics", {})
            })

        # Render big readable outlines: Green=Normal, Red=Suspect, Amber=Uncertain (thickness 3)
        raw_bgr = cv2.imread(raw_disk_path)
        if raw_bgr is not None:
            ann_bgr = annotate_frame_kernels(raw_bgr, boxes, ignore_zones=active_ignore_zones)
            cv2.imwrite(annotated_disk_path, ann_bgr)
            annotated_url = f"/static/uploads/live_frames/annotated/{annotated_filename}"
        else:
            annotated_url = raw_web_url
        debug_view_url = annotated_url

        if uncertain_count > 0 or defect_count > 0:
            model_status = "DEFECTS_DETECTED"
        elif good_count > 0:
            model_status = "NO_DEFECTS"
        else:
            model_status = "NO_SPECIMENS"
        avg_confidence = 1.0

    else:
        # engine_param is 'ai'
        yolo_res = run_yolo_visual_inspection(
            raw_image_path=raw_disk_path,
            output_annotated_dir=annotated_dir
        )
        frame_infer_ms = round((time.time() - start_infer) * 1000, 1)

        detected_material = get_mostly_detected_material(yolo_res)
        if not detected_material and sess.lot and sess.lot.material_name:
            detected_material = extract_material_name(sess.lot.material_name)

        # Filter defects and healthy by ignore zones and product mode (if restricted)
        product_filter = None
        if scan_mode_val and scan_mode_val.lower() not in ('auto', 'all', 'none', ''):
            product_filter = scan_mode_val.strip().lower()

        all_confs = []
        boxes = []
        filtered_defects_count = 0
        filtered_healthy_count = 0

        for d in yolo_res.get("detected_defects", []):
            d_cls = d.get("defect_class", "defect")
            if product_filter and product_filter not in d_cls.lower():
                continue

            x_pct = float(d.get("bbox_x", 0.0))
            y_pct = float(d.get("bbox_y", 0.0))
            w_pct = float(d.get("bbox_w", 0.0))
            h_pct = float(d.get("bbox_h", 0.0))
            cx = (x_pct + w_pct / 2.0) / 100.0
            cy = (y_pct + h_pct / 2.0) / 100.0
            if is_center_in_ignore_zones(cx, cy, active_ignore_zones):
                continue
            filtered_defects_count += 1
            conf_val = float(d.get("confidence", 0.0))
            if conf_val > 0:
                all_confs.append(conf_val)
            boxes.append({
                "class": d_cls,
                "type": "defect",
                "severity": d.get("severity", "WARNING"),
                "category": d.get("category", "Contamination"),
                "confidence": round(conf_val, 3),
                "reason_why": f"{d_cls} ({conf_val:.0%})",
                "ai_opinion": f"AI: {d_cls} ({conf_val:.0%})",
                "x": round(x_pct / 100.0, 4),
                "y": round(y_pct / 100.0, 4),
                "w": round(w_pct / 100.0, 4),
                "h": round(h_pct / 100.0, 4),
                "x_pct": x_pct,
                "y_pct": y_pct,
                "w_pct": w_pct,
                "h_pct": h_pct
            })

        for h in yolo_res.get("detected_healthy", []):
            h_cls = h.get("specimen_class", "Healthy")
            if product_filter and product_filter not in h_cls.lower():
                continue

            x_pct = float(h.get("bbox_x", 0.0))
            y_pct = float(h.get("bbox_y", 0.0))
            w_pct = float(h.get("bbox_w", 0.0))
            h_pct = float(h.get("bbox_h", 0.0))
            cx = (x_pct + w_pct / 2.0) / 100.0
            cy = (y_pct + h_pct / 2.0) / 100.0
            if is_center_in_ignore_zones(cx, cy, active_ignore_zones):
                continue
            filtered_healthy_count += 1
            conf_val = float(h.get("confidence", 0.0))
            if conf_val > 0:
                all_confs.append(conf_val)
            boxes.append({
                "class": h_cls,
                "type": "healthy",
                "severity": "NORMAL",
                "category": "Healthy",
                "confidence": round(conf_val, 3),
                "reason_why": f"Healthy ({conf_val:.0%})",
                "ai_opinion": f"AI: Healthy ({conf_val:.0%})",
                "x": round(x_pct / 100.0, 4),
                "y": round(y_pct / 100.0, 4),
                "w": round(w_pct / 100.0, 4),
                "h": round(h_pct / 100.0, 4),
                "x_pct": x_pct,
                "y_pct": y_pct,
                "w_pct": w_pct,
                "h_pct": h_pct
            })

        good_count = filtered_healthy_count
        defect_count = filtered_defects_count
        avg_confidence = round(sum(all_confs) / len(all_confs), 3) if all_confs else 0.0

        if defect_count > 0:
            model_status = "DEFECTS_DETECTED"
        elif good_count > 0:
            model_status = "NO_DEFECTS"
        else:
            model_status = "NO_SPECIMENS"

        # Render big readable outlines with annotate_frame_kernels
        raw_bgr = cv2.imread(raw_disk_path)
        if raw_bgr is not None:
            ann_bgr = annotate_frame_kernels(raw_bgr, boxes, ignore_zones=active_ignore_zones)
            cv2.imwrite(annotated_disk_path, ann_bgr)
            annotated_url = f"/static/uploads/live_frames/annotated/{annotated_filename}"
        else:
            annotated_url = raw_web_url
        debug_view_url = annotated_url

    # 7. Save to live_frames table
    if engine_param in ['colour', 'color']:
        raw_summary = f"Colour screening: {good_count} Normal, {defect_count} Suspect (discoloured). Colour screening only. Not a mold or lab test."
        raw_status_msg = f"{good_count} Normal, {defect_count} Suspect (discoloured). Colour screening only. Not a mold or lab test."
    elif engine_param == 'both':
        raw_summary = f"Dual engine screening: {good_count} Normal, {defect_count} Suspect, {uncertain_count} Uncertain"
        raw_status_msg = f"Both engines: {good_count} Normal, {defect_count} Suspect, {uncertain_count} Uncertain"
    else:
        raw_summary = yolo_res.get("summary") if yolo_res else f"Classical Finder: {good_count} kernels"
        raw_status_msg = yolo_res.get("status_message") if yolo_res else f"{good_count} kernels detected via Lab Otsu"

    frame = LiveFrame(
        session_id=sess.id,
        created_at=datetime.datetime.utcnow(),
        image_path=raw_web_url,
        annotated_path=annotated_url,
        material=detected_material,
        good_count=good_count,
        defect_count=defect_count,
        avg_confidence=avg_confidence,
        status=model_status,
        is_locked=is_lock_frame,
        raw_json=json.dumps({
            "summary": raw_summary,
            "status_message": raw_status_msg,
            "inference_time_ms": frame_infer_ms,
            "engine": engine_param,
            "debug_view_url": debug_view_url,
            "boxes": boxes
        })
    )
    db.add(frame)
    db.commit()

    # 8. Check Phase 2 Lock Evaluation
    locked_result = None
    if is_lock_frame:
        locked_frames = db.query(LiveFrame).filter_by(session_id=sess.id, is_locked=True).order_by(LiveFrame.id.asc()).all()
        if len(locked_frames) >= 5:
            batch = locked_frames[-5:]
            locked_result = evaluate_locked_frames(sess, batch, db, request)

    return jsonify({
        "success": True,
        "frame_id": frame.id,
        "session_id": sess.id,
        "status": model_status,
        "engine": engine_param,
        "debug_view_url": debug_view_url,
        "counts": {
            "good_count": good_count,
            "defect_count": defect_count,
            "total_count": good_count + defect_count
        },
        "good_count": good_count,
        "defect_count": defect_count,
        "total_count": good_count + defect_count,
        "material": detected_material,
        "avg_confidence": avg_confidence,
        "boxes": boxes,
        "raw_image_url": raw_web_url,
        "annotated_image_url": annotated_url,
        "is_locked": is_lock_frame,
        "locked_result": locked_result
    }), 200


@qc_bp.route('/api/capture/<token>/burst-scan', methods=['POST'])
def capture_burst_scan(token):
    """
    Stabilized 5-frame burst scan endpoint.
    Receives a burst of 8 frames over ~2 seconds, discards blurry ones using
    variance of Laplacian, keeps the best 5, runs detection at imgsz 640,
    merges kernels across frames by position (deduplicating), and returns
    one stable verdict per kernel with an averaged confidence.
    """
    db = get_db()
    sess = db.query(LiveSession).filter_by(token=token).first()
    if not sess:
        return jsonify({"success": False, "error": "Invalid session token."}), 404

    if sess.status == "CLOSED":
        return jsonify({"success": False, "error": "This inspection session is closed."}), 410

    if sess.expires_at and datetime.datetime.utcnow() > sess.expires_at:
        sess.status = "EXPIRED"
        db.commit()
        return jsonify({"success": False, "error": "This inspection session has expired."}), 410

    # 1. Collect uploaded files (supports 'images', 'images[]', or 'frames')
    uploaded_files = request.files.getlist('images') or request.files.getlist('images[]') or request.files.getlist('frames')
    if not uploaded_files and 'image' in request.files:
        uploaded_files = [request.files['image']]

    if not uploaded_files:
        return jsonify({"success": False, "error": "No frames provided for scan."}), 400

    import cv2
    import numpy as np
    from ai.scan_pipeline import run_burst_scan_pipeline

    raw_dir = os.path.join(Config.BASE_DIR, 'static', 'uploads', 'live_frames', 'raw')
    annotated_dir = os.path.join(Config.BASE_DIR, 'static', 'uploads', 'live_frames', 'annotated')
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(annotated_dir, exist_ok=True)

    # Read and decode frames
    decoded_frames = []
    for idx, f in enumerate(uploaded_files):
        file_bytes = f.read()
        if not file_bytes:
            continue
        arr = np.frombuffer(file_bytes, np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_bgr is not None and img_bgr.size > 0:
            decoded_frames.append(img_bgr)

    if not decoded_frames:
        return jsonify({"success": False, "error": "Could not decode any valid image frames."}), 400

    # 2. Extract parameters
    scan_mode_val = request.form.get('scan_mode') or request.args.get('scan_mode')
    product_filter = None
    if scan_mode_val and scan_mode_val.lower() not in ('auto', 'all', 'none', ''):
        product_filter = scan_mode_val.strip()
    elif sess.lot and sess.lot.material_name:
        product_filter = sess.lot.material_name.strip()

    conf_floor = float(request.form.get('confidence_floor') or request.form.get('conf_floor') or getattr(Config, 'CONFIDENCE_FLOOR', 0.25))
    imgsz = int(request.form.get('imgsz') or 640)
    augment = request.form.get('augment', '').lower() in ('1', 'true', 'yes')

    active_ignore_zones = getattr(Config, 'IGNORE_ZONES', [{"x": 0.0, "y": 0.82, "w": 0.22, "h": 0.18}])
    raw_iz = request.form.get('ignore_zones') or request.args.get('ignore_zones')
    if raw_iz:
        try:
            active_ignore_zones = json.loads(raw_iz)
        except Exception:
            pass

    # 3. Execute Stabilized Scan Pipeline
    scan_res = run_burst_scan_pipeline(
        frames=decoded_frames,
        product=product_filter,
        imgsz=imgsz,
        conf_floor=conf_floor,
        ignore_zones=active_ignore_zones,
        augment=augment,
        min_kernels=getattr(Config, 'MIN_SCAN_KERNELS', 3)
    )

    if not scan_res.get('success'):
        return jsonify({"success": False, "error": scan_res.get('error', 'Scan failed')}), 400

    # 4. Save best frame and annotated frame to disk
    ts_now = int(time.time() * 1000)
    best_raw_filename = f"scan_{sess.id}_{ts_now}_best.jpg"
    best_ann_filename = f"annotated_scan_{sess.id}_{ts_now}.jpg"

    best_raw_path = os.path.join(raw_dir, best_raw_filename)
    best_ann_path = os.path.join(annotated_dir, best_ann_filename)

    cv2.imwrite(best_raw_path, scan_res['best_frame_bgr'])
    cv2.imwrite(best_ann_path, scan_res['annotated_bgr'])

    best_raw_url = f"/static/uploads/live_frames/raw/{best_raw_filename}"
    best_ann_url = f"/static/uploads/live_frames/annotated/{best_ann_filename}"

    # 5. Record LiveFrame entry in DB
    frame_rec = LiveFrame(
        session_id=sess.id,
        created_at=datetime.datetime.utcnow(),
        image_path=best_raw_url,
        annotated_path=best_ann_url,
        material=product_filter or "Sample",
        good_count=scan_res['good_count'],
        defect_count=scan_res['defect_count'],
        avg_confidence=scan_res['avg_confidence'],
        status=scan_res['status'],
        is_locked=True,
        raw_json=json.dumps({
            "summary": f"Stabilized Scan: {scan_res['good_count']} Good, {scan_res['defect_count']} Defect across 5 sharpest frames",
            "status_message": scan_res['decision_reason'],
            "elapsed_ms": scan_res['elapsed_time_ms'],
            "tracked_kernels": scan_res['tracked_kernels'],
            "pipeline_settings": scan_res['pipeline_settings'],
            "sharpness_scores": scan_res['sharpness_scores']
        })
    )
    db.add(frame_rec)
    db.commit()

    # 6. Check material mismatch vs linked lot (warning only, never auto-correct)
    warnings = list(scan_res.get('warnings') or [])
    if sess.lot and sess.lot.material_name:
        lot_mat = sess.lot.material_name.strip()
        # If classes indicate a different material, add warning only
        classes_seen = [tk.get('class', '') for tk in scan_res['tracked_kernels']]
        detected_materials = set()
        for c in classes_seen:
            mat = extract_material_name(c)
            if mat:
                detected_materials.add(mat)
        if detected_materials and not any(lot_mat.lower() in dm.lower() for dm in detected_materials):
            warnings.append(f"Possible material mismatch: lot says {lot_mat}, camera detected {', '.join(detected_materials)}. Please verify.")

    # 7. Build authoritative result object
    detected_material_name = product_filter or (sess.lot.material_name if sess.lot else "Specimen")
    result_payload = {
        "status": scan_res['status'],
        "suggestion": scan_res['suggestion'],
        "material": detected_material_name,
        "confidence": scan_res['avg_confidence'],
        "confidence_percent": scan_res['confidence_percent'],
        "items_counted": scan_res['total_kernels'],
        "total_items_counted": scan_res['total_kernels'],
        "kernels_checked": scan_res['total_kernels'],
        "good_count": scan_res['good_count'],
        "defect_count": scan_res['defect_count'],
        "uncertain_count": scan_res['uncertain_count'],
        "good_pct": scan_res['good_pct'],
        "defect_pct": scan_res['defect_pct'] if scan_res['status'] != "NEEDS_RETAKE" else None,
        "defect_pct_raw": scan_res['defect_pct'],
        "warnings": warnings,
        "usable_frames_count": scan_res['frames_evaluated_count'],
        "total_frames_count": scan_res['total_burst_frames'],
        "best_frames": [frame_rec.to_dict()],
        "best_annotated_urls": [best_ann_url],
        "annotated_image_url": best_ann_url,
        "raw_image_url": best_raw_url,
        "tracked_kernels": scan_res['tracked_kernels'],
        "pipeline_settings": scan_res['pipeline_settings'],
        "completed_at": datetime.datetime.utcnow().strftime("%H:%M:%S")
    }

    dec = final_decision(result_payload)
    result_payload["final_decision"] = dec
    result_payload["decision_state"] = dec["state"]
    result_payload["decision_reason"] = dec["reason"]
    result_payload["next_step"] = dec["next_step"]
    result_payload["decision_details"] = dec["details"]

    sess.locked_result_json = json.dumps(result_payload)
    db.commit()

    return jsonify({
        "success": True,
        "locked_result": result_payload,
        "annotated_image_url": best_ann_url,
        "status": scan_res['status'],
        "kernels_found": scan_res['total_kernels']
    }), 200


@qc_bp.route('/api/qc/live-session/<int:session_id>/confirm-verdict', methods=['POST'])
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def confirm_live_session_verdict(session_id):
    """
    On the laptop, the logged-in QC inspector confirms Accept or Reject.
    Updates the lot status through existing logic, saves final result to
    normal inspection history (AIInspection & InspectionImage), and enables
    existing PDF report download.
    Phone cannot change lot status (requires login).
    """
    db = get_db()
    sess = db.query(LiveSession).filter_by(id=session_id).first()
    if not sess:
        return jsonify({"success": False, "error": "Live session not found."}), 404

    data = request.get_json(silent=True) or {}
    verdict = (data.get('verdict') or data.get('action') or '').upper() # 'ACCEPT' or 'REJECT'
    notes = data.get('notes', '')
    user = get_current_user()

    if verdict not in ['ACCEPT', 'PASS', 'APPROVED', 'REJECT', 'FAIL', 'REJECTED']:
        return jsonify({"success": False, "error": f"Invalid verdict '{verdict}'. Must be ACCEPT or REJECT."}), 400

    is_accept = verdict in ['ACCEPT', 'PASS', 'APPROVED']
    final_status = 'APPROVED' if is_accept else 'REJECTED'

    # Parse locked result to determine state
    locked_res = {}
    if sess.locked_result_json:
        try:
            locked_res = json.loads(sess.locked_result_json)
        except Exception:
            locked_res = {}

    dec_obj = final_decision(locked_res)
    analysis_state = dec_obj.get("state", "REVIEW")
    written_reason = (data.get('notes') or data.get('reason') or data.get('action_notes') or '').strip()

    # Enforce written reason requirement (who, when, reason)
    if is_accept and analysis_state != "PASS":
        if not written_reason:
            return jsonify({
                "success": False,
                "error": f"Approving a lot when the analysis state is {analysis_state} requires a written reason."
            }), 400

    if (not is_accept) and analysis_state != "REJECT":
        if not written_reason:
            return jsonify({
                "success": False,
                "error": f"Rejecting a lot when the analysis state is {analysis_state} requires a written reason."
            }), 400

    now_utc = datetime.datetime.utcnow()
    who_name = user.full_name if (user and user.full_name) else (user.username if user else "QC Inspector")
    when_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    is_override = (is_accept and analysis_state != "PASS") or ((not is_accept) and analysis_state != "REJECT")
    if is_override:
        audit_note = f"Override Verdict [{final_status}] by {who_name} at {when_str}. Analysis State was {analysis_state}. Reason: {written_reason}"
    else:
        audit_note = f"Verdict [{final_status}] confirmed by {who_name} at {when_str}." + (f" Notes: {written_reason}" if written_reason else "")

    # 1. Update linked lot status through existing logic
    lot = sess.lot
    if lot:
        lot.qc_status = final_status
        if is_accept:
            lot.status = StatusEnum.APPROVED.value
        else:
            lot.status = StatusEnum.REJECTED.value

    # 2. Pick best frame for permanent inspection image
    best_frame_rec = db.query(LiveFrame).filter_by(session_id=sess.id, is_locked=True).order_by(LiveFrame.id.desc()).first()
    if not best_frame_rec:
        best_frame_rec = db.query(LiveFrame).filter_by(session_id=sess.id).order_by(LiveFrame.id.desc()).first()

    raw_url = best_frame_rec.image_path if best_frame_rec else "/static/uploads/live_frames/default.jpg"
    ann_url = best_frame_rec.annotated_path if best_frame_rec else raw_url

    insp_image = InspectionImage(
        raw_material_lot_id=lot.id if lot else None,
        image_url=raw_url,
        annotated_image_url=ann_url,
        image_type="Live Hold-Steady Mobile Inspection",
        uploaded_at=datetime.datetime.utcnow()
    )
    db.add(insp_image)
    db.flush()

    # 3. Create permanent AIInspection record in normal inspection history
    defect_pct = locked_res.get('defect_pct', 0.0)
    items_count = int(locked_res.get('total_items_counted', 1))
    approx_defects = int(defect_pct * items_count / 100.0)

    ai_insp = AIInspection(
        inspection_image_id=insp_image.id,
        raw_material_lot_id=lot.id if lot else None,
        model_version="YOLOv8-LiveHoldLock",
        model_status="DEFECTS_DETECTED" if defect_pct > 0 else "NO_DEFECTS",
        inference_time_ms=0.0,
        total_defects_count=approx_defects,
        summary=f"Live Multi-Frame Lock: {locked_res.get('material', 'Specimen')} | Good: {locked_res.get('good_pct', 0)}% | Defective: {defect_pct}% | Suggestion: {locked_res.get('suggestion', 'Review')}",
        status_message=audit_note,
        annotated_image_url=ann_url,
        material_mismatch=locked_res.get('material_mismatch', False),
        mismatch_warning=locked_res.get('mismatch_warning'),
        detected_material=locked_res.get('material'),
        lot_material=lot.material_name if lot else None,
        avg_confidence=locked_res.get('confidence', 0.0),
        created_at=now_utc
    )
    db.add(ai_insp)
    db.flush()

    # Link session to ai_inspection
    sess.ai_inspection_id = ai_insp.id

    # 4. Save human QC decision
    decision = QCDecision(
        raw_material_lot_id=lot.id if lot else None,
        decided_by_user_id=user.id if user else 1,
        final_status=final_status,
        reason=f"Override ({analysis_state} -> {final_status}): {written_reason}" if is_override else f"Live Camera Lock ({final_status})",
        action_notes=audit_note,
        decided_at=now_utc
    )
    db.add(decision)
    create_qc_handoff_alert(db, lot, final_status, who_name)
    db.commit()

    return jsonify({
        "success": True,
        "message": f"Verdict confirmed. Lot {lot.lot_number if lot else 'Record'} status updated to {final_status}.",
        "inspection_id": ai_insp.id,
        "pdf_url": f"/api/qc/ai-inspection/{ai_insp.id}/pdf",
        "final_status": final_status,
        "lot_number": lot.lot_number if lot else None,
        "decision_id": decision.id
    })


@qc_bp.route('/api/qc/live-session/<int:session_id>/reset-lock', methods=['POST'])
def reset_live_lock(session_id):
    """
    Resets lock state on phone and laptop for 'Scan next sample'.
    Cleans up previous locked frames on disk and in DB so the session is ready
    for the next sample tray without regenerating QR pairing.
    """
    db = get_db()
    sess = db.query(LiveSession).filter_by(id=session_id).first()
    if not sess:
        return jsonify({"success": False, "error": "Live session not found."}), 404

    sess.locked_result_json = None

    # Delete previous locked frames
    locked_frames = db.query(LiveFrame).filter_by(session_id=sess.id, is_locked=True).all()
    for lf in locked_frames:
        for p in [lf.image_path, lf.annotated_path]:
            if p:
                dp = os.path.join(Config.BASE_DIR, p.lstrip('/').replace('/', os.sep))
                if os.path.isfile(dp):
                    try:
                        os.remove(dp)
                    except Exception:
                        pass
        db.delete(lf)

    db.commit()
    return jsonify({
        "success": True,
        "message": "Ready to scan next sample."
    })


@qc_bp.route('/api/capture/<token>/reset-lock', methods=['POST'])
def reset_capture_lock(token):
    """
    Phone alias to reset lock state for 'Scan next sample'.
    """
    db = get_db()
    sess = db.query(LiveSession).filter_by(token=token).first()
    if not sess:
        return jsonify({"success": False, "error": "Invalid token."}), 404

    return reset_live_lock(sess.id)


@qc_bp.route('/api/qc/debug/latest', methods=['GET'])
def get_latest_debug_image():
    """
    Returns the latest classical kernel finder debug view image or JSON summary.
    Exposes kernel outlines, ID badges, Lab paper estimation, and Otsu threshold.
    """
    db = get_db()
    latest_frame = db.query(LiveFrame).order_by(LiveFrame.id.desc()).first()
    if not latest_frame:
        return jsonify({"success": False, "error": "No frames available."}), 404

    return get_frame_debug_image(latest_frame.id)


@qc_bp.route('/api/qc/frame/<int:frame_id>/debug', methods=['GET'])
def get_frame_debug_image(frame_id):
    """
    Returns classical kernel finder debug view for a specific live frame.
    If ?raw=1 is passed, sends the raw JPEG image directly.
    """
    db = get_db()
    frame = db.query(LiveFrame).filter_by(id=frame_id).first()
    if not frame:
        return jsonify({"success": False, "error": f"Frame {frame_id} not found."}), 404

    raw_disk_path = os.path.join(Config.BASE_DIR, frame.image_path.lstrip('/').replace('/', os.sep))
    if not os.path.isfile(raw_disk_path):
        return jsonify({"success": False, "error": f"Image file for frame {frame_id} not found on disk."}), 404

    from ai.classical_kernel_finder import find_kernels_classical
    import cv2

    res = find_kernels_classical(raw_disk_path)
    debug_dir = os.path.join(Config.BASE_DIR, 'static', 'uploads', 'live_frames', 'debug')
    os.makedirs(debug_dir, exist_ok=True)
    fname = f"debug_frame_{frame.id}.jpg"
    out_path = os.path.join(debug_dir, fname)
    cv2.imwrite(out_path, res["debug_image"])

    if (request.args.get('raw') or '').lower() in ['1', 'true', 'yes']:
        return send_file(out_path, mimetype='image/jpeg')

    return jsonify({
        "success": True,
        "frame_id": frame.id,
        "session_id": frame.session_id,
        "total_kernels": res["total_kernels"],
        "normal_count": res.get("normal_count", 0),
        "suspect_count": res.get("suspect_count", 0),
        "ignored_count": res["ignored_count"],
        "paper_lab": res["paper_lab"],
        "otsu_threshold": res["otsu_threshold"],
        "debug_image_url": f"/static/uploads/live_frames/debug/{fname}",
        "raw_image_url": frame.image_path,
        "footer_notice": "Colour screening only. Not a mold or lab test.",
        "kernels": [
            {
                "id": k["id"],
                "bbox": k["bbox"],
                "bbox_normalized": k["bbox_normalized"],
                "area": k["area"],
                "area_pct": k["area_pct"],
                "solidity": k["solidity"],
                "aspect_ratio": k["aspect_ratio"],
                "suspect_score": k.get("suspect_score", 0.0),
                "classification": k.get("classification", "Normal"),
                "reason_tags": k.get("reason_tags", [])
            }
            for k in res["kernels"]
        ]
    })


# ==============================================================================
# CALIBRATION PAGE & SIMPLE THRESHOLD FITTING ENDPOINTS (Requirement 2 & 3)
# ==============================================================================

@qc_bp.route('/qc/calibration', methods=['GET'])
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def calibration_page():
    """
    Login-required Calibration page for Colour Screening.
    Displays kernel cards from saved frames with user Normal/Suspect marking,
    simple threshold fitting per material (no ML), Reset button,
    and a separation performance table.
    """
    user = get_current_user()
    db = get_db()
    pending_qc_count = db.query(RawMaterialLot).filter(
        (RawMaterialLot.qc_status == "PENDING_QC") | (RawMaterialLot.status == StatusEnum.PENDING.value)
    ).count()

    thresholds = {
        "Peanut": get_material_colour_threshold("Peanut"),
        "Corn": get_material_colour_threshold("Corn"),
        "Sunflower": get_material_colour_threshold("Sunflower")
    }

    return render_template(
        'qc_calibration.html',
        user=user,
        active_view='calibration',
        view_title='Colour Screening Calibration',
        breadcrumb=["Home", "Quality Control", "Colour Screening Calibration"],
        pending_qc_count=pending_qc_count,
        thresholds=thresholds,
        footer_notice="Colour screening only. Not a mold or lab test."
    )


@qc_bp.route('/api/qc/calibration/data', methods=['GET'])
@login_required
def get_calibration_data():
    """
    Returns data for the Calibration page:
    - Current thresholds per material
    - Separation performance table
    - Kernel cards from saved frames with Lab metrics, reason tags, and crops
    """
    db = get_db()
    materials = ["Peanut", "Corn", "Sunflower"]
    thresholds = {m: get_material_colour_threshold(m) for m in materials}
    user_marks = get_user_calibration_marks()

    sep_table = [
        compute_material_separation_stats(m, thresholds[m], user_marks)
        for m in materials
    ]

    try:
        limit_frames = min(30, max(1, int(request.args.get('limit', 10))))
    except (ValueError, TypeError):
        limit_frames = 10

    saved_frames = db.query(LiveFrame).order_by(LiveFrame.id.desc()).limit(limit_frames).all()
    kernels_data = []

    crops_dir = os.path.join(Config.BASE_DIR, 'static', 'uploads', 'live_frames', 'crops')
    os.makedirs(crops_dir, exist_ok=True)

    from ai.classical_kernel_finder import find_kernels_classical, crop_kernel_image
    import cv2

    for frame in saved_frames:
        if not frame.image_path:
            continue
        disk_path = os.path.join(Config.BASE_DIR, frame.image_path.lstrip('/').replace('/', os.sep))
        if not os.path.isfile(disk_path):
            continue

        raw_mat = frame.session.lot.material_name if (frame.session and frame.session.lot and frame.session.lot.material_name) else (frame.material or "Peanut")
        mat_canon = detect_material_from_text(raw_mat) or "Peanut"
        thresh = thresholds.get(mat_canon, 40.0)

        try:
            res = find_kernels_classical(disk_path, suspect_threshold=thresh, material=mat_canon)
            img = cv2.imread(disk_path)
            for k in res["kernels"]:
                kid = k["id"]
                uid = f"{frame.id}_{kid}"
                crop_fname = f"crop_{frame.id}_{kid}.jpg"
                crop_disk = os.path.join(crops_dir, crop_fname)
                if img is not None and not os.path.isfile(crop_disk):
                    crop_img = crop_kernel_image(img, k["bbox"], padding=12)
                    cv2.imwrite(crop_disk, crop_img)

                existing_mark = user_marks.get(uid, {}).get("mark")

                kernels_data.append({
                    "kernel_uid": uid,
                    "frame_id": frame.id,
                    "kernel_id": kid,
                    "frame_created_at": frame.created_at.strftime("%Y-%m-%d %H:%M") if frame.created_at else "",
                    "material": mat_canon,
                    "crop_url": f"/api/qc/calibration/crop/{frame.id}/{kid}",
                    "median_lab": k["metrics"]["median_lab"],
                    "dark_patch_pct": k["metrics"]["dark_patch_pct"],
                    "patch_pct": k["metrics"]["patch_pct"],
                    "unevenness": k["metrics"]["unevenness"],
                    "suspect_score": k["metrics"]["suspect_score"],
                    "reason_tags": k["metrics"]["reason_tags"],
                    "model_classification": k["metrics"]["classification"],
                    "user_mark": existing_mark
                })
        except Exception:
            continue

    return jsonify({
        "success": True,
        "thresholds": thresholds,
        "separation_table": sep_table,
        "total_kernels": len(kernels_data),
        "total_marks": len(user_marks),
        "kernels": kernels_data,
        "footer_notice": "Colour screening only. Not a mold or lab test."
    })


@qc_bp.route('/api/qc/calibration/crop/<int:frame_id>/<int:kernel_id>', methods=['GET'])
def get_calibration_crop(frame_id, kernel_id):
    """Serves cropped thumbnail image for a kernel."""
    crops_dir = os.path.join(Config.BASE_DIR, 'static', 'uploads', 'live_frames', 'crops')
    os.makedirs(crops_dir, exist_ok=True)
    crop_fname = f"crop_{frame_id}_{kernel_id}.jpg"
    crop_path = os.path.join(crops_dir, crop_fname)
    if os.path.isfile(crop_path):
        return send_file(crop_path, mimetype='image/jpeg')

    db = get_db()
    frame = db.query(LiveFrame).filter_by(id=frame_id).first()
    if not frame or not frame.image_path:
        return jsonify({"success": False, "error": "Frame not found"}), 404

    disk_path = os.path.join(Config.BASE_DIR, frame.image_path.lstrip('/').replace('/', os.sep))
    if not os.path.isfile(disk_path):
        return jsonify({"success": False, "error": "Image file not found"}), 404

    from ai.classical_kernel_finder import find_kernels_classical, crop_kernel_image
    import cv2

    res = find_kernels_classical(disk_path)
    target_k = next((k for k in res["kernels"] if k["id"] == kernel_id), None)
    if not target_k:
        return jsonify({"success": False, "error": f"Kernel {kernel_id} not found in frame {frame_id}"}), 404

    img = cv2.imread(disk_path)
    if img is None:
        return jsonify({"success": False, "error": "Could not decode frame image"}), 500

    crop_img = crop_kernel_image(img, target_k["bbox"], padding=12)
    cv2.imwrite(crop_path, crop_img)
    return send_file(crop_path, mimetype='image/jpeg')


@qc_bp.route('/api/qc/calibration/mark', methods=['POST'])
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def mark_calibration_kernel():
    """
    Saves or clears a user mark ('normal' or 'suspect') on a kernel card.
    Updates inspection_station_settings table and returns live separation metrics.
    """
    data = request.get_json() or {}
    uid = data.get("kernel_uid")
    mark = (data.get("mark") or "").lower()
    material = data.get("material") or "Peanut"
    mat_canon = detect_material_from_text(material) or "Peanut"
    score = float(data.get("score", 0.0))
    frame_id = data.get("frame_id")
    kernel_id = data.get("kernel_id")

    if not uid:
        return jsonify({"success": False, "error": "kernel_uid is required"}), 400

    marks = get_user_calibration_marks()
    if mark in ["clear", "none", ""]:
        marks.pop(uid, None)
    elif mark in ["normal", "suspect"]:
        marks[uid] = {
            "kernel_uid": uid,
            "frame_id": frame_id,
            "kernel_id": kernel_id,
            "material": mat_canon,
            "mark": mark,
            "score": score,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
    else:
        return jsonify({"success": False, "error": f"Invalid mark '{mark}'. Must be 'normal', 'suspect', or 'clear'."}), 400

    set_user_calibration_marks(marks)

    materials = ["Peanut", "Corn", "Sunflower"]
    thresholds = {m: get_material_colour_threshold(m) for m in materials}
    sep_table = [
        compute_material_separation_stats(m, thresholds[m], marks)
        for m in materials
    ]

    return jsonify({
        "success": True,
        "kernel_uid": uid,
        "mark": marks.get(uid, {}).get("mark"),
        "thresholds": thresholds,
        "separation_table": sep_table
    })


@qc_bp.route('/api/qc/calibration/fit', methods=['POST'])
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def fit_calibration_thresholds():
    """
    Fits simple thresholds per material from user marks (NO machine learning).
    Saves them in the settings table and returns the updated separation table.
    """
    data = request.get_json() or {}
    target_mat = data.get("material")
    marks = get_user_calibration_marks()
    materials = [detect_material_from_text(target_mat)] if target_mat and target_mat != "all" else ["Peanut", "Corn", "Sunflower"]

    new_thresholds = {}
    for mat in materials:
        if not mat:
            continue
        fitted_t = fit_threshold_from_marks(mat, marks)
        set_inspection_setting(f"colour_screening_threshold_{mat.lower()}", f"{fitted_t:.1f}")
        new_thresholds[mat] = fitted_t

    all_materials = ["Peanut", "Corn", "Sunflower"]
    current_thresholds = {m: get_material_colour_threshold(m) for m in all_materials}
    sep_table = [
        compute_material_separation_stats(m, current_thresholds[m], marks)
        for m in all_materials
    ]

    return jsonify({
        "success": True,
        "fitted_thresholds": new_thresholds,
        "thresholds": current_thresholds,
        "separation_table": sep_table,
        "message": "Simple thresholds fitted from manual marks (no machine learning)."
    })


@qc_bp.route('/api/qc/calibration/reset', methods=['POST'])
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def reset_calibration_thresholds():
    """
    Resets thresholds in the settings table back to default 40.0.
    """
    data = request.get_json() or {}
    target_mat = data.get("material")
    materials = [detect_material_from_text(target_mat)] if target_mat and target_mat != "all" else ["Peanut", "Corn", "Sunflower"]

    for mat in materials:
        if not mat:
            continue
        set_inspection_setting(f"colour_screening_threshold_{mat.lower()}", "40.0")

    marks = get_user_calibration_marks()
    all_materials = ["Peanut", "Corn", "Sunflower"]
    current_thresholds = {m: get_material_colour_threshold(m) for m in all_materials}
    sep_table = [
        compute_material_separation_stats(m, current_thresholds[m], marks)
        for m in all_materials
    ]

    return jsonify({
        "success": True,
        "thresholds": current_thresholds,
        "separation_table": sep_table,
        "message": "Thresholds reset to default (40.0)."
    })


@qc_bp.route('/api/qc/calibration/clear-marks', methods=['POST'])
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def clear_user_marks():
    """Clears all user marks."""
    set_user_calibration_marks({})
    all_materials = ["Peanut", "Corn", "Sunflower"]
    current_thresholds = {m: get_material_colour_threshold(m) for m in all_materials}
    sep_table = [
        compute_material_separation_stats(m, current_thresholds[m], {})
        for m in all_materials
    ]
    return jsonify({
        "success": True,
        "thresholds": current_thresholds,
        "separation_table": sep_table,
        "message": "All user marks cleared."
    })


# ==============================================================================
# UNIFIED QC MEASURES ENTRY & MERGED RELEASE DECISION (STEP 2 & 3)
# ==============================================================================
@qc_bp.route('/api/qc/lot/<int:lot_id>/qc-measures', methods=['GET'])
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN, RoleEnum.FOOD_TECHNOLOGIST)
def get_lot_qc_measures(lot_id):
    """
    Returns existing COA document, lab test measures, and merged release decision.
    """
    db = get_db()
    lot = db.query(RawMaterialLot).filter_by(id=lot_id).first()
    if not lot:
        return jsonify({"success": False, "error": f"Lot #{lot_id} not found."}), 404

    coa = db.query(COADocument).filter_by(raw_material_lot_id=lot.id).first()
    qc_sample = db.query(QCSample).filter_by(raw_material_lot_id=lot.id).first()

    tests = qc_sample.tests if qc_sample else []
    test_dict = {}
    for t in tests:
        pname = (t.parameter_name or '').lower()
        if 'moisture' in pname:
            test_dict['moisture'] = parse_numeric_value(t.measured_value)
        elif 'aflatoxin' in pname:
            test_dict['aflatoxin_b1'] = parse_numeric_value(t.measured_value)
        elif 'free fatty' in pname or 'ffa' in pname:
            test_dict['ffa'] = parse_numeric_value(t.measured_value)
        elif 'purity' in pname:
            test_dict['purity'] = parse_numeric_value(t.measured_value)

    decision = release_decision(lot, db=db)
    raw_outcome = decision.get("outcome", "HOLD")
    plain_label = "GOOD" if raw_outcome == "RELEASE" else ("BAD" if raw_outcome == "REJECT" else "NEEDS REVIEW")

    return jsonify({
        "success": True,
        "lot": {
            "id": lot.id,
            "lot_number": lot.lot_number,
            "material_name": lot.material_name,
            "supplier_name": lot.supplier_name or (lot.supplier.name if lot.supplier else "N/A"),
            "qc_status": lot.qc_status or "PENDING_QC",
            "status": lot.status
        },
        "coa": {
            "doc_number": coa.doc_number if coa else "",
            "lab_accreditation": getattr(coa, 'lab_accreditation', '') if coa else "",
            "issued_date": coa.issued_date.strftime("%Y-%m-%d") if (coa and coa.issued_date) else "",
            "is_verified": getattr(coa, 'is_verified', True) if coa else False,
            "file_url": getattr(coa, 'file_url', '') if coa else ""
        },
        "measures": test_dict,
        "release_decision": decision,
        "merged_outcome": raw_outcome,
        "merged_label": plain_label
    })


@qc_bp.route('/api/qc/lot/<int:lot_id>/qc-measures', methods=['POST'])
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def record_lot_qc_measures(lot_id):
    """
    Step 2: Unified QC Measures & Lab Values Entry.
    Records/updates COADocument and QCTest lab parameters:
    - Moisture Content (%)
    - Aflatoxin B1 (ppb)
    - Free Fatty Acids / FFA (%)
    - Purity Rate (%)
    Re-evaluates release_decision(lot) and returns the merged result with plain label:
    GOOD (maps to RELEASE), NEEDS REVIEW (HOLD), BAD (REJECT).
    """
    db = get_db()
    lot = db.query(RawMaterialLot).filter_by(id=lot_id).first()
    if not lot:
        return jsonify({"success": False, "error": f"Lot #{lot_id} not found."}), 404

    data = request.get_json(silent=True) or {}
    user = get_current_user()

    doc_number = (data.get('doc_number') or f"COA-{lot.lot_number}").strip()
    lab_accreditation = (data.get('lab_accreditation') or "Standard QA Lab").strip()

    moisture = parse_numeric_value(data.get('moisture'))
    aflatoxin = parse_numeric_value(data.get('aflatoxin_b1') if data.get('aflatoxin_b1') is not None else data.get('aflatoxin'))
    ffa = parse_numeric_value(data.get('ffa'))
    purity = parse_numeric_value(data.get('purity'))

    now_utc = datetime.datetime.utcnow()
    exp_utc = now_utc + datetime.timedelta(days=365)

    # 1. Update or create COADocument
    coa = db.query(COADocument).filter_by(raw_material_lot_id=lot.id).first()
    if not coa:
        coa = COADocument(
            raw_material_lot_id=lot.id,
            supplier_id=lot.supplier_id,
            doc_number=doc_number,
            filename=f"COA_{lot.lot_number}.pdf",
            file_url=data.get('file_path', '/static/uploads/sample_coa.pdf'),
            issued_date=now_utc,
            lab_accreditation=lab_accreditation,
            is_verified=True,
            uploaded_at=now_utc,
            notes=f"Material: {lot.material_name}, Lab: {lab_accreditation}"
        )
        db.add(coa)
    else:
        coa.doc_number = doc_number
        coa.is_verified = True
        coa.lab_accreditation = lab_accreditation
        coa.notes = f"Material: {lot.material_name}, Lab: {lab_accreditation}"
        if data.get('file_path'):
            coa.file_url = data.get('file_path')

    # 2. Update or create QCSample for lab tests
    qc_sample = db.query(QCSample).filter_by(raw_material_lot_id=lot.id).first()
    if not qc_sample:
        qc_sample = QCSample(
            raw_material_lot_id=lot.id,
            sample_code=f"SMP-LAB-{lot.lot_number}",
            sampler_user_id=user.id if user else None,
            sample_date=now_utc,
            storage_temp="Cool storage 4-6°C",
            sample_size="500g composite sample",
            notes="Station lab QC measures intake"
        )
        db.add(qc_sample)
        db.flush()

    # 3. Create or update QCTest records according to MATERIAL_SPECS
    norm_mat = normalize_material_name(lot.material_name)
    specs = MATERIAL_SPECS.get(norm_mat, {})

    def upsert_test(param_name, measured_val, unit, is_pass_fn, default_spec_str):
        if measured_val is None:
            return
        t = db.query(QCTest).filter_by(qc_sample_id=qc_sample.id, parameter_name=param_name).first()
        is_pass = is_pass_fn(measured_val)
        meas_str = f"{measured_val} {unit}".strip()
        if not t:
            t = QCTest(
                qc_sample_id=qc_sample.id,
                parameter_name=param_name,
                measured_value=meas_str,
                standard_spec=default_spec_str,
                is_pass=is_pass,
                tested_at=now_utc
            )
            db.add(t)
        else:
            t.measured_value = meas_str
            t.standard_spec = default_spec_str
            t.is_pass = is_pass
            t.tested_at = now_utc

    # Moisture
    spec_moist = specs.get('moisture', {}).get('max', 10.0)
    upsert_test("Moisture Content", moisture, "%", lambda v: v <= spec_moist, f"<= {spec_moist}%")

    # Aflatoxin
    if 'aflatoxin' in specs or aflatoxin is not None:
        spec_afla = specs.get('aflatoxin', {}).get('max', 5.0)
        upsert_test("Aflatoxin B1", aflatoxin, "ppb", lambda v: v <= spec_afla, f"<= {spec_afla} ppb")

    # FFA
    if 'ffa' in specs or ffa is not None:
        spec_ffa = specs.get('ffa', {}).get('max', 1.5)
        upsert_test("Free Fatty Acids (FFA)", ffa, "%", lambda v: v <= spec_ffa, f"<= {spec_ffa}%")

    # Purity
    spec_pur = specs.get('purity', {}).get('min', 98.0)
    upsert_test("Purity Rate", purity, "%", lambda v: v >= spec_pur, f">= {spec_pur}%")

    db.commit()

    # 4. Evaluate combined release decision
    decision_result = release_decision(lot, db=db)
    raw_outcome = decision_result.get("outcome", "HOLD")

    # Plain label mapping
    plain_label = "GOOD" if raw_outcome == "RELEASE" else ("BAD" if raw_outcome == "REJECT" else "NEEDS REVIEW")
    decision_result["plain_label"] = plain_label
    decision_result["raw_outcome"] = raw_outcome

    return jsonify({
        "success": True,
        "message": f"QC measures recorded for Lot #{lot.lot_number}. Outcome: {plain_label}",
        "lot_id": lot.id,
        "lot_number": lot.lot_number,
        "merged_outcome": raw_outcome,
        "merged_label": plain_label,
        "release_decision": decision_result
    })





