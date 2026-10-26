"""
Combined Release Decision Engine (COA + AI)
Implements release_decision(lot) pure function:
- coa_state: PASS, FAIL, MISSING
- ai_state: PASS, REVIEW, REJECT, RETAKE, NOT_RUN
- outcome: RELEASE, HOLD, REJECT
- plain one-sentence reason and detail lines
- Material mismatch, sunflower exemption, and peanut aflatoxin rules
"""
import datetime
import json
import re
from typing import Dict, Any, Optional, List


# Standard material specifications for physicochemical and safety limits
MATERIAL_SPECS = {
    "peanut": {
        "moisture": {"max": 8.0, "unit": "%", "name": "Moisture Content"},
        "aflatoxin": {"max": 2.0, "unit": "ppb", "name": "Aflatoxin B1"},
        "purity": {"min": 98.0, "unit": "%", "name": "Purity Rate"},
        "oil": {"min": 48.0, "unit": "%", "name": "Oil Content"},
    },
    "corn": {
        "moisture": {"max": 14.0, "unit": "%", "name": "Moisture Content"},
        "aflatoxin": {"max": 5.0, "unit": "ppb", "name": "Aflatoxin B1"},
        "purity": {"min": 98.0, "unit": "%", "name": "Purity Rate"},
    },
    "sunflower": {
        "moisture": {"max": 9.0, "unit": "%", "name": "Moisture Content"},
        "ffa": {"max": 1.5, "unit": "%", "name": "Free Fatty Acids (FFA)"},
        "purity": {"min": 98.0, "unit": "%", "name": "Purity Rate"},
    }
}


def normalize_material_name(raw_name: Optional[str]) -> str:
    """Extracts standardized material key ('peanut', 'corn', 'sunflower') or returns lower string."""
    if not raw_name:
        return "unknown"
    t = str(raw_name).lower().strip()
    if "peanut" in t or "groundnut" in t:
        return "peanut"
    if "corn" in t or "maize" in t:
        return "corn"
    if "sunflower" in t:
        return "sunflower"
    return t


