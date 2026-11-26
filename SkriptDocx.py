# -*- coding: utf-8 -*-
"""
SkriptDocx(TM) - SKRIPT DEVELOPMENT ENVIRONMENT
Publisher: Zenith   |   (c) 2012 by Zenith
Single-file application. Paste parts 1-6 one after another.
Local preferences: QSettings only (no JSON files).
Accounts, profiles, avatars and public scripts: Supabase.
"""

import html
import math
import os
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QObject, QPoint, QRectF, QRunnable, QSettings, QSize, Qt,
    QThreadPool, QTimer, Signal
)
from PySide6.QtGui import (
    QAction, QColor, QFont, QIcon, QKeySequence, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient, QSyntaxHighlighter,
    QTextCharFormat, QTextCursor, QTextDocument
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFontComboBox,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMenuBar, QMessageBox,
    QPlainTextEdit, QPushButton, QSizeGrip, QSpinBox, QSplitter,
    QStackedWidget, QStatusBar, QTabWidget, QTextEdit, QToolBar,
    QToolButton, QVBoxLayout, QWidget
)

APP_NAME = "SkriptDocx"
APP_TITLE = "SkriptDocx\u2122"
APP_VERSION = "v1.4_13.452b1373"
APP_SUBTITLE = "SKRIPT DEVELOPMENT ENVIRONMENT"
APP_COPYRIGHT = "\u00a9 2012 by Zenith"
APP_PUBLISHER = "Zenith"

BASE_DIR = Path(__file__).resolve().parent

SUPABASE_URL = "https://zzuedhphczlbxonysynf.supabase.co"
# Public (publishable) key only. NEVER put a service_role key in a desktop app.
SUPABASE_KEY = "sb_publishable_Qbv61Plp3QmB8nxwPiSRhQ_KQY1yJJ1"

# Database mapping. Kept identical to the previous working version.
# After you verify your real schema, change ONLY these constants.
TABLE_CATEGORIES = "categories"
TABLE_SCRIPTS = "scripts"
TABLE_PROFILES = "profiles"
SCRIPT_AUTHOR_COLUMN = "owner_id"
AVATAR_BUCKET = "avatars"

KEYRING_SERVICE = "SkriptDocx"
KEYRING_ACCOUNT = "supabase-refresh-token"

LANGUAGE_CODES = (
    "en", "pl", "de", "fr", "es", "it", "pt", "ru",
    "uk", "cs", "sk", "nl", "tr", "zh", "ja"
)

LANGUAGE_NAMES = {
    "en": "English", "pl": "Polski", "de": "Deutsch", "fr": "Fran\u00e7ais",
    "es": "Espa\u00f1ol", "it": "Italiano", "pt": "Portugu\u00eas",
    "ru": "\u0420\u0443\u0441\u0441\u043a\u0438\u0439",
    "uk": "\u0423\u043a\u0440\u0430\u0457\u043d\u0441\u044c\u043a\u0430",
    "cs": "\u010ce\u0161tina", "sk": "Sloven\u010dina",
    "nl": "Nederlands", "tr": "T\u00fcrk\u00e7e",
    "zh": "\u7b80\u4f53\u4e2d\u6587", "ja": "\u65e5\u672c\u8a9e"
}

NEW_SCRIPT_TEMPLATE = (
    "# SkriptDocx Workspace\n"
    "# Write your Skript code here.\n\n"
    "on load:\n"
    "    send \"Hello from SkriptDocx!\" to console"
)


# --------------------------------------------------------------------------
# Local preferences (QSettings only)
# --------------------------------------------------------------------------

class AppSettings:
    """Non-sensitive local preferences. Never stores passwords or tokens."""

    def __init__(self):
        self._settings = QSettings(APP_PUBLISHER, APP_NAME)

    def language(self):
        value = self._settings.value("ui/language", "en", type=str)
        return value if value in LANGUAGE_CODES else "en"

    def set_language(self, code):
        if code in LANGUAGE_CODES:
            self._settings.setValue("ui/language", code)

    def theme(self):
        return self._settings.value(
            "ui/theme", "aero-classic-blue", type=str
        )

    def set_theme(self, name):
        self._settings.setValue("ui/theme", name)

    def editor_font_family(self):
        return self._settings.value("editor/font_family", "Consolas", type=str)

    def editor_font_size(self):
        return self._settings.value("editor/font_size", 10, type=int)

    def editor_wrap(self):
        return self._settings.value("editor/wrap", False, type=bool)

    def set_editor_preferences(self, family, size, wrap):
        self._settings.setValue("editor/font_family", family)
        self._settings.setValue("editor/font_size", int(size))
        self._settings.setValue("editor/wrap", bool(wrap))

    def save_window(self, window):
        self._settings.setValue("window/geometry", window.saveGeometry())
        self._settings.setValue("window/maximized", window.isMaximized())

    def restore_window(self, window):
        geometry = self._settings.value("window/geometry")
        restored = bool(geometry) and window.restoreGeometry(geometry)
        if self._settings.value("window/maximized", False, type=bool):
            window.showMaximized()
        return restored

    def sync(self):
        self._settings.sync()


# --------------------------------------------------------------------------
# Translation manager (the table itself is defined in part 6)
# --------------------------------------------------------------------------

TRANSLATIONS = {}
_current_language = "en"


def set_language(code):
    global _current_language
    _current_language = code if code in LANGUAGE_CODES else "en"


def current_language():
    return _current_language


def tr(text):
    """Translate an English UI string. Falls back to English."""
    if _current_language == "en":
        return text
    return TRANSLATIONS.get(_current_language, {}).get(text, text)


def trf(text, *args):
    """Translate and then format a string containing {0}, {1}, ..."""
    return tr(text).format(*args)


class Translatable:
    """Mixin: remembers how to refresh texts so the language can change live."""

    def bind(self, update):
        self.__dict__.setdefault("_bindings", []).append(update)
        update()

    def bt(self, widget, key, prefix="", suffix=""):
        self.bind(
            lambda w=widget, k=key, p=prefix, s=suffix:
            w.setText(p + tr(k) + s)
        )

    def bph(self, widget, key):
        self.bind(
            lambda w=widget, k=key: w.setPlaceholderText(tr(k))
        )

    def btip(self, widget, key):
        self.bind(lambda w=widget, k=key: w.setToolTip(tr(k)))

    def add_tr_child(self, child):
        self.__dict__.setdefault("_tr_children", []).append(child)
        return child

    def retranslate(self):
        for update in list(self.__dict__.get("_bindings", [])):
            update()
        for child in list(self.__dict__.get("_tr_children", [])):
            child.retranslate()


# --------------------------------------------------------------------------
# Development log (shown on the Development Tools page)
# --------------------------------------------------------------------------

APP_LOG = []
LOG_LISTENERS = []


def log_event(message):
    line = f"{datetime.now():%H:%M:%S}  {message}"
    APP_LOG.append(line)
    del APP_LOG[:-500]
    for listener in list(LOG_LISTENERS):
        listener(line)


# --------------------------------------------------------------------------
# Background work: network calls never block the interface
# --------------------------------------------------------------------------

class _MainThreadBridge(QObject):
    deliver = Signal(object)

    def __init__(self):
        super().__init__()
        self.deliver.connect(self._run)

    def _run(self, callback):
        try:
            callback()
        except RuntimeError as error:
            # The target widget was closed before the result arrived.
            print(f"[SkriptDocx] late callback dropped: {error}",
                  file=sys.stderr)


_BRIDGE = None
_ACTIVE_WORKERS = set()


def main_thread_bridge():
    global _BRIDGE
    if _BRIDGE is None:
        _BRIDGE = _MainThreadBridge()
    return _BRIDGE


class _Worker(QRunnable):

    def __init__(self, function, args, on_done, on_error):
        super().__init__()
        self.function = function
        self.args = args
        self.on_done = on_done
        self.on_error = on_error

    def run(self):
        bridge = main_thread_bridge()
        try:
            result = self.function(*self.args)
        except Exception as error:
            if self.on_error:
                bridge.deliver.emit(lambda e=error: self.on_error(e))
            else:
                print(f"[SkriptDocx] background error: {error}",
                      file=sys.stderr)
        else:
            if self.on_done:
                bridge.deliver.emit(lambda r=result: self.on_done(r))
        finally:
            _ACTIVE_WORKERS.discard(self)


def run_async(function, on_done=None, on_error=None, *args):
    """Run function(*args) off the UI thread; callbacks run on the UI thread."""
    main_thread_bridge()
    worker = _Worker(function, args, on_done, on_error)
    _ACTIVE_WORKERS.add(worker)
    QThreadPool.globalInstance().start(worker)


def friendly_error(error):
    """Convert an exception into a short, translated message."""
    text = str(error)
    low = text.lower()
    name = type(error).__name__.lower()

    if "invalid login credentials" in low or "invalid_credentials" in low:
        return tr("Invalid e-mail or password.")
    if "email not confirmed" in low or "email_not_confirmed" in low:
        return tr("Please confirm your e-mail address before signing in.")
    if "already registered" in low or "user_already_exists" in low:
        return tr("This e-mail address is already registered.")
    if (
        any(word in name for word in ("connect", "timeout", "network"))
        or any(word in low for word in (
            "timed out", "getaddrinfo", "network is unreachable",
            "name or service", "connection"
        ))
    ):
        return tr(
            "Cannot reach Supabase. Check your internet connection "
            "and try again."
        )
    return trf("Unexpected error: {0}", text)


