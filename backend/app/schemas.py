from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------- Auth ----------

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    role: str = Field(default="client", pattern="^(client|carrier)$")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str
    role: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------- Carriers ----------

class CarrierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    type: str
    city: str
    vehicle: str
    package_types: List[str]
    zones_served: List[str]
    base_price: float
    price_per_km: float
    rating: float
    review_count: int
    available_days: List[str]
    time_windows: List[str]
    response_time: str
    verified: bool
    completed_deliveries: int
    years_active: int
    delivery_estimate: Optional[str] = None
    bio: str


# ---------- Bookings ----------

class BookingCreate(BaseModel):
    carrier_id: str
    pickup_address: str
    pickup_city: str
    pickup_postal_code: Optional[str] = None
    dropoff_address: str
    dropoff_city: str
    dropoff_postal_code: Optional[str] = None
    package_type: str
    weight_kg: float = Field(gt=0)
    dimensions: Optional[str] = None
    description: Optional[str] = None
    fragile: bool = False
    requested_date: str
    time_window: str


class BookingQuote(BaseModel):
    distance_km: float
    distance_source: str
    base_price: float
    distance_price: float
    fragile_surcharge: float
    total_price: float
    currency: str = "EUR"


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    ref: str
    carrier_id: str
    pickup_address: str
    pickup_city: str
    dropoff_address: str
    dropoff_city: str
    package_type: str
    weight_kg: float
    fragile: bool
    requested_date: str
    time_window: str
    distance_km: float
    distance_source: str
    price: float
    currency: str
    status: str
    payment_status: str
    confirmation_code: str
    external_tracking_number: Optional[str] = None
    created_at: datetime


# ---------- Tracking ----------

class TrackingEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    note: Optional[str] = None
    source: str
    created_at: datetime


class TrackingUpdateIn(BaseModel):
    status: str
    note: Optional[str] = None


# ---------- Messaging ----------

class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    conversation_id: str
    sender_user_id: str
    sender_role: str
    text: str
    created_at: datetime
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    booking_id: Optional[str] = None
    client_id: str
    carrier_id: str
    created_at: datetime


# ---------- Payments ----------

class PaymentIntentOut(BaseModel):
    client_secret: str
    publishable_key: str
    amount_cents: int
    currency: str


# ---------- Geocoding ----------

class DistanceQuery(BaseModel):
    pickup_city: str
    dropoff_city: str
    pickup_address: Optional[str] = None
    dropoff_address: Optional[str] = None
    vehicle: str = "voiture"
    carrier_id: Optional[str] = None
    fragile: bool = False


class DistanceOut(BaseModel):
    distance_km: float
    source: str
    pickup_coordinates: Optional[List[float]] = None
    dropoff_coordinates: Optional[List[float]] = None
