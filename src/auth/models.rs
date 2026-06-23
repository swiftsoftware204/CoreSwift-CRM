//! Auth models: User, Claims, TokenResponse, and request/response types.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// JWT claims struct stored in access/refresh tokens.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    /// User ID (subject)
    pub sub: String,
    /// Tenant ID
    pub tid: String,
    /// Role within their tenant: owner | admin | member
    pub role: String,
    /// Expiration timestamp (UTC epoch seconds)
    pub exp: usize,
    /// Issued at timestamp (UTC epoch seconds)
    pub iat: usize,
}

/// User model — database row.
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct User {
    pub id: Uuid,
    pub tenant_id: Uuid,
    pub email: String,
    pub password_hash: String,
    pub name: String,
    pub role: String,
    pub is_active: bool,
    pub last_login_at: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

/// User response sent to clients (excludes password_hash).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserResponse {
    pub id: Uuid,
    pub tenant_id: Uuid,
    pub email: String,
    pub name: String,
    pub role: String,
    pub is_active: bool,
    pub last_login_at: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
}

impl From<User> for UserResponse {
    fn from(u: User) -> Self {
        Self {
            id: u.id,
            tenant_id: u.tenant_id,
            email: u.email,
            name: u.name,
            role: u.role,
            is_active: u.is_active,
            last_login_at: u.last_login_at,
            created_at: u.created_at,
        }
    }
}

/// Token response sent after login/register.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TokenResponse {
    pub access_token: String,
    pub refresh_token: String,
    pub token_type: String,
    pub expires_in: i64,
    pub user: UserResponse,
}

/// Register request body.
///
/// Every person who signs up gets their own account (separate tenant).
/// Admins and tenants are both account holders — no difference in architecture.
/// Pass tenant_name and tenant_slug to customize the tenant name,
/// or pass invite_token to join an existing tenant via invite.
#[derive(Debug, Deserialize)]
pub struct RegisterRequest {
    pub name: String,
    pub email: String,
    pub password: String,
    pub tenant_name: Option<String>,
    pub tenant_slug: Option<String>,
    pub invite_token: Option<String>,
}

/// Register response with tenant info included.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegisterResponse {
    pub access_token: String,
    pub refresh_token: String,
    pub token_type: String,
    pub expires_in: i64,
    pub user: UserResponse,
    pub tenant: TenantResponse,
    pub next_steps: Vec<String>,
}

/// Tenant info for response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TenantResponse {
    pub id: Uuid,
    pub name: String,
    pub slug: String,
    pub is_active: bool,
}

/// Login request body.
#[derive(Debug, Deserialize)]
pub struct LoginRequest {
    pub email: String,
    pub password: String,
}

/// Refresh token request body.
#[derive(Debug, Deserialize)]
pub struct RefreshRequest {
    pub refresh_token: String,
}

/// Tenant model reference for auth handlers.
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct Tenant {
    pub id: Uuid,
    pub name: String,
    pub slug: String,
    pub is_active: bool,
}

/// Create invite request.
#[derive(Debug, Deserialize)]
pub struct CreateInviteRequest {
    pub role: String,  // "admin" | "member"
}

/// Helper to extract claims from an Authorization header in a handler
/// that doesn't use the extension extractor (e.g. /me, /logout).
pub fn extract_claims_from_request(request: &axum::extract::Request, secret: &str) -> Result<Claims, crate::errors::AppError> {
    let auth_header = request
        .headers()
        .get("Authorization")
        .and_then(|v| v.to_str().ok())
        .ok_or(crate::errors::AppError::Unauthorized)?;

    let token = auth_header
        .strip_prefix("Bearer ")
        .ok_or(crate::errors::AppError::Unauthorized)?;

    use crate::auth::middleware;
    middleware::verify_token(token, secret)
}
