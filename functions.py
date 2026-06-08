def validate_password(password):
    \
\
\
\
\
\
\
    if not isinstance(password, str):
        raise TypeError("Пароль должен быть строкой")
    
    if len(password) < 8:
        return False
    
    if " " in password:
        return False
        
    has_digit = any(char.isdigit() for char in password)
    has_letter = any(char.isalpha() for char in password)
    
    return has_digit and has_letter


def divide(a, b):
    \
\
\
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("Аргументы должны быть числами (int или float)")
        
    if b == 0:
        raise ZeroDivisionError("Деление на ноль недопустимо")
        
    return a / b
