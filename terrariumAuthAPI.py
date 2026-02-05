# -*- coding: utf-8 -*-
"""
TerrariumPI Login API Routes
Provides REST endpoints for user authentication including password login and 2FA.
"""

import terrariumLogging

logger = terrariumLogging.logging.getLogger(__name__)

import json
from bottle import request, response

class terrariumAuthAPI:
    """
    REST API endpoints for authentication.
    Routes:
    - POST /api/login - Authenticate with username/password
    - POST /api/login/2fa - Verify 2FA code
    - POST /api/logout - Invalidate session
    - GET /api/auth/2fa/setup - Get 2FA setup QR code
    """

    def __init__(self, webserver):
        """
        Initialize authentication API.

        Args:
            webserver: terrariumWebserver instance
        """
        self.webserver = webserver
        self.engine = webserver.engine
        self.auth = self.engine.auth
        # List of IP addresses of trusted reverse proxies.
        # Only when the immediate peer (request.remote_addr) is in this list
        # will X-Real-Ip / X-Forwarded-For headers be honored.
        # If webserver exposes such a configuration, use it; otherwise default to empty.
        self.trusted_proxies = getattr(webserver, "trusted_proxies", []) or []

    def __get_client_ip(self):
        """
        Get client IP address, safely handling reverse proxy headers.

        Returns:
            str: Client IP address
        """
        remote_addr = request.remote_addr

        # By default, trust only the direct peer's IP address. Only honor
        # X-Real-Ip / X-Forwarded-For when the immediate peer is a trusted proxy.
        if remote_addr not in self.trusted_proxies:
            return remote_addr

        # request.remote_addr is a trusted proxy; respect proxy headers.
        real_ip = request.headers.get("X-Real-Ip")
        if real_ip:
            return real_ip

        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP in case of multiple proxies
            return forwarded_for.split(",")[0].strip()

        return remote_addr
    def login(self):
        """
        POST /api/login
        Authenticate user with username and password.

        Request body:
        {
            "username": "admin",
            "password": "your_password"
        }

        Response:
        {
            "success": true/false,
            "message": "string",
            "session_token": "string (if success)",
            "requires_2fa": true/false (if 2FA needed),
            "error": "string (if error)"
        }
        """
        try:
            data = request.json
            username = data.get("username", "").strip()
            password = data.get("password", "")

            if not username or not password:
                response.status = 400
                return {
                    "success": False,
                    "error": "Username and password are required"
                }

            # Get client IP for rate limiting
            client_ip = self.__get_client_ip()

            # Attempt authentication
            result = self.auth.authenticate(username, password, client_ip)

            if result.get("success"):
                response.status = 200
                # Set secure session cookie
                if result.get("session_token"):
                    response.set_cookie(
                        "session_token",
                        result["session_token"],
                        max_age=3600,  # 1 hour
                        path="/",
                        httponly=True,  # Prevent JavaScript access
                        secure=True,  # HTTPS only
                        samesite="Strict"  # CSRF protection
                    )

                logger.info(f"Successful login for user '{username}' from IP {client_ip}")
                return {
                    "success": True,
                    "message": result.get("message", "Login successful"),
                    "session_token": result.get("session_token"),
                    "requires_2fa": result.get("requires_2fa", False),
                    "preauth_token": result.get("preauth_token")  # Include pre-auth token for 2FA
                }
            else:
                response.status = 401
                logger.warning(f"Failed login attempt for user '{username}' from IP {client_ip}")
                return {
                    "success": False,
                    "error": result.get("error", "Authentication failed")
                }

        except json.JSONDecodeError:
            response.status = 400
            return {
                "success": False,
                "error": "Invalid JSON in request body"
            }
        except Exception as e:
            logger.error(f"Error during login: {e}", exc_info=True)
            response.status = 500
            return {
                "success": False,
                "error": "Internal server error"
            }

    def login_2fa(self):
        """
        POST /api/login/2fa
        Verify 2FA code after successful password authentication.

        Request body:
        {
            "username": "admin",
            "totp_code": "123456",
            "preauth_token": "token_from_login_response"
        }

        Response:
        {
            "success": true/false,
            "message": "string",
            "session_token": "string (if success)",
            "error": "string (if error)"
        }
        """
        try:
            data = request.json
            username = data.get("username", "").strip()
            totp_code = data.get("totp_code", "").strip()
            preauth_token = data.get("preauth_token", "").strip()

            if not username or not totp_code:
                response.status = 400
                return {
                    "success": False,
                    "error": "Username and TOTP code are required"
                }

            if not preauth_token:
                response.status = 400
                return {
                    "success": False,
                    "error": "Pre-auth token is required. Please login again."
                }

            if len(totp_code) != 6 or not totp_code.isdigit():
                response.status = 400
                return {
                    "success": False,
                    "error": "TOTP code must be 6 digits"
                }

            # Get client IP
            client_ip = self.__get_client_ip()

            # Verify 2FA with pre-auth token
            result = self.auth.complete_2fa_authentication(username, totp_code, client_ip, preauth_token)

            if result.get("success"):
                response.status = 200
                # Set secure session cookie
                response.set_cookie(
                    "session_token",
                    result["session_token"],
                    max_age=3600,  # 1 hour
                    path="/",
                    httponly=True,
                    secure=True,
                    samesite="Strict"
                )

                logger.info(f"2FA verification successful for user '{username}' from IP {client_ip}")
                return {
                    "success": True,
                    "message": "2FA verification successful",
                    "session_token": result["session_token"]
                }
            else:
                response.status = 401
                logger.warning(f"Failed 2FA attempt for user '{username}' from IP {client_ip}")
                return {
                    "success": False,
                    "error": result.get("error", "2FA verification failed")
                }

        except json.JSONDecodeError:
            response.status = 400
            return {
                "success": False,
                "error": "Invalid JSON in request body"
            }
        except Exception as e:
            logger.error(f"Error during 2FA verification: {e}", exc_info=True)
            response.status = 500
            return {
                "success": False,
                "error": "Internal server error"
            }

    def logout(self):
        """
        POST /api/logout
        Invalidate current session.

        Response:
        {
            "success": true/false,
            "message": "string"
        }
        """
        try:
            session_token = request.get_cookie("session_token")

            if session_token:
                self.auth.invalidate_session(session_token)
                response.delete_cookie("session_token", path="/")
                logger.info("User logged out successfully")

            response.status = 200
            return {
                "success": True,
                "message": "Logged out successfully"
            }

        except Exception as e:
            logger.error(f"Error during logout: {e}", exc_info=True)
            response.status = 500
            return {
                "success": False,
                "error": "Internal server error"
            }

    def setup_2fa(self):
        """
        GET /api/auth/2fa/setup
        Get 2FA setup information including QR code.

        Requires authentication.

        Response:
        {
            "success": true/false,
            "secret": "string",
            "qr_code": "base64_encoded_image",
            "provisioning_uri": "otpauth://...",
            "error": "string (if error)"
        }
        """
        try:
            # Get authenticated user from session
            session_token = request.get_cookie("session_token")
            if not session_token:
                response.status = 401
                return {
                    "success": False,
                    "error": "Authentication required"
                }

            client_ip = self.__get_client_ip()
            session = self.auth.verify_session(session_token, client_ip)

            if not session:
                response.status = 401
                return {
                    "success": False,
                    "error": "Invalid or expired session"
                }

            username = session.get("username")

            # Generate 2FA setup
            setup_info = self.auth.setup_2fa_for_user(username)

            if "error" in setup_info:
                response.status = 500
                return setup_info

            response.status = 200
            logger.info(f"2FA setup initiated for user '{username}'")
            return {
                "success": True,
                "secret": setup_info["secret"],
                "qr_code": setup_info["qr_code"],
                "provisioning_uri": setup_info["provisioning_uri"]
            }

        except Exception as e:
            logger.error(f"Error during 2FA setup: {e}", exc_info=True)
            response.status = 500
            return {
                "success": False,
                "error": "Internal server error"
            }

    def verify_session(self):
        """
        GET /api/auth/verify
        Verify current session is valid.

        Response:
        {
            "authenticated": true/false,
            "username": "string (if authenticated)",
            "message": "string"
        }
        """
        try:
            session_token = request.get_cookie("session_token")
            if not session_token:
                response.status = 401
                return {
                    "authenticated": False,
                    "message": "No active session"
                }

            client_ip = self.__get_client_ip()
            session = self.auth.verify_session(session_token, client_ip)

            if session:
                response.status = 200
                return {
                    "authenticated": True,
                    "username": session.get("username"),
                    "message": "Session valid"
                }
            else:
                response.status = 401
                return {
                    "authenticated": False,
                    "message": "Invalid or expired session"
                }

        except Exception as e:
            logger.error(f"Error verifying session: {e}", exc_info=True)
            response.status = 500
            return {
                "authenticated": False,
                "error": "Internal server error"
            }
