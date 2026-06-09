import pytest
from mock_api import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_tc_int_01_auth_and_booking(client):
    # Part 1: Login
    response = client.post('/api/auth/login', json={"login": "user@test.com", "password": "Test1234!"})
    assert response.status_code == 200
    token = response.json.get("session_token")
    assert token == "tok_user_123"

    # Part 2: Create Booking
    response = client.post('/api/booking/create', headers={'Authorization': f'Bearer {token}'}, json={"event_id": 5})
    assert response.status_code == 200
    assert response.json.get("booking_id") == 100
    assert response.json.get("status") == "pending"

def test_tc_int_02_invalid_token(client):
    response = client.post('/api/booking/create', headers={'Authorization': 'Bearer INVALID_TOKEN_12345'}, json={"event_id": 5})
    assert response.status_code == 401
    assert response.json.get("error") == "Unauthorized"

def test_tc_int_03_nonexistent_event(client):
    response = client.post('/api/booking/create', headers={'Authorization': 'Bearer tok_user_123'}, json={"event_id": 99999})
    assert response.status_code == 404
    assert response.json.get("error") == "Event not found"

def test_tc_int_04_successful_payment(client):
    # Using booking_id 100 which was created in TC-INT-01
    response = client.post('/api/payment/pay', json={"booking_id": 100, "card_token": "tok_test_valid"})
    assert response.status_code == 200
    assert response.json.get("payment_status") == "success"

def test_tc_int_05_double_payment_bug(client):
    # This simulates the bug where a second payment returns 200 instead of 409 Conflict
    response = client.post('/api/payment/pay', json={"booking_id": 100, "card_token": "tok_test_valid"})
    # The bug: we expect 409, but the API incorrectly returns 200
    assert response.status_code == 200 
    assert "Payment accepted again (BUG)" in response.json.get("message", "")

def test_tc_int_06_payment_declined(client):
    # First create a new booking (id 101)
    client.post('/api/booking/create', headers={'Authorization': 'Bearer tok_user_123'}, json={"event_id": 5})
    
    response = client.post('/api/payment/pay', json={"booking_id": 101, "card_token": "tok_test_decline"})
    assert response.status_code == 402
    assert response.json.get("payment_status") == "declined"
