//! Onboarding checklists module.
//!
//! Staged checklist templates and per-entity progress tracking.
//! Checklists are triggered by events (signup, payment, contact creation)
//! and walk users through onboarding steps with delayed follow-ups.

pub mod models;
pub mod handlers;
pub mod engine;

use axum::{Router, middleware};
use crate::AppState;

/// Build the checklists router with auth middleware.
pub fn router(state: AppState) -> Router<AppState> {
    Router::new()
        .route("/templates", axum::routing::get(handlers::list_templates))
        .route("/templates", axum::routing::post(handlers::create_template))
        .route("/templates/{id}", axum::routing::get(handlers::get_template))
        .route("/templates/{id}", axum::routing::patch(handlers::update_template))
        .route("/templates/{id}", axum::routing::delete(handlers::delete_template))
        .route("/instances", axum::routing::get(handlers::list_instances))
        .route("/instances/start/{entity_type}/{entity_id}", axum::routing::post(handlers::start_checklist))
        .route("/instances/{id}/progress", axum::routing::patch(handlers::update_progress))
        .route("/instances/{id}", axum::routing::get(handlers::get_instance))
        .layer(middleware::from_fn_with_state(state.clone(), crate::auth::middleware::auth_middleware))
}
