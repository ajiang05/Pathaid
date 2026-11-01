"""Minimal local foundation models for one PathAid installation."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class LocalProfile(Base):
    """Singleton private profile and its structured matching inputs."""

    __tablename__ = "local_profile"
    __table_args__ = (CheckConstraint("id = 1", name="ck_local_profile_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    school_revision: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    experiences: Mapped[list["ProfileExperience"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="ProfileExperience.position"
    )


class ProfileExperience(Base):
    """One structured activity, job, service role, membership, or honor."""

    __tablename__ = "profile_experiences"
    __table_args__ = (
        CheckConstraint("profile_id = 1", name="ck_profile_experience_singleton_owner"),
        CheckConstraint("kind IN ('activity', 'employment', 'volunteering', 'membership', 'leadership', 'honor')", name="ck_profile_experience_kind"),
        CheckConstraint("hours IS NULL OR hours >= 0", name="ck_profile_experience_hours"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("local_profile.id", ondelete="CASCADE"), default=1, index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    organization: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    current: Mapped[bool] = mapped_column(Boolean, default=False)
    hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    leadership: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    profile: Mapped[LocalProfile] = relationship(back_populates="experiences")


class AppSetting(Base):
    """Non-secret local settings; keys and credentials never belong here."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
