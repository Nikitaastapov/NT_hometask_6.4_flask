from flask import Flask, jsonify, request
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, create_engine, func
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.exc import IntegrityError
from sqlalchemy_utils import EmailType
from hashlib import md5
import pydantic
from flask.views import MethodView

app = Flask("app")
# для БД: тип БД, имя пользователя, пароль@, хост, порт, имя БД
engine = create_engine('postgresql+psycopg2://nikita:1234@127.0.0.1:5431/billboard')
# создание базового класса для ORM модели
Base = declarative_base()


# DB
class User(Base):
    __tablename__ = 'user_fields'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_name = Column(String, nullable=False, index=True, unique=True)
    email = Column(EmailType, index=True, unique=True)
    password = Column(String(60), nullable=False)
    registration_time = Column(DateTime, server_default=func.now())
    billboards = relationship("Billboard", backref='user_fields')


class Billboard(Base):
    __tablename__ = 'billboard_fields'
    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String, nullable=False, index=True, unique=True)
    description = Column(String, nullable=False, index=True, unique=True)
    user_id = Column(Integer, ForeignKey('user_fields.id', ondelete="CASCADE"))
    creation_time = Column(DateTime, server_default=func.now())


Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)


# ERRORS
class HttpError(Exception):
    def __init__(self, status_code: int, description):
        self.status_code = status_code
        self.description = description


# обработка ошибок
@app.errorhandler(HttpError)
def error_handler(error: HttpError):
    response = jsonify({'status': 'error', 'description': error.description})
    response.status_code = error.status_code
    return response


class CreateUser(pydantic.BaseModel):
    user_name: str
    password: str
    email: str

    @pydantic.field_validator('password')
    def validate_password(cls, value):
        if len(value) < 6:
            raise ValueError('password is too short')
        return value


def validate(input_data, validation_model):
    try:
        model_item = validation_model(**input_data)
        return model_item.dict(exclude_none=True)
    except pydantic.ValidationError as err:
        raise HttpError(400, err.errors())


def get_user(user_id: int, session: Session):
    user = session.get(User, user_id)
    if user is None:
        raise HttpError(404, 'user not found')
    return user


def hash_password(password: str):
    return md5(password.encode()).hexdigest()


class CreateBillboard(pydantic.BaseModel):
    topic: str
    description: str
    user_id: int


def get_article(billboard_id: int, session: Session):
    article = session.get(Billboard, billboard_id)
    if article is None:
        raise HttpError(404, 'article not found')
    return article


# VIEW
class UserView(MethodView):
    def get(self, user_id: int):
        with Session() as session:
            user = get_user(user_id, session)
            # user = session.get(User, user_id)
            return jsonify({'id': user.id,
                            'user_name': user.user_name,
                            'registration_time': user.registration_time.isoformat()})

    def post(self):
        json_data = request.json
        json_data = validate(json_data, CreateUser)
        # преобразуем пароль в хэш
        json_data['password'] = hash_password(json_data['password'])
        with Session() as session:
            user = User(user_name=json_data['user_name'], password=json_data['password'], email=json_data['email'])
            session.add(user)
            try:
                session.commit()
            except IntegrityError as er:
                raise HttpError(409, 'user already exists')
            return jsonify({'id': user.id, 'password': json_data['password']})


class BillboardView(MethodView):
    def get(self, billboard_id: int):
        with Session() as session:
            article = get_article(billboard_id, session)
            # user = session.get(User, user_id)
            return jsonify({'id': article.id,
                            'topic': article.topic,
                            'description': article.description,
                            'user_id': article.user_id,
                            'creation_time_time': article.creation_time.isoformat()})


    def post(self):
        json_data = request.json
        json_data = validate(json_data, CreateBillboard)
        with Session() as session:
            article = Billboard(topic=json_data['topic'],
                                description=json_data['description'],
                                user_id=json_data['user_id'])
            session.add(article)
            try:
                session.commit()
            except IntegrityError as er:
                raise HttpError(409, 'article already exists')
            return jsonify({'id': article.id, 'topic': json_data['topic'], 'status': 'published'})

    def delete(self, billboard_id: int):
        with Session() as session:
            article = get_article(billboard_id, session)
            session.delete(article)
            session.commit()
            return jsonify({'status': 'deleted'})


# REQUESTS
app.add_url_rule('/user/<int:user_id>/', view_func=UserView.as_view('user'), methods=['GET', 'DELETE'])
app.add_url_rule('/user/', view_func=UserView.as_view('user_create'), methods=['POST'])
app.add_url_rule('/article/', view_func=BillboardView.as_view('billboard_create'), methods=['POST'])
app.add_url_rule('/article/<int:billboard_id>/',
                 view_func=BillboardView.as_view('billboard'),
                 methods=['GET', 'DELETE'])

if __name__ == '__main__':
    app.run()
