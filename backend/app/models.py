import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    client = "client"
    carrier = "carrier"
    admin = "admin"


class BookingStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    picked_up = "picked_up"
    in_transit = "in_transit"
    delivered = "delivered"
    cancelled = "cancelled"


class PaymentStatus(str, enum.Enum):
    unpaid = "unpaid"
    processing = "processing"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"


class VehicleType(str, enum.Enum):
    velo = "velo"
    scooter = "scooter"
    voiture = "voiture"
    camionnette = "camionnette"
    camion = "camion"
    avion = "avion"
    bateau = "bateau"


class ExternalCarrierNetwork(str, enum.Enum):
    none = "none"
    chronopost = "chronopost"
    colissimo = "colissimo"
    dhl = "dhl"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.client, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    carrier_profile: Mapped[Optional["CarrierProfile"]] = relationship(back_populates="user", uselist=False)
    bookings: Mapped[list["Booking"]] = relationship(back_populates="client", foreign_keys="Booking.client_id")


class CarrierProfile(Base):
    __tablename__ = "carrier_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # individuel / entreprise
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    vehicle: Mapped[VehicleType] = mapped_column(Enum(VehicleType), nullable=False)
    external_network: Mapped[ExternalCarrierNetwork] = mapped_column(
        Enum(ExternalCarrierNetwork), default=ExternalCarrierNetwork.none
    )

    package_types: Mapped[list] = mapped_column(JSON, default=list)
    zones_served: Mapped[list] = mapped_column(JSON, default=list)

    base_price: Mapped[float] = mapped_column(Float, nullable=False)
    price_per_km: Mapped[float] = mapped_column(Float, nullable=False)

    rating: Mapped[float] = mapped_column(Float, default=4.5)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    available_days: Mapped[list] = mapped_column(JSON, default=list)
    time_windows: Mapped[list] = mapped_column(JSON, default=list)
    response_time: Mapped[str] = mapped_column(String(50), default="< 2h")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_deliveries: Mapped[int] = mapped_column(Integer, default=0)
    years_active: Mapped[int] = mapped_column(Integer, default=1)
    delivery_estimate: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    bio: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[Optional["User"]] = relationship(back_populates="carrier_profile")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="carrier")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ref: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)

    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    carrier_id: Mapped[str] = mapped_column(String(36), ForeignKey("carrier_profiles.id"), nullable=False)

    pickup_address: Mapped[str] = mapped_column(String(255), nullable=False)
    pickup_city: Mapped[str] = mapped_column(String(120), nullable=False)
    pickup_postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pickup_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pickup_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    dropoff_address: Mapped[str] = mapped_column(String(255), nullable=False)
    dropoff_city: Mapped[str] = mapped_column(String(120), nullable=False)
    dropoff_postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    dropoff_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dropoff_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    package_type: Mapped[str] = mapped_column(String(50), nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    dimensions: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fragile: Mapped[bool] = mapped_column(Boolean, default=False)

    requested_date: Mapped[str] = mapped_column(String(20), nullable=False)
    time_window: Mapped[str] = mapped_column(String(20), nullable=False)

    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    distance_source: Mapped[str] = mapped_column(String(30), default="estimated")  # geocoded_driving / great_circle / fallback
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="EUR")

    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), default=BookingStatus.pending)
    payment_status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.unpaid)
    confirmation_code: Mapped[str] = mapped_column(String(10), nullable=False)

    external_tracking_number: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    client: Mapped["User"] = relationship(back_populates="bookings", foreign_keys=[client_id])
    carrier: Mapped["CarrierProfile"] = relationship(back_populates="bookings")
    tracking_events: Mapped[list["TrackingEvent"]] = relationship(
        back_populates="booking", order_by="TrackingEvent.created_at"
    )
    payment: Mapped[Optional["Payment"]] = relationship(back_populates="booking", uselist=False)
    conversation: Mapped[Optional["Conversation"]] = relationship(back_populates="booking", uselist=False)


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id: Mapped[str] = mapped_column(String(36), ForeignKey("bookings.id"), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="internal")  # internal / chronopost / colissimo / dhl
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    booking: Mapped["Booking"] = relationship(back_populates="tracking_events")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("bookings.id"), nullable=True)
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    carrier_id: Mapped[str] = mapped_column(String(36), ForeignKey("carrier_profiles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    booking: Mapped[Optional["Booking"]] = relationship(back_populates="conversation")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), nullable=False)
    sender_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    sender_role: Mapped[str] = mapped_column(String(20), nullable=False)  # client / carrier
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id: Mapped[str] = mapped_column(String(36), ForeignKey("bookings.id"), unique=True, nullable=False)
    stripe_payment_intent_id: Mapped[str] = mapped_column(String(120), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="eur")
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.unpaid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    booking: Mapped["Booking"] = relationship(back_populates="payment")
