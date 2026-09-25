from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./foh.db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 1800
    db_pool_pre_ping: bool = True

    jwt_secret: str = "dev-secret-change-in-production"
    jwt_expire_hours: int = 8
    cors_origins: str = "http://localhost:5173"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"

    # Groq cloud LLM (free tier — get key from console.groq.com)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"        # text generation
    groq_chat_model: str = "llama-3.3-70b-versatile"    # tool-calling chat
    guest_menu_base_url: str = "http://localhost:8000"
    payment_webhook_secret: str = "dev-webhook-secret"

    # Demo user passwords (read from env — never hardcoded in source)
    owner_password: str = "Owner@1234"
    manager_password: str = "Manager@1234"
    host_password: str = "Host@1234"
    cashier_password: str = "Cashier@1234"
    waiter_password: str = "Waiter@1234"
    chef_password: str = "Chef@1234"
    cook_password: str = "Cook@1234"



    # YOLO / camera pipeline
    camera_enabled: bool = True
    yolo_table_state_model_path: str = "backend/models/table_cleanliness_best.pt"
    
    # YOLO11 & ByteTrack Computer Vision settings
    cv_model_name: str = "yolo11n.pt"  # Can be yolo11n.pt, yolo11m.pt, or models/foh_yolo11.pt
    cv_tracker: str = "bytetrack.yaml"  # bytetrack.yaml or botsort.yaml
    cv_confidence_threshold: float = 0.35
    cv_img_size: int = 640
    cv_process_fps: int = 10
    cv_occupancy_confirm_frames: int = 5
    cv_departure_confirm_seconds: int = 15
    cv_face_blur: bool = False
    cv_mismatch_alert_enabled: bool = True

    camera_scan_interval_seconds: int = 10
    camera_cleaning_grace_seconds: int = 60
    camera_dirty_alert_seconds: int = 600
    camera_dirty_escalation_seconds: int = 1200
    camera_no_camera_cleaning_alert_seconds: int = 900
    table_state_confidence_threshold: float = 0.25
    consecutive_scans_required: int = 3
    camera_clean_scans_required: int = 3
    table_state_sample_frames: int = 5
    table_state_sample_stride: int = 3
    stream_label_history_size: int = 6
    stream_inference_stride: int = 2
    stream_roi_match_min_overlap: float = 0.3
    default_camera_url: str | None = None

    # Kitchen alert thresholds (minutes)
    received_alert_minutes: float = 10.0
    preparation_alert_minutes: float = 20.0
    ready_alert_minutes: float = 5.0

    # Customer self-service booking & OTP settings (Member 4 feature)
    customer_otp_expiry_minutes: int = 10
    customer_otp_resend_seconds: int = 60
    customer_otp_max_attempts: int = 5
    customer_session_expire_hours: int = 24
    customer_hold_minutes: int = 10
    customer_booking_duration_minutes: int = 120
    customer_payment_mode: str = "development"
    customer_deposit_amount: int = 100
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

