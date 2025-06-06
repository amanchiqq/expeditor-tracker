from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

if __name__ == "__main__":
    password = "password"  # Пароль для user1
    hashed_password = get_password_hash(password)
    print(hashed_password)