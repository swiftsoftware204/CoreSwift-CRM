pub mod models;
pub mod handlers;
pub mod engine;
pub mod actions;

use axum::{Router, middleware};
use crate::AppState;

pub fn router(state: AppState) -> Router<AppState> {
    Router::new()
        .route("/rules", axum::routing::get(handlers::list_rules))
        .route("/rules", axum::routing::post(handlers::create_rule))
        .route("/rules/:id", axum::routing::get(handlers::get_rule))
        .route("/rules/:id", axum::routing::patch(handlers::update_rule))
        .route("/rules/:id", axum::routing::delete(handlers::delete_rule))
        .layer(middleware::from_fn_with_state(state.clone(), crate::auth::middleware::auth_middleware))
}
