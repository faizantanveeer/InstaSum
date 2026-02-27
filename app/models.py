from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Index
from sqlalchemy.orm import relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    jobs = relationship("Job", back_populates="user")
    reels = relationship("Reel", back_populates="user")


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    biography = Column(Text, nullable=True)
    profile_pic_url = Column(String(1000), nullable=True)
    followers = Column(Integer, nullable=True)
    following = Column(Integer, nullable=True)
    post_count = Column(Integer, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    last_job_id = Column(Integer, nullable=True)
    is_private_last_seen = Column(Boolean, default=False)
    last_fetched_at = Column(DateTime, nullable=True)

    jobs = relationship("Job", back_populates="profile", foreign_keys="Job.profile_id")
    reels = relationship("Reel", back_populates="profile")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    job_type = Column(String(20), default="batch")
    target_profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    target_reel_id = Column(Integer, ForeignKey("reels.id"), nullable=True)

    status = Column(String(50), default="queued")
    phase = Column(String(50), default="queued")
    message = Column(Text, default="Queued")

    requested_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    total_count = Column(Integer, default=0)
    processed_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)

    cache_hit = Column(Boolean, default=False)

    profile = relationship("Profile", foreign_keys=[profile_id], back_populates="jobs")
    target_profile = relationship("Profile", foreign_keys=[target_profile_id])
    user = relationship("User", back_populates="jobs")
    reels = relationship("Reel", back_populates="job", foreign_keys="Reel.job_id")


class Reel(Base):
    __tablename__ = "reels"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    username = Column(String(255), nullable=True, index=True)

    shortcode = Column(String(50), nullable=False)
    reel_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(1000), nullable=True)
    video_url = Column(String(1000), nullable=True)
    thumbnail_path = Column(String(500), nullable=True)
    audio_path = Column(String(500), nullable=True)
    caption = Column(Text, nullable=True)

    posted_at = Column(DateTime, nullable=True)
    like_count = Column(Integer, nullable=True)
    comment_count = Column(Integer, nullable=True)
    view_count = Column(Integer, nullable=True)
    video_duration = Column(Integer, nullable=True)

    transcript = Column(Text, nullable=True)
    transcript_status = Column(String(50), default="pending")
    ai_title = Column(String(500), nullable=True)
    ai_summary = Column(Text, nullable=True)
    summary_detail = Column(Text, nullable=True)

    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    processing_status = Column(String(50), default="pending")
    error_reason = Column(Text, nullable=True)

    job = relationship("Job", back_populates="reels", foreign_keys=[job_id])
    profile = relationship("Profile", back_populates="reels")
    user = relationship("User", back_populates="reels")

    __table_args__ = (
        Index("ix_reels_user_profile_shortcode", "user_id", "profile_id", "shortcode", unique=True),
    )


class ReelError(Base):
    __tablename__ = "reel_errors"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, nullable=False)
    shortcode = Column(String(50), nullable=True)
    stage = Column(String(50), nullable=False)
    error_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


