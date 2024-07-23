from project import db

class User(db.Model):    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    position = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(60), nullable=False)


class Cracked_ball(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cracked_ball = db.Column(db.Integer, nullable=False)
    date=db.Column(db.DateTime, nullable=False)

    
    def __repr__(self):
        return f'<Employee {self.name}>'