def fetch_url_bytes(url):
    if not str(url).startswith("https://"):
        raise ValueError("Only https:// avatar URLs are allowed.")
    request = urllib.request.Request(url, headers={"User-Agent": "SkriptDocx"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read(6 * 1024 * 1024)


def circular_pixmap(pixmap, size):
    scaled = pixmap.scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation
    )
    cropped = scaled.copy(
        (scaled.width() - size) // 2,
        (scaled.height() - size) // 2,
        size, size
    )
    circle = QPixmap(size, size)
    circle.fill(Qt.GlobalColor.transparent)

    painter = QPainter(circle)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return circle


# --------------------------------------------------------------------------
# Supabase service (blocking methods: always call through run_async)
# --------------------------------------------------------------------------

SUPABASE_ENABLED = (
    SUPABASE_URL.startswith("https://")
    and SUPABASE_KEY not in (
        "", "YOUR_SUPABASE_PUBLISHABLE_KEY", "YOUR_EXISTING_PUBLISHABLE_KEY"
    )
)

try:
    from supabase import create_client
    SUPABASE_PACKAGE_AVAILABLE = True
except ImportError:
    create_client = None
    SUPABASE_PACKAGE_AVAILABLE = False

try:
    import keyring
except ImportError:
    keyring = None


class SupabaseService:

    AVATAR_TYPES = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp"
    }

    def __init__(self):
        self.client = None
        self.user = None
        self.session = None
        self.error = None
        self.last_warning = None

        if not SUPABASE_PACKAGE_AVAILABLE:
            self.error = (
                "The Supabase package is not installed "
                "(pip install supabase)."
            )
            return

        if not SUPABASE_ENABLED:
            self.error = "Supabase credentials are not configured."
            return

        try:
            self.client = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as error:
            self.error = str(error)

    @property
    def available(self):
        return self.client is not None

    @property
    def logged_in(self):
        return self.user is not None

    def unavailable_message(self):
        return trf("Supabase is unavailable: {0}", self.error or "?")

    def _require(self):
        if not self.available:
            raise RuntimeError(self.unavailable_message())

    def _require_login(self):
        self._require()
        if not self.logged_in:
            raise RuntimeError(tr("You must sign in first."))

    # -- session handling (only the refresh token is kept, never a password)

    def _remember_session(self, session):
        if keyring is None or session is None:
            return
        try:
            keyring.set_password(
                KEYRING_SERVICE, KEYRING_ACCOUNT, session.refresh_token
            )
        except Exception as error:
            self.last_warning = f"Could not store the session token: {error}"

    def _forget_session(self):
        if keyring is None:
            return
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        except Exception as error:
            self.last_warning = f"Could not remove the session token: {error}"

    def restore_session(self):
        if not self.available or keyring is None:
            return False
        try:
            token = keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        except Exception as error:
            self.last_warning = f"Could not read the session token: {error}"
            return False
        if not token:
            return False
        try:
            result = self.client.auth.refresh_session(token)
        except Exception as error:
            self.last_warning = f"Saved session could not be restored: {error}"
            self._forget_session()
            return False
        self.session = result.session
        self.user = result.user or (
            result.session.user if result.session else None
        )
        self._remember_session(self.session)
        return self.user is not None

    # -- authentication

    def sign_in(self, email, password):
        self._require()
        result = self.client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        self.session = result.session
        self.user = result.user
        self._remember_session(self.session)
        return result

    def sign_up(self, email, password, username):
        self._require()
        result = self.client.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"username": username}}
        })
        user = result.user
        if user is not None and getattr(user, "identities", None) == []:
            raise RuntimeError("user_already_exists")
        if result.session:
            self.session = result.session
            self.user = result.user
            self._remember_session(self.session)
        return result

    def sign_out(self):
        try:
            if self.available and self.logged_in:
                self.client.auth.sign_out()
        finally:
            self.user = None
            self.session = None
            self._forget_session()

    # -- profiles

    def get_profile(self):
        self._require_login()
        rows = (
            self.client.table(TABLE_PROFILES)
            .select("*")
            .eq("id", self.user.id)
            .limit(1)
            .execute()
            .data
        ) or []
        return rows[0] if rows else None

    def ensure_profile(self):
        profile = self.get_profile()
        if profile:
            return profile

        metadata = getattr(self.user, "user_metadata", None) or {}
        username = metadata.get("username") or (
            (self.user.email or "user").split("@")[0]
        )
        fallback = {
            "id": self.user.id,
            "username": username,
            "display_name": username
        }
        try:
            rows = (
                self.client.table(TABLE_PROFILES)
                .insert(fallback)
                .execute()
                .data
            ) or []
            return rows[0] if rows else fallback
        except Exception as error:
            self.last_warning = (
                f"Profile row is missing and could not be created: {error}"
            )
            return fallback

    def update_profile(self, display_name, avatar_url=None):
        self._require_login()
        self.ensure_profile()

        payload = {"display_name": display_name}
        if avatar_url is not None:
            payload["avatar_url"] = avatar_url

        rows = (
            self.client.table(TABLE_PROFILES)
            .update(payload)
            .eq("id", self.user.id)
            .execute()
            .data
        ) or []
        if not rows:
            raise RuntimeError(
                tr("Your profile could not be saved. "
                   "Check the database policies.")
            )
        return rows[0]

    def upload_avatar(self, file_path):
        self._require_login()

        extension = Path(file_path).suffix.lower()
        if extension not in self.AVATAR_TYPES:
            raise ValueError(tr("Use PNG, JPG, JPEG or WEBP."))
        if os.path.getsize(file_path) > 5 * 1024 * 1024:
            raise ValueError(tr("Avatar must be smaller than 5 MB."))

        bucket = self.client.storage.from_(AVATAR_BUCKET)
        storage_path = f"{self.user.id}/avatar{extension}"

        stale = [
            f"{self.user.id}/avatar{other}"
            for other in self.AVATAR_TYPES if other != extension
        ]
        try:
            bucket.remove(stale)
        except Exception as error:
            self.last_warning = f"Old avatar cleanup failed: {error}"

        with open(file_path, "rb") as image_file:
            bucket.upload(
                storage_path,
                image_file.read(),
                {
                    "content-type": self.AVATAR_TYPES[extension],
                    "upsert": "true"
                }
            )

        url = str(bucket.get_public_url(storage_path)).rstrip("?")
        return f"{url}?v={int(time.time())}"

    # -- global library

    def get_categories(self):
        self._require()
        return (
            self.client.table(TABLE_CATEGORIES)
            .select("*")
            .order("name")
            .execute()
            .data
        ) or []

    def get_scripts(self, search_text="", category_id=None):
        self._require()
        text = re.sub(r"[,()%*\\]", " ", search_text or "").strip()

        def build(ordered):
            query = self.client.table(TABLE_SCRIPTS).select("*").limit(100)
            if text:
                query = query.or_(
                    f"title.ilike.*{text}*,description.ilike.*{text}*"
                )
            if category_id:
                query = query.eq("category_id", category_id)
            if ordered:
                query = query.order("created_at", desc=True)
            return query.execute().data or []

        try:
            return build(True)
        except Exception:
            # The table may have no created_at column: retry unordered.
            return build(False)

    def publish_script(self, title, description, content, category_id):
        self._require_login()
        payload = {
            "title": title,
            "description": description,
            "content": content,
            "category_id": category_id,
            SCRIPT_AUTHOR_COLUMN: self.user.id
        }
        return (
            self.client.table(TABLE_SCRIPTS).insert(payload).execute().data
        )

    def delete_script(self, script_id):
        self._require_login()
        result = (
            self.client.table(TABLE_SCRIPTS)
            .delete()
            .eq("id", script_id)
            .execute()
        )
        if not result.data:
            raise RuntimeError(
                "The script was not deleted. It may no longer exist, "
                "or you may not have permission to delete it."
            )
        return result.data


# --------------------------------------------------------------------------
# Windows 7 Aero style sheet
# --------------------------------------------------------------------------

STYLE = """
QWidget {
    font-family: "Segoe UI";
    font-size: 9pt;
    color: #29445c;
}
QMainWindow { background: #eaf1f7; }
QFrame#MainFrame { background: #eaf1f7; border: 1px solid #7795af; }
QFrame#AeroTitleBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:0.10 #f5faff, stop:0.43 #d9eafa,
        stop:0.52 #c6dff3, stop:1 #eaf3fb);
    border: none;
}
QFrame#MenuArea {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f8fbfe, stop:1 #e4edf5);
    border-bottom: 1px solid #bdcddd;
}
QMenuBar { background: transparent; }
QMenuBar::item { padding: 4px 10px; background: transparent; border-radius: 3px; }
QMenuBar::item:selected { background: #dceafa; border: 1px solid #b3cde4; }
QToolBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f4f9fd, stop:1 #e1ebf4);
    border: none;
    border-bottom: 1px solid #bdcddd;
    spacing: 3px;
    padding: 2px 6px;
}
QToolBar QToolButton {
    padding: 4px 9px;
    border: 1px solid transparent;
    border-radius: 3px;
    background: transparent;
}
QToolBar QToolButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:1 #d8eafa);
    border: 1px solid #a8c5df;
}
QFrame#Navigation {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #e6eef6, stop:1 #d6e3ef);
    border-right: 1px solid #b3c6d8;
}
QFrame#ContentPanel { background: #f8fbfe; border: 1px solid #c0cfdd; }
QFrame#Card {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:1 #f0f5fa);
    border: 1px solid #c1d0dd;
    border-radius: 5px;
}
QFrame#HeaderCard {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:1 #e4eff9);
    border: 1px solid #b6cadc;
    border-radius: 5px;
}
QFrame#QuickCard {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:1 #f0f5fa);
    border: 1px solid #c1d0dd;
    border-radius: 5px;
}
QFrame#QuickCard:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:1 #d8eafa);
    border: 1px solid #8eb6d8;
}
QFrame#QuickCard QLabel { background: transparent; border: none; }
QFrame#FindBar {
    background: #eef4fa;
    border-top: 1px solid #b5c7d7;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:0.48 #edf4fa, stop:0.5 #dce9f5, stop:1 #eaf2f9);
    border: 1px solid #9db4c9;
    border-radius: 3px;
    padding: 5px 12px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #fffdf6, stop:0.5 #ffedc9, stop:1 #f7d99b);
    border: 1px solid #d3a34e;
}
QPushButton:pressed { background: #d1e2f0; border: 1px solid #7e9eb9; }
QPushButton:disabled { color: #98a9b9; background: #eef2f6; border: 1px solid #c6d2dd; }
QPushButton#PrimaryButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #fefefe, stop:0.45 #e6f4ff, stop:0.5 #c4e1f7, stop:1 #e2f1fc);
    border: 1px solid #7fa9ca;
    font-weight: bold;
    padding: 7px 16px;
}
QPushButton#NavigationButton {
    text-align: left;
    padding: 9px 11px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
}
QPushButton#NavigationButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:1 #d8eafa);
    border: 1px solid #a8c5df;
}
QPushButton#NavigationButton[active="true"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e5f2fc, stop:1 #c8e0f4);
    border: 1px solid #8eb6d8;
    font-weight: bold;
}
QLineEdit, QTextEdit, QPlainTextEdit, QListWidget, QComboBox, QSpinBox {
    background: #ffffff;
    border: 1px solid #aebfce;
    border-radius: 2px;
    selection-background-color: #b9d8f2;
    selection-color: #173b5b;
    padding: 5px;
}
QListWidget::item:selected { background: #d4e8f8; color: #173b5b; }
QTabWidget::pane { border: 1px solid #b5c7d7; background: #ffffff; }
QTabBar::tab {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f8fbfe, stop:1 #dce8f2);
    border: 1px solid #b5c7d7;
    padding: 6px 14px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #ffffff;
    border-bottom: 1px solid #ffffff;
    font-weight: bold;
}
QStatusBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f1f6fb, stop:1 #dce7f1);
    border-top: 1px solid #b7c8d8;
    color: #587086;
}
QMenu { background: #f8fbfe; border: 1px solid #9eb4c9; padding: 4px; }
QMenu::item { padding: 6px 28px 6px 22px; }
QMenu::item:selected { background: #dceafa; border: 1px solid #b3cde4; }
QProgressBar {
    border: 1px solid #a7bacb;
    border-radius: 3px;
    background: #edf3f8;
    text-align: center;
    height: 12px;
}
QProgressBar::chunk { border-radius: 2px; background: #77c34f; }
"""
# --------------------------------------------------------------------------
# Skript syntax highlighting and static analysis
# --------------------------------------------------------------------------

def find_comment_start(text):
    """Index of a '#' that starts a comment (outside of a string), or -1."""
    in_string = False
    for index, char in enumerate(text):
        if char == '"':
            in_string = not in_string
        elif char == "#" and not in_string:
            return index
    return -1


class SkriptHighlighter(QSyntaxHighlighter):

    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        def make_format(color, bold=False, italic=False):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(QFont.Weight.Bold)
            if italic:
                fmt.setFontItalic(True)
            return fmt

        self.comment_format = make_format("#7d8b98", italic=True)
        self.string_format = make_format("#a45d25")
        self.variable_format = make_format("#d07820", bold=True)
        self.number_format = make_format("#8a55ad")
        self.keyword_format = make_format("#8154b8", bold=True)
        self.effect_format = make_format("#236ca5")
        self.event_format = make_format("#168477", bold=True)
        self.operator_format = make_format("#bd6540")

        keywords = [
            "if", "else", "else if", "and", "or", "not",
            "is", "is not", "contains", "does not contain",
            "starts with", "ends with", "matches", "in",
            "loop", "while", "for", "each", "every",
            "function", "return", "stop", "cancel",
            "continue", "wait", "run", "trigger",
            "on", "command", "permission", "permission message",
            "aliases", "usage", "description", "executable by",
            "cooldown", "cooldown bypass", "world",
            "skript", "options", "local", "true", "false"
        ]
        effects = [
            "set", "add", "remove", "delete", "clear",
            "send", "broadcast", "message", "give", "take",
            "teleport", "heal", "damage", "kill", "ban",
            "unban", "kick", "play", "stop sound",
            "spawn", "drop", "strike lightning",
            "open", "close", "wait", "increase",
            "decrease", "reset", "execute", "make",
            "apply", "push", "pull", "equip"
        ]
        events = [
            "on load", "on unload", "on join", "on quit",
            "on death", "on respawn", "on damage",
            "on click", "on right click", "on left click",
            "on inventory click", "on inventory close",
            "on chat", "on command", "on break",
            "on place", "on drop", "on pickup",
            "on move", "on sneak toggle",
            "on world change", "on teleport"
        ]

        for word in sorted(keywords, key=len, reverse=True):
            self.rules.append((
                re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE),
                self.keyword_format
            ))
        for word in sorted(effects, key=len, reverse=True):
            self.rules.append((
                re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE),
                self.effect_format
            ))
        for word in sorted(events, key=len, reverse=True):
            self.rules.append((
                re.compile(re.escape(word), re.IGNORECASE),
                self.event_format
            ))

        self.rules.extend([
            (re.compile(r'"(?:[^"]|"")*"'), self.string_format),
            (re.compile(r"\{[^{}\n]+\}"), self.variable_format),
            (re.compile(r"\b\d+(?:\.\d+)?\b"), self.number_format),
            (re.compile(r"(?<!\S)(?:==|!=|>=|<=|>|<|=)(?!\S)"),
             self.operator_format)
        ])

    def highlightBlock(self, text):
        comment_start = find_comment_start(text)
        code_part = text

        if comment_start >= 0:
            code_part = text[:comment_start]
            self.setFormat(
                comment_start, len(text) - comment_start, self.comment_format
            )

        for pattern, fmt in self.rules:
            for match in pattern.finditer(code_part):
                self.setFormat(
                    match.start(), match.end() - match.start(), fmt
                )


