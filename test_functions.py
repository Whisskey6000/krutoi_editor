import pytest
from functions import validate_password, divide

                                     

@pytest.mark.parametrize("password,expected", [
    ("KrutoiPass123", True),                                  
    ("P1234567", True),                                               
    ("VeryLongPassword999", True),                 
])
def test_validate_password_positive(password, expected):
    assert validate_password(password) is expected

@pytest.mark.parametrize("password,expected", [
    ("Short1", False),                                             
    ("NoDigitsHere", False),                
    ("1234567890", False),                  
    ("Pass 1234", False),                          
])
def test_validate_password_negative(password, expected):
    assert validate_password(password) is expected

def test_validate_password_type_error():
    with pytest.raises(TypeError):
        validate_password(12345678)             


                          

@pytest.mark.parametrize("a,b,expected", [
    (10, 2, 5.0),                          
    (5.0, 2.0, 2.5),                       
    (-12, 3, -4.0),                                
    (10, -2, -5.0),                                 
    (0, 5, 0.0),                          
])
def test_divide_positive(a, b, expected):
    assert divide(a, b) == expected

def test_divide_zero_division():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)

@pytest.mark.parametrize("a,b", [
    ("10", 2),
    (10, "2"),
    (None, 5),
])
def test_divide_type_error(a, b):
    with pytest.raises(TypeError):
        divide(a, b)
