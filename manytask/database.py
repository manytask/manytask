import logging
import time
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from sqlalchemy.exc import OperationalError

from .table import RatingTableAbs, TableApi

logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    pass


class DatabaseApi(TableApi):
    def __init__(self, app: Flask, db_url: str, retries: int = 10, delay: int = 1):
        """
        :param app:
        :param db_url:
        :param retries:
        :param delay:
        """

        self.app = app
        self.app.config['SQLALCHEMY_DATABASE_URI'] = db_url
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        self.db = SQLAlchemy(self.app)
        self.define_models()

        self.wait_for_db(retries, delay)

        with self.app.app_context():
            self.db.create_all()

    def wait_for_db(self, retries: int, delay: int):
        """Wait until the database is available"""
        
        for _ in range(retries):
            try:
                with self.app.app_context():
                    self.db.engine.connect()
                    self.db.engine.dispose()
                logger.info("Database connected")
                return
            except OperationalError as e:
                logger.warning(f"Database connect failed: {e}\nRetrying...")
                time.sleep(delay)

        logger.error("Database connect failed")
        raise DatabaseConnectionError("Database connect failed")

    def define_models(self):
        """Defining database models"""

        class User(self.db.Model):
            __tablename__ = "users"

            id = self.db.Column(self.db.Integer, primary_key=True)
            username = self.db.Column(self.db.String(100), unique=True, nullable=False)
            is_manytask_admin = self.db.Column(self.db.Boolean, default=False)
        
        
        class Course(self.db.Model):
            __tablename__ = 'courses'
            
            id = self.db.Column(self.db.Integer, primary_key=True)
            name = self.db.Column(self.db.String(100), nullable=False)
            registration_secret = self.db.Column(self.db.String(100), nullable=False)
            # gitlab_data_id
            # gdoc_data_id
            show_allscores = self.db.Column(self.db.Boolean, default=False)
        
        
        class UserOnCourse(self.db.Model):
            __tablename__ = 'user_on_course'
            
            id = self.db.Column(self.db.Integer, primary_key=True)
            user_id = self.db.Column(self.db.Integer, self.db.ForeignKey('users.id'))
            course_id = self.db.Column(self.db.Integer, self.db.ForeignKey('courses.id'))
            is_course_admin = self.db.Column(self.db.Boolean, default=False)
            repo_name = self.db.Column(self.db.String(100))
            join_date = self.db.Column(self.db.DateTime, default=datetime.now)
        
        
        class Task(self.db.Model):
            __tablename__ = 'tasks'
            
            id = self.db.Column(self.db.Integer, primary_key=True)
            name = self.db.Column(self.db.String(100), nullable=False)
            course_id = self.db.Column(self.db.Integer, self.db.ForeignKey('courses.id'))
            group_id = self.db.Column(self.db.Integer, self.db.ForeignKey('task_groups.id'))
            deadline_id = self.db.Column(self.db.Integer, self.db.ForeignKey('deadlines.id'))
        
        
        class TaskGroup(self.db.Model):
            __tablename__ = 'task_groups'
            
            id = self.db.Column(self.db.Integer, primary_key=True)
            name = self.db.Column(self.db.String(100))
        
        
        class Deadline(self.db.Model):
            __tablename__ = 'deadlines'
            
            id = self.db.Column(self.db.Integer, primary_key=True)
            data = self.db.Column(self.db.JSON)
        
        
        class Grade(self.db.Model):
            __tablename__ = 'grades'
            
            id = self.db.Column(self.db.Integer, primary_key=True)
            user_id = self.db.Column(self.db.Integer, self.db.ForeignKey('users.id'))
            task_id = self.db.Column(self.db.Integer, self.db.ForeignKey('tasks.id'))
            score = self.db.Column(self.db.Integer)
            submit_date = self.db.Column(self.db.DateTime)
        
        
        class ApiRequest(self.db.Model):
            __tablename__ = 'api_requests'
            
            id = self.db.Column(self.db.Integer, primary_key=True)
            course_id = self.db.Column(self.db.Integer, self.db.ForeignKey('courses.id'))
            date = self.db.Column(self.db.DateTime, default=datetime.now)
            type # TODO: Enum
            data = self.db.Column(self.db.JSON)
        
        

        self.User = User
        self.Course = Course
        self.UserOnCourse = UserOnCourse
        self.Task = Task
        self.TaskGroup = TaskGroup
        self.Deadline = Deadline
        self.Grade = Grade
        self.ApiRequest = ApiRequest

    def fetch_rating_table(self) -> "RatingTableAbs":
        pass

    def get_spreadsheet_url(self) -> str:
        pass


class RatingDatabase(RatingTableAbs):
    pass