def parse_numeric_value(val_str: Any) -> Optional[float]:
    """Extracts first float or int from a string (e.g. '6.8%', '< 2.0 ppb', '99.2%')."""
    if val_str is None:
        return None
    if isinstance(val_str, (int, float)):
        return float(val_str)
    match = re.search(r'[-+]?\d*\.?\d+', str(val_str))
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def evaluate_coa_document(
    lot: Any,
    coa: Any = None,
    tests: Optional[List[Any]] = None,
    db: Any = None
) -> Dict[str, Any]:
    """
    Evaluates COA state (PASS, FAIL, MISSING):
    - PASS only if:
      1. COA belongs to this lot (lot number, supplier and material match)
      2. COA is not expired
      3. Every tested value is within the stored material spec
    - FAIL if any value is outside spec or belongs to wrong lot/supplier/expired
    - MISSING if no valid COA exists
    """
    lot_id = getattr(lot, 'id', None)
    lot_number = getattr(lot, 'lot_number', str(lot) if lot else "")
    lot_supplier_id = getattr(lot, 'supplier_id', None)
    lot_supplier_name = getattr(lot, 'supplier_name', "")
    raw_material_name = getattr(lot, 'material_name', "") or getattr(lot, 'category', "")
    norm_mat = normalize_material_name(raw_material_name)

    # 1. Resolve COA document
    coa_doc = coa
    if coa_doc is None and db and lot_id:
        from models.qc import COADocument
        coa_doc = db.query(COADocument).filter_by(raw_material_lot_id=lot_id).first()

    if coa_doc is None:
        return {
            "state": "MISSING",
            "doc_number": None,
            "reason": "No valid COA document exists for this lot.",
            "details": ["Certificate of Analysis document is missing from the COA Library."],
            "is_valid": False,
            "tested_params": []
        }

    doc_num = getattr(coa_doc, 'doc_number', 'COA-UNKNOWN')

    # 2. Check ownership: Does COA belong to this lot?
    coa_lot_id = getattr(coa_doc, 'raw_material_lot_id', None)
    if coa_lot_id is not None and lot_id is not None and coa_lot_id != lot_id:
        return {
            "state": "FAIL",
            "doc_number": doc_num,
            "reason": f"COA #{doc_num} belongs to lot #{coa_lot_id}, not lot #{lot_id}.",
            "details": [f"Mismatched raw_material_lot_id (expected {lot_id}, got {coa_lot_id})."],
            "is_valid": False,
            "tested_params": []
        }

    # Supplier match check
    coa_sup_id = getattr(coa_doc, 'supplier_id', None)
    if coa_sup_id is not None and lot_supplier_id is not None and coa_sup_id != lot_supplier_id:
        return {
            "state": "FAIL",
            "doc_number": doc_num,
            "reason": f"COA supplier (#{coa_sup_id}) does not match lot supplier (#{lot_supplier_id}).",
            "details": ["Supplier identity on COA does not match order record."],
            "is_valid": False,
            "tested_params": []
        }

    if hasattr(coa_doc, 'supplier') and coa_doc.supplier and lot_supplier_name:
        sup_name = getattr(coa_doc.supplier, 'name', '')
        if sup_name and lot_supplier_name and sup_name.lower() != lot_supplier_name.lower():
            return {
                "state": "FAIL",
                "doc_number": doc_num,
                "reason": f"COA supplier '{sup_name}' does not match lot supplier '{lot_supplier_name}'.",
                "details": [f"Supplier mismatch: '{sup_name}' vs '{lot_supplier_name}'."],
                "is_valid": False,
                "tested_params": []
            }

    # Material match check
    coa_notes = getattr(coa_doc, 'notes', '') or ''
    if coa_notes and "material:" in coa_notes.lower():
        match = re.search(r'material:\s*([a-zA-Z\s]+)', coa_notes, re.IGNORECASE)
        if match:
            coa_mat = normalize_material_name(match.group(1).strip())
            if coa_mat != "unknown" and coa_mat != norm_mat:
                return {
                    "state": "FAIL",
                    "doc_number": doc_num,
                    "reason": f"COA material '{coa_mat}' does not match lot material '{norm_mat}'.",
                    "details": [f"Material mismatch on COA certificate: '{coa_mat}' vs order '{norm_mat}'."],
                    "is_valid": False,
                    "tested_params": []
                }

    # 3. Check expiration
    now_utc = datetime.datetime.utcnow()
    exp_date = getattr(coa_doc, 'expiry_date', None)
    if exp_date is not None:
        if exp_date < now_utc:
            return {
                "state": "FAIL",
                "doc_number": doc_num,
                "reason": f"COA #{doc_num} expired on {exp_date.strftime('%Y-%m-%d')}.",
                "details": [f"Certificate expiration date ({exp_date.strftime('%Y-%m-%d')}) has passed."],
                "is_valid": False,
                "tested_params": []
            }

    # Check notes for explicit expiry indication
    if "expired" in coa_notes.lower():
        return {
            "state": "FAIL",
            "doc_number": doc_num,
            "reason": f"COA #{doc_num} is marked as expired.",
            "details": ["Certificate validity period has lapsed."],
            "is_valid": False,
            "tested_params": []
        }

    # Check issued_date age (older than 365 days is considered expired)
    issued_date = getattr(coa_doc, 'issued_date', None)
    if issued_date and (now_utc - issued_date).days > 365:
        return {
            "state": "FAIL",
            "doc_number": doc_num,
            "reason": f"COA #{doc_num} is older than 365 days (issued {issued_date.strftime('%Y-%m-%d')}).",
            "details": ["Certificate exceeds maximum 1-year validity threshold."],
            "is_valid": False,
            "tested_params": []
        }

    # 4. Check tested parameters against material specifications
    test_records = []
    if tests is not None:
        test_records = tests
    elif db and lot_id:
        from models.qc import QCSample, QCTest
        samples = db.query(QCSample).filter_by(raw_material_lot_id=lot_id).all()
        for s in samples:
            test_records.extend(s.tests)
    elif hasattr(lot, 'qc_samples') and lot.qc_samples:
        for s in lot.qc_samples:
            if hasattr(s, 'tests'):
                test_records.extend(s.tests)

    tested_params_summary = []
    failed_params = []

    spec_dict = MATERIAL_SPECS.get(norm_mat, {})

    if test_records:
        for t in test_records:
            p_name = getattr(t, 'parameter_name', '') or ''
            p_meas = getattr(t, 'measured_value', '') or ''
            p_spec = getattr(t, 'standard_spec', '') or ''
            p_pass = getattr(t, 'is_pass', True)

            num_val = parse_numeric_value(p_meas)
            param_key = p_name.lower()

            # Direct boolean check
            if p_pass is False:
                failed_params.append(f"{p_name}: {p_meas} (criteria: {p_spec}) marked FAIL")
                tested_params_summary.append(f"{p_name}: {p_meas} [FAIL]")
                continue

            # Check numeric boundaries against MATERIAL_SPECS
            param_failed = False
            for spec_key, spec_rule in spec_dict.items():
                if spec_key in param_key:
                    if num_val is not None:
                        if "max" in spec_rule and num_val > spec_rule["max"]:
                            failed_params.append(
                                f"{spec_rule['name']} ({num_val}{spec_rule['unit']}) exceeds maximum {spec_rule['max']}{spec_rule['unit']}"
                            )
                            param_failed = True
                        elif "min" in spec_rule and num_val < spec_rule["min"]:
                            failed_params.append(
                                f"{spec_rule['name']} ({num_val}{spec_rule['unit']}) below minimum {spec_rule['min']}{spec_rule['unit']}"
                            )
                            param_failed = True
                    break

            tested_params_summary.append(f"{p_name}: {p_meas} [{'FAIL' if param_failed else 'PASS'}]")

    # If coa_notes contains explicit parameter overrides (e.g. for testing)
    if coa_notes:
        try:
            parsed_notes = json.loads(coa_notes)
            if isinstance(parsed_notes, dict):
                for k, v in parsed_notes.items():
                    k_lower = k.lower()
                    val_num = parse_numeric_value(v)
                    for spec_key, spec_rule in spec_dict.items():
                        if spec_key in k_lower and val_num is not None:
                            if "max" in spec_rule and val_num > spec_rule["max"]:
                                failed_params.append(f"{spec_rule['name']} ({val_num}) exceeds {spec_rule['max']}")
                            elif "min" in spec_rule and val_num < spec_rule["min"]:
                                failed_params.append(f"{spec_rule['name']} ({val_num}) below {spec_rule['min']}")
        except Exception:
            pass

    if failed_params:
        return {
            "state": "FAIL",
            "doc_number": doc_num,
            "reason": f"COA #{doc_num} failed specification: " + "; ".join(failed_params),
            "details": failed_params,
            "is_valid": False,
            "tested_params": tested_params_summary
        }

    # All tests compliant
    return {
        "state": "PASS",
        "doc_number": doc_num,
        "reason": f"COA #{doc_num} verified: lot match, supplier match, not expired, all tested parameters within specification.",
        "details": tested_params_summary or ["All laboratory physicochemical and safety parameters within spec."],
        "is_valid": True,
        "tested_params": tested_params_summary
    }


