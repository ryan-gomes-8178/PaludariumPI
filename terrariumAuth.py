# -*- coding: utf-8 -*-
"""
TerrariumPI Authentication Module
Provides secure authentication with password hashing and 2FA support (TOTP).
This module handles user authentication for secure public access.
"""

import terrariumLogging

logger = terrariumLogging.logging.getLogger(__name__)

import time
import secrets
import qrcode
from io import BytesIO
import base64
from datetime import datetime, timedelta

try:
    import pyotp
except ImportError:
    logger.warning("pyotp not installed. 2FA features will be disabled.")
    pyotp = None

from terrariumUtils import terrariumUtils


class terrariumAuth:
    """
    Handles authentication including:
    - Password-based login
    - Session management
    - TOTP-based 2FA
    - Login attempt tracking
    - Device fingerprinting
    """

    # Rate limiting: max 5 failed attempts in 15 minutes
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = 900  # 15 minutes in seconds
    SESSION_TIMEOUT = 3600  # 1 hour
    PREAUTH_TIMEOUT = 300  # 5 minutes for pre-auth context

    def __init__(self, engine):
        """
        Initialize authentication module.

        Args:
            engine: TerrariumEngine instance
        """
        self.engine = engine
        # Store active sessions {session_id: {user, timestamp, device_fingerprint}}
        # NOTE: Sessions are stored in-memory only. When the application restarts,
        # all active sessions will be lost and users will need to re-authenticate.
        # For persistent sessions across restarts, consider storing them in the database.
        self.sessions = {}
        self.failed_attempts = {}  # Track failed login attempts {ip: {attempts, timestamp}}
        self.preauth_contexts = {}  # Track pre-auth contexts {token: {username, ip, timestamp, attempts}}
        self.cleanup_task = None

    def setup_2fa_for_user(self, username):
        """
        Generate 2FA secret for a user and return setup QR code.

        Args:
            username (str): Username to enable 2FA for

        Returns:
            dict: Contains 'secret' and 'qr_code' (base64 encoded image)
        """
        if not pyotp:
            logger.warning("pyotp not installed. 2FA setup not available.")
            return {"error": "2FA not available"}

        # Generate a secret key
        secret = pyotp.random_base32()

        # Create provisioning URI for QR code
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=username,
            issuer_name='TerrariumPI'
        )

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()

        # Persist the 2FA secret and enabled flag in engine settings and, if possible, to the database
        try:
            # Always keep the in-memory settings up to date for immediate use
            if hasattr(self.engine, "settings") and isinstance(self.engine.settings, dict):
                self.engine.settings["two_fa_secret"] = secret
                self.engine.settings["two_fa_enabled"] = True

            # Attempt to persist settings using common engine helpers, if available
            persist_ok = False
            for method_name in ("save_setting", "update_setting", "setting_update"):
                method = getattr(self.engine, method_name, None)
                if not callable(method):
                    continue
                # Prefer simple (key, value) signatures; ignore incompatible ones
                try:
                    method("two_fa_secret", secret)
                    method("two_fa_enabled", True)
                    persist_ok = True
                    break
                except TypeError:
                    # Signature mismatch; try the next candidate helper
                    continue
                except Exception as e:
                    logger.warning(f"Error while persisting 2FA settings via '{method_name}': {e}")
                    break

            # Reload settings from the backing store so in-memory settings match the database
            if persist_ok and hasattr(self.engine, "load_settings") and callable(self.engine.load_settings):
                try:
                    self.engine.load_settings()
                except Exception as e:
                    logger.warning(f"Failed to reload settings after persisting 2FA configuration: {e}")

        except Exception as e:
            logger.warning(f"Failed to persist 2FA settings: {e}")

        return {
            "secret": secret,
            "qr_code": f"data:image/png;base64,{qr_code_base64}",
            "provisioning_uri": provisioning_uri,
            "two_fa_enabled": True
        }

    def verify_totp_token(self, token):
        """
        Verify TOTP token.
        
        Note: TerrariumPI currently supports single-user authentication,
        so the 2FA secret is stored globally in self.engine.settings['two_fa_secret'].

        Args:
            token (str): 6-digit TOTP token

        Returns:
            bool: True if token is valid
        """
        if not pyotp:
            return False

        # Get user's 2FA secret from settings
        two_fa_secret = self.engine.settings.get("two_fa_secret", None)
        if not two_fa_secret:
            return False

        totp = pyotp.TOTP(two_fa_secret)

        # Allow for time drift (±1 window)
        try:
            return totp.verify(token, valid_window=1)
        except Exception as e:
            logger.warning(f"TOTP verification error: {e}")
            return False

    def check_rate_limit(self, ip_address):
        """
        Check if IP address is rate-limited due to failed login attempts.

        Args:
            ip_address (str): IP address to check

        Returns:
            tuple: (is_limited, remaining_wait_seconds)
        """
        now = time.time()

        if ip_address not in self.failed_attempts:
            return False, 0

        attempt_data = self.failed_attempts[ip_address]

        # Check if lockout period has expired
        if now - attempt_data["timestamp"] > self.LOCKOUT_DURATION:
            del self.failed_attempts[ip_address]
            return False, 0

        # Check if max attempts exceeded
        if attempt_data["attempts"] >= self.MAX_LOGIN_ATTEMPTS:
            remaining = self.LOCKOUT_DURATION - (now - attempt_data["timestamp"])
            return True, int(remaining)

        return False, 0

    def record_failed_attempt(self, ip_address):
        """
        Record a failed login attempt for rate limiting.

        Args:
            ip_address (str): IP address of failed attempt
        """
        now = time.time()

        if ip_address not in self.failed_attempts:
            self.failed_attempts[ip_address] = {"attempts": 1, "timestamp": now}
        else:
            # Reset counter if lockout period expired
            if now - self.failed_attempts[ip_address]["timestamp"] > self.LOCKOUT_DURATION:
                self.failed_attempts[ip_address] = {"attempts": 1, "timestamp": now}
            else:
                self.failed_attempts[ip_address]["attempts"] += 1

    def reset_failed_attempts(self, ip_address):
        """
        Clear failed login attempts for an IP address after successful login.

        Args:
            ip_address (str): IP address to clear
        """
        if ip_address in self.failed_attempts:
            del self.failed_attempts[ip_address]

    def create_preauth_context(self, username, ip_address):
        """
        Create a pre-auth context after successful password verification.
        This context is required to complete 2FA authentication.

        Args:
            username (str): Authenticated username
            ip_address (str): Client IP address

        Returns:
            str: Pre-auth token
        """
        preauth_token = secrets.token_urlsafe(32)
        self.preauth_contexts[preauth_token] = {
            "username": username,
            "ip_address": ip_address,
            "timestamp": time.time(),
            "attempts": 0
        }
        logger.info(f"Pre-auth context created for user '{username}' from IP {ip_address}")
        return preauth_token

    def verify_preauth_context(self, preauth_token, ip_address):
        """
        Verify a pre-auth context is valid and hasn't expired.

        Args:
            preauth_token (str): Pre-auth token
            ip_address (str): Client IP address

        Returns:
            dict: Pre-auth context if valid, None otherwise
        """
        if preauth_token not in self.preauth_contexts:
            logger.warning(f"Invalid pre-auth token from IP {ip_address}")
            return None

        context = self.preauth_contexts[preauth_token]

        # Check if expired
        if time.time() - context["timestamp"] > self.PREAUTH_TIMEOUT:
            del self.preauth_contexts[preauth_token]
            logger.warning(f"Expired pre-auth token for user '{context['username']}' from IP {ip_address}")
            return None

        # Verify IP address matches
        if context["ip_address"] != ip_address:
            logger.warning(f"Pre-auth IP mismatch for token. Expected {context['ip_address']}, got {ip_address}")
            return None

        return context

    def record_2fa_failure(self, preauth_token):
        """
        Record a failed 2FA attempt for rate limiting.

        Args:
            preauth_token (str): Pre-auth token
        """
        if preauth_token in self.preauth_contexts:
            self.preauth_contexts[preauth_token]["attempts"] += 1
            logger.warning(f"2FA failure recorded for token (attempt {self.preauth_contexts[preauth_token]['attempts']})")

    def check_2fa_rate_limit(self, preauth_token):
        """
        Check if 2FA attempts are rate-limited.

        Args:
            preauth_token (str): Pre-auth token

        Returns:
            bool: True if rate limited
        """
        if preauth_token not in self.preauth_contexts:
            return False

        context = self.preauth_contexts[preauth_token]
        if context["attempts"] >= self.MAX_LOGIN_ATTEMPTS:
            logger.warning(f"2FA rate limit exceeded for user '{context['username']}'")
            return True

        return False

    def invalidate_preauth_context(self, preauth_token):
        """
        Invalidate a pre-auth context after successful 2FA or on error.

        Args:
            preauth_token (str): Pre-auth token to invalidate
        """
        if preauth_token in self.preauth_contexts:
            username = self.preauth_contexts[preauth_token].get("username", "unknown")
            del self.preauth_contexts[preauth_token]
            logger.info(f"Pre-auth context invalidated for user '{username}'")

    def create_session(self, username, ip_address, device_fingerprint=None):
        """
        Create a new authenticated session.

        Args:
            username (str): Authenticated username
            ip_address (str): Client IP address
            device_fingerprint (str): Optional device identifier

        Returns:
            str: Session token
        """
        session_token = secrets.token_urlsafe(32)
        self.sessions[session_token] = {
            "username": username,
            "ip_address": ip_address,
            "device_fingerprint": device_fingerprint,
            "created": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "two_fa_verified": False
        }

        logger.info(f"Session created for user '{username}' from IP {ip_address}")
        return session_token

    def verify_session(self, session_token, ip_address=None):
        """
        Verify if a session token is valid and active.

        Args:
            session_token (str): Session token to verify
            ip_address (str): Optional IP address to verify against

        Returns:
            dict: Session data if valid, None otherwise
        """
        if session_token not in self.sessions:
            return None

        session = self.sessions[session_token]

        # Check session timeout
        last_activity = session.get("last_activity")
        if isinstance(last_activity, str):
            last_activity = datetime.fromisoformat(last_activity)

        if datetime.utcnow() - last_activity > timedelta(seconds=self.SESSION_TIMEOUT):
            del self.sessions[session_token]
            logger.info(f"Session expired for user '{session['username']}'")
            return None

        # Verify IP address if provided (prevent session hijacking)
        if ip_address and session.get("ip_address") != ip_address:
            logger.warning(f"Session IP mismatch for token {session_token[:8]}... expected {session['ip_address']}, got {ip_address}")
            return None

        # Update last activity
        session["last_activity"] = datetime.utcnow()
        return session

    def invalidate_session(self, session_token):
        """
        Invalidate/logout a session.

        Args:
            session_token (str): Session token to invalidate
        """
        if session_token in self.sessions:
            username = self.sessions[session_token].get("username", "unknown")
            del self.sessions[session_token]
            logger.info(f"Session invalidated for user '{username}'")

    def authenticate(self, username, password, ip_address):
        """
        Authenticate user with username and password.

        Args:
            username (str): Username
            password (str): Password (plain text)
            ip_address (str): Client IP address for rate limiting

        Returns:
            dict: {
                'success': bool,
                'message': str,
                'requires_2fa': bool (if password is correct but 2FA is required),
                'session_token': str (on success),
                'error': str (on failure)
            }
        """
        # Check rate limiting
        is_limited, wait_time = self.check_rate_limit(ip_address)
        if is_limited:
            logger.warning(f"Rate limit exceeded for IP {ip_address}. Wait {wait_time} seconds.")
            return {
                "success": False,
                "error": f"Too many failed attempts. Please try again in {wait_time} seconds."
            }

        # Verify username and password
        db_username = self.engine.settings.get("username")
        db_password_hash = self.engine.settings.get("password")

        # Use constant-time comparison for username and always perform password check
        username_matches = secrets.compare_digest(
            username if username is not None else "",
            db_username if db_username is not None else "",
        )
        password_valid = terrariumUtils.check_password(password, db_password_hash)

        if not username_matches or not password_valid:
            self.record_failed_attempt(ip_address)
            logger.warning(f"Failed login attempt for user '{username}' from IP {ip_address}")
            return {
                "success": False,
                "error": "Invalid username or password"
            }

        # Check if 2FA is required
        two_fa_enabled = self.engine.settings.get("two_fa_enabled", False)
        if terrariumUtils.is_true(two_fa_enabled):
            logger.info(f"2FA required for user '{username}'")
            # Create pre-auth context for 2FA verification
            preauth_token = self.create_preauth_context(username, ip_address)
            return {
                "success": True,
                "requires_2fa": True,
                "preauth_token": preauth_token,
                "message": "2FA code required"
            }

        # Clear failed attempts and create session
        self.reset_failed_attempts(ip_address)
        session_token = self.create_session(username, ip_address)

        return {
            "success": True,
            "session_token": session_token,
            "message": f"Successfully authenticated as '{username}'"
        }

    def complete_2fa_authentication(self, username, token, ip_address, preauth_token):
        """
        Complete authentication by verifying 2FA token.
        Requires a valid pre-auth context from successful password authentication.

        Args:
            username (str): Username
            token (str): 6-digit TOTP token
            ip_address (str): Client IP address
            preauth_token (str): Pre-auth token from password authentication

        Returns:
            dict: {
                'success': bool,
                'session_token': str (on success),
                'error': str (on failure)
            }
        """
        # Verify pre-auth context exists and is valid
        context = self.verify_preauth_context(preauth_token, ip_address)
        if not context:
            logger.warning(f"Invalid or expired pre-auth context for 2FA attempt from IP {ip_address}")
            return {
                "success": False,
                "error": "Invalid or expired authentication session. Please login again."
            }

        # Verify username matches pre-auth context
        if context["username"] != username:
            logger.warning(f"Username mismatch in 2FA: expected '{context['username']}', got '{username}'")
            self.invalidate_preauth_context(preauth_token)
            return {
                "success": False,
                "error": "Authentication error. Please login again."
            }

        # Check 2FA rate limiting
        if self.check_2fa_rate_limit(preauth_token):
            self.invalidate_preauth_context(preauth_token)
            return {
                "success": False,
                "error": "Too many failed 2FA attempts. Please login again."
            }

        # Verify TOTP token
        if not self.verify_totp_token(token):
            self.record_2fa_failure(preauth_token)
            logger.warning(f"Invalid 2FA token for user '{username}' from IP {ip_address} (attempt {context['attempts'] + 1})")
            return {
                "success": False,
                "error": "Invalid 2FA code"
            }

        # Success: invalidate pre-auth context and create session
        self.invalidate_preauth_context(preauth_token)
        self.reset_failed_attempts(ip_address)
        session_token = self.create_session(username, ip_address)
        session = self.sessions[session_token]
        session["two_fa_verified"] = True

        logger.info(f"2FA verification successful for user '{username}'")
        return {
            "success": True,
            "session_token": session_token,
            "message": "2FA authentication successful"
        }

    def cleanup_expired_sessions(self):
        """
        Clean up expired sessions and pre-auth contexts periodically.
        Should be called by the main engine's cleanup task.
        """
        now = datetime.utcnow()
        expired_tokens = []

        for token, session in self.sessions.items():
            last_activity = session.get("last_activity")
            if isinstance(last_activity, str):
                last_activity = datetime.fromisoformat(last_activity)

            if now - last_activity > timedelta(seconds=self.SESSION_TIMEOUT):
                expired_tokens.append(token)

        for token in expired_tokens:
            username = self.sessions[token].get("username", "unknown")
            del self.sessions[token]
            logger.debug(f"Cleaned up expired session for user '{username}'")

        if expired_tokens:
            logger.debug(f"Cleaned up {len(expired_tokens)} expired sessions")

        # Clean up expired pre-auth contexts
        now_timestamp = time.time()
        expired_preauth = []

        for token, context in list(self.preauth_contexts.items()):
            if now_timestamp - context["timestamp"] > self.PREAUTH_TIMEOUT:
                expired_preauth.append(token)

        for token in expired_preauth:
            if token in self.preauth_contexts:
                username = self.preauth_contexts[token].get("username", "unknown")
                del self.preauth_contexts[token]
                logger.debug(f"Cleaned up expired pre-auth context for user '{username}'")

        if expired_preauth:
            logger.debug(f"Cleaned up {len(expired_preauth)} expired pre-auth contexts")
