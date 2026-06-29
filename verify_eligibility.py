from app import app, db
from models import Donor
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

with app.app_context():
    if not Donor.query.filter_by(email='charlie@example.com').first():
        d3 = Donor(
            name='Charlie (B+)', 
            email='charlie@example.com', 
            phone='1122334455', 
            blood_group='B+', 
            dob=date(1995, 5, 5), 
            weight=70.0, 
            gender='Male', 
            password_hash=generate_password_hash('password123'), 
            last_donation_date=date.today() - timedelta(days=10), 
            is_approved=True
        )
        db.session.add(d3)
        db.session.commit()
        print('Charlie (B+) added (Recent donor - should not be eligible)')
    else:
        print('Charlie already exists')
