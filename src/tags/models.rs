use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct TagCategory {
    pub id: Uuid, pub tenant_id: Uuid, pub name: String, pub color: Option<String>,
    pub created_at: DateTime<Utc>, pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct Tag {
    pub id: Uuid, pub tenant_id: Uuid, pub category_id: Option<Uuid>,
    pub name: String, pub color: Option<String>, pub parent_id: Option<Uuid>,
    pub is_active: bool, pub created_at: DateTime<Utc>, pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct TagAssignment {
    pub id: Uuid, pub tag_id: Uuid, pub entity_type: String, pub entity_id: Uuid,
    pub tenant_id: Uuid, pub assigned_by: Option<Uuid>, pub created_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct CreateCategoryRequest { pub name: String, pub color: Option<String> }
#[derive(Debug, Deserialize)]
pub struct UpdateCategoryRequest { pub name: Option<String>, pub color: Option<String> }
#[derive(Debug, Deserialize)]
pub struct CreateTagRequest { pub name: String, pub category_id: Option<Uuid>, pub color: Option<String>, pub parent_id: Option<Uuid> }
#[derive(Debug, Deserialize)]
pub struct UpdateTagRequest { pub name: Option<String>, pub category_id: Option<Uuid>, pub color: Option<String>, pub parent_id: Option<Uuid>, pub is_active: Option<bool> }
#[derive(Debug, Deserialize)]
pub struct AssignTagRequest { pub tag_id: Uuid, pub entity_type: String, pub entity_id: Uuid }
