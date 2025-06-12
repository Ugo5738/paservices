# Product Requirements Document: Super ID Service

## 1. Introduction

The Super ID Service is a critical utility microservice within the property analysis ecosystem. Its primary responsibility is to generate, record, and provide unique identifiers (UUIDs, referred to as `super_ids`) on demand. These `super_ids` are intended to serve as overarching workflow IDs, version IDs, or transaction IDs, typically generated at the inception of a multi-step process by an orchestrating entity (e.g., an Orchestrator Service, API Gateway/BFF, or an AI Agent). All generated `super_ids` will be persisted in a dedicated Supabase table for audit and system integrity purposes. Access to this service, via a valid JWT from the `auth_service`, is a prerequisite for obtaining a new `super_id`.

## 2. Goals & Objectives

- **Primary Goal:** Provide a highly available and performant service for generating and securely recording unique `super_ids` (UUID v4).
- **Uniqueness:** Guarantee the universal uniqueness of each generated `super_id`.
- **Persistence:** Ensure every generated `super_id` is stored in the Supabase database, along with relevant metadata (e.g., generation time, requesting client).
- **Simplicity:** Offer a minimal and straightforward API for requesting `super_ids`.
- **Security:** Ensure that only authenticated and authorized clients (as determined by the Auth Service) can request `super_ids` and that database interactions are secure.
- **Developer Experience:** Provide clear API documentation for easy integration by client services that orchestrate workflows.
- **Auditability:** Facilitate auditing by maintaining a persistent record of all generated IDs.

## 3. Target Users/Personas

- **Orchestrating Service Clients (`app_clients`):** Authenticated internal microservices (e.g., "Orchestrator Service") that request a `super_id` to initiate and identify a new workflow, with the understanding that this ID is recorded.
- **AI Agents (`app_clients`):** Automated agents that obtain and use a recorded `super_id` for complex analysis tasks.
- **Application Developers:** Developers building or maintaining the orchestrating services or AI agents.
- **System Administrators:** Personnel responsible for monitoring the service, managing the Supabase instance, and potentially querying the `super_id` log for audit purposes.

## 4. Features & User Stories

### 4.1. Super ID Generation and Recording

**F1: Single Super ID Generation & Recording**

- **US1.1:** As an authenticated Orchestrator Service, I want to request a single new `super_id`, and I expect this ID to be recorded by the Super ID Service before it's returned to me.
- **US1.2:** As an authenticated AI Agent, I want to obtain a `super_id` that is centrally recorded, to use as a primary identifier for a complex analysis task.
- **US1.3:** As an authenticated client, I want the received `super_id` to be in a standard UUID v4 string format.

## 5. Technical Design & Architecture

- **Framework:** FastAPI (Python).
- **Database:** PostgreSQL (managed by Supabase). The service will interact with Supabase using the `supabase-py` client library.
- **UUID Generation:** Utilizes Python's standard library `uuid.uuid4()`.
- **Authentication & Authorization for Super ID Service:**
  - Requires a valid JWT from the `auth_service`.
  - The service will validate the JWT and (recommended) check for `super_id:generate` permission.
- **Interaction Flow (Super ID Generation, Recording, and Usage):**
  1.  An orchestrating client (Orchestrator Service, AI Agent) authenticates with `auth_service` and obtains a JWT.
  2.  The client requests a new `super_id` from `super_id_service` (`POST /super_ids`), including its JWT.
  3.  `super_id_service` validates the JWT.
  4.  If authorized, `super_id_service` generates a new UUID v4.
  5.  `super_id_service` writes the generated UUID and relevant metadata (e.g., `generated_at`, `requested_by_client_id` from JWT claims) to a dedicated table in its Supabase database instance.
  6.  Upon successful storage in Supabase, `super_id_service` returns the `super_id`(s) to the orchestrating client.
  7.  The orchestrating client uses this `super_id` for its workflows, passing it to other services.
- **Role of Downstream Services:** Unchanged. They validate the JWT of the incoming request from the orchestrator and use the `super_id` for correlation. They do not typically query the `super_id_service`'s database.

## 6. Database Schema (Supabase)

A new table will be created in the Supabase project, for example, within the `public` schema (or a custom schema if preferred).

**Table: `generated_super_ids`**

| Column Name              | Data Type     | Constraints                 | Description                                                                  |
| ------------------------ | ------------- | --------------------------- | ---------------------------------------------------------------------------- |
| `id`                     | `BIGSERIAL`   | `PRIMARY KEY`               | Auto-incrementing primary key for the record.                                |
| `super_id`               | `UUID`        | `NOT NULL`, `UNIQUE`        | The generated UUID v4. Indexed for uniqueness.                               |
| `generated_at`           | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Timestamp of when the ID was generated and recorded.                         |
| `requested_by_client_id` | `TEXT`        | `NULLABLE`                  | The `client_id` or `sub` claim from the JWT of the requesting service/agent. |
| `metadata`               | `JSONB`       | `NULLABLE`                  | Optional field for any other metadata associated with the request.           |

(RLS - Row Level Security should be configured on this table in Supabase to ensure that the `super_id_service`'s service role key has write access, and potentially restrict read access if needed in the future).

## 7. API Endpoints (High-Level)

**Super ID Generation:**
**`POST /super_ids`**

- **Description:** Generates one or more new `super_ids` and records them.
- **Authentication:** Required (Valid JWT from `auth_service`).
- **Authorization:** (Recommended) Requires `super_id:generate` permission.
- **Internal Action:** Generates UUID(s), inserts record(s) into `generated_super_ids` table in Supabase.
- **Request Body (Optional for batch):**
  ```json
  {
    "count": 1 // Optional, defaults to 1.
  }
  ```
- **Responses:**
  - **201 Created (Single ID):**
    ```json
    {
      "super_id": "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"
    }
    ```
  - **201 Created (Batch IDs):**
    ```json
    {
      "super_ids": [
        "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx",
        "yyyyyyyy-yyyy-4yyy-zyyy-yyyyyyyyyyyy"
      ]
    }
    ```
  - **400 Bad Request:** If `count` is invalid.
  - **401 Unauthorized:** Invalid/missing JWT.
  - **403 Forbidden:** Lacks permission.
  - **500 Internal Server Error:** If UUID generation fails or if there's an issue writing to Supabase.
  - **503 Service Unavailable:** If Supabase is temporarily unavailable.

## 8. Non-Functional Requirements

- **Security:**
  - HTTPS for all communication.
  - Secure management of Supabase service role key by `super_id_service`.
  - RLS policies on Supabase table.
  - Rate limiting.
- **Performance:**
  - ID generation and recording latency: `< 150ms` (`p95`), accounting for UUID generation and a single Supabase insert. Batch inserts should be optimized.
- **Scalability:**
  - The service remains horizontally scalable at the application layer. Scalability will also depend on the performance and connection limits of the Supabase instance.
  - Consider Supabase plan limits for database connections and operations.
- **Reliability:**
  - High availability for the service (e.g., `99.9%`). Overall reliability is now also dependent on Supabase's uptime.
  - Implement retry mechanisms for Supabase writes if appropriate for transient errors.
- **Data Integrity & Durability:**
  - `super_id` stored with `UNIQUE` constraint in Supabase provides an additional layer of uniqueness enforcement (though UUIDv4 collisions are practically impossible).
  - Data durability is managed by Supabase (backups, replication, etc., according to your Supabase plan).
- **Usability (Developer):**
  - Clear API documentation.
- **Logging:**
  - Structured logging for requests to `super_id_service`.
  - Log success/failure of Supabase write operations.