class SkriptAnalyzer:
    """Static analysis only. It never executes a script."""

    @staticmethod
    def analyze(source):
        problems = []
        lines = source.splitlines()
        clean = []

        for raw in lines:
            at = find_comment_start(raw)
            clean.append((raw if at < 0 else raw[:at]).rstrip())

        def add(line, severity, message):
            problems.append({
                "line": line, "severity": severity, "message": message
            })

        first_indent_kind = None
        mixed_reported = False

        for index, code in enumerate(clean, start=1):
            if not code.strip():
                continue

            stripped = code.lstrip()
            indent_text = code[:len(code) - len(stripped)]

            has_tab = "\t" in indent_text
            has_space = " " in indent_text
            if has_tab and has_space and not mixed_reported:
                add(index, "Warning", "Mixed tab and space indentation.")
                mixed_reported = True
            if indent_text:
                kind = "tab" if has_tab else "space"
                if first_indent_kind is None:
                    first_indent_kind = kind
                elif kind != first_indent_kind and not mixed_reported:
                    add(index, "Warning", "Mixed tab and space indentation.")
                    mixed_reported = True

            if code.count('"') % 2 != 0:
                add(index, "Error", "Possible unclosed string.")

            lowered = stripped.lower()

            if lowered.startswith("command ") and not lowered.endswith(":"):
                add(index, "Warning",
                    "Command declaration usually ends with ':'.")

            if lowered.startswith("on ") and not lowered.endswith(":"):
                add(index, "Warning",
                    "Event declaration usually ends with ':'.")

            if lowered.startswith("if ") and not lowered.endswith(":"):
                add(index, "Warning", "An if block usually ends with ':'.")

            if lowered.startswith("else if ") and not lowered.endswith(":"):
                add(index, "Warning",
                    "An else if block usually ends with ':'.")

            if lowered in ("else", "else :"):
                add(index, "Warning", "Use 'else:' for an else block.")

            if (
                lowered.startswith("command ")
                and "<" in stripped and ">" not in stripped
            ):
                add(index, "Error", "Possible incomplete command argument.")

        for index, code in enumerate(clean, start=1):
            if not code.strip() or not code.endswith(":"):
                continue

            following = None
            for next_line in clean[index:]:
                if next_line.strip():
                    following = next_line
                    break

            if following is None:
                add(index, "Warning", "Block has no following body.")
                continue

            current_indent = len(code) - len(code.lstrip())
            next_indent = len(following) - len(following.lstrip())
            if next_indent <= current_indent:
                add(index, "Warning", "Expected an indented block after ':'.")

        problems.sort(key=lambda item: item["line"])
        return problems


# --------------------------------------------------------------------------
# The "sk." logo: one implementation used everywhere
# --------------------------------------------------------------------------

LOGO_TEXT_COLOR = QColor("#244d72")
LOGO_DOT_COLOR = QColor("#f29a32")
LOGO_PADDING = 2


def _logo_font(pixel_size):
    font = QFont("Segoe UI")
    font.setPixelSize(int(pixel_size))
    font.setWeight(QFont.Weight.Bold)
    return font


def logo_metrics(pixel_size):
    """Glyph path and measured ink geometry of the 'sk.' logo."""
    path = QPainterPath()
    path.addText(0, 0, _logo_font(pixel_size), "sk")
    ink = path.boundingRect()
    dot = max(3.0, pixel_size * 0.17)
    gap = pixel_size * 0.05
    width = ink.width() + gap + dot
    ascent = -ink.top()
    descent = max(ink.bottom(), 0.0)
    return path, ink, dot, gap, width, ascent, descent


def draw_logo(painter, center_x, baseline_y, pixel_size):
    """Draw 'sk.' centered on center_x. The dot rests on the text baseline."""
    path, ink, dot, gap, width, _ascent, _descent = logo_metrics(pixel_size)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.translate(center_x - width / 2 - ink.left(), baseline_y)
    painter.fillPath(path, LOGO_TEXT_COLOR)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(LOGO_DOT_COLOR)
    painter.drawEllipse(QRectF(ink.right() + gap, -dot, dot, dot))
    painter.restore()


class LogoWidget(QWidget):
    """Fixed-size widget whose size equals the real bounds of the logo."""

    def __init__(self, pixel_size=28, parent=None):
        super().__init__(parent)
        self.pixel_size = pixel_size
        _p, _i, _d, _g, width, ascent, descent = logo_metrics(pixel_size)
        self._ascent = ascent
        self.setFixedSize(
            math.ceil(width) + 2 * LOGO_PADDING,
            math.ceil(ascent + descent) + 2 * LOGO_PADDING
        )

    def sizeHint(self):
        return QSize(self.width(), self.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        draw_logo(
            painter, self.width() / 2,
            LOGO_PADDING + self._ascent, self.pixel_size
        )
        painter.end()


def fallback_avatar_pixmap(size):
    """Round placeholder avatar that shows the same 'sk.' logo."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#a8bfd2"), 1))
    painter.setBrush(QColor("#dceaf6"))
    painter.drawEllipse(QRectF(0.5, 0.5, size - 1, size - 1))

    pixel_size = max(8, int(size * 0.38))
    _p, _i, _d, _g, _w, ascent, descent = logo_metrics(pixel_size)
    baseline = size / 2 + (ascent - descent) / 2
    draw_logo(painter, size / 2, baseline, pixel_size)
    painter.end()
    return pixmap


# --------------------------------------------------------------------------
# Window chrome (Windows 7 Aero style)
# --------------------------------------------------------------------------

class AeroCaptionButton(QToolButton):

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.is_hovered = False
        self.is_pressed = False

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(44 if kind == "close" else 28, 19)
        self.setStyleSheet("background: transparent; border: none;")

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.is_pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.is_pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def set_maximized_icon(self, maximized):
        self.kind = "restore" if maximized else "maximize"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        close = self.kind == "close"

        if close:
            if self.is_pressed:
                colors = ("#a91e15", "#c82c20", "#e34b3e")
            elif self.is_hovered:
                colors = ("#ffb9a9", "#f34c3d", "#c51e13")
            else:
                colors = ("#f3dcd8", "#e2b0aa", "#cf968f")
            border = "#9d241b" if self.is_hovered else "#a98c88"
        else:
            if self.is_pressed:
                colors = ("#a9cce8", "#c6e0f4", "#e5f2fb")
            elif self.is_hovered:
                colors = ("#ffffff", "#e4f4ff", "#acd8f6")
            else:
                colors = ("#f9fcff", "#e3eff8", "#c0d6e8")
            border = "#78a6cb" if self.is_hovered else "#91acc4"

        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(colors[0]))
        gradient.setColorAt(0.48, QColor(colors[1]))
        gradient.setColorAt(1, QColor(colors[2]))

        painter.setPen(QPen(QColor(border), 0.8))
        painter.setBrush(gradient)
        painter.drawRoundedRect(
            QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 2.5, 2.5
        )

        reflection = QLinearGradient(0, 1, 0, 8)
        reflection.setColorAt(0, QColor(255, 255, 255, 170))
        reflection.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(reflection)
        painter.drawRoundedRect(
            QRectF(1.5, 1, self.width() - 3, 7), 2, 2
        )

        cx = self.width() / 2
        cy = self.height() / 2

        if close:
            pen_color = "#ffffff" if (self.is_hovered or self.is_pressed) \
                else "#5a2d28"
            painter.setPen(QPen(QColor(pen_color), 1.6))
            painter.drawLine(QPoint(int(cx - 4), int(cy - 3)),
                             QPoint(int(cx + 4), int(cy + 3)))
            painter.drawLine(QPoint(int(cx + 4), int(cy - 3)),
                             QPoint(int(cx - 4), int(cy + 3)))
        elif self.kind == "minimize":
            painter.setPen(QPen(QColor("#294b67"), 1.4))
            painter.drawLine(QPoint(int(cx - 4), int(cy + 3)),
                             QPoint(int(cx + 4), int(cy + 3)))
        elif self.kind == "maximize":
            painter.setPen(QPen(QColor("#294b67"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(cx - 4.5, cy - 3.5, 9, 7))
        elif self.kind == "restore":
            painter.setPen(QPen(QColor("#294b67"), 1))
            painter.setBrush(QColor("#edf6fc"))
            painter.drawRect(QRectF(cx - 2, cy - 4.5, 6, 5))
            painter.setBrush(QColor("#ffffff"))
            painter.drawRect(QRectF(cx - 4.5, cy - 1.5, 6, 5))

        painter.end()


class AeroTitleBar(QFrame, Translatable):

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.setObjectName("AeroTitleBar")
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 1, 6, 0)
        layout.setSpacing(6)

        self.logo = LogoWidget(18)
        layout.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignVCenter)

        self.title = QLabel(APP_TITLE)
        self.title.setStyleSheet(
            "font-size: 10pt; font-weight: 600; color: #294d70;"
        )
        layout.addWidget(self.title, 0, Qt.AlignmentFlag.AlignVCenter)

        self.subtitle = QLabel("")
        self.subtitle.setStyleSheet("font-size: 8pt; color: #72889c;")
        layout.addWidget(self.subtitle, 0, Qt.AlignmentFlag.AlignVCenter)
        self.bt(self.subtitle, "Development Environment")

        layout.addStretch()

        self.minimize_button = AeroCaptionButton("minimize")
        self.maximize_button = AeroCaptionButton("maximize")
        self.close_button = AeroCaptionButton("close")

        self.minimize_button.clicked.connect(
            lambda *_: main_window.showMinimized()
        )
        self.maximize_button.clicked.connect(lambda *_: self.toggle_maximize())
        self.close_button.clicked.connect(lambda *_: main_window.close())

        layout.addWidget(self.minimize_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.maximize_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)

        self.bind(self._update_tooltips)

    def _update_tooltips(self):
        self.minimize_button.setToolTip(tr("Minimize"))
        self.maximize_button.setToolTip(
            tr("Restore") if self.main_window.isMaximized() else tr("Maximize")
        )
        self.close_button.setToolTip(tr("Close"))

    def toggle_maximize(self):
        if self.main_window.isMaximized():
            self.main_window.showNormal()
        else:
            self.main_window.showMaximized()
        self.update_maximize_button()

    def update_maximize_button(self):
        self.maximize_button.set_maximized_icon(self.main_window.isMaximized())
        self._update_tooltips()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.main_window.windowHandle()
            if handle is not None and not self.main_window.isMaximized():
                handle.startSystemMove()
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximize()


class AeroMainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        )

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            if hasattr(self, "title_bar"):
                self.title_bar.update_maximize_button()


# --------------------------------------------------------------------------
# Shared page widgets
# --------------------------------------------------------------------------

class PageHeader(QFrame, Translatable):

    def __init__(self, title_key, description_key):
        super().__init__()
        self.setObjectName("HeaderCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(17, 12, 17, 12)
        layout.setSpacing(4)

        heading = QLabel()
        heading.setStyleSheet(
            "font-size: 16pt; font-weight: 600; color: #294f72;"
        )
        subtitle = QLabel()
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #74899c;")

        self.bt(heading, title_key)
        self.bt(subtitle, description_key)

        layout.addWidget(heading)
        layout.addWidget(subtitle)


class QuickCard(QFrame, Translatable):
    """Clickable Quick Access tile. Every tile triggers a real action."""

    clicked = Signal()

    def __init__(self, symbol, title_key):
        super().__init__()
        self.setObjectName("QuickCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(58)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(12)

        icon = QLabel(symbol)
        icon.setStyleSheet("font-size: 18pt; color: #e89a3b;")
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        title = QLabel()
        title.setWordWrap(True)
        title.setStyleSheet(
            "font-size: 10pt; font-weight: bold; color: #365b7e;"
        )
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.bt(title, title_key)

        layout.addWidget(icon)
        layout.addWidget(title, 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter,
                           Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)


QUICK_ACCESS_ITEMS = [
    ("\uff0b", "New Script", "new"),
    ("\u25a4", "Open Script", "open"),
    ("\u25a3", "Save Script", "save"),
    ("\u25a5", "Save As", "save_as"),
    ("\u2715", "Close Tab", "close_tab"),
    ("\u25b6", "Analyze Script", "analyze"),
    ("\u25c8", "Global Library", "library"),
    ("\u27f3", "Refresh Library", "refresh_library"),
    ("\u21e7", "Publish Script", "publish"),
    ("\u263a", "Account", "account"),
    ("\u2699", "Settings", "settings"),
    ("\u24d8", "About", "about"),
]


class DashboardPage(QWidget, Translatable):
    quick_action = Signal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(17, 15, 17, 15)
        layout.setSpacing(14)

        layout.addWidget(self.add_tr_child(PageHeader(
            "Welcome to SkriptDocx",
            "Your development environment for creating Skript projects."
        )))

        welcome = QFrame()
        welcome.setObjectName("HeaderCard")
        welcome_layout = QVBoxLayout(welcome)
        welcome_layout.setContentsMargins(24, 20, 24, 20)
        welcome_layout.setSpacing(10)

        logo = LogoWidget(40)
        welcome_layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignLeft)

        heading = QLabel()
        heading.setStyleSheet(
            "font-size: 21pt; font-weight: 600; color: #2d5275;"
        )
        self.bt(heading, "Build something remarkable.")

        description = QLabel()
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 10pt; color: #657d93;")
        self.bt(
            description,
            "Create, edit and organize your Skript projects in one "
            "dedicated development environment."
        )

        button = QPushButton()
        button.setObjectName("PrimaryButton")
        button.setMinimumWidth(205)
        self.bt(button, "Open Workspace", prefix="\uff0b   ")
        button.clicked.connect(lambda *_: self.quick_action.emit("workspace"))

        library_button = QPushButton()
        library_button.setMinimumWidth(205)
        self.bt(library_button, "Browse Global Library", prefix="\u25a4   ")
        library_button.clicked.connect(
            lambda *_: self.quick_action.emit("library")
        )

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addWidget(button)
        buttons.addWidget(library_button)
        buttons.addStretch()

        welcome_layout.addWidget(heading)
        welcome_layout.addWidget(description)
        welcome_layout.addSpacing(6)
        welcome_layout.addLayout(buttons)
        layout.addWidget(welcome)

        label = QLabel()
        label.setStyleSheet("font-weight: bold; color: #71879b; padding: 3px;")
        self.bt(label, "QUICK ACCESS")
        layout.addWidget(label)

        grid = QGridLayout()
        grid.setSpacing(10)

        for index, (symbol, key, action_id) in enumerate(QUICK_ACCESS_ITEMS):
            card = QuickCard(symbol, key)
            self.add_tr_child(card)
            card.clicked.connect(
                lambda a=action_id: self.quick_action.emit(a)
            )
            grid.addWidget(card, index // 4, index % 4)

        for column in range(4):
            grid.setColumnStretch(column, 1)

        layout.addLayout(grid)
        layout.addStretch()

        footer = QLabel()
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(
            "color: #94a4b3; font-size: 8pt; letter-spacing: 1px;"
        )
        self.bt(footer, "SKRIPT DEVELOPMENT  \u2022  GLOBAL KNOWLEDGE  "
                        "\u2022  COMMUNITY")
        layout.addWidget(footer)
        # --------------------------------------------------------------------------
# Editor documents and the Workspace page
# --------------------------------------------------------------------------

def sanitize_filename(name, default="script"):
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", name or "").strip(" .")
    return cleaned[:80] or default


def read_text_file(path):
    """Read a text file. Returns (text, encoding). Never raises on encoding."""
    with open(path, "rb") as source:
        raw = source.read()
    for encoding in ("utf-8-sig", "cp1250", "cp1252"):
        try:
            if encoding == "utf-8-sig":
                return raw.decode("utf-8-sig"), "utf-8"
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1"), "latin-1"


class EditorDocument(QWidget, Translatable):
    modified_changed = Signal()

    def __init__(self, content="", file_path=None, untitled_number=0,
                 display_name=None):
        super().__init__()
        self.file_path = file_path
        self.untitled_number = untitled_number
        self.display_name = display_name
        self.last_problems = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.editor = QPlainTextEdit()
        self.editor.setTabStopDistance(32)
        self.editor.setPlainText(content)
        self.editor.document().setModified(False)
        self.highlighter = SkriptHighlighter(self.editor.document())
        self.editor.document().modificationChanged.connect(
            lambda *_: self.modified_changed.emit()
        )

        lower = QWidget()
        lower_layout = QVBoxLayout(lower)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.setSpacing(4)

        self.problem_title = QLabel()
        self.problem_title.setStyleSheet(
            "font-weight: bold; color: #71879b; padding: 5px;"
        )
        self.bt(self.problem_title, "Problems")

        self.problems = QListWidget()
        self.problems.setMaximumHeight(130)
        self.problems.itemClicked.connect(self.jump_to_problem)

        lower_layout.addWidget(self.problem_title)
        lower_layout.addWidget(self.problems)

        splitter.addWidget(self.editor)
        splitter.addWidget(lower)
        splitter.setSizes([500, 130])
        layout.addWidget(splitter)

        self.analysis_timer = QTimer(self)
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.setInterval(350)
        self.analysis_timer.timeout.connect(self.run_analysis)
        self.editor.textChanged.connect(self.analysis_timer.start)

        self.bind(self.render_problems)
        self.run_analysis()

    def apply_preferences(self, family, size, wrap):
        self.editor.setFont(QFont(family, size))
        self.editor.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth if wrap
            else QPlainTextEdit.LineWrapMode.NoWrap
        )

    def run_analysis(self):
        self.last_problems = SkriptAnalyzer.analyze(
            self.editor.toPlainText()
        )
        self.render_problems()
        return self.last_problems

    def render_problems(self):
        self.problems.clear()

        if not self.last_problems:
            item = QListWidgetItem(tr("No problems detected."))
            item.setForeground(QColor("#43854b"))
            self.problems.addItem(item)
            return

        for problem in self.last_problems:
            severity = problem["severity"]
            line = problem["line"]
            item = QListWidgetItem(
                f"{tr(severity)}  |  {tr('Line')} {line}: "
                f"{tr(problem['message'])}"
            )
            item.setData(Qt.ItemDataRole.UserRole, line)
            item.setForeground(
                QColor("#bd3e36") if severity == "Error" else QColor("#a87927")
            )
            self.problems.addItem(item)

    def jump_to_problem(self, item):
        line = item.data(Qt.ItemDataRole.UserRole)
        if not line:
            return

        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(
            QTextCursor.MoveOperation.Down,
            QTextCursor.MoveMode.MoveAnchor,
            int(line) - 1
        )
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def is_modified(self):
        return self.editor.document().isModified()

    def mark_saved(self):
        self.editor.document().setModified(False)

    def base_name(self):
        if self.file_path:
            return os.path.basename(self.file_path)
        return self.display_name or f"{tr('Untitled')} {self.untitled_number}"

    def tab_label(self):
        return self.base_name() + (" *" if self.is_modified() else "")

    def suggested_file_name(self):
        if self.file_path:
            return self.file_path
        if self.display_name:
            return sanitize_filename(self.display_name.removesuffix(".sk")) \
                + ".sk"
        return f"untitled-{self.untitled_number}.sk"


class FindReplaceBar(QFrame, Translatable):

    def __init__(self, get_editor, notify):
        super().__init__()
        self.setObjectName("FindBar")
        self.get_editor = get_editor
        self.notify = notify

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)

        row = QHBoxLayout()
        self.find_input = QLineEdit()
        self.bph(self.find_input, "Find what")
        self.find_input.returnPressed.connect(lambda: self.find_next(False))

        previous_button = QPushButton()
        next_button = QPushButton()
        self.case_check = QCheckBox()
        close_button = QPushButton("\u2715")
        close_button.setFixedWidth(30)
        self.bt(previous_button, "Previous")
        self.bt(next_button, "Next")
        self.bt(self.case_check, "Match case")
        self.btip(close_button, "Close")

        previous_button.clicked.connect(lambda *_: self.find_next(True))
        next_button.clicked.connect(lambda *_: self.find_next(False))
        close_button.clicked.connect(lambda *_: self.hide())

        row.addWidget(self.find_input, 1)
        row.addWidget(previous_button)
        row.addWidget(next_button)
        row.addWidget(self.case_check)
        row.addWidget(close_button)
        layout.addLayout(row)

        self.replace_row = QWidget()
        replace_layout = QHBoxLayout(self.replace_row)
        replace_layout.setContentsMargins(0, 0, 0, 0)
        self.replace_input = QLineEdit()
        self.bph(self.replace_input, "Replace with")
        replace_button = QPushButton()
        replace_all_button = QPushButton()
        self.bt(replace_button, "Replace")
        self.bt(replace_all_button, "Replace All")
        replace_button.clicked.connect(lambda *_: self.replace_one())
        replace_all_button.clicked.connect(lambda *_: self.replace_all())
        replace_layout.addWidget(self.replace_input, 1)
        replace_layout.addWidget(replace_button)
        replace_layout.addWidget(replace_all_button)
        layout.addWidget(self.replace_row)

        self.hide()

    def show_find(self, with_replace=False):
        self.show()
        self.replace_row.setVisible(with_replace)
        editor = self.get_editor()
        if editor is not None:
            selected = editor.textCursor().selectedText()
            if selected and "\u2029" not in selected:
                self.find_input.setText(selected)
        self.find_input.setFocus()
        self.find_input.selectAll()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)

    def _flags(self, backward=False):
        flags = QTextDocument.FindFlag(0)
        if self.case_check.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        return flags

    def find_next(self, backward=False):
        editor = self.get_editor()
        text = self.find_input.text()
        if editor is None or not text:
            return False

        flags = self._flags(backward)
        if editor.find(text, flags):
            return True

        cursor = editor.textCursor()
        cursor.movePosition(
            QTextCursor.MoveOperation.End if backward
            else QTextCursor.MoveOperation.Start
        )
        editor.setTextCursor(cursor)
        if editor.find(text, flags):
            return True

        self.notify(tr("Not found."))
        return False

    def replace_one(self):
        editor = self.get_editor()
        text = self.find_input.text()
        if editor is None or not text:
            return

        cursor = editor.textCursor()
        selected = cursor.selectedText()
        same = (
            selected == text if self.case_check.isChecked()
            else selected.lower() == text.lower()
        )
        if cursor.hasSelection() and same:
            cursor.insertText(self.replace_input.text())
        self.find_next(False)

    def replace_all(self):
        editor = self.get_editor()
        text = self.find_input.text()
        if editor is None or not text:
            return

        document = editor.document()
        flags = self._flags(False)
        replacement = self.replace_input.text()
        count = 0

        cursor = QTextCursor(document)
        cursor.beginEditBlock()
        while True:
            found = document.find(text, cursor, flags)
            if found.isNull():
                break
            found.insertText(replacement)
            count += 1
            cursor = found
        cursor.endEditBlock()

        self.notify(trf("{0} replacement(s) made.", count))


class WorkspacePage(QWidget, Translatable):
    status_message = Signal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.untitled_counter = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(17, 15, 17, 15)
        layout.setSpacing(10)

        layout.addWidget(self.add_tr_child(PageHeader(
            "Workspace", "Create and edit your Skript source files."
        )))

        toolbar = QHBoxLayout()
        buttons = [
            ("New Script", self.new_script),
            ("Open Script", self.open_files),
            ("Save Script", self.save_current),
            ("Save As", self.save_current_as),
            ("Close Tab", self.close_tab),
            ("Analyze Script", self.analyze_current),
            ("Find", lambda: self.show_find(False)),
            ("Replace", lambda: self.show_find(True)),
        ]
        for key, slot in buttons:
            button = QPushButton()
            self.bt(button, key)
            button.clicked.connect(lambda *_, s=slot: s())
            toolbar.addWidget(button)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.remove_tab)
        layout.addWidget(self.tabs, 1)

        self.find_bar = FindReplaceBar(
            self.current_editor, self.status_message.emit
        )
        self.add_tr_child(self.find_bar)
        layout.addWidget(self.find_bar)

        self.add_tab()

    # -- helpers

    def documents(self):
        return [self.tabs.widget(i) for i in range(self.tabs.count())]

    def current_document(self):
        return self.tabs.currentWidget()

    def current_editor(self):
        document = self.current_document()
        return document.editor if document else None

    def current_content(self):
        editor = self.current_editor()
        return editor.toPlainText() if editor else ""

    def current_title(self):
        document = self.current_document()
        return document.base_name().removesuffix(".sk") if document else ""

    def file_filter(self):
        return (
            f"{tr('Skript files')} (*.sk);;"
            f"{tr('Text files')} (*.txt);;"
            f"{tr('All files')} (*.*)"
        )

    def apply_preferences(self):
        family = self.settings.editor_font_family()
        size = self.settings.editor_font_size()
        wrap = self.settings.editor_wrap()
        for document in self.documents():
            document.apply_preferences(family, size, wrap)

    def retranslate(self):
        Translatable.retranslate(self)
        for document in self.documents():
            document.retranslate()
            self.update_document_title(document)

    # -- documents

    def new_script(self):
        self.add_tab()

    def add_tab(self, content=None, file_path=None, display_name=None):
        if not isinstance(content, str):
            content = NEW_SCRIPT_TEMPLATE

        number = 0
        if file_path is None and display_name is None:
            self.untitled_counter += 1
            number = self.untitled_counter

        document = EditorDocument(content, file_path, number, display_name)
        document.apply_preferences(
            self.settings.editor_font_family(),
            self.settings.editor_font_size(),
            self.settings.editor_wrap()
        )
        document.modified_changed.connect(
            lambda d=document: self.update_document_title(d)
        )

        index = self.tabs.addTab(document, document.tab_label())
        self.tabs.setCurrentIndex(index)
        document.editor.setFocus()
        return document

    def update_document_title(self, document):
        index = self.tabs.indexOf(document)
        if index >= 0:
            self.tabs.setTabText(index, document.tab_label())

    def save_document(self, document, save_as=False):
        if document is None:
            return False

        path = document.file_path
        if save_as or not path:
            path, _ = QFileDialog.getSaveFileName(
                self, tr("Save Skript file"),
                document.suggested_file_name(), self.file_filter()
            )
            if not path:
                return False
            if not os.path.splitext(path)[1]:
                path += ".sk"

        try:
            with open(path, "w", encoding="utf-8", newline="\n") as target:
                target.write(document.editor.toPlainText())
        except OSError as error:
            QMessageBox.critical(self, tr("Save error"), str(error))
            return False

        document.file_path = path
        document.display_name = None
        document.mark_saved()
        self.update_document_title(document)
        self.status_message.emit(trf("Saved: {0}", path))
        return True

    def save_current(self):
        document = self.current_document()
        if document is None:
            QMessageBox.information(
                self, tr("Save Script"), tr("There is no open document.")
            )
            return False
        return self.save_document(document)

    def save_current_as(self):
        document = self.current_document()
        if document is None:
            QMessageBox.information(
                self, tr("Save As"), tr("There is no open document.")
            )
            return False
        return self.save_document(document, save_as=True)

    def open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, tr("Open Skript file"), "", self.file_filter()
        )
        for path in paths:
            self.open_path(path)

    def open_path(self, path):
        target = os.path.normcase(os.path.abspath(path))
        for index, document in enumerate(self.documents()):
            if document.file_path and os.path.normcase(
                os.path.abspath(document.file_path)
            ) == target:
                self.tabs.setCurrentIndex(index)
                return

        try:
            text, encoding = read_text_file(path)
        except OSError as error:
            QMessageBox.critical(self, tr("Open error"), str(error))
            return

        self.add_tab(text, path)
        if encoding != "utf-8":
            self.status_message.emit(
                trf("Opened with a fallback encoding: {0}. "
                    "It will be saved as UTF-8.", encoding)
            )
        else:
            self.status_message.emit(trf("Opened: {0}", path))

    def open_text(self, title, content):
        """Open downloaded/library content in a new, not yet saved tab."""
        self.add_tab(content, None, display_name=sanitize_filename(title) + ".sk")

    def confirm_close(self, document):
        """Ask about unsaved changes. Returns True when it may be closed."""
        if not document.is_modified():
            return True

        box = QMessageBox(
            QMessageBox.Icon.Warning,
            tr("Unsaved changes"),
            f"{document.base_name()}\n\n"
            + tr("This document has unsaved changes. Save before closing?"),
            QMessageBox.StandardButton.NoButton,
            self
        )
        save = box.addButton(tr("Save changes"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Discard"), QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(
            tr("Keep editing"), QMessageBox.ButtonRole.RejectRole
        )
        box.setDefaultButton(save)
        box.setEscapeButton(cancel)
        box.exec()

        clicked = box.clickedButton()
        if clicked is cancel:
            return False
        if clicked is save:
            return self.save_document(document)
        return True

    def remove_tab(self, index):
        document = self.tabs.widget(index)
        if document is None or not self.confirm_close(document):
            return

        self.tabs.removeTab(index)
        document.deleteLater()

        if self.tabs.count() == 0:
            self.add_tab()

    def close_tab(self):
        index = self.tabs.currentIndex()
        if index >= 0:
            self.remove_tab(index)

    def confirm_exit(self):
        """Ask only when there is unsaved work. Returns True to exit."""
        dirty = [d for d in self.documents() if d.is_modified()]
        if not dirty:
            return True

        box = QMessageBox(
            QMessageBox.Icon.Warning,
            tr("Unsaved changes"),
            trf("{0} document(s) have unsaved changes. "
                "Save them before exiting?", len(dirty)),
            QMessageBox.StandardButton.NoButton,
            self
        )
        save = box.addButton(tr("Save all"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Discard"), QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(
            tr("Keep editing"), QMessageBox.ButtonRole.RejectRole
        )
        box.setDefaultButton(save)
        box.setEscapeButton(cancel)
        box.exec()

        clicked = box.clickedButton()
        if clicked is cancel:
            return False
        if clicked is save:
            return all(self.save_document(d) for d in dirty)
        return True

    # -- editing tools

    def undo(self):
        editor = self.current_editor()
        if editor is not None:
            editor.undo()

    def redo(self):
        editor = self.current_editor()
        if editor is not None:
            editor.redo()

    def show_find(self, with_replace=False):
        if self.current_editor() is not None:
            self.find_bar.show_find(with_replace)

    def analyze_current(self):
        document = self.current_document()
        if document is None:
            return None

        problems = document.run_analysis()
        errors = sum(1 for p in problems if p["severity"] == "Error")
        warnings = len(problems) - errors
        message = trf(
            "Static analysis finished: {0} error(s), {1} warning(s). "
            "The script was not executed.", errors, warnings
        )
        log_event(f"{document.base_name()}: {message}")
        self.status_message.emit(message)
        return problems
    # --------------------------------------------------------------------------
# Helpers that talk to Supabase from background threads
# --------------------------------------------------------------------------

def fetch_author_names(service, ids):
    """Best effort: map user IDs to display names and roles."""
    if not ids or not service.available:
        return {}

    rows = (
        service.client.table(TABLE_PROFILES)
        .select("id, display_name, username, role")
        .in_("id", list(ids))
        .execute()
        .data
    ) or []

    return {
        row.get("id"): {
            "name": row.get("display_name") or row.get("username") or "",
            "role": row.get("role") or "user",
        }
        for row in rows
    }


def fetch_community_stats(service):
    if not service.available:
        raise RuntimeError(service.unavailable_message())
    scripts = (
        service.client.table(TABLE_SCRIPTS)
        .select("*", count="exact").limit(1).execute()
    )
    categories = (
        service.client.table(TABLE_CATEGORIES)
        .select("*", count="exact").limit(1).execute()
    )
    return scripts.count or 0, categories.count or 0


def diagnostics_text(service, settings):
    try:
        import PySide6
        pyside_version = PySide6.__version__
    except Exception:
        pyside_version = "?"
    lines = [
        f"{APP_TITLE} {APP_VERSION}",
        f"Python: {sys.version.split()[0]}",
        f"PySide6: {pyside_version}",
        f"Supabase package: {'yes' if SUPABASE_PACKAGE_AVAILABLE else 'no'}",
        f"Supabase client: {'ready' if service.available else 'unavailable'}",
        f"Signed in: {'yes' if service.logged_in else 'no'}",
        f"keyring: {'yes' if keyring is not None else 'no'}",
        f"Language: {settings.language()}",
        f"Theme: {settings.theme()}",
    ]
    if service.error:
        lines.append(f"Supabase error: {service.error}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Publish dialog
# --------------------------------------------------------------------------

class PublishDialog(QDialog, Translatable):

    def __init__(self, service, categories, title, content, parent=None):
        super().__init__(parent)
        self.service = service
        self.content = content

        self.setMinimumWidth(560)
        self.bind(lambda: self.setWindowTitle(tr("Publish Script")))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        self.title_input = QLineEdit(title)
        self.category_input = QComboBox()
        for category in categories:
            self.category_input.addItem(
                str(category.get("name", "?")), category.get("id")
            )
        self.description_input = QPlainTextEdit()
        self.description_input.setFixedHeight(80)

        self.preview = QPlainTextEdit(content)
        self.preview.setReadOnly(True)
        self.preview.setFixedHeight(130)
        SkriptHighlighter(self.preview.document())

        title_label = QLabel()
        category_label = QLabel()
        description_label = QLabel()
        code_label = QLabel()
        self.bt(title_label, "Title")
        self.bt(category_label, "Category")
        self.bt(description_label, "Description")
        self.bt(code_label, "Code")

        form.addRow(title_label, self.title_input)
        form.addRow(category_label, self.category_input)
        form.addRow(description_label, self.description_input)
        form.addRow(code_label, self.preview)
        layout.addLayout(form)

        self.message = QLabel("")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #bd3e36;")
        layout.addWidget(self.message)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_button = QPushButton()
        self.publish_button = QPushButton()
        self.publish_button.setObjectName("PrimaryButton")
        self.bt(self.cancel_button, "Cancel")
        self.bt(self.publish_button, "Publish")
        self.cancel_button.clicked.connect(lambda *_: self.reject())
        self.publish_button.clicked.connect(lambda *_: self.submit())
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.publish_button)
        layout.addLayout(buttons)

    def submit(self):
        title = self.title_input.text().strip()
        if not title:
            self.message.setText(tr("Title is required."))
            return
        if not self.content.strip():
            self.message.setText(tr("The script is empty."))
            return
        if self.category_input.count() and self.category_input.currentData() is None:
            self.message.setText(tr("Choose a category."))
            return

        self.message.setStyleSheet("color: #587086;")
        self.message.setText(tr("Publishing..."))
        self.publish_button.setEnabled(False)

        run_async(
            self.service.publish_script,
            self._published,
            self._failed,
            title,
            self.description_input.toPlainText().strip(),
            self.content,
            self.category_input.currentData()
        )

    def _published(self, _result):
        log_event("Script published to the Global Library.")
        self.accept()

    def _failed(self, error):
        self.message.setStyleSheet("color: #bd3e36;")
        self.message.setText(friendly_error(error))
        self.publish_button.setEnabled(True)
        log_event(f"Publish failed: {error}")


# --------------------------------------------------------------------------
# Global Library
# --------------------------------------------------------------------------

class LibraryPage(QWidget, Translatable):
    open_in_editor = Signal(str, str)
    status_message = Signal(str)
    login_required = Signal()

    def __init__(self, service):
        super().__init__()
        self.service = service
        self.categories = []
        self.authors = {}
        self.current_row = None
        self._loaded = False
        self._request_id = 0
        self._state = ("Loading...", ())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(17, 15, 17, 15)
        layout.setSpacing(10)

        layout.addWidget(self.add_tr_child(PageHeader(
            "Global Library", "Browse scripts shared by the community."
        )))

        controls = QHBoxLayout()
        self.search_input = QLineEdit()
        self.bph(self.search_input, "Search scripts")
        self.search_input.returnPressed.connect(lambda: self.refresh())

        self.category_filter = QComboBox()
        self.category_filter.setMinimumWidth(180)
        self.category_filter.addItem("", None)
        self.bind(lambda: self.category_filter.setItemText(
            0, tr("All categories")
        ))
        self.category_filter.currentIndexChanged.connect(
            lambda *_: self.refresh() if self._loaded else None
        )

        search_button = QPushButton()
        refresh_button = QPushButton()
        publish_button = QPushButton()
        publish_button.setObjectName("PrimaryButton")
        self.bt(search_button, "Search")
        self.bt(refresh_button, "Refresh Library")
        self.bt(publish_button, "Publish Script")
        search_button.clicked.connect(lambda *_: self.refresh())
        refresh_button.clicked.connect(lambda *_: self.refresh(True))
        publish_button.clicked.connect(
            lambda *_: self.publish_current_requested()
        )

        controls.addWidget(self.search_input, 1)
        controls.addWidget(self.category_filter)
        controls.addWidget(search_button)
        controls.addWidget(refresh_button)
        controls.addWidget(publish_button)
        layout.addLayout(controls)

        self.state_label = QLabel()
        self.state_label.setStyleSheet("color: #74899c;")
        self.bind(self.render_state)
        layout.addWidget(self.state_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._selection_changed)
        splitter.addWidget(self.list_widget)

        details = QFrame()
        details.setObjectName("Card")
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(14, 12, 14, 12)
        details_layout.setSpacing(6)

        self.detail_title = QLabel()
        self.detail_title.setWordWrap(True)
        self.detail_title.setStyleSheet(
            "font-size: 13pt; font-weight: 600; color: #294f72;"
        )
        self.detail_meta = QLabel()
        self.detail_meta.setWordWrap(True)
        self.detail_meta.setStyleSheet("color: #74899c;")
        self.detail_description = QLabel()
        self.detail_description.setWordWrap(True)

        self.detail_code = QPlainTextEdit()
        self.detail_code.setReadOnly(True)
        self.detail_code.setFont(QFont("Consolas", 10))
        SkriptHighlighter(self.detail_code.document())

        button_row = QHBoxLayout()
        self.open_button = QPushButton()
        self.download_button = QPushButton()
        self.copy_button = QPushButton()
        self.delete_button = QPushButton()
        self.bt(self.open_button, "Open in Editor")
        self.bt(self.download_button, "Download .sk")
        self.bt(self.copy_button, "Copy Code")
        self.bt(self.delete_button, "Delete Script")
        self.open_button.clicked.connect(lambda *_: self.open_selected())
        self.download_button.clicked.connect(lambda *_: self.download_selected())
        self.copy_button.clicked.connect(lambda *_: self.copy_selected())
        self.delete_button.clicked.connect(lambda *_: self.delete_selected())
        button_row.addWidget(self.open_button)
        button_row.addWidget(self.download_button)
        button_row.addWidget(self.copy_button)
        button_row.addWidget(self.delete_button)
        button_row.addStretch()

        details_layout.addWidget(self.detail_title)
        details_layout.addWidget(self.detail_meta)
        details_layout.addWidget(self.detail_description)
        details_layout.addWidget(self.detail_code, 1)
        details_layout.addLayout(button_row)
        splitter.addWidget(details)
        splitter.setSizes([300, 560])
        layout.addWidget(splitter, 1)

        self.bind(self.render_details)

    # -- state

    def set_state(self, key, *args):
        self._state = (key, args)
        self.render_state()

    def render_state(self):
        key, args = self._state
        self.state_label.setText(trf(key, *args) if args else tr(key))

    # -- loading

    def ensure_loaded(self):
        if not self._loaded:
            self.refresh(True)

    def category_name(self, category_id):
        for category in self.categories:
            if category.get("id") == category_id:
                return str(category.get("name", "?"))
        return tr("Unknown")

    def refresh(self, reload_categories=False):
        if not self.service.available:
            self.set_state(
                "Supabase is unavailable: {0}", self.service.error or "?"
            )
            return

        self._loaded = True
        self._request_id += 1
        request_id = self._request_id
        self.set_state("Loading...")

        if reload_categories or not self.categories:
            run_async(
                self.service.get_categories,
                self._categories_loaded,
                lambda e: log_event(f"Categories failed: {e}")
            )

        run_async(
            self.service.get_scripts,
            lambda rows, r=request_id: self._scripts_loaded(rows, r),
            lambda e, r=request_id: self._load_failed(e, r),
            self.search_input.text(),
            self.category_filter.currentData()
        )

    def _categories_loaded(self, rows):
        self.categories = rows
        selected = self.category_filter.currentData()

        self.category_filter.blockSignals(True)
        while self.category_filter.count() > 1:
            self.category_filter.removeItem(1)
        for category in rows:
            self.category_filter.addItem(
                str(category.get("name", "?")), category.get("id")
            )
        index = self.category_filter.findData(selected)
        self.category_filter.setCurrentIndex(max(index, 0))
        self.category_filter.blockSignals(False)

    def _load_failed(self, error, request_id):
        if request_id != self._request_id:
            return
        self.list_widget.clear()
        self.current_row = None
        self.render_details()
        self.set_state("Could not load the library: {0}", friendly_error(error))
        log_event(f"Library load failed: {error}")

    def _scripts_loaded(self, rows, request_id):
        if request_id != self._request_id:
            return

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for row in rows:
            item = QListWidgetItem(str(row.get("title") or "?"))
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)

        self.current_row = None
        if rows:
            self.set_state("{0} script(s) found.", len(rows))
            self.list_widget.setCurrentRow(0)
        else:
            self.set_state("No scripts found.")
        self.render_details()

        ids = sorted({
            row.get(SCRIPT_AUTHOR_COLUMN) for row in rows
            if row.get(SCRIPT_AUTHOR_COLUMN)
        })
        if ids:
            run_async(
                fetch_author_names, self._authors_loaded, None,
                self.service, ids
            )

    def _authors_loaded(self, mapping):
        self.authors.update(mapping)
        self.render_details()

    # -- details

    def _selection_changed(self, current, _previous):
        self.current_row = (
            current.data(Qt.ItemDataRole.UserRole) if current else None
        )
        self.render_details()

    def render_details(self):
        row = self.current_row
        has_row = row is not None

        for button in (self.open_button, self.download_button,
                       self.copy_button):
            button.setEnabled(has_row)

        self.delete_button.setEnabled(
            has_row and self.service.logged_in and row.get("id") is not None
        )

        if not has_row:
            self.detail_title.setText(tr("Select a script to see its details."))
            self.detail_meta.setText("")
            self.detail_description.setText("")
            self.detail_code.setPlainText("")
            return

        author_info = self.authors.get(row.get(SCRIPT_AUTHOR_COLUMN)) or {}
        author = author_info.get("name") or tr("Unknown")
        author_role = author_info.get("role")
        created = str(row.get("created_at") or "")[:10] or "-"

        author_text = html.escape(author)
        if author_role == "admin":
            author_text = f'<span style="color: #238b45;">{author_text}</span>'

        author_label = html.escape(tr("Author: {0}").format(""))
        category = html.escape(
            trf("Category: {0}", self.category_name(row.get("category_id")))
        )
        published = html.escape(trf("Published: {0}", created))

        self.detail_title.setText(str(row.get("title") or "?"))
        self.detail_meta.setTextFormat(Qt.TextFormat.RichText)
        self.detail_meta.setText(
            f"{author_label}{author_text}   |   {category}   |   {published}"
        )
        self.detail_description.setText(
            str(row.get("description") or "") or tr("No description.")
        )
        content = str(row.get("content") or "")
        if self.detail_code.toPlainText() != content:
            self.detail_code.setPlainText(content)

    def _selected(self):
        row = self.current_row
        if row is None:
            return None, None
        return str(row.get("title") or "script"), str(row.get("content") or "")

    def open_selected(self):
        title, content = self._selected()
        if title is not None:
            self.open_in_editor.emit(title, content)

    def download_selected(self):
        title, content = self._selected()
        if title is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Save Skript file"),
            sanitize_filename(title) + ".sk",
            f"{tr('Skript files')} (*.sk)"
        )
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".sk"
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as target:
                target.write(content)
        except OSError as error:
            QMessageBox.critical(self, tr("Save error"), str(error))
            return
        self.status_message.emit(trf("Saved: {0}", path))

    def delete_selected(self):
        row = self.current_row
        if row is None or not self.service.logged_in:
            return

        script_id = row.get("id")
        if script_id is None:
            QMessageBox.warning(
                self, tr("Delete Script"), tr("This script has no ID.")
            )
            return

        title = str(row.get("title") or "script")
        answer = QMessageBox.question(
            self,
            tr("Delete Script"),
            trf("Delete script '{0}'? This cannot be undone.", title),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.delete_button.setEnabled(False)
        run_async(
            self.service.delete_script,
            self._script_deleted,
            self._delete_failed,
            script_id,
        )

    def _script_deleted(self, _result):
        self.status_message.emit(tr("Script deleted."))
        self.refresh()

    def _delete_failed(self, error):
        self.render_details()
        QMessageBox.warning(
            self, tr("Delete Script"), friendly_error(error)
        )

    def copy_selected(self):
        _title, content = self._selected()
        if content is not None:
            QApplication.clipboard().setText(content)
            self.status_message.emit(tr("Code copied to the clipboard."))

    # -- publishing (the code comes from the active editor tab)

    def publish_current_requested(self):
        self.publish_provider()

    publish_provider = lambda self: None  # replaced by MainWindow

    def open_publish_dialog(self, title, content):
        if not self.service.available:
            QMessageBox.warning(
                self, tr("Publish Script"), self.service.unavailable_message()
            )
            return
        if not self.service.logged_in:
            self.login_required.emit()
            return
        if not content.strip():
            QMessageBox.information(
                self, tr("Publish Script"), tr("The script is empty.")
            )
            return

        if self.categories:
            self._show_publish(title, content)
            return

        def loaded(rows):
            self.categories = rows
            self._show_publish(title, content)

        run_async(
            self.service.get_categories, loaded,
            lambda e: QMessageBox.warning(
                self, tr("Publish Script"), friendly_error(e)
            )
        )

    def _show_publish(self, title, content):
        dialog = PublishDialog(
            self.service, self.categories, title, content, self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.status_message.emit(tr("Script published successfully."))
            self.refresh(True)


# --------------------------------------------------------------------------
# Development Tools
# --------------------------------------------------------------------------

class ToolsPage(QWidget, Translatable):
    analyze_requested = Signal()
    status_message = Signal(str)

    def __init__(self, service, settings):
        super().__init__()
        self.service = service
        self.settings = settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(17, 15, 17, 15)
        layout.setSpacing(10)

        layout.addWidget(self.add_tr_child(PageHeader(
            "Development Tools",
            "Diagnostics and helpers for working with Skript."
        )))

        row = QHBoxLayout()
        analyze_button = QPushButton()
        test_button = QPushButton()
        copy_button = QPushButton()
        clear_button = QPushButton()
        self.bt(analyze_button, "Analyze Current Script")
        self.bt(test_button, "Test Supabase Connection")
        self.bt(copy_button, "Copy Diagnostics")
        self.bt(clear_button, "Clear Log")
        analyze_button.clicked.connect(
            lambda *_: self.analyze_requested.emit()
        )
        test_button.clicked.connect(lambda *_: self.test_connection())
        copy_button.clicked.connect(lambda *_: self.copy_diagnostics())
        clear_button.clicked.connect(lambda *_: self.clear_log())
        for button in (analyze_button, test_button, copy_button, clear_button):
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)

        environment_label = QLabel()
        environment_label.setStyleSheet("font-weight: bold; color: #71879b;")
        self.bt(environment_label, "Environment")
        layout.addWidget(environment_label)

        self.environment = QPlainTextEdit()
        self.environment.setReadOnly(True)
        self.environment.setMaximumHeight(170)
        layout.addWidget(self.environment)

        log_label = QLabel()
        log_label.setStyleSheet("font-weight: bold; color: #71879b;")
        self.bt(log_label, "Event Log")
        layout.addWidget(log_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 9))
        self.log_view.setPlainText("\n".join(APP_LOG))
        layout.addWidget(self.log_view, 1)

        LOG_LISTENERS.append(self.append_log)
        self.refresh_environment()

    def refresh_environment(self):
        self.environment.setPlainText(
            diagnostics_text(self.service, self.settings)
        )

    def append_log(self, line):
        self.log_view.appendPlainText(line)

    def clear_log(self):
        APP_LOG.clear()
        self.log_view.clear()

    def copy_diagnostics(self):
        self.refresh_environment()
        QApplication.clipboard().setText(
            diagnostics_text(self.service, self.settings)
            + "\n\n" + "\n".join(APP_LOG[-100:])
        )
        self.status_message.emit(tr("Diagnostics copied to the clipboard."))

    def test_connection(self):
        if not self.service.available:
            QMessageBox.warning(
                self, tr("Test Supabase Connection"),
                self.service.unavailable_message()
            )
            return

        self.status_message.emit(tr("Testing connection..."))
        run_async(
            self.service.get_categories,
            self._connection_ok,
            self._connection_failed
        )

    def _connection_ok(self, rows):
        message = trf("Connection OK. {0} category row(s) readable.", len(rows))
        log_event(message)
        self.status_message.emit(message)
        self.refresh_environment()

    def _connection_failed(self, error):
        log_event(f"Connection test failed: {error}")
        self.status_message.emit(friendly_error(error))
        self.refresh_environment()


# --------------------------------------------------------------------------
# Community
# --------------------------------------------------------------------------

class CommunityPage(QWidget, Translatable):

    def __init__(self, service):
        super().__init__()
        self.service = service
        self._state = ("Loading...", ())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(17, 15, 17, 15)
        layout.setSpacing(12)

        layout.addWidget(self.add_tr_child(PageHeader(
            "Community", "Live statistics from the shared database."
        )))

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(8)

        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        self.stats_label.setStyleSheet(
            "font-size: 12pt; font-weight: 600; color: #294f72;"
        )
        self.bind(self.render_state)

        refresh_button = QPushButton()
        self.bt(refresh_button, "Refresh")
        refresh_button.clicked.connect(lambda *_: self.refresh())

        card_layout.addWidget(self.stats_label)
        card_layout.addWidget(refresh_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(card)

        soon = QFrame()
        soon.setObjectName("Card")
        soon_layout = QVBoxLayout(soon)
        soon_layout.setContentsMargins(18, 14, 18, 14)
        soon_title = QLabel()
        soon_title.setStyleSheet("font-weight: bold; color: #71879b;")
        soon_text = QLabel()
        soon_text.setWordWrap(True)
        self.bt(soon_title, "Not available yet")
        self.bt(
            soon_text,
            "Likes, comments, script versions and content reports are "
            "planned. They are not part of this version."
        )
        soon_layout.addWidget(soon_title)
        soon_layout.addWidget(soon_text)
        layout.addWidget(soon)
        layout.addStretch()

    def set_state(self, key, *args):
        self._state = (key, args)
        self.render_state()

    def render_state(self):
        key, args = self._state
        self.stats_label.setText(trf(key, *args) if args else tr(key))

    def refresh(self):
        if not self.service.available:
            self.set_state(
                "Statistics unavailable: {0}", self.service.unavailable_message()
            )
            return
        self.set_state("Loading...")
        run_async(
            fetch_community_stats, self._loaded, self._failed, self.service
        )

    def _loaded(self, stats):
        scripts, categories = stats
        self.set_state(
            "Scripts shared: {0}   |   Categories: {1}", scripts, categories
        )

    def _failed(self, error):
        self.set_state("Statistics unavailable: {0}", friendly_error(error))
        from PySide6.QtGui import QIcon


# --------------------------------------------------------------------------
# Settings and About
# --------------------------------------------------------------------------

class SettingsPage(QWidget, Translatable):
    language_changed = Signal(str)
    preferences_changed = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(17, 15, 17, 15)
        layout.setSpacing(12)

        layout.addWidget(self.add_tr_child(PageHeader(
            "Settings", "Customize language and editor preferences."
        )))

        card = QFrame()
        card.setObjectName("Card")
        form = QFormLayout(card)
        form.setContentsMargins(18, 16, 18, 16)
        form.setSpacing(12)

        self.language_combo = QComboBox()
        for code in LANGUAGE_CODES:
            self.language_combo.addItem(LANGUAGE_NAMES[code], code)
        self.language_combo.setCurrentIndex(
            max(0, self.language_combo.findData(settings.language()))
        )
        self.language_combo.currentIndexChanged.connect(
            lambda *_: self._language_selected()
        )

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(settings.editor_font_family()))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 32)
        self.size_spin.setValue(settings.editor_font_size())
        self.wrap_check = QCheckBox()
        self.wrap_check.setChecked(settings.editor_wrap())

        self.font_combo.currentFontChanged.connect(
            lambda *_: self._preferences_edited()
        )
        self.size_spin.valueChanged.connect(
            lambda *_: self._preferences_edited()
        )
        self.wrap_check.toggled.connect(lambda *_: self._preferences_edited())

        language_label = QLabel()
        font_label = QLabel()
        size_label = QLabel()
        self.bt(language_label, "Language")
        self.bt(font_label, "Editor font")
        self.bt(size_label, "Font size")
        self.bt(self.wrap_check, "Wrap long lines")

        form.addRow(language_label, self.language_combo)
        form.addRow(font_label, self.font_combo)
        form.addRow(size_label, self.size_spin)
        form.addRow("", self.wrap_check)
        layout.addWidget(card)

        note = QLabel()
        note.setWordWrap(True)
        note.setStyleSheet("color: #74899c;")
        self.bt(note, "Preferences are stored on this computer.")
        layout.addWidget(note)
        layout.addStretch()

    def _language_selected(self):
        code = self.language_combo.currentData()
        if code not in LANGUAGE_CODES:
            return
        self.settings.set_language(code)
        set_language(code)
        self.language_changed.emit(code)

    def _preferences_edited(self):
        self.settings.set_editor_preferences(
            self.font_combo.currentFont().family(),
            self.size_spin.value(),
            self.wrap_check.isChecked()
        )
        self.preferences_changed.emit()


class AboutPage(QWidget, Translatable):

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(17, 15, 17, 15)
        layout.setSpacing(12)

        layout.addWidget(self.add_tr_child(PageHeader(
            "About", "Information about this application."
        )))

        card = QFrame()
        card.setObjectName("HeaderCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 28, 30, 28)
        card_layout.setSpacing(8)

        card_layout.addWidget(LogoWidget(64), 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel(APP_TITLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20pt; font-weight: 600; color: #2d5275;")
        card_layout.addWidget(title)

        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #74899c; letter-spacing: 1px;")
        card_layout.addWidget(subtitle)

        for key, value in (
            ("Version", APP_VERSION),
            ("Publisher", APP_PUBLISHER),
            ("Copyright", APP_COPYRIGHT),
        ):
            label = QLabel()
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.bind(lambda l=label, k=key, v=value: l.setText(f"{tr(k)}: {v}"))
            card_layout.addWidget(label)

        description = QLabel()
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setStyleSheet("color: #657d93; padding-top: 10px;")
        self.bt(
            description,
            "SkriptDocx is a development environment for Skript. "
            "Preferences are kept locally; accounts and shared scripts "
            "are stored in Supabase."
        )
        card_layout.addWidget(description)

        layout.addWidget(card)
        layout.addStretch()


# --------------------------------------------------------------------------
# Account dialogs
# --------------------------------------------------------------------------

class AuthDialog(QDialog, Translatable):

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.register_mode = False
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        layout.addWidget(LogoWidget(34), 0, Qt.AlignmentFlag.AlignHCenter)

        self.heading = QLabel()
        self.heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.heading.setStyleSheet(
            "font-size: 14pt; font-weight: 600; color: #294f72;"
        )
        layout.addWidget(self.heading)

        self.form = QFormLayout()
        self.form.setSpacing(8)

        self.username_input = QLineEdit()
        self.email_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)

        username_label = QLabel()
        email_label = QLabel()
        password_label = QLabel()
        confirm_label = QLabel()
        self.bt(username_label, "Username")
        self.bt(email_label, "E-mail")
        self.bt(password_label, "Password")
        self.bt(confirm_label, "Confirm password")

        self.form.addRow(username_label, self.username_input)
        self.form.addRow(email_label, self.email_input)
        self.form.addRow(password_label, self.password_input)
        self.form.addRow(confirm_label, self.confirm_input)
        layout.addLayout(self.form)

        for field in (self.username_input, self.email_input,
                      self.password_input, self.confirm_input):
            field.returnPressed.connect(lambda: self.submit())

        self.message = QLabel("")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        self.submit_button = QPushButton()
        self.submit_button.setObjectName("PrimaryButton")
        self.submit_button.clicked.connect(lambda *_: self.submit())
        layout.addWidget(self.submit_button)

        self.switch_button = QPushButton()
        self.switch_button.clicked.connect(lambda *_: self.toggle_mode())
        layout.addWidget(self.switch_button)

        cancel_button = QPushButton()
        self.bt(cancel_button, "Cancel")
        cancel_button.clicked.connect(lambda *_: self.reject())
        layout.addWidget(cancel_button)

        self.bind(self.render_mode)

        if not service.available:
            self.show_error(service.unavailable_message())
            self.submit_button.setEnabled(False)

    def render_mode(self):
        register = self.register_mode
        self.setWindowTitle(tr("Create account") if register else tr("Sign in"))
        self.heading.setText(tr("Create account") if register else tr("Sign in"))
        self.submit_button.setText(
            tr("Create account") if register else tr("Sign in")
        )
        self.switch_button.setText(
            tr("Already have an account? Sign in") if register
            else tr("Don't have an account? Create one")
        )
        self.form.setRowVisible(0, register)
        self.form.setRowVisible(3, register)

    def toggle_mode(self):
        self.register_mode = not self.register_mode
        self.message.setText("")
        self.render_mode()

    def show_error(self, text):
        self.message.setStyleSheet("color: #bd3e36;")
        self.message.setText(text)

    def show_info(self, text):
        self.message.setStyleSheet("color: #43854b;")
        self.message.setText(text)

    def submit(self):
        if not self.service.available:
            return

        email = self.email_input.text().strip()
        password = self.password_input.text()

        if "@" not in email or "." not in email.split("@")[-1]:
            self.show_error(tr("Enter a valid e-mail address."))
            return

        if self.register_mode:
            username = self.username_input.text().strip()
            if len(username) < 3:
                self.show_error(tr("Username must have at least 3 characters."))
                return
            if len(password) < 8:
                self.show_error(tr("Password must have at least 8 characters."))
                return
            if password != self.confirm_input.text():
                self.show_error(tr("Passwords do not match."))
                return
            run_async(
                self.service.sign_up, self._registered, self._failed,
                email, password, username
            )
        else:
            if not password:
                self.show_error(tr("Password must have at least 8 characters."))
                return
            run_async(
                self.service.sign_in, self._logged_in, self._failed,
                email, password
            )

        self.submit_button.setEnabled(False)
        self.show_info(tr("Please wait..."))

    def _logged_in(self, _result):
        self.password_input.clear()
        log_event("Signed in.")
        self.accept()

    def _registered(self, _result):
        self.password_input.clear()
        self.confirm_input.clear()
        self.submit_button.setEnabled(True)
        log_event("Account created.")
        if self.service.logged_in:
            self.accept()
            return
        self.register_mode = False
        self.render_mode()
        self.show_info(
            tr("Account created. Check your e-mail to confirm it, "
               "then sign in.")
        )

    def _failed(self, error):
        self.submit_button.setEnabled(True)
        self.show_error(friendly_error(error))
        log_event(f"Authentication failed: {type(error).__name__}")


class ProfileDialog(QDialog, Translatable):

    def __init__(self, service, profile, avatar_pixmap, parent=None):
        super().__init__(parent)
        self.service = service
        self.profile = profile or {}
        self.pending_avatar = None
        self.signed_out = False
        self.changed = False
        self.setMinimumWidth(420)
        self.bind(lambda: self.setWindowTitle(tr("Account")))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(96, 96)
        layout.addWidget(self.avatar_label, 0, Qt.AlignmentFlag.AlignHCenter)
        self.set_avatar(avatar_pixmap)

        email = getattr(service.user, "email", "") or ""
        email_label = QLabel(email)
        email_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        email_label.setStyleSheet("color: #74899c;")
        layout.addWidget(email_label)

        self.avatar_button = QPushButton()
        self.bt(self.avatar_button, "Change Avatar")
        self.avatar_button.clicked.connect(lambda *_: self.choose_avatar())
        layout.addWidget(self.avatar_button, 0, Qt.AlignmentFlag.AlignHCenter)

        form = QFormLayout()
        form.setSpacing(8)
        self.name_input = QLineEdit(
            str(self.profile.get("display_name")
                or self.profile.get("username") or "")
        )
        name_label = QLabel()
        self.bt(name_label, "Display name")
        form.addRow(name_label, self.name_input)

        username = str(self.profile.get("username") or "")
        if username:
            username_label = QLabel()
            self.bt(username_label, "Username")
            form.addRow(username_label, QLabel(username))
        layout.addLayout(form)

        self.message = QLabel("")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        row = QHBoxLayout()
        self.save_button = QPushButton()
        self.save_button.setObjectName("PrimaryButton")
        self.sign_out_button = QPushButton()
        close_button = QPushButton()
        self.bt(self.save_button, "Save")
        self.bt(self.sign_out_button, "Sign Out")
        self.bt(close_button, "Close")
        self.save_button.clicked.connect(lambda *_: self.save())
        self.sign_out_button.clicked.connect(lambda *_: self.sign_out())
        close_button.clicked.connect(lambda *_: self.reject())
        row.addWidget(self.save_button)
        row.addWidget(self.sign_out_button)
        row.addStretch()
        row.addWidget(close_button)
        layout.addLayout(row)

    def set_avatar(self, pixmap):
        if pixmap is not None and not pixmap.isNull():
            self.avatar_label.setPixmap(circular_pixmap(pixmap, 96))
        else:
            self.avatar_label.setPixmap(fallback_avatar_pixmap(96))

    def show_error(self, text):
        self.message.setStyleSheet("color: #bd3e36;")
        self.message.setText(text)

    def show_info(self, text):
        self.message.setStyleSheet("color: #43854b;")
        self.message.setText(text)

    def choose_avatar(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Select avatar image"), "",
            f"{tr('Images')} (*.png *.jpg *.jpeg *.webp)"
        )
        if not path:
            return

        if os.path.getsize(path) > 5 * 1024 * 1024:
            self.show_error(tr("Avatar must be smaller than 5 MB."))
            return

        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.show_error(tr("Could not read the selected image."))
            return

        self.pending_avatar = path
        self.set_avatar(pixmap)
        self.message.setText("")

    def _save_job(self, name, avatar_path):
        url = None
        if avatar_path:
            url = self.service.upload_avatar(avatar_path)
        return self.service.update_profile(name, url)

    def save(self):
        name = self.name_input.text().strip()
        if not name:
            self.show_error(tr("Display name is required."))
            return

        self.save_button.setEnabled(False)
        self.show_info(tr("Saving..."))
        run_async(
            self._save_job, self._saved, self._save_failed,
            name, self.pending_avatar
        )

    def _saved(self, row):
        self.profile = row
        self.changed = True
        log_event("Profile saved.")
        self.accept()

    def _save_failed(self, error):
        self.save_button.setEnabled(True)
        self.show_error(friendly_error(error))
        log_event(f"Profile save failed: {error}")

    def sign_out(self):
        self.sign_out_button.setEnabled(False)
        run_async(self.service.sign_out, self._signed_out, self._signed_out)

    def _signed_out(self, _result=None):
        self.signed_out = True
        log_event("Signed out.")
        self.accept()


# --------------------------------------------------------------------------
# Splash screen
# --------------------------------------------------------------------------

class SplashScreen(QWidget):

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(460, 260)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        frame = QFrame()
        frame.setObjectName("MainFrame")
        outer.addWidget(frame)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(8)
        layout.addStretch()
        layout.addWidget(LogoWidget(60), 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel(APP_TITLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18pt; font-weight: 600; color: #2d5275;")
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #74899c; letter-spacing: 1px;")
        version = QLabel(f"{APP_VERSION}   |   {APP_COPYRIGHT}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("color: #94a4b3; font-size: 8pt;")

        self.status = QLabel(tr("Starting..."))
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("color: #587086;")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(version)
        layout.addStretch()
        layout.addWidget(self.status)

        screen = QApplication.primaryScreen()
        if screen is not None:
            center = screen.availableGeometry().center()
            self.move(center - self.rect().center())

    def set_status(self, key):
        self.status.setText(tr(key))


# --------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------

class MainWindow(AeroMainWindow, Translatable):

    def __init__(self, service, settings):
        super().__init__()
        self.service = service
        self.settings = settings
        self.profile = None
        self.avatar_pixmap = None
        self.pages = {}
        self.nav_buttons = {}
        self.actions_by_id = {}
        self._visited = set()

        self.setWindowTitle(f"{APP_TITLE} - {APP_SUBTITLE}")
        self.setMinimumSize(1000, 680)
        self.resize(1200, 780)

        frame = QFrame()
        frame.setObjectName("MainFrame")
        self.setCentralWidget(frame)

        root = QVBoxLayout(frame)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)

        self.title_bar = AeroTitleBar(self)
        self.add_tr_child(self.title_bar)
        root.addWidget(self.title_bar)

        self.build_actions()
        root.addWidget(self.build_menu_area())
        root.addWidget(self.build_toolbar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.build_navigation())

        self.stack = QStackedWidget()
        content = QFrame()
        content.setObjectName("ContentPanel")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.stack)
        body.addWidget(content, 1)
        root.addLayout(body, 1)

        self.build_pages()

        self.status = QStatusBar()
        self.status.setSizeGripEnabled(False)
        self.connection_label = QLabel()
        self.status.addPermanentWidget(self.connection_label)
        self.status.addPermanentWidget(QSizeGrip(self))
        root.addWidget(self.status)

        self.bind(self.update_account_button)
        self.show_status(tr("Ready."))
        self.show_page("dashboard")
        self.load_account()

    # -- construction

    def make_action(self, action_id, key, handler, shortcut=None):
        action = QAction(self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(lambda *_: handler())
        self.bind(lambda a=action, k=key: a.setText(tr(k)))
        self.addAction(action)  # makes the shortcut work from every page
        self.actions_by_id[action_id] = action
        return action

    def workspace_do(self, method):
        self.show_page("workspace")
        method()

    def build_actions(self):
        w = lambda name: (lambda: self.workspace_do(getattr(self.workspace, name)))

        self.make_action("new", "New Script", w("new_script"), "Ctrl+N")
        self.make_action("open", "Open Script", w("open_files"), "Ctrl+O")
        self.make_action("save", "Save Script", w("save_current"), "Ctrl+S")
        self.make_action("save_as", "Save As", w("save_current_as"),
                         "Ctrl+Shift+S")
        self.make_action("close_tab", "Close Tab", w("close_tab"), "Ctrl+W")
        self.make_action("exit", "Exit", self.close, "Ctrl+Q")
        self.make_action("undo", "Undo", w("undo"))
        self.make_action("redo", "Redo", w("redo"))
        self.make_action("find", "Find", lambda: self.workspace_do(
            lambda: self.workspace.show_find(False)), "Ctrl+F")
        self.make_action("replace", "Replace", lambda: self.workspace_do(
            lambda: self.workspace.show_find(True)), "Ctrl+H")
        self.make_action("analyze", "Analyze Script", w("analyze_current"), "F5")

        self.make_action("library", "Global Library",
                         lambda: self.show_page("library"), "Ctrl+L")
        self.make_action("refresh_library", "Refresh Library",
                         self.refresh_library, "Ctrl+Shift+R")
        self.make_action("publish", "Publish Script",
                         self.publish_current, "Ctrl+Shift+P")

        self.make_action("account", "Account", self.open_account,
                         "Ctrl+Shift+A")
        self.make_action("sign_out", "Sign Out", self.sign_out)

        self.make_action("dashboard", "Dashboard",
                         lambda: self.show_page("dashboard"))
        self.make_action("workspace", "Workspace",
                         lambda: self.show_page("workspace"))
        self.make_action("tools", "Development Tools",
                         lambda: self.show_page("tools"))
        self.make_action("community", "Community",
                         lambda: self.show_page("community"))
        self.make_action("settings", "Settings",
                         lambda: self.show_page("settings"), "Ctrl+,")
        self.make_action("about", "About", lambda: self.show_page("about"), "F1")

    def build_menu_area(self):
        area = QFrame()
        area.setObjectName("MenuArea")
        row = QHBoxLayout(area)
        row.setContentsMargins(4, 0, 8, 0)
        row.setSpacing(6)

        menu_bar = QMenuBar()
        row.addWidget(menu_bar)

        structure = [
            ("File", ["new", "open", "save", "save_as", "close_tab", None,
                      "exit"]),
            ("Edit", ["undo", "redo", None, "find", "replace"]),
            ("Script", ["analyze"]),
            ("Library", ["library", "refresh_library", "publish"]),
            ("Account", ["account", "sign_out"]),
            ("Go", ["dashboard", "workspace", "tools", "community",
                    "settings"]),
            ("Help", ["about"]),
        ]
        for title_key, items in structure:
            menu = menu_bar.addMenu("")
            self.bind(lambda m=menu, k=title_key: m.setTitle(tr(k)))
            for item in items:
                if item is None:
                    menu.addSeparator()
                else:
                    menu.addAction(self.actions_by_id[item])

        row.addStretch()

        self.account_button = QPushButton()
        self.account_button.setIconSize(QSize(22, 22))
        self.account_button.setMinimumHeight(26)
        self.account_button.clicked.connect(lambda *_: self.open_account())
        row.addWidget(self.account_button)
        return area

    def build_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        for action_id in ("new", "open", "save", "analyze", "library",
                          "publish", "settings"):
            toolbar.addAction(self.actions_by_id[action_id])
        return toolbar

    def build_navigation(self):
        nav = QFrame()
        nav.setObjectName("Navigation")
        nav.setFixedWidth(210)
        layout = QVBoxLayout(nav)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(4)

        logo_row = QHBoxLayout()
        logo_row.addWidget(LogoWidget(30))
        logo_row.addStretch()
        layout.addLayout(logo_row)
        layout.addSpacing(8)

        items = [
            ("dashboard", "\u2302", "Dashboard"),
            ("workspace", "\u25a4", "Workspace"),
            ("library", "\u25c8", "Global Library"),
            ("tools", "\u2692", "Development Tools"),
            ("community", "\u263a", "Community"),
            ("settings", "\u2699", "Settings"),
            ("about", "\u24d8", "About"),
        ]
        for page_id, symbol, key in items:
            button = QPushButton()
            button.setObjectName("NavigationButton")
            self.bt(button, key, prefix=f"{symbol}   ")
            button.clicked.connect(lambda *_, p=page_id: self.show_page(p))
            layout.addWidget(button)
            self.nav_buttons[page_id] = button

        layout.addStretch()
        return nav

    def build_pages(self):
        self.dashboard = DashboardPage()
        self.workspace = WorkspacePage(self.settings)
        self.library = LibraryPage(self.service)
        self.tools = ToolsPage(self.service, self.settings)
        self.community = CommunityPage(self.service)
        self.settings_page = SettingsPage(self.settings)
        self.about = AboutPage()

        pages = {
            "dashboard": self.dashboard,
            "workspace": self.workspace,
            "library": self.library,
            "tools": self.tools,
            "community": self.community,
            "settings": self.settings_page,
            "about": self.about,
        }
        for page_id, page in pages.items():
            self.pages[page_id] = page
            self.stack.addWidget(page)
            self.add_tr_child(page)

        self.dashboard.quick_action.connect(self.handle_quick_action)
        self.workspace.status_message.connect(self.show_status)
        self.library.status_message.connect(self.show_status)
        self.library.open_in_editor.connect(self.open_library_script)
        self.library.login_required.connect(self.open_account)
        self.library.publish_provider = self.publish_current
        self.tools.status_message.connect(self.show_status)
        self.tools.analyze_requested.connect(
            lambda: self.workspace_do(self.workspace.analyze_current)
        )
        self.settings_page.language_changed.connect(self.on_language_changed)
        self.settings_page.preferences_changed.connect(
            self.workspace.apply_preferences
        )

    # -- navigation and actions

    def show_page(self, page_id):
        page = self.pages.get(page_id)
        if page is None:
            return
        self.stack.setCurrentWidget(page)

        for pid, button in self.nav_buttons.items():
            button.setProperty("active", pid == page_id)
            button.style().unpolish(button)
            button.style().polish(button)

        if page_id == "library":
            self.library.ensure_loaded()
        elif page_id == "community" and page_id not in self._visited:
            self.community.refresh()
        elif page_id == "tools":
            self.tools.refresh_environment()
        self._visited.add(page_id)

    def handle_quick_action(self, action_id):
        if action_id == "workspace":
            self.show_page("workspace")
            return
        action = self.actions_by_id.get(action_id)
        if action is not None:
            action.trigger()

    def show_status(self, text):
        self.status.showMessage(text, 8000)

    def refresh_library(self):
        self.show_page("library")
        self.library.refresh(True)

    def open_library_script(self, title, content):
        self.show_page("workspace")
        self.workspace.open_text(title, content)
        self.show_status(trf("Opened from the library: {0}", title))

    def publish_current(self):
        self.library.open_publish_dialog(
            self.workspace.current_title(), self.workspace.current_content()
        )

    def on_language_changed(self, code):
        log_event(f"Language changed to {code}")
        self.retranslate()
        self.show_status(tr("Ready."))

    # -- account

    def display_name(self):
        if not self.service.logged_in:
            return ""
        profile = self.profile or {}
        return str(
            profile.get("display_name") or profile.get("username")
            or getattr(self.service.user, "email", "") or ""
        )

    def update_account_button(self):
        if self.service.logged_in:
            pixmap = (
                circular_pixmap(self.avatar_pixmap, 22)
                if self.avatar_pixmap is not None
                else fallback_avatar_pixmap(22)
            )
            self.account_button.setText(self.display_name())
            self.connection_label.setText(
                trf("Signed in as {0}", self.display_name())
            )
        else:
            pixmap = fallback_avatar_pixmap(22)
            self.account_button.setText(tr("Sign in"))
            self.connection_label.setText(
                tr("Not signed in") if self.service.available
                else tr("Offline mode")
            )
        is_admin = (
            self.service.logged_in
            and (self.profile or {}).get("role") == "admin"
        )
        self.account_button.setStyleSheet(
            "color: #238b45; font-weight: bold;" if is_admin else ""
        )
        self.account_button.setIcon(QIcon(pixmap))

    def load_account(self):
        self.update_account_button()
        if not self.service.logged_in:
            self.profile = None
            self.avatar_pixmap = None
            return
        run_async(
            self.service.ensure_profile,
            self._profile_loaded,
            lambda e: log_event(f"Profile load failed: {e}")
        )

    def _profile_loaded(self, profile):
        self.profile = profile
        if self.service.last_warning:
            log_event(self.service.last_warning)
        self.update_account_button()

        url = (profile or {}).get("avatar_url")
        if url:
            run_async(
                fetch_url_bytes, self._avatar_loaded,
                lambda e: log_event(f"Avatar download failed: {e}"), url
            )

    def _avatar_loaded(self, data):
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self.avatar_pixmap = pixmap
            self.update_account_button()

    def open_account(self):
        if not self.service.available:
            QMessageBox.warning(
                self, tr("Account"), self.service.unavailable_message()
            )
            return

        if self.service.logged_in:
            dialog = ProfileDialog(
                self.service, self.profile, self.avatar_pixmap, self
            )
            dialog.exec()
            if dialog.signed_out:
                self._clear_account()
            elif dialog.changed:
                self.load_account()
        else:
            dialog = AuthDialog(self.service, self)
            if (dialog.exec() == QDialog.DialogCode.Accepted
                    and self.service.logged_in):
                self.load_account()
                self.show_status(tr("Signed in."))

    def sign_out(self):
        if not self.service.logged_in:
            self.show_status(tr("You are not signed in."))
            return
        run_async(
            self.service.sign_out,
            lambda _r: self._clear_account(),
            lambda _e: self._clear_account()
        )

    def _clear_account(self):
        self.profile = None
        self.avatar_pixmap = None
        self.update_account_button()
        self.show_status(tr("Signed out."))

    # -- closing

    def closeEvent(self, event):
        if not self.workspace.confirm_exit():
            event.ignore()
            return
        self.settings.save_window(self)
        self.settings.sync()
        event.accept()


# --------------------------------------------------------------------------
# Application bootstrap
# --------------------------------------------------------------------------

class SkriptDocxApplication:

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName(APP_NAME)
        self.app.setOrganizationName(APP_PUBLISHER)
        self.app.setStyleSheet(STYLE)

        self.settings = AppSettings()
        set_language(self.settings.language())
        self.service = SupabaseService()
        self.splash = None
        self.window = None

    def run(self):
        self.splash = SplashScreen()
        self.splash.show()

        QTimer.singleShot(8000, self.finish_startup)  # never hang on startup

        if self.service.available and keyring is not None:
            self.splash.set_status("Restoring session...")
            run_async(
                self.service.restore_session,
                self._session_done, self._session_done
            )
        else:
            QTimer.singleShot(900, self.finish_startup)

        return self.app.exec()

    def _session_done(self, _result=None):
        if self.window is None:
            self.finish_startup()
        else:
            self.window.load_account()  # the session arrived after the timeout

    def finish_startup(self):
        if self.window is not None:
            return
        self.window = MainWindow(self.service, self.settings)
        self.settings.restore_window(self.window)
        self.window.show()
        if self.splash is not None:
            self.splash.close()

if __name__ == "__main__":
    try:
        application = SkriptDocxApplication()
        sys.exit(application.run())
    except Exception as error:
        print(f"Startup error: {error}", file=sys.stderr)
        input("Press Enter to close...")
        raise
