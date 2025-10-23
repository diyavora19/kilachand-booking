from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy 
from flask_cors import CORS 
from datetime import datetime, timedelta
import os 

app = Flask(__name__)
CORS(app)

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bookings.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
db = SQLAlchemy(app)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)

# Database for bookings
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    room = db.Column(db.String(50), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    time = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'room': self.room,
            'date': self.date,
            'time': self.time
        }
    
with app.app_context():
    db.create_all()
    # Load approved emails from text file on startup 
    if os.path.exists('emails.txt'):
        with open('emails.txt', 'r') as file:
            for line in file:
                email = line.strip()
                if email and not Student.query.filter_by(email=email).first():
                    db.session.add(Student(email=email))
            db.session.commit()
            print(f'Loaded approved emails')

# Routes
@app.route('/')
def home():
    return render_template('index.html')

# API endpoints
@app.route('/api/login', methods=['POST'])
def login():
    """Verify if email is an approved student"""
    data = request.json 
    email = data.get('email', '').strip()

    student = Student.query.filter_by(email=email).first()
    if student:
        return jsonify({'success': True, 'message': 'Login successful'}), 200
    else:
        return jsonify({'success': False, 'message': 'Email not approved'}), 401

@app.route('/api/bookings/<room>/<date>', methods=['GET'])
def get_bookings(room, date):
    """Get all bookings for a specific room and date"""
    bookings = Booking.query.filter_by(room=room, date=date).all()
    return jsonify([booking.to_dict() for booking in bookings]), 200

@app.route('/api/user-booking/<email>', methods=['GET'])
def get_user_booking(email):
    """Get active booking for a user"""
    booking = Booking.query.filter_by(email=email).first()
    if booking:
        return jsonify(booking.to_dict()), 200
    return jsonify(None), 200

@app.route('/api/book', methods=['POST']) 
def book_room():
    """Create a new booking"""
    data = request.json 
    email = data.get('email')
    room = data.get('room')
    date = data.get('date')
    time = data.get('time')

    # Check if user already has a booking 
    existing_booking = Booking.query.filter_by(email=email).first()
    if existing_booking:
        return jsonify({'success': False, 'message': 'You already have an active booking'}), 400

    # Helper function to parse time
    def parse_time(time_str):
        parts = time_str.strip().split()
        hour = int(parts[0].split(':')[0])
        minute = int(parts[0].split(':')[1]) if ':' in parts[0] else 0
        am_pm = parts[1] if len(parts) > 1 else ''
        
        if am_pm == 'PM' and hour != 12:
            hour += 12
        elif am_pm == 'AM' and hour == 12:
            hour = 0
            
        return hour * 60 + minute
    
    def times_overlap(slot1, slot2):
        s1_parts = slot1.split(' - ')
        s1_start = parse_time(s1_parts[0])
        s1_end = parse_time(s1_parts[1])
        
        s2_parts = slot2.split(' - ')
        s2_start = parse_time(s2_parts[0])
        s2_end = parse_time(s2_parts[1])
        
        return s1_start < s2_end and s2_start < s1_end

    # Check if slot conflicts with existing bookings for this room
    all_bookings = Booking.query.filter_by(room=room, date=date).all()
    for booking in all_bookings:
        if times_overlap(time, booking.time):
            return jsonify({'success': False, 'message': 'This time slot conflicts with an existing booking'}), 400
    
    # Create booking 
    new_booking = Booking(email=email, room=room, date=date, time=time)
    db.session.add(new_booking)
    db.session.commit()

    return jsonify({'success': True, 'booking': new_booking.to_dict()}), 201

@app.route('/api/cancel-booking/<int:booking_id>', methods=['DELETE'])
def cancel_booking(booking_id):
    """Cancel a booking"""
    booking = Booking.query.get(booking_id)
    if not booking:
        return jsonify({'success': False, 'message': 'Booking not found'}), 404
    
    db.session.delete(booking)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Booking cancelled'}), 200

@app.route('/api/date-range', methods=['GET'])
def get_date_range():
    """Get min and max dates for booking (next day to 7 days from now)"""
    today = datetime.now()
    min_date = today.strftime('%Y-%m-%d')
    max_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')

    return jsonify({'min_date': min_date, 'max_date': max_date}), 200

