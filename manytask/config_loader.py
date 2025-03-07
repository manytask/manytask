import logging
import os
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from . import models

logger = logging.getLogger(__name__)


def load_environment_config(unique_course_name: Optional[str] = None) -> bool:
    """
    Load environment configuration. Common configuration from .env.common,
    course-specific configuration from database.

    Args:
        unique_course_name: Optional unique course name to load specific course config from database

    Returns:
        bool: True if configuration was loaded successfully
    """
    root_dir = Path(__file__).parent.parent

    # load common configuration
    common_config_path = root_dir / ".env.common"
    if not common_config_path.exists():
        return False

    load_dotenv(common_config_path)

    required_common_vars = [
        "FLASK_SECRET_KEY",
        "DATABASE_URL",
        "STORAGE",
    ]

    missing_vars = []
    for var in required_common_vars:
        if not os.environ.get(var):
            missing_vars.append(var)

    if missing_vars:
        logger.error(f"Missing required common variables: {', '.join(missing_vars)}")
        return False

    # if a course name is specified, load its config from database
    if unique_course_name:
        if not get_course_config_from_db(unique_course_name):
            return False

        gitlab_url = os.environ.get("GITLAB_URL", "").rstrip("/")
        gitlab_instance = os.environ.get("GITLAB_INSTANCE_HOST", "").rstrip("/")
        if gitlab_instance != gitlab_url:
            logger.warning(f"GITLAB_INSTANCE_HOST ({gitlab_instance}) does not match GITLAB_URL ({gitlab_url})")
            os.environ["GITLAB_INSTANCE_HOST"] = gitlab_url

        required_course_vars = [
            "REGISTRATION_SECRET",
            "MANYTASK_COURSE_TOKEN",
            "UNIQUE_COURSE_NAME",
            "GITLAB_URL",
            "GITLAB_ADMIN_TOKEN",
            "GITLAB_COURSE_GROUP",
            "GITLAB_COURSE_PUBLIC_REPO",
            "GITLAB_COURSE_STUDENTS_GROUP",
            "GITLAB_CLIENT_ID",
            "GITLAB_CLIENT_SECRET",
        ]

        for var in required_course_vars:
            if not os.environ.get(var):
                missing_vars.append(var)

    return True


def get_available_courses() -> list[Dict[str, str]]:
    """
    Get a list of all available course configurations from database.

    Returns:
        list[Dict[str, str]]: List of dictionaries containing course information
                    [{name: str, unique_course_name: str}, ...]
    """

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return []

    try:
        engine = create_engine(database_url, echo=False)
        with Session(engine) as session:
            courses = session.query(models.Course).all()
            return [{"name": course.name, "unique_course_name": course.unique_course_name} for course in courses]
    except Exception as e:
        logger.error(f"Error getting available courses from database: {str(e)}")
        return []


def get_course_config_from_db(unique_course_name: str) -> bool:
    """
    Retrieve course configuration from the database and set environment variables.

    Args:
        course_name: Unique name of the course to load configuration for

    Returns:
        bool: True if configuration was loaded successfully
    """

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return False

    try:
        engine = create_engine(database_url, echo=False)
        with Session(engine) as session:
            try:
                course = session.query(models.Course).filter_by(unique_course_name=unique_course_name).one()
            except NoResultFound:
                logger.error(f"Course '{unique_course_name}' not found in database")
                return False

            os.environ["REGISTRATION_SECRET"] = course.registration_secret
            os.environ["MANYTASK_COURSE_TOKEN"] = course.token
            os.environ["UNIQUE_COURSE_NAME"] = course.unique_course_name
            os.environ["GITLAB_URL"] = course.gitlab_instance_host
            os.environ["GITLAB_ADMIN_TOKEN"] = course.gitlab_admin_token
            os.environ["GITLAB_COURSE_GROUP"] = course.gitlab_course_group
            os.environ["GITLAB_COURSE_PUBLIC_REPO"] = course.gitlab_course_public_repo
            os.environ["GITLAB_COURSE_STUDENTS_GROUP"] = course.gitlab_course_students_group
            os.environ["GITLAB_CLIENT_ID"] = course.gitlab_client_id
            os.environ["GITLAB_CLIENT_SECRET"] = course.gitlab_client_secret
            os.environ["SHOW_ALLSCORES"] = str(course.show_allscores).lower()

            logger.info(f"Successfully loaded configuration for course: {unique_course_name}")
            return True

    except Exception as e:
        logger.error(f"Error loading course configuration from database: {str(e)}")
        return False
