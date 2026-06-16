from database import engine
from sqlalchemy.orm import Session
from models.user import User

with Session(engine) as session:
    user = User(name="peter", age=18)
    session.add(user)
    session.commit()

    users = session.query(User).all()

    for user in users:
        print(user)