def evaluate_ai_inspection(
    lot: Any,
    ai_result: Optional[Dict[str, Any]] = None,
    db: Any = None
) -> Dict[str, Any]:
    """
    Evaluates AI inspection state (PASS, REVIEW, REJECT, RETAKE, NOT_RUN):
    - Reads from explicit ai_result, or LiveSession locked_result_json, or AIInspection record.
    - Sunflower never gets an AI PASS (always REVIEW).
    - Checks for material mismatch between lot and camera.
    """
    lot_id = getattr(lot, 'id', None)
    raw_material_name = getattr(lot, 'material_name', "") or getattr(lot, 'category', "")
    norm_mat = normalize_material_name(raw_material_name)

    # 1. Direct ai_result dictionary
    if ai_result:
        raw_state = (ai_result.get("state") or ai_result.get("decision_state") or "").upper()
        if not raw_state and "total_defects_count" in ai_result:
            defects = ai_result.get("total_defects_count", 0)
            raw_state = "PASS" if defects == 0 else "REJECT"

        mismatch = bool(ai_result.get("material_mismatch"))
        camera_mat = ai_result.get("material") or ai_result.get("detected_material")
        if camera_mat and norm_mat != "unknown":
            norm_cam = normalize_material_name(camera_mat)
            if norm_cam != "unknown" and norm_cam != norm_mat:
                mismatch = True

        state = raw_state or "REVIEW"
        if norm_mat == "sunflower" and state == "PASS":
            state = "REVIEW"

        return {
            "state": state,
            "material_mismatch": mismatch,
            "camera_material": camera_mat,
            "reason": ai_result.get("reason", f"AI inspection state: {state}"),
            "defects_count": ai_result.get("total_defects_count", 0),
            "confidence": ai_result.get("confidence", 0.95),
            "details": ai_result.get("warnings", [])
        }

    # 2. Check LiveSession locked result
    live_sess = None
    if db and lot_id:
        from models.qc import LiveSession
        live_sess = db.query(LiveSession).filter_by(lot_id=lot_id).order_by(LiveSession.id.desc()).first()

    if live_sess and live_sess.locked_result_json:
        try:
            l_json = json.loads(live_sess.locked_result_json)
            fd = l_json.get("final_decision", {})
            st = (fd.get("state") or l_json.get("decision_state") or "REVIEW").upper()
            cam_mat = fd.get("material") or l_json.get("material")
            mismatch = bool(l_json.get("material_mismatch") or fd.get("material_mismatch"))

            if cam_mat and norm_mat != "unknown":
                if normalize_material_name(cam_mat) != norm_mat:
                    mismatch = True

            # Sunflower rule: never gets AI PASS
            if norm_mat == "sunflower" and st == "PASS":
                st = "REVIEW"

            return {
                "state": st,
                "material_mismatch": mismatch,
                "camera_material": cam_mat,
                "reason": fd.get("reason", f"Live camera station verdict: {st}"),
                "defects_count": fd.get("defect_count", l_json.get("total_defects_count", 0)),
                "confidence": fd.get("confidence", 0.90),
                "details": fd.get("details", [])
            }
        except Exception:
            pass

    # 3. Check AIInspection database records
    ai_insp = None
    if db and lot_id:
        from models.qc import AIInspection
        ai_insp = db.query(AIInspection).filter_by(raw_material_lot_id=lot_id).order_by(AIInspection.id.desc()).first()

    if ai_insp:
        defects = ai_insp.total_defects_count or 0
        mismatch = bool(ai_insp.material_mismatch)
        cam_mat = ai_insp.detected_material
        if cam_mat and norm_mat != "unknown":
            if normalize_material_name(cam_mat) != norm_mat:
                mismatch = True

        if getattr(ai_insp, 'model_status', '') == 'NEEDS_REVIEW' or mismatch or getattr(ai_insp, 'is_low_confidence', False):
            st = "REVIEW"
        elif defects > 0:
            st = "REJECT"
        else:
            st = "PASS"

        # Sunflower rule: never gets AI PASS
        if norm_mat == "sunflower" and st == "PASS":
            st = "REVIEW"

        return {
            "state": st,
            "material_mismatch": mismatch,
            "camera_material": cam_mat,
            "reason": ai_insp.summary or f"YOLOv8 visual scan result: {st}",
            "defects_count": defects,
            "confidence": ai_insp.avg_confidence or 0.92,
            "details": [ai_insp.status_message] if ai_insp.status_message else []
        }

    # 4. No AI inspection executed
    return {
        "state": "NOT_RUN",
        "material_mismatch": False,
        "camera_material": None,
        "reason": "Camera inspection has not been run for this lot.",
        "defects_count": 0,
        "confidence": None,
        "details": ["No visual camera inspection dossier on file."]
    }


