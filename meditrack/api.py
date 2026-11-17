"""Device-scoped HTTP API; firmware reports commands, not pill detection."""
import logging
import sqlite3
from flask import Flask, g, jsonify, request
from .config import load
from .database import Store, StoreError

logger = logging.getLogger(__name__)


def create_app(settings=None, store=None, clock=None):
    settings = settings or load()
    store = store or Store(settings.database_path, clock=clock, late_seconds=settings.late_seconds)
    store.initialize()
    if settings.device_secret and settings.owner_telegram_id:
        store.register_device(settings.device_id, settings.owner_telegram_id, settings.device_secret)
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=2048)
    app.extensions["meditrack_store"] = store

    @app.before_request
    def authenticate():
        if not request.path.startswith("/api/"):
            return None
        authorization = request.headers.get("Authorization", "")
        device_id = request.headers.get("X-Device-ID", "")
        if not authorization.startswith("Bearer ") or not store.authenticate(device_id, authorization[7:]):
            return jsonify(error="Потрібна автентифікація пристрою."), 401
        g.device_id = device_id

    @app.after_request
    def prevent_cache(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(StoreError)
    def domain_error(error):
        return jsonify(error=str(error)), error.status

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        logger.error("База даних недоступна: %s", type(error).__name__)
        return jsonify(error="База даних тимчасово недоступна. Рух не дозволено."), 503

    @app.get("/")
    def health():
        return jsonify(service="MediTrack", protocol=1, timezone="Europe/Kyiv")

    @app.get("/api/check")
    def check():
        if request.args:
            raise StoreError("Параметри часу в запиті не підтримуються.", 400)
        return jsonify(store.poll(g.device_id))

    @app.post("/api/confirm")
    def confirm():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) != {"event_id", "outcome"} or not isinstance(data.get("outcome"), str):
            raise StoreError("Потрібен JSON з полями event_id і outcome.", 400)
        return jsonify(store.confirm(g.device_id, data["event_id"], data["outcome"]))

    def device_owner():
        with store.connection() as conn:
            return store._device(conn, g.device_id)["owner"]

    @app.get("/api/status")
    def status():
        return jsonify(store.status(device_owner(), g.device_id))

    @app.get("/api/schedules")
    def schedules():
        return jsonify(schedules=store.schedules(device_owner(), g.device_id))

    @app.get("/api/events")
    def events():
        return jsonify(events=store.events(device_owner(), g.device_id))

    return app
