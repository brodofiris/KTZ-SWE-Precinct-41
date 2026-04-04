# create_admin.py
import asyncio
from src.database import AsyncSessionLocal, User
from src.auth import get_password_hash

async def make_admin():
    print("=== TRAIN SYSTEM ADMIN CREATION ===")
    fname = input("First Name: ")
    lname = input("Last Name: ")
    op_id = input("Admin ID (Username): ")
    password = input("Password: ")

    async with AsyncSessionLocal() as session:
        new_admin = User(
            first_name=fname,
            last_name=lname,
            operator_id=op_id,
            hashed_password=get_password_hash(password),
            role="admin" # Here is where the magic happens!
        )
        session.add(new_admin)
        await session.commit()
        print(f"\nSUCCESS: Admin '{op_id}' has been added to the database.")

if __name__ == "__main__":
    asyncio.run(make_admin())