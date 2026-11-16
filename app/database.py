import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Load environment configuration
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'flashback.db'}")
if DATABASE_URL.startswith("sqlite:///./"):
    # Normalize relative path to absolute relative to BASE_DIR
    relative_path = DATABASE_URL.replace("sqlite:///./", "")
    DATABASE_URL = f"sqlite:///{BASE_DIR / relative_path}"

# SQLAlchemy SQLite setup
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Visitor(Base):
    __tablename__ = "visitors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    guest_name = Column(String(100), default="Anonymous Guest", nullable=False, index=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    photos = relationship("Photo", back_populates="visitor", cascade="all, delete-orphan")


class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    visitor_id = Column(Integer, ForeignKey("visitors.id"), nullable=True, index=True)
    filename = Column(String(255), unique=True, index=True, nullable=False)
    original_filename = Column(String(255), nullable=False)
    guest_name = Column(String(100), default="Anonymous Guest", nullable=False)
    caption = Column(String(500), nullable=True)
    filter_applied = Column(String(50), default="normal", nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    visitor = relationship("Visitor", back_populates="photos")

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "guest_name": self.guest_name,
            "caption": self.caption or "",
            "filter_applied": self.filter_applied or "normal",
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "likes_count": self.likes_count,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "url": f"/uploads/{self.filename}",
        }


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

