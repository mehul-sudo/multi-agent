# Phase 4 Auth Guide

## Endpoints

POST /api/auth/login - authenticate
POST /api/auth/refresh - refresh access token
POST /api/auth/logout - revoke token
GET  /api/auth/me - user profile
POST /api/auth/change-password - change password

## Env Vars

JWT_SECRET_KEY (required in production)
JWT_ACCESS_TOKEN_EXPIRES_MINUTES (default 15)
JWT_REFRESH_TOKEN_EXPIRES_DAYS (default 30)

## See README.md for full documentation.
