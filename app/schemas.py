from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class PhotoBase(BaseModel):
    guest_name: str = Field(default="Anonymous Guest", max_length=100)
    caption: Optional[str] = Field(default="", max_length=500)
    filter_applied: str = Field(default="normal", max_length=50)


class PhotoCreate(PhotoBase):
    pass


class PhotoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    original_filename: str
    guest_name: str
    caption: Optional[str] = ""
    filter_applied: str = "normal"
    file_size: int
    mime_type: str
    likes_count: int = 0
    created_at: datetime
    url: str


class PhotoLikeResponse(BaseModel):
    id: int
    likes_count: int
    message: str = "Liked successfully"


class StatsResponse(BaseModel):
    total_photos: int
    total_guests: int
    total_likes: int
    latest_photo: Optional[PhotoResponse] = None


class DeleteResponse(BaseModel):
    success: bool
    message: str
    deleted_id: int

