//! Chat Action Endpoint — run the entire business from a Telegram conversation
//!
//! POST /api/admin/chat-action
//! Body: { "intent": "...", "params": { ... } }
//!
//! This is the programmatic version of what I do when David messages me.
//! OpenClaw / n8n / CheatLayer can call this to drive multi-step flows
//! across all apps without chaining multiple webhook calls.

pub mod handlers;

use axum::{Router, middleware};
use crate::AppState;

pub fn router(state: AppState) -> Router<AppState> {
    Router::new()
        .route("/chat-action", axum::routing::post(handlers::execute_chat_action))
        .route("/chat-action/intents", axum::routing::get(handlers::list_intents))
        .layer(middleware::from_fn_with_state(state.clone(), crate::auth::middleware::auth_middleware))
}