@app.route('/api/available-rooms/<date>/<time>', methods=['GET'])
def get_available_rooms(date, time):
    """Get all rooms and their availability for a specific date and time"""
    
    # Parse the requested time slot
    def parse_time(time_str):
        """Convert time string to minutes since midnight"""
        parts = time_str.strip().split()
        hour = int(parts[0].split(':')[0])
        minute = int(parts[0].split(':')[1]) if ':' in parts[0] else 0
        am_pm = parts[1] if len(parts) > 1 else ''
        
        if am_pm == 'PM' and hour != 12:
            hour += 12
        elif am_pm == 'AM' and hour == 12:
            hour = 0
            
        return hour * 60 + minute
    
    def times_overlap(slot1, slot2):
        """Check if two time slots overlap"""
        # Parse slot1 (requested slot)
        s1_parts = slot1.split(' - ')
        s1_start = parse_time(s1_parts[0])
        s1_end = parse_time(s1_parts[1])
        
        # Parse slot2 (booked slot)
        s2_parts = slot2.split(' - ')
        s2_start = parse_time(s2_parts[0])
        s2_end = parse_time(s2_parts[1])
        
        # Check overlap: slots overlap if one starts before the other ends
        # Use <= to allow exact touching times (e.g., 9-10 and 10-12 don't overlap)
        return s1_start < s2_end and s2_start < s1_end
    
    # Get all bookings for this date
    all_bookings = Booking.query.filter_by(date=date).all()
    
    # Room definitions
    rooms = [
        {'name': '910', 'capacity': '1-8 people'},
        {'name': '911', 'capacity': '1-4 people'},
        {'name': '912', 'capacity': '1-8 people'},
    ]
    
    # Check availability for each room
    available_rooms = []
    for room in rooms:
        is_available = True
        # Check if any booking for this room conflicts with requested time
        for booking in all_bookings:
            if booking.room == room['name'] and times_overlap(time, booking.time):
                is_available = False
                break
        
        available_rooms.append({
            'name': room['name'],
            'capacity': room['capacity'],
            'available': is_available
        })
    
    return jsonify({'rooms': available_rooms}), 200

# Admin password 
ADMIN_PASSWORD = 'diyavora19'

# Admin endpoints
@app.route('/admin')
def admin_dashboard():
    """Admin dashboard - password protected"""
    return render_template('admin.html')

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Verify admin password"""
    data = request.json
    password = data.get('password', '')

    if password == ADMIN_PASSWORD:
        return jsonify({'success': True, 'message': 'Login successful'}), 200
    else:
        return jsonify({'success': False, 'message': 'Incorrect password'}), 401

@app.route('/api/admin/students', methods=['GET'])
def admin_get_students():
    """Get all approved students"""
    students = Student.query.all()
    return jsonify([{'id': s.id, 'email': s.email} for s in students]), 200

@app.route('/api/admin/add-student', methods=['POST'])
def admin_add_student_api():
    """Add a new approved student"""
    data = request.json
    email = data.get('email', '').strip()
    password = data.get('password', '')

    # Verify password
    if password != ADMIN_PASSWORD:
        return jsonify({'success': False, 'message': 'Incorrect password'}), 401
    
    if not email:
        return jsonify({'success': False, 'message': 'Email required'}), 400

    # Check if student already exists
    if Student.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Email already exists'}), 400

    # Add new student
    new_student = Student(email=email)
    db.session.add(new_student)
    db.session.commit()

    return jsonify({'success': True, 'message': f'{email} added successfully'}), 201

@app.route('/api/admin/delete-student/<int:student_id>', methods=['POST'])
def admin_delete_student_api(student_id):
    """Delete a student"""
    data = request.json
    password = data.get('password', '')

    # Verify password
    if password != ADMIN_PASSWORD:
        return jsonify({'success': False, 'message': 'Incorrect password'}), 401
    
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    db.session.delete(student)
    db.session.commit()

    return jsonify({'success': True, 'message': f'{student.email} deleted'}), 200

if __name__ == '__main__':
    app.run(debug=False)