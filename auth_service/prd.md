# Product Requirements Document: Auth Service

## 1. Introduction

The Auth Service is a foundational microservice responsible for managing user and application client identities, authentication, and authorization within the distributed property analysis ecosystem. It will leverage `Supabase` for core human user authentication functionalities while providing a `FastAPI` proxy layer for enhanced control and custom logic. It will also implement a robust Role-Based Access Control (RBAC) system and a secure mechanism for machine-to-machine (M2M) client authentication. This service is a prerequisite for other services that require authenticated and authorized access, ensuring that interactions are secure and permissioned. It does not manage or store the `super_id`; that is handled by a dedicated Super ID Service.

## 2. Goals & Objectives

- **Primary Goal:** Provide a secure, reliable, and centralized authentication and authorization mechanism for all users (human) and service clients (machine).
- **Secure Human User Authentication:** Offer standard authentication methods (email/password, social logins, magic links) by proxying `Supabase`, allowing for future custom pre/post-processing.
- **Secure M2M Authentication:** Implement OAuth 2.0 Client Credentials Grant for `app_clients`.
- **Granular Authorization:** Establish a flexible RBAC system (roles and permissions) to control access to resources and operations across different services.
- **JWT Issuance:**
  - For human users: Ensure `Supabase`-issued JWTs are enriched with custom claims (roles, permissions) via `Supabase` configuration.
  - For `app_clients`: Issue custom JWTs containing appropriate claims (roles, permissions).
- **Developer Experience:** Provide clear API documentation for easy integration by other services and frontends.
- **Scalability & Reliability:** Design the service to handle anticipated load and maintain high availability.
- **Maintainability:** Ensure code is well-structured and documented for future development.

## 3. Target Users/Personas

- **End Users (Humans):** Individuals interacting with the platform (e.g., property owners, agents). They need to register, log in, manage their passwords, and have their sessions maintained securely.
- **Service Clients (`app_clients`):** Other internal microservices (e.g., Super ID Service, Rapid API Scraper Service) or automated agents that need to authenticate programmatically to access resources or perform actions.
- **Application Developers:** Developers building the frontend or other backend services who will integrate with the Auth Service for authentication and authorization.
- **System Administrators:** Personnel responsible for managing `app_clients`, roles, and permissions within the Auth Service.

## 4. Features & User Stories

### 4.1. Human User Authentication (Proxying `Supabase`)

- **F1: User Registration (via Proxy)**
  - **US1.1:** As a new End User, I want to register using my email and password so I can create an account.
  - **US1.2:** As a new End User, I want to register using my Google/Social Provider account (if configured) so I can sign up quickly.
  - **US1.3:** As a new End User, I want to receive a magic link via email to register/log in so I don't have to remember a password.
  - _(Technical: `FastAPI` endpoints will call corresponding `Supabase` functions via `supabase-py`)_
- **F2: User Login (via Proxy)**
  - **US2.1:** As an End User, I want to log in using my email and password so I can access my account.
  - **US2.2:** As an End User, I want to log in using my Google/Social Provider account so I can access my account quickly.
  - **US2.3:** As an End User, I want to log in using a magic link.
  - _(Technical: Returns `Supabase` JWT upon successful authentication)_
- **F3: Password Management (via Proxy)**
  - **US3.1:** As an End User, I want to request a password reset link if I forget my password.
  - **US3.2:** As an End User, I want to set a new password using the reset link.
  - **US3.3:** As a logged-in End User, I want to change my current password.
- **F4: User Logout (via Proxy)**
  - **US4.1:** As an End User, I want to log out of my account to end my session.
  - _(Technical: Calls `Supabase signOut()` and advises client to clear local tokens)_
- **F5: Multi-Factor Authentication (MFA - Leveraged from `Supabase`)**
  - **US5.1:** As an End User, I want to be able to set up MFA for my account for added security.
  - **US5.2:** As an End User, I want to be prompted for my MFA code during login if enabled.
  - _(Technical: `Supabase` handles MFA logic. Proxy endpoints may pass through necessary parameters.)_
- **F6: Email Verification (Leveraged from `Supabase`)**
  - **US6.1:** As a new End User, I want to receive an email to verify my email address.
  - _(Technical: `Supabase` handles this. Proxy endpoints pass through necessary parameters.)_

### 4.2. User Profile Management (Custom in `FastAPI` Auth Service)

