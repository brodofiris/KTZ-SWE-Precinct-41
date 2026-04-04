import jwt
import datetime
import os
from dotenv import load_dotenv
from passlib.context import CryptContext

# Setup the password hashing context
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Hashes a plain-text password."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Checks if a plain-text password matches the hashed one."""
    return pwd_context.verify (plain_password, hashed_password)

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY") # Keep this safe!

def create_token(user_id, role):
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
    }
    if SECRET_KEY is None:
        raise ValueError("Secret key is not set")
    
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def verify_token(token):
    try:
        if SECRET_KEY is None:
            raise ValueError("Secret key is not set")
        
        data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return data  # Returns the dictionary with user_id and role
    except:
        return None