pub mod handlers;

use axum::{Router, middleware};
use crate::AppState;

pub fn router(state: AppState) -> Router<AppState> {
    Router::new()
        .route("/", axum::routing::get(handlers::list))
        .route("/{id}/read", axum::routing::post(handlers::mark_read))
        .route("/read-all", axum::routing::post(handlers::mark_all_read))
        .route("/unread-count", axum::routing::get(handlers::unread_count))
        .layer(middleware::from_fn_with_state(state.clone(), crate::auth::middleware::auth_middleware))
}
