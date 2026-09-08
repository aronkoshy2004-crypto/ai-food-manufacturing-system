"""
Authentication Routes and Role-Based Access Control
"""
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from models import get_db
from models.user import User
from models.enums import RoleEnum

auth_bp = Blueprint('auth', __name__)

def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    db = get_db()
    return db.query(User).filter_by(id=user_id, is_active=True).first()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({"error": "Unauthorized", "message": "Please sign in"}), 401
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return redirect(url_for('auth.login'))
            
            # Admin has access to all roles
            if user.is_admin():
                return f(*args, **kwargs)
            
            role_strs = [r.value if isinstance(r, RoleEnum) else str(r) for r in allowed_roles]
            if user.role not in role_strs:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({
                        "error": "Forbidden", 
                        "message": f"Role '{user.role}' is not authorized to access this resource."
                    }), 403
                flash(f"Your account ({user.role}) is not authorized to perform this action.", "warning")
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('dashboard.index'))

    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        
        db = get_db()
        user = db.query(User).filter_by(email=email, is_active=True).first()
        
        if user and user.check_password(password):
            session.clear()
            session['user_id'] = user.id
            session['user_email'] = user.email
            session['user_name'] = user.full_name
            session['user_role'] = user.role
            session['user_initials'] = user.avatar_initials
            session.permanent = True

            next_url = request.args.get('next') or url_for('dashboard.index')
            return redirect(next_url)
        else:
            error = "Invalid email or password. Please verify and try again."

    # Pre-fetch demo users for one-click testing
    db = get_db()
    demo_users = db.query(User).filter_by(is_active=True).all()

    return render_template('login.html', error=error, demo_users=demo_users)


@auth_bp.route('/demo-login/<role>', methods=['GET'])
def demo_login(role):
    """
    Convenience endpoint for testing role-appropriate UI shell and nav visibility instantly.
    """
    db = get_db()
    user = db.query(User).filter_by(role=role, is_active=True).first()
    
    if not user:
        # Try case-insensitive lookup
        for u in db.query(User).filter_by(is_active=True).all():
            if u.role.lower() == role.lower():
                user = u
                break

    if user:
        session.clear()
        session['user_id'] = user.id
        session['user_email'] = user.email
        session['user_name'] = user.full_name
        session['user_role'] = user.role
        session['user_initials'] = user.avatar_initials
        session.permanent = True

    return redirect(url_for('dashboard.index'))


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/api/auth/me', methods=['GET'])
@login_required
def api_me():
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "user": user.to_dict()
    })
