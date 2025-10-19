from flask import Flask, render_template, request,jsonify
from flask_sqlalchemy import SQLAlchemy 
from flask_cors import CORS 
from datetime import datetime,timedelta
import os 

app= Flask(__name__)
CORS(app)

#Database set up
app.config['SQLALCHEMY_DATABASE_URI']  = 'sqlite:///bookings.db'
app.config['SQLALCHEMY_TRACK'] = FALSE 
db=SQLAlchemy(app)

class Student(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    email=db.Column(db.String(120),unique=True,nullable=False)

#Database for bookings
class Booking(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    email=db.Column(db.String(120),nullable=False)
    room=db.Column(db.String(50), nullable=False)
    date=db.Column(db.String(10),nullable=False)
    time=db.Column(db.String(50),nullable=False)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id
            'email':self.email
            'room':self.room
            'date':self.date
            'time':self.time
        }
    
with app.app_context():
    db.create_all()
    #Load approved emails from text file on startup 
    if os.path.exists('emails.txt'):
        with open('emails.txt','r') as file:
            for line in file:
                email=line.strip()
                if email and not Student.query.filter_by(email=email).first():
                    db.session.add(Student(email=email))
            de.session.commit()
            print(f'Loaded approved emails')

#routes
@app.route('/')
def home():
    return render_template('index.html')


#API endpoints
@app.route('/api/login',methods=['POST'])
def login():
    """"Verify if email is an approved student"""
    data=request.json 
    email=data.get('email','').strip()

    student=Student.query.filter_by(email=email).first()
    if student:
        return jsonify({'success':True,'message':'Login successful'}),200
    else:
        return jsonify({'success':False,'message':'Email not approved'}),401

@app.route('/api/bookings/<room>/<date>', methods=['GET'])
def get_bookings(room,date):
    """Get all bookings for a specific room and date"""
    bookings=Booking.query.filter_by(room=room,date=date).all()
    return jsonify([booking.to_dict() for booking in bookings]),200

@app.route('/api/user-booking/<email>', methods=['GET'])
def get_user_booking(email):
    """Get active booking for a user"""
    booking=Booking.query.filter_by(email=email).first()
    if booking:
        return jsonify(booking.to_dict()),200
    return jsonify(None),200

@app.route('/api/book',methods=['POST']) 
def book_room():
    """Create a new booking"""
    data=request.json 
    email=data.get('email')
    room=data.get('room')
    date=data.get('date')
    time=data.get('time')

    #Check if user alreay has a booking 
    existing_booking=Booking.query.filter_by(email=email).first()
    if existing_booking:
        return jsonify({'success':False, 'message':'You already have an active booking'}),400

    #Check if slot is already booked 
    slot_booked=Booking.query.filter_by(room=room,date=date,time=time).first()
    if slot_booked:
        return jsonify({'success':False, 'message':'This slot is already booked'})
    
    #Create booking 
    new_booking=Booking(email=email, room=room, date=date, time=time)
    db.session.add(new_booking)
    db.session.commit()

    return jsonify({'success':True, 'booking':new_booking.to_dict()}),201

@app.route('/api/date-range', methods=['GET'])
def get_date_range():
    """Get min and max dates for booking (next day to 7 days from now)"""
    today=datetime.now()
    min_date=(today+ timedelta(days=1)).strftime('%Y-%m-%d')
    max_date=(today+ timedelta(days=7)).strftime('%Y=%m-%d')

    return jsonify({'min_date': min_date, 'max_date':max_date}),200

#Admin password 
ADMIN_PASSWORD= 'diyavora19'

#Admin endpoints
@app.route('/admin')
def admin_dashboard():
    """Admin dashboard- password protected"""
    data= request.json
    password=data.get('password','')

    if password==ADMIN_PASSWORD:
        return jsonify({'success':True, 'message': 'Login successful'}),200
    else:
        return jsonify({'success':False, 'message': 'Incorrect password'}),401

@app.route('/api/admin/students', methods=['GET'])
def admin_get_students():
    students=Student.query.all()
    return jsonify([{'id':s.id, 'email':s.email}for s in students]),200

@app.route('/api/admin/add-student',methods=['POST'])
def admin_add_student_api():
    """Add a new approved student"""
    data=request.json
    email= data.get('email','').strip()
    password= data.get('password','')

    #Verify password
    if password!= ADMIN_PASSWORD:
        return jsonify({'success':False, 'Incorrect password'}),401
    
    if not email:
        return jsonify({'success':False,'message':'Email required'}),400

    #Add new student
    new_student= Student(email=email)
    db.session.add(new_student)
    db.session.commit()

    return jsonify({'success': True, 'message': f'{email} added successfully'}), 201

@app.route('/api/admin/delete-student/<int:student_id>', methods=['POSt'])
def admin_delete_student_api(student_id):
    """Delete a student"""
    data=request.json
    password=data.get('password', '')

    #Verify password
    if password!= ADMIN_PASSWORD:
        return jsonify({'success':False, 'message':'Incorrect password'}),401
    
    student=Student.query.get(student_id)
    if not student:
        return jsonify({'success':False, 'message':'Student not found'}),404

    db.session.delete(student)
    db.session.commit()

    return jsonify({'success':True, 'message':f'{student.email} deleted' }),200

if __name__ =='__main__':
    app.run(debug=True)
        
 

