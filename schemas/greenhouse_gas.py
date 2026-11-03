from pydantic import BaseModel, Field


class GreenhouseGasListItem(BaseModel):
    id: int
    name: str
    formula: str | None
    global_warming_potential_100y: float | None
    short_description: str | None
    concentration_ppm: float | None
    temperature_change_c: float | None
    image_url: str
    video_url: str
    is_creator: int


class GreenhouseGasFeedItem(BaseModel):
    id: int
    name: str
    formula: str | None
    global_warming_potential_100y: float | None
    short_description: str | None
    concentration_ppm: float | None
    temperature_change_c: float | None
    image_url: str
    video_url: str
    is_liked: int
    likes_count: int


class GreenhouseGasDraftResponse(BaseModel):
    id: int
    name: str
    formula: str | None
    global_warming_potential_100y: float | None
    short_description: str | None
    concentration_ppm: float | None
    temperature_change_c: float | None
    image_url: str
    video_url: str


class GreenhouseGasCreateResponse(BaseModel):
    id: int
    name: str
    status: str
    image_url: str
    video_url: str


class GreenhouseGasCreateRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )
    formula: str | None = Field(
        default=None,
        max_length=50,
    )
    global_warming_potential_100y: float | None = None
    short_description: str | None = None
    concentration_ppm: float | None = Field(
        default=None,
        gt=0,
    )


class GreenhouseGasPublishResponse(BaseModel):
    id: int
    name: str
    status: str
    image_url: str
    video_url: str
    published_at: str


class LikeRequest(BaseModel):
    like: int = Field(
        ...,
        ge=0,
        le=1,
        description="0 — убрать лайк, 1 — поставить лайк",
    )