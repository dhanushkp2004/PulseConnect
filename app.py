from flask import Flask, render_template, redirect, url_for, flash, session, request, jsonify
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import random
import os
import re

from models import db, Donor, Organization, Admin, BloodRequest, Event

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-12345'
basedir = os.path.abspath(os.path.dirname(__name__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'bloodbank.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Flask-Mail Configuration
# IMPORTANT: For Gmail, use an "App Password" (NOT your regular password).
# Enable 2-Step Verification in Google Account -> Security -> 2-Step Verification.
# Search for "App Passwords" at the bottom of the 2-Step Verification page.
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465 # Use 465 for SSL or 587 for TLS
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = 'dilliop0912@gmail.com' # Replace with your email
app.config['MAIL_PASSWORD'] = 'snpnqckregjdkcng'    # Replace with your app password
app.config['MAIL_DEFAULT_SENDER'] = ('PulseConnect', 'dilliop0912@gmail.com')

mail = Mail(app)

def send_otp_email(email, otp):
    msg = Message('Verify Your PulseConnect Account',
                  recipients=[email])
    msg.body = f"Your OTP for PulseConnect registration is {otp}. It will expire in 10 minutes."
    try:
        mail.send(msg)
        return True
    except Exception as e:
        # Improved error logging for development
        app.logger.error(f"OTP Email Delivery Failed for {email}: {e}")
        return False

def send_reset_otp_email(email, otp):
    msg = Message('Reset Your PulseConnect Password',
                  recipients=[email])
    msg.body = f"Your OTP for password reset is {otp}. It will expire in 10 minutes."
    try:
        mail.send(msg)
        return True
    except Exception as e:
        app.logger.error(f"Reset OTP Email Delivery Failed for {email}: {e}")
        return False

with app.app_context():
    db.create_all()
    
    # Create default admin if not exists
    if not Admin.query.filter_by(username='admin').first():
        admin = Admin(username='admin', password_hash=generate_password_hash('password123'))
        db.session.add(admin)
        db.session.commit()

# Blood donor compatibility mapping: recipient -> eligible donors
BLOOD_COMPATIBILITY = {
    'A+': ['A+', 'A-', 'O+', 'O-'],
    'A-': ['A-', 'O-'],
    'B+': ['B+', 'B-', 'O+', 'O-'],
    'B-': ['B-', 'O-'],
    'AB+': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
    'AB-': ['AB-', 'A-', 'B-', 'O-'],
    'O+': ['O+', 'O-'],
    'O-': ['O-']
}

@app.route('/')
def index():
    requests = BloodRequest.query.order_by(BloodRequest.created_at.desc()).all()
    # Only show approved events on the home page
    events = Event.query.filter_by(is_approved=True).order_by(Event.date.asc()).all()
    return render_template('index.html', requests=requests, events=events)

@app.route('/api/check_blood/<blood_group>')
def check_blood(blood_group):
    if blood_group in BLOOD_COMPATIBILITY:
        eligible_groups = BLOOD_COMPATIBILITY[blood_group]
        count = Donor.query.filter(Donor.blood_group.in_(eligible_groups), Donor.is_approved == True).count()
    else:
        count = Donor.query.filter_by(blood_group=blood_group, is_approved=True).count()
    return jsonify({'count': count})

@app.route('/api/get_donors/<blood_group>')
def get_donors(blood_group):
    if blood_group == 'all':
        donors = Donor.query.filter_by(is_approved=True).all()
    elif blood_group in BLOOD_COMPATIBILITY:
        eligible_groups = BLOOD_COMPATIBILITY[blood_group]
        donors = Donor.query.filter(Donor.blood_group.in_(eligible_groups), Donor.is_approved == True).all()
    else:
        donors = Donor.query.filter_by(blood_group=blood_group, is_approved=True).all()
        
    donors_data = []
    for d in donors:
        donors_data.append({
            'name': d.name,
            'blood_group': d.blood_group,
            'phone': d.phone,
            'email': d.email,
            'gender': d.gender,
            'last_donation_date': d.last_donation_date.isoformat() if d.last_donation_date else None
        })
    return jsonify(donors_data)

@app.route('/submit_request', methods=['POST'])
def submit_request():
    blood_group = request.form.get('blood_group')
    patient_name = request.form.get('patient_name')
    hospital = request.form.get('hospital')
    contact_info = request.form.get('contact_info')
    message = request.form.get('message')

    full_message = f"Patient: {patient_name} | Hospital: {hospital} | Message: {message}"

    new_request = BloodRequest(
        requested_blood_group=blood_group,
        patient_message=full_message,
        contact_info=contact_info
    )
    db.session.add(new_request)
    db.session.commit()
    flash("Blood request submitted successfully.", "success")
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form.get('role')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate Email Format
        if not email or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            flash("Invalid email format (e.g., something@gmail.com).", "error")
            return redirect(url_for('register'))
        
        # Validate Password Complexity
        if not password or len(password) < 8 or not re.search(r'[A-Z]', password) or not re.search(r'\d', password):
            flash("Password must be at least 8 characters long, include at least one uppercase letter and one digit.", "error")
            return redirect(url_for('register'))
            
        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password)
        
        if role == 'donor':
            name = request.form.get('name')
            phone = request.form.get('phone')
            dob_str = request.form.get('dob')
            weight = float(request.form.get('weight', 0))
            gender = request.form.get('gender')
            
            # Age and Weight Validation
            if not dob_str:
                flash("Date of Birth is required.", "error")
                return redirect(url_for('register'))
            
            dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            today = datetime.now().date()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            
            if age < 18:
                flash("Registration failed: Donors must be at least 18 years old.", "error")
                return redirect(url_for('register'))
            
            if weight < 50:
                flash("Registration failed: Donors must weigh at least 50kg.", "error")
                return redirect(url_for('register'))
            
            # Validate Phone Format
            if not phone or not re.match(r'^\d{10}$', phone):
                flash("Phone number must contain exactly 10 digits.", "error")
                return redirect(url_for('register'))
            
            blood_group = request.form.get('blood_group')
            last_date_str = request.form.get('last_donation_date')
            
            last_donation_date = None
            if last_date_str:
                last_donation_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
                
            if Donor.query.filter_by(email=email).first() or Organization.query.filter_by(email=email).first():
                flash("Email already registered.", "error")
                return redirect(url_for('register'))
                
            # Store data in session for verification
            session['temp_reg_data'] = {
                'role': 'donor',
                'name': name, 'email': email, 'phone': phone,
                'blood_group': blood_group, 'dob': dob_str, 'weight': weight, 'gender': gender,
                'last_donation_date': last_date_str,
                'password_hash': hashed_password
            }
            
        elif role == 'organization':
            name = request.form.get('name')
            if Donor.query.filter_by(email=email).first() or Organization.query.filter_by(email=email).first():
                flash("Email already registered.", "error")
                return redirect(url_for('register'))
                
            # Store data in session for verification
            session['temp_reg_data'] = {
                'role': 'organization',
                'name': name, 'email': email,
                'password_hash': hashed_password
            }
            
        # Generate and Send OTP
        otp = str(random.randint(100000, 999999))
        session['otp'] = otp
        session['otp_time'] = datetime.now().timestamp()
        
        if send_otp_email(email, otp):
            flash(f"A verification code has been sent to {email}.", "success")
            session['otp_delivery_success'] = True
        else:
            # Fallback for development if email fails
            flash("Email delivery failed. Using development fallback.", "warning")
            session['otp_delivery_success'] = False
            
        return redirect(url_for('verify_otp'))
            
    return render_template('register.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'temp_reg_data' not in session or 'otp' not in session:
        flash("Please start the registration process first.", "error")
        return redirect(url_for('register'))
        
    if request.method == 'POST':
        user_otp = request.form.get('otp')
        
        # Check OTP expiration (10 minutes)
        if datetime.now().timestamp() - session.get('otp_time', 0) > 600:
            flash("OTP has expired. Please request a new one.", "error")
            return redirect(url_for('verify_otp'))
            
        if user_otp == session['otp']:
            data = session['temp_reg_data']
            
            if data['role'] == 'donor':
                dob = datetime.strptime(data['dob'], '%Y-%m-%d').date()
                last_donation_date = None
                if data['last_donation_date']:
                    last_donation_date = datetime.strptime(data['last_donation_date'], '%Y-%m-%d').date()
                    
                new_user = Donor(
                    name=data['name'], email=data['email'], phone=data['phone'],
                    blood_group=data['blood_group'], dob=dob, weight=data['weight'], 
                    gender=data['gender'], last_donation_date=last_donation_date,
                    password_hash=data['password_hash']
                )
            else:
                new_user = Organization(
                    name=data['name'], email=data['email'], 
                    password_hash=data['password_hash']
                )
            
            db.session.add(new_user)
            db.session.commit()
            
            # Clear session data
            session.pop('temp_reg_data', None)
            session.pop('otp', None)
            session.pop('otp_time', None)
            
            flash("Registration successful! Your account is pending admin approval.", "info")
            return redirect(url_for('login'))
        else:
            flash("Invalid OTP. Please try again.", "error")
            
    return render_template('verify_otp.html', email=session['temp_reg_data']['email'])

@app.route('/resend-otp')
def resend_otp():
    if 'temp_reg_data' not in session:
        flash("Please start the registration process first.", "error")
        return redirect(url_for('register'))
        
    email = session['temp_reg_data']['email']
    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    session['otp_time'] = datetime.now().timestamp()
    
    if send_otp_email(email, otp):
        flash("A new verification code has been sent.", "success")
        session['otp_delivery_success'] = True
    else:
        app.logger.warning(f"Resend failed for {email}. Falling back to dev mode.")
        flash("Email delivery failed again. Using development fallback.", "warning")
        session['otp_delivery_success'] = False
        
    return redirect(url_for('verify_otp'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get('role')
        email_username = request.form.get('email_or_username')
        password = request.form.get('password')
        
        if role == 'donor':
            user = Donor.query.filter_by(email=email_username).first()
            if user and check_password_hash(user.password_hash, password):
                if not user.is_approved:
                    flash("Your account is pending admin approval. Please check back later.", "warning")
                    return redirect(url_for('login'))
                session['user_id'] = user.id
                session['role'] = 'donor'
                return redirect('/dashboard/donor')
        elif role == 'organization':
            user = Organization.query.filter_by(email=email_username).first()
            if user and check_password_hash(user.password_hash, password):
                if not user.is_approved:
                    flash("Your organization account is pending admin approval.", "warning")
                    return redirect(url_for('login'))
                session['user_id'] = user.id
                session['role'] = 'organization'
                return redirect('/dashboard/org')
        elif role == 'admin':
            user = Admin.query.filter_by(username=email_username).first()
            if user and check_password_hash(user.password_hash, password):
                session['user_id'] = user.id
                session['role'] = 'admin'
                return redirect('/dashboard/admin')
                
        flash("Invalid credentials or role selected.", "error")
        return redirect(url_for('login'))
        
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        # Check both Donor and Organization
        user_donor = Donor.query.filter_by(email=email).first()
        user_org = Organization.query.filter_by(email=email).first()
        
        if user_donor or user_org:
            role = 'donor' if user_donor else 'organization'
            otp = str(random.randint(100000, 999999))
            
            # Store in session
            session['reset_email'] = email
            session['reset_role'] = role
            session['reset_otp'] = otp
            session['reset_otp_time'] = datetime.now().timestamp()
            
            if send_reset_otp_email(email, otp):
                flash("A password reset code has been sent to your email.", "success")
                session['reset_otp_delivery_success'] = True
            else:
                flash("Email delivery failed. Using development fallback.", "warning")
                session['reset_otp_delivery_success'] = False
                
            return redirect(url_for('reset_password'))
        else:
            flash("If that email is registered, you will receive a reset code.", "info")
            return redirect(url_for('forgot_password'))
            
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_email' not in session:
        flash("Please request a password reset first.", "error")
        return redirect(url_for('forgot_password'))
        
    if request.method == 'POST':
        otp = request.form.get('otp')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if otp != session.get('reset_otp'):
            flash("Invalid OTP code.", "error")
            return redirect(url_for('reset_password'))
            
        if datetime.now().timestamp() - session.get('reset_otp_time', 0) > 600:
            flash("OTP has expired.", "error")
            return redirect(url_for('forgot_password'))
            
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for('reset_password'))
            
        # Complexity validation (same as registration)
        if len(password) < 8 or not re.search(r'[A-Z]', password) or not re.search(r'\d', password):
            flash("Password must be at least 8 characters, include 1 uppercase and 1 digit.", "error")
            return redirect(url_for('reset_password'))
            
        # Update password
        email = session['reset_email']
        role = session['reset_role']
        
        if role == 'donor':
            user = Donor.query.filter_by(email=email).first()
        else:
            user = Organization.query.filter_by(email=email).first()
            
        if user:
            user.password_hash = generate_password_hash(password)
            db.session.commit()
            
            # Clear session
            session.pop('reset_email', None)
            session.pop('reset_role', None)
            session.pop('reset_otp', None)
            session.pop('reset_otp_time', None)
            
            flash("Password updated successfully. You can now login.", "success")
            return redirect(url_for('login'))
            
    return render_template('reset_password.html', email=session['reset_email'])

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = Admin.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['role'] = 'admin'
            return redirect('/dashboard/admin')
                
        flash("Invalid admin credentials.", "error")
        return redirect(url_for('admin_login'))
        
    return render_template('admin_login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('index'))

@app.route('/dashboard/donor')
def donor_dashboard():
    if session.get('role') != 'donor':
        return redirect(url_for('login'))
    user = Donor.query.get(session['user_id'])
    requests = BloodRequest.query.filter_by(requested_blood_group=user.blood_group).all()
    # Fetch all approved events for donors to express interest
    approved_events = Event.query.filter_by(is_approved=True).order_by(Event.date.asc()).all()
    return render_template('donor_dashboard.html', user=user, matching_requests=requests, approved_events=approved_events)

@app.route('/dashboard/donor/mark_interest/<int:event_id>', methods=['POST'])
def mark_interest(event_id):
    if session.get('role') != 'donor':
        return redirect(url_for('login'))
    
    donor = Donor.query.get(session['user_id'])
    event = Event.query.get(event_id)
    
    if donor and event:
        if event in donor.interested_events:
            donor.interested_events.remove(event)
            flash(f"You've removed your interest from {event.event_name}.", "info")
        else:
            donor.interested_events.append(event)
            flash(f"Your interest in {event.event_name} has been recorded!", "success")
        db.session.commit()
        
    return redirect('/dashboard/donor')
@app.route('/dashboard/donor/update_date', methods=['POST'])
def update_donation_date():
    if session.get('role') != 'donor':
        return redirect(url_for('login'))
    date_str = request.form.get('last_donation_date')
    if date_str:
        user = Donor.query.get(session['user_id'])
        user.last_donation_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        db.session.commit()
        flash("Donation date updated successfully.", "success")
    return redirect('/dashboard/donor')

@app.route('/dashboard/donor/delete_profile', methods=['POST'])
def delete_donor_profile():
    if session.get('role') != 'donor':
        return redirect(url_for('login'))
    user = Donor.query.get(session['user_id'])
    if user:
        db.session.delete(user)
        db.session.commit()
        session.clear()
        flash("Your donor profile has been permanently deleted.", "success")
    return redirect(url_for('index'))

@app.route('/dashboard/org')
def org_dashboard():
    if session.get('role') != 'organization':
        return redirect(url_for('login'))
    user = Organization.query.get(session['user_id'])
    return render_template('org_dashboard.html', user=user, events=user.events)

@app.route('/dashboard/org/create_event', methods=['POST'])
def create_event():
    if session.get('role') != 'organization':
        return redirect(url_for('login'))
    name = request.form.get('event_name')
    date_str = request.form.get('date')
    location = request.form.get('location')
    description = request.form.get('description')
    
    event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    new_event = Event(org_id=session['user_id'], event_name=name, date=event_date, location=location, description=description, is_approved=False)
    db.session.add(new_event)
    db.session.commit()
    flash("Event submitted successfully! It is now pending admin approval.", "info")
    return redirect('/dashboard/org')

@app.route('/dashboard/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    # Approved users
    donors = Donor.query.filter_by(is_approved=True).all()
    orgs = Organization.query.filter_by(is_approved=True).all()
    
    # Pending users
    pending_donors = Donor.query.filter_by(is_approved=False).all()
    pending_orgs = Organization.query.filter_by(is_approved=False).all()
    
    # Events
    pending_events = Event.query.filter_by(is_approved=False).all()
    approved_events = Event.query.filter_by(is_approved=True).all()
    all_events = Event.query.all()
    
    return render_template('admin_dashboard.html', 
                           donors=donors, organizations=orgs, 
                           pending_donors=pending_donors, pending_orgs=pending_orgs,
                           pending_events=pending_events, approved_events=approved_events,
                           all_events=all_events)

@app.route('/dashboard/admin/approve_event/<int:id>', methods=['POST'])
def approve_event(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    event = Event.query.get(id)
    if event:
        event.is_approved = True
        db.session.commit()
        flash("Event approved successfully.", "success")
    return redirect('/dashboard/admin')

@app.route('/dashboard/admin/reject_event/<int:id>', methods=['POST'])
def reject_event(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    event = Event.query.get(id)
    if event:
        db.session.delete(event)
        db.session.commit()
        flash("Event rejection confirmed.", "info")
    return redirect('/dashboard/admin')

@app.route('/dashboard/admin/approve_user/<role>/<int:id>', methods=['POST'])
def approve_user(role, id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    if role == 'donor':
        user = Donor.query.get(id)
    else:
        user = Organization.query.get(id)
        
    if user:
        user.is_approved = True
        db.session.commit()
        flash(f"{role.capitalize()} approved successfully.", "success")
    return redirect('/dashboard/admin')

@app.route('/dashboard/admin/reject_user/<role>/<int:id>', methods=['POST'])
def reject_user(role, id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    if role == 'donor':
        user = Donor.query.get(id)
    else:
        user = Organization.query.get(id)
        
    if user:
        db.session.delete(user)
        db.session.commit()
        flash(f"{role.capitalize()} registration rejected.", "info")
    return redirect('/dashboard/admin')

@app.route('/dashboard/admin/delete_donor/<int:id>', methods=['POST'])
def delete_donor(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    donor = Donor.query.get(id)
    if donor:
        db.session.delete(donor)
        db.session.commit()
        flash("Donor deleted.", "success")
    return redirect('/dashboard/admin')

@app.route('/dashboard/admin/delete_org/<int:id>', methods=['POST'])
def delete_org(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    org = Organization.query.get(id)
    if org:
        Event.query.filter_by(org_id=id).delete()
        db.session.delete(org)
        db.session.commit()
        flash("Organization and its events deleted.", "success")
    return redirect('/dashboard/admin')

@app.route('/dashboard/admin/delete_event/<int:id>', methods=['POST'])
def delete_event(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    event = Event.query.get(id)
    if event:
        db.session.delete(event)
        db.session.commit()
        flash("Event deleted.", "success")
    return redirect('/dashboard/admin')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
