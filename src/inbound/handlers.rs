//! Inbound webhook handlers — receive events from satellite apps via API key
//!
//! Satellite apps (FunnelSwift, IncentiveSwift, WorkflowSwift, MissedCall Respondr)
//! push data via these endpoints. Authentication is via key_prefix lookup.

use axum::{extract::{Path, State, Json}, http::StatusCode, response::IntoResponse};
use serde_json::{json, Value};
use uuid::Uuid;

use crate::AppState;
use crate::errors::{AppError, ApiResult};

/// POST /inbound/{key_prefix}/{event_type}
/// Receive an event from a satellite app using API key prefix auth
pub async fn receive(
    Path((key_prefix, event_type)): Path<(String, String)>,
    State(state): State<AppState>,
    Json(payload): Json<Value>,
) -> ApiResult<impl IntoResponse> {
    // Look up the API key by prefix
    let key = sqlx::query_as::<_, (Uuid, Uuid, String)>(
        r#"SELECT id, tenant_id, name FROM satellite_api_keys WHERE key_prefix = $1 AND is_active = true"#,
    )
    .bind(&key_prefix)
    .fetch_optional(&state.db)
    .await?
    .ok_or_else(|| AppError::NotFound("Invalid webhook key".into()))?;

    let (key_id, tenant_id, _key_name) = key;

    // Record inbound event
    let event_id = sqlx::query_scalar::<_, Uuid>(
        r#"INSERT INTO inbound_webhook_events (id, tenant_id, source_app, event_type, event_payload, api_key_id, status)
           VALUES ($1, $2, $3, $4, $5, $6, 'received')
           RETURNING id"#,
    )
    .bind(Uuid::new_v4())
    .bind(tenant_id)
    .bind(&_key_name)
    .bind(&event_type)
    .bind(&payload)
    .bind(key_id)
    .fetch_one(&state.db)
    .await?;

    Ok((StatusCode::OK, Json(json!({
        "status": "received",
        "event_id": event_id.to_string()
    }))))
}

/// POST /inbound/v2/{key_prefix}/{event_type}
/// Alias/version for receive — same handler
pub async fn receive_v2(
    Path((key_prefix, event_type)): Path<(String, String)>,
    State(state): State<AppState>,
    Json(payload): Json<Value>,
) -> ApiResult<impl IntoResponse> {
    receive(Path((key_prefix, event_type)), State(state), Json(payload)).await
}
