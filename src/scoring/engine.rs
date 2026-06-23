use sqlx::PgPool;
use uuid::Uuid;
use super::models::{Score, ScoreRule, score_category};

/// Calculate score for a contact based on an event type.
/// Applies all matching active rules and records history.
pub async fn calculate_score(db: &PgPool, tenant_id: Uuid, contact_id: Uuid, event_type: &str) -> Result<Score, crate::errors::AppError> {
    let rules = sqlx::query_as::<_, ScoreRule>(
        "SELECT * FROM score_rules WHERE tenant_id=$1 AND event_type=$2 AND is_active=true"
    )
    .bind(tenant_id)
    .bind(event_type)
    .fetch_all(db)
    .await?;

    let mut score = sqlx::query_as::<_, Score>(
        "SELECT * FROM scores WHERE tenant_id=$1 AND contact_id=$2"
    )
    .bind(tenant_id)
    .bind(contact_id)
    .fetch_optional(db)
    .await?;

    let score_id = if let Some(ref s) = score {
        s.id
    } else {
        let ns = sqlx::query_as::<_, Score>(
            "INSERT INTO scores(id,tenant_id,contact_id,total_score,category) VALUES($1,$2,$3,0,'cold') RETURNING *"
        )
        .bind(Uuid::new_v4())
        .bind(tenant_id)
        .bind(contact_id)
        .fetch_one(db)
        .await?;
        score = Some(ns.clone());
        ns.id
    };

    let current_score = score.as_ref().map(|s| s.total_score).unwrap_or(0);
    let mut total_points = 0i32;

    for rule in &rules {
        let pts = if rule.direction == "subtract" { -rule.points } else { rule.points };
        total_points += pts;
        let previous = (current_score + total_points - pts).max(0);
        let new_score_val = (current_score + total_points).max(0);

        sqlx::query(
            "INSERT INTO score_history(id,score_id,contact_id,rule_id,tenant_id,points,previous_score,new_score,event_type) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)"
        )
        .bind(Uuid::new_v4())
        .bind(score_id)
        .bind(contact_id)
        .bind(rule.id)
        .bind(tenant_id)
        .bind(pts)
        .bind(previous)
        .bind(new_score_val)
        .bind(event_type)
        .execute(db)
        .await?;
    }

    let final_score = (current_score + total_points).max(0);
    let category = score_category(final_score);
    let old_cat = score.map(|s| s.category).unwrap_or_else(|| "cold".to_string());

    let updated = sqlx::query_as::<_, Score>(
        "UPDATE scores SET total_score=$1, category=$2, last_event_type=$3, last_event_at=NOW(), updated_at=NOW() WHERE id=$4 RETURNING *"
    )
    .bind(final_score)
    .bind(category)
    .bind(event_type)
    .bind(score_id)
    .fetch_one(db)
    .await?;

    if old_cat != category {
        crate::automation::engine::fire_score_trigger(db, tenant_id, contact_id, final_score, category).await;
    }

    Ok(updated)
}

/// Ensure a score record exists for a contact, creating one if needed.
pub async fn ensure_score_record(db: &PgPool, tenant_id: Uuid, contact_id: Uuid) -> Result<Score, crate::errors::AppError> {
    Ok(match sqlx::query_as::<_, Score>("SELECT * FROM scores WHERE tenant_id=$1 AND contact_id=$2")
        .bind(tenant_id)
        .bind(contact_id)
        .fetch_optional(db)
        .await?
    {
        Some(s) => s,
        None => sqlx::query_as::<_, Score>(
            "INSERT INTO scores(id,tenant_id,contact_id,total_score,category) VALUES($1,$2,$3,0,'cold') RETURNING *"
        )
        .bind(Uuid::new_v4())
        .bind(tenant_id)
        .bind(contact_id)
        .fetch_one(db)
        .await?,
    })
}