- **F7: User Profile Data**
  - **US7.1:** As a logged-in End User, I want to view my profile information (username, first name, last name).
  - **US7.2:** As a logged-in End User, I want to update my profile information.
  - _(Technical: Stored in the Auth Service's `profiles` table, linked to `supabase.auth.users.id`)_

### 4.3. `app_client` (Machine-to-Machine) Authentication

- **F8: `app_client` Management (Admin)**
  - **US8.1:** As a System Administrator, I want to create new `app_clients` with a unique `client_id` and a securely generated `client_secret` (displayed once).
  - **US8.2:** As a System Administrator, I want to view, update (name, description, active status), and delete `app_clients`.
- **F9: `app_client` Token Acquisition**
  - **US9.1:** As an `app_client`, I want to exchange my `client_id` and `client_secret` for an access token (JWT) using the Client Credentials Grant.
  - _(Technical: Auth Service issues its own JWT for `app_clients`)_
- **F10: `app_client` Refresh Tokens (Optional)**
  - **US10.1:** As an `app_client`, if refresh tokens are implemented, I want to use a refresh token to obtain a new access token without re-sending my credentials.

### 4.4. Role-Based Access Control (RBAC)

- **F11: Role Management (Admin)**
  - **US11.1:** As a System Administrator, I want to create, read, update, and delete roles (e.g., `standard_user`, `agent_user`, `scraper_service_access`).
- **F12: Permission Management (Admin)**
  - **US12.1:** As a System Administrator, I want to create, read, update, and delete permissions (e.g., `property:read`, `property:create`, `agent:find`, `scrape:property_details`).
- **F13: Role-Permission Assignment (Admin)**
  - **US13.1:** As a System Administrator, I want to assign multiple permissions to a role.
  - **US13.2:** As a System Administrator, I want to remove permissions from a role.
- **F14: User/Client Role Assignment (Admin)**
  - **US14.1:** As a System Administrator, I want to assign one or more roles to a human user.
  - **US14.2:** As a System Administrator, I want to assign one or more roles to an `app_client`.
  - **US14.3:** As a System Administrator, I want to remove roles from a user or `app_client`.

### 4.5. JWT Handling & Claims

- **F15: `Supabase` JWT Enrichment for Human Users**
  - **US15.1:** As a consuming service, when I receive a JWT for a human user, I want it to contain their assigned roles and permissions as custom claims so I can perform authorization checks.
  - _(Technical: Implemented via Postgres function in `Supabase`, configured to add claims to JWTs)_
- **F16: Custom JWT for `app_clients`**
  - **US16.1:** As a consuming service, when I receive a JWT for an `app_client`, I want it to contain its `client_id` (as `sub`), assigned roles, and permissions as claims.
  - _(Technical: Auth Service generates and signs these JWTs)_

## 5. Technical Design & Architecture

- **Framework:** `FastAPI` (`Python`)
- **Database:** `PostgreSQL` (managed by `Supabase`)
- **Human User Core Auth:** `Supabase` `auth.users` schema.
- **Custom Auth Data:** Separate schema (`auth_service_schema` or `public` with prefixes) for `profiles`, `app_clients`, `roles`, `permissions`, and junction tables.
- **Human User Authentication Flow:**
  1. Frontend/Client calls `FastAPI` Auth Service endpoint (e.g., `/auth/users/login`).
  2. `FastAPI` Auth Service endpoint uses `supabase-py` client to call the corresponding `Supabase` auth function (e.g., `supabase.auth.sign_in_with_password()`).
  3. (Optional) Custom pre-processing logic in `FastAPI`.
  4. `Supabase` handles authentication, issues JWT (with custom RBAC claims added via DB function).
  5. (Optional) Custom post-processing logic in `FastAPI`.
  6. `FastAPI` Auth Service returns the `Supabase` session/JWT to the client.
- **`app_client` Authentication Flow:**
  1. `app_client` calls `FastAPI` Auth Service token endpoint (`/auth/token`) with `client_id` and `client_secret`.
  2. `FastAPI` Auth Service validates credentials against its `app_clients` table.
  3. `FastAPI` Auth Service generates a new JWT, signed with its own secret, including `sub` (`client_id`), roles, permissions.
  4. `FastAPI` Auth Service returns the JWT to the `app_client`.
- **RBAC Claims in `Supabase` JWT:**
  - A `PostgreSQL` function will be created in the `Supabase` database.
  - This function will take a `user_id` (from `auth.users`) as input.
  - It will query the `user_roles` and `role_permissions` tables to fetch the user's assigned roles and permissions.
  - It will return these as a JSON object.
  - `Supabase` will be configured (e.g., via `auth.hook_set_custom_claims` or `supabase/config.toml` if available for this mechanism) to call this function during JWT minting and add the returned JSON to the JWT payload.
- **Super ID Interaction:** The Auth Service does not directly interact with the Super ID service for linking or storing `super_id`. Other services that require a `super_id` will be responsible for querying the Super ID Service after authenticating the user/client via the JWT provided by this Auth Service.

## 6. Database Schema (Auth Service specific tables)

Refer to the previously discussed schema, specifically:

- `profiles` (linked to `supabase.auth.users.id`, no `super_id` field)
- `app_clients`
- `roles`
- `permissions`
- `user_roles` (linking `supabase.auth.users.id` to `roles.id`)
- `app_client_roles` (linking `app_clients.id` to `roles.id`)
- `role_permissions`
- `refresh_tokens` (for `app_clients` if implemented)

## 7. API Endpoints (High-Level)

### Human User Auth (Proxy to `Supabase`):

- `POST /auth/users/register` (email/pass)
- `POST /auth/users/login` (email/pass)
- `POST /auth/users/login/magiclink`
- `GET /auth/users/login/{provider}` (for social login initiation)
- `POST /auth/users/login/{provider}/callback` (for social login callback)
- `POST /auth/users/logout`
- `POST /auth/users/password/reset`
- `PUT /auth/users/password/update` (for logged-in user)
- `POST /auth/users/mfa/enroll`
- `POST /auth/users/mfa/challenge`
- `POST /auth/users/verify/resend`

### User Profile:

- `GET /auth/users/me` (Requires Auth)
- `PUT /auth/users/me` (Requires Auth)

### `app_client` (M2M) Auth:

- `POST /auth/token` (For `app_clients` to get JWT; Grant Type: `client_credentials`)

### Admin - `app_client` Management: (Requires Admin Auth)

- `POST /auth/admin/clients`
- `GET /auth/admin/clients`
- `GET /auth/admin/clients/{client_id}`
- `PUT /auth/admin/clients/{client_id}`
- `DELETE /auth/admin/clients/{client_id}`

### Admin - RBAC Management: (Requires Admin Auth)

- `POST /auth/admin/roles`
- `GET /auth/admin/roles`
- `PUT /auth/admin/roles/{role_id}`
- `DELETE /auth/admin/roles/{role_id}`
- `POST /auth/admin/permissions`
- `GET /auth/admin/permissions`
- `PUT /auth/admin/permissions/{permission_id}`
- `DELETE /auth/admin/permissions/{permission_id}`
- `POST /auth/admin/roles/{role_id}/permissions` (Assign permission to role)
- `DELETE /auth/admin/roles/{role_id}/permissions/{permission_id}` (Remove permission from role)
- `POST /auth/admin/users/{user_id}/roles` (Assign role to user)
- `DELETE /auth/admin/users/{user_id}/roles/{role_id}` (Remove role from user)
- `POST /auth/admin/clients/{client_id}/roles` (Assign role to `app_client`)
- `DELETE /auth/admin/clients/{client_id}/roles/{role_id}` (Remove role from `app_client`)

## 8. Non-Functional Requirements

- **Security:**
  - Protection against OWASP Top 10 vulnerabilities.
  - Secure storage of `client_secrets` (hashed).
  - Rate limiting on sensitive endpoints (login, registration, token).
  - HTTPS for all communication.
  - Regular security audits (recommended).
  - Secure management of production secrets and configurations will be implemented, moving beyond local .env files (e.g., using environment variables injected by the hosting platform, or a dedicated secret management system as the application scales).
- **Performance:**
  - Login/Token generation latency: < 500ms (p95).
  - Other API calls: < 200ms (p95).
- **Scalability:** Design to be horizontally scalable (stateless API if possible).
- **Reliability:** High availability (e.g., 99.9% uptime). Proper error handling and logging.
- **Usability (Developer):** Clear, versioned API documentation (e.g., OpenAPI/Swagger).
- **Logging:** Comprehensive structured logging (e.g., JSON format) will be implemented for audit trails and debugging. Key auditable events include: admin actions (client/role/permission management), app_client token issuance, user registration, successful/failed login attempts, and significant errors.

## 9. Future Considerations

- Advanced Token Revocation (e.g., denylists for JWTs).
- Audit Logs for admin actions.
- More granular permission checks (e.g., attribute-based access control - ABAC).
- Support for other OAuth 2.0 flows if needed.
- User impersonation for admins.

## 10. Success Metrics

- Number of successful user authentications per day/week.
- Number of successful `app_client` token generations per day/week.
- API error rates (< 0.1%).
- API latency meets performance NFRs.
- Time to integrate for new services (developer satisfaction).
- Zero security incidents related to authentication/authorization bypass.

## 11. Out of Scope

- User Interface (UI) for login, registration, or admin panels (this service is API-only).
- `super_id` generation, storage, or direct management.
- The actual implementation of other microservices (Scraper, Agent Finder, etc.).
- Billing or subscription management.
