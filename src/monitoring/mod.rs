pub mod models;
pub mod handlers;
pub mod engine;

use axum::{Router, middleware};
use crate::AppState;

pub fn router(state: AppState) -> Router<AppState> {
    Router::new()
        .route("/health", axum::routing::get(handlers::get_health))
        .route("/health", axum::routing::post(handlers::update_health_signal))
        .route("/thresholds", axum::routing::get(handlers::list_thresholds))
        .route("/thresholds", axum::routing::post(handlers::create_threshold))
        .route("/thresholds/:id", axum::routing::patch(handlers::update_threshold))
        .route("/thresholds/:id", axum::routing::delete(handlers::delete_threshold))
        .layer(middleware::from_fn_with_state(state.clone(), crate::auth::middleware::auth_middleware))
}
