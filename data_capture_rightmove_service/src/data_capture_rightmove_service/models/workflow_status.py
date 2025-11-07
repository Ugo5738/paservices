"""
Workflow status tracking models for the Data Capture Rightmove service.
"""

from sqlalchemy import Column, Float, Integer, String, Text, UniqueConstraint

from data_capture_rightmove_service.models.base import Base, SuperIdMixin


class WorkflowStatus(Base, SuperIdMixin):
    __tablename__ = "workflow_status"

    id = Column(Integer, primary_key=True)
    property_id = Column(String(255), nullable=True, index=True)
    context = Column(String(64), nullable=False, default="property_search")
    status = Column(String(64), nullable=False, default="STARTED")
    stage = Column(String(128), nullable=True)
    progress = Column(Float, nullable=True)
    data_location = Column(String(2048), nullable=True)
    last_error = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("super_id", "context", name="uq_workflow_status_context"),
    )
