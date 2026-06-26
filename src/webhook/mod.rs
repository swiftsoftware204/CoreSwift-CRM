//! Public Automation Webhook — single endpoint for OpenClaw, n8n, CheatLayer
//!
//! Every tenant gets an auto-generated webhook token on signup.
//! External automation tools call this endpoint with the token in the URL
//! and a JSON body specifying which action to perform.
//!
//! POST /api/webhook/{token}/{action}
//! Body: { ...action-specific params... }
//!
//! This is the universal entry point so OpenClaw, n8n, and CheatLayer
//! only need to know one URL + one token to access the entire CRM Swift API.

pub mod handlers;
pub mod models;
pub mod actions;

use axum::Router;
use crate::AppState;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/{token}/{action}", axum::routing::post(handlers::handle_webhook))
}
