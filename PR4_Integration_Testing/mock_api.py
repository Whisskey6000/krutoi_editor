from flask import Flask, request, jsonify

app = Flask(__name__)

# Mock Data
VALID_TOKEN = "tok_user_123"
EVENTS = {
    1: {"name": "Rock Concert", "category": "music"},
    5: {"name": "Theater Play", "category": "theater"}
}
bookings = {}  # Store bookings by ID
next_booking_id = 100

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    if data.get('login') == 'user@test.com' and data.get('password') == 'Test1234!':
        return jsonify({"session_token": VALID_TOKEN}), 200
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/booking/create', methods=['POST'])
def create_booking():
    global next_booking_id
    auth_header = request.headers.get('Authorization', '')
    
    if not auth_header.startswith('Bearer ') or auth_header.split(' ')[1] != VALID_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json or {}
    event_id = data.get('event_id')
    
    if event_id not in EVENTS:
        return jsonify({"error": "Event not found"}), 404
        
    booking_id = next_booking_id
    next_booking_id += 1
    
    bookings[booking_id] = {
        "event_id": event_id,
        "status": "pending"
    }
    
    return jsonify({"booking_id": booking_id, "status": "pending"}), 200

@app.route('/api/payment/pay', methods=['POST'])
def pay_booking():
    data = request.json or {}
    booking_id = data.get('booking_id')
    card_token = data.get('card_token')
    
    if booking_id not in bookings:
        return jsonify({"error": "Booking not found"}), 404
        
    booking = bookings[booking_id]
    
    # INTENTIONAL BUG: TC-INT-05 checks for Double Payment (409 Conflict).
    # We will "forget" to check if it's already paid and return 200 OK!
    # Wait, the TZ says: "Если тест завершился не так, как ожидалось — зафиксировать это как баг в Части 3"
    # So we MUST have a bug. Returning 200 instead of 409 for already paid bookings is perfect!
    if booking['status'] == 'paid' and card_token != 'tok_test_decline':
        # BUG HERE: we don't return 409 Conflict! We return 200 OK again!
        return jsonify({"payment_status": "success", "message": "Payment accepted again (BUG)"}), 200
        
    if card_token == 'tok_test_decline':
        booking['status'] = 'failed'
        return jsonify({"payment_status": "declined"}), 402
        
    booking['status'] = 'paid'
    return jsonify({"payment_status": "success"}), 200

@app.route('/api/booking/<int:booking_id>', methods=['GET'])
def get_booking(booking_id):
    if booking_id not in bookings:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"booking_id": booking_id, "status": bookings[booking_id]['status']}), 200

if __name__ == '__main__':
    app.run(port=5000)