def release_decision(
    lot: Any,
    db: Any = None,
    coa: Any = None,
    ai_result: Optional[Dict[str, Any]] = None,
    tests: Optional[List[Any]] = None
) -> Dict[str, Any]:
    """
    Combined Release Decision function.
    Returns:
    - coa_state: PASS, FAIL, MISSING
    - ai_state: PASS, REVIEW, REJECT, RETAKE, NOT_RUN
    - outcome: RELEASE, HOLD, REJECT
    - reason: one-sentence plain reason
    - details: list of detail lines
    """
    # Normalize lot object
    lot_id = getattr(lot, 'id', None)
    lot_number = getattr(lot, 'lot_number', str(lot) if lot else "LOT-UNKNOWN")
    raw_material_name = getattr(lot, 'material_name', "") or getattr(lot, 'category', "")
    norm_mat = normalize_material_name(raw_material_name)
    is_peanut = (norm_mat == "peanut")
    is_sunflower = (norm_mat == "sunflower")

    # 1. Evaluate COA and AI components
    coa_eval = evaluate_coa_document(lot, coa=coa, tests=tests, db=db)
    ai_eval = evaluate_ai_inspection(lot, ai_result=ai_result, db=db)

    coa_state = coa_eval["state"]   # PASS, FAIL, MISSING
    ai_state = ai_eval["state"]     # PASS, REVIEW, REJECT, RETAKE, NOT_RUN

    # 2. Outcome Determination Rules
    outcome = "HOLD"
    reason = ""
    details: List[str] = []

    # Rule A: COA FAIL -> REJECT (Peanut rule: COA aflatoxin decides, AI never overrides failed COA)
    if coa_state == "FAIL":
        outcome = "REJECT"
        if is_peanut and "aflatoxin" in coa_eval["reason"].lower():
            reason = "Peanut lot rejected: COA aflatoxin safety limit failed. AI inspection cannot override."
        else:
            reason = f"Lot rejected: Certificate of Analysis failed specifications ({coa_eval['reason']})."

    # Rule B: COA MISSING -> HOLD ("valid COA needed")
    elif coa_state == "MISSING":
        outcome = "HOLD"
        reason = "Valid COA needed."

    # Rule C: Material mismatch between order and camera -> HOLD
    elif ai_eval.get("material_mismatch"):
        outcome = "HOLD"
        cam_mat = ai_eval.get("camera_material") or "different material"
        reason = f"Material on the order ({raw_material_name}) differs from material seen by camera ({cam_mat}). Hold for investigation."

    # Rule D: Sunflower rule (Sunflower never gets an AI PASS, outcome rests on COA plus inspector)
    elif is_sunflower:
        outcome = "HOLD"
        reason = "Sunflower screening rests on COA plus inspector visual confirmation."

    # Rule E: COA PASS & AI PASS -> RELEASE
    elif coa_state == "PASS" and ai_state == "PASS":
        outcome = "RELEASE"
        reason = "All laboratory COA parameters and camera AI inspection verified compliant. Safe to release."

    # Rule F: COA PASS & AI REJECT -> HOLD ("paper passes, camera disagrees: investigate")
    elif coa_state == "PASS" and ai_state == "REJECT":
        outcome = "HOLD"
        reason = "Paper passes, camera disagrees: investigate."

    # Rule G: COA PASS & (AI REVIEW, RETAKE, or NOT_RUN) -> HOLD ("inspector checks by eye")
    elif coa_state == "PASS" and ai_state in ("REVIEW", "RETAKE", "NOT_RUN"):
        outcome = "HOLD"
        reason = "Inspector checks by eye."

    # Fallback
    else:
        outcome = "HOLD"
        reason = f"Lot placed on hold for quality specialist manual evaluation (COA: {coa_state}, AI: {ai_state})."

    # 3. Assemble detail lines
    details.append(f"Paper check (COA): {coa_state} — {coa_eval['reason']}")
    details.append(f"Camera check (AI): {ai_state} — {ai_eval['reason']}")
    details.append(f"Combined Outcome: {outcome} — {reason}")

    # Peanut mandatory advisory notice
    if is_peanut:
        details.append("Camera screening only. Peanut lots need lab testing before release.")

    if is_sunflower:
        details.append("Sunflower lots require physical inspector sign-off alongside valid COA.")

    return {
        "coa_state": coa_state,
        "ai_state": ai_state,
        "outcome": outcome,
        "reason": reason,
        "outcome_reason": reason,
        "details": details,
        "lot_number": lot_number,
        "material": raw_material_name or norm_mat.capitalize(),
        "is_release_enabled": (outcome == "RELEASE"),
        "coa_doc_number": coa_eval.get("doc_number"),
        "peanut_advisory": "Camera screening only. Peanut lots need lab testing before release." if is_peanut else None,
        "sunflower_advisory": "Sunflower screening rests on COA plus inspector." if is_sunflower else None,
        "coa_details": coa_eval,
        "ai_details": ai_eval
    }
