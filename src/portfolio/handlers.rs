//! Portfolio company handlers — CRUD for portfolio_companies
//!
//! Portfolio companies represent sub-companies under a tenant. They
//! are used for multi-entity CRM management, integration targets, etc.

use axum::{extract::{State, Path, Extension, Json}, http::StatusCode, response::IntoResponse};
use serde_json::json;
use uuid::Uuid;

use crate::AppState;
use crate::errors::{AppError, ApiResult};
use crate::auth::Claims;
use super::models::*;

/// GET /api/portfolio — list portfolio companies for the tenant
pub async fn list(
    State(s): State<AppState>,
    Extension(c): Extension<Claims>,
) -> ApiResult<impl IntoResponse> {
    let tenant_id = Uuid::parse_str(&c.tid).map_err(|_| AppError::Unauthorized)?;
    let companies = sqlx::query_as::<_, PortfolioCompany>(
        "SELECT id, tenant_id, name, slug, email, description, settings, is_active, created_at, updated_at FROM portfolio_companies WHERE tenant_id = $1 ORDER BY name"
    )
    .bind(tenant_id)
    .fetch_all(&s.db)
    .await?;
    Ok(Json(json!({"portfolio_companies": companies})))
}

/// POST /api/portfolio — create a portfolio company
pub async fn create(
    State(s): State<AppState>,
    Extension(c): Extension<Claims>,
    Json(req): Json<CreatePortfolioRequest>,
) -> ApiResult<impl IntoResponse> {
    let tenant_id = Uuid::parse_str(&c.tid).map_err(|_| AppError::Unauthorized)?;
    if req.name.is_empty() {
        return Err(AppError::Validation("Name is required".into()));
    }
    let slug = req.slug.clone().unwrap_or_else(|| req.name.to_lowercase().replace(' ', "-"));
    let id = Uuid::new_v4();
    let company = sqlx::query_as::<_, PortfolioCompany>(
        "INSERT INTO portfolio_companies (id, tenant_id, name, slug, settings) VALUES ($1, $2, $3, $4, $5) RETURNING *"
    )
    .bind(id)
    .bind(tenant_id)
    .bind(&req.name)
    .bind(&slug)
    .bind(&req.settings)
    .fetch_one(&s.db)
    .await?;
    Ok((StatusCode::CREATED, Json(json!(company))))
}

/// GET /api/portfolio/{id} — get a single portfolio company
pub async fn get(
    State(s): State<AppState>,
    Extension(c): Extension<Claims>,
    Path(id): Path<Uuid>,
) -> ApiResult<impl IntoResponse> {
    let tenant_id = Uuid::parse_str(&c.tid).map_err(|_| AppError::Unauthorized)?;
    let company = sqlx::query_as::<_, PortfolioCompany>(
        "SELECT id, tenant_id, name, slug, email, description, settings, is_active, created_at, updated_at FROM portfolio_companies WHERE id = $1 AND tenant_id = $2"
    )
    .bind(id)
    .bind(tenant_id)
    .fetch_optional(&s.db)
    .await?
    .ok_or(AppError::NotFound("Portfolio company not found".into()))?;
    Ok(Json(json!(company)))
}

/// PUT /api/portfolio/{id} — update a portfolio company
pub async fn update(
    State(s): State<AppState>,
    Extension(c): Extension<Claims>,
    Path(id): Path<Uuid>,
    Json(req): Json<UpdatePortfolioRequest>,
) -> ApiResult<impl IntoResponse> {
    let tenant_id = Uuid::parse_str(&c.tid).map_err(|_| AppError::Unauthorized)?;
    let company = sqlx::query_as::<_, PortfolioCompany>(
        "UPDATE portfolio_companies SET name = COALESCE($1, name), slug = COALESCE($2, slug), email = COALESCE($3, email), description = COALESCE($4, description), settings = COALESCE($5, settings), updated_at = NOW() WHERE id = $6 AND tenant_id = $7 RETURNING *"
    )
    .bind(&req.name)
    .bind(&req.slug)
    .bind(&req.email)
    .bind(&req.description)
    .bind(&req.settings)
    .bind(id)
    .bind(tenant_id)
    .fetch_optional(&s.db)
    .await?
    .ok_or(AppError::NotFound("Portfolio company not found".into()))?;
    Ok(Json(json!(company)))
}

/// DELETE /api/portfolio/{id} — delete a portfolio company
pub async fn delete(
    State(s): State<AppState>,
    Extension(c): Extension<Claims>,
    Path(id): Path<Uuid>,
) -> ApiResult<impl IntoResponse> {
    let tenant_id = Uuid::parse_str(&c.tid).map_err(|_| AppError::Unauthorized)?;
    let result = sqlx::query("DELETE FROM portfolio_companies WHERE id = $1 AND tenant_id = $2")
        .bind(id)
        .bind(tenant_id)
        .execute(&s.db)
        .await?;
    if result.rows_affected() == 0 {
        return Err(AppError::NotFound("Portfolio company not found".into()));
    }
    Ok(Json(json!({"message": "Deleted"})))
}

/// GET /api/portfolio/{id}/targets — list integration targets for a portfolio company
pub async fn list_targets(
    State(s): State<AppState>,
    Extension(c): Extension<Claims>,
    Path(id): Path<Uuid>,
) -> ApiResult<impl IntoResponse> {
    let tenant_id = Uuid::parse_str(&c.tid).map_err(|_| AppError::Unauthorized)?;
    let targets = sqlx::query_as::<_, IntegrationTarget>(
        "SELECT id, tenant_id, portfolio_company_id, user_id, name, provider, webhook_url, api_key, events, is_active, created_at, updated_at FROM integration_targets WHERE portfolio_company_id = $1 AND tenant_id = $2 ORDER BY name"
    )
    .bind(id)
    .bind(tenant_id)
    .fetch_all(&s.db)
    .await?;
    Ok(Json(json!({"integration_targets": targets})))
}

/// POST /api/portfolio/{id}/targets — create an integration target for a portfolio company
pub async fn create_target(
    State(s): State<AppState>,
    Extension(c): Extension<Claims>,
    Path(id): Path<Uuid>,
    Json(req): Json<CreateTargetRequest>,
) -> ApiResult<impl IntoResponse> {
    let tenant_id = Uuid::parse_str(&c.tid).map_err(|_| AppError::Unauthorized)?;
    if req.name.is_empty() || req.webhook_url.is_empty() {
        return Err(AppError::Validation("Name and webhook_url are required".into()));
    }
    let target = sqlx::query_as::<_, IntegrationTarget>(
        "INSERT INTO integration_targets (id, tenant_id, portfolio_company_id, name, provider, webhook_url, api_key, events) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *"
    )
    .bind(Uuid::new_v4())
    .bind(tenant_id)
    .bind(id)
    .bind(&req.name)
    .bind(&req.provider)
    .bind(&req.webhook_url)
    .bind(&req.api_key)
    .bind(&req.events)
    .fetch_one(&s.db)
    .await?;
    Ok((StatusCode::CREATED, Json(json!(target))))
}
