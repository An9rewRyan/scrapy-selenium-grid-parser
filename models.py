from typing import List, Optional
from pydantic import BaseModel, Field

class Categorie(BaseModel):
    name: str
    parent: str
    link: str

class City(BaseModel):
    id: int
    name: str
    regionId: int
    slug: Optional[str] = None
    isDelivery: bool

class PriceData(BaseModel):
    current: float
    original: float
    sale_tag: str

class Stock(BaseModel):
    in_stock: bool
    count: int

class Assets(BaseModel):
    main_image: str
    set_images: List[str]
    view360: List[str]
    video: List[str]

class Metadata(BaseModel):
    description: str = Field(..., alias="__description")
    АРТИКУЛ: Optional[str]
    СТРАНА_ПРОИЗВОДИТЕЛЬ: str = Field(..., alias="СТРАНА ПРОИЗВОДИТЕЛЬ")

class ProductInfo(BaseModel):
    timestamp: int
    RPC: Optional[str]
    url: str
    title: str
    marketing_tags: List[str]
    brand: str
    section: List[str]
    price_data: PriceData
    stock: Stock
    assets: Assets
    metadata: Metadata
    variants: int
