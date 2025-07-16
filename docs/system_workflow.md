# System Workflow: Technical Sequence

This document outlines the precise sequence of API calls and internal processes required to fetch and store property data. The primary client in this workflow is an orchestrating service or agent.

---

#### **Prerequisites**

- The client must have a valid `client_id` and `client_secret` issued by the **Auth Service**.
- All services (`Auth Service`, `Super ID Service`, `Data Capture Rightmove Service`) are running and accessible.

---

### **Step 1: Obtain a Machine-to-Machine (M2M) Access Token**

The workflow begins with the client authenticating itself to gain access to the ecosystem.

- **Action:** Acquire a JWT access token.
- **Service:** `Auth Service`
- **Endpoint:** `POST /api/v1/auth/token`
- **Request Payload:**
  ```json
  {
    "grant_type": "client_credentials",
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET"
  }
  ```
- **Successful Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 900
  }
  ```
  The `access_token` is a JWT that must be included as a Bearer token in the `Authorization` header for all subsequent API calls.

### **Step 2: Generate a Unique Workflow Identifier (Super ID)**

Before initiating a data capture process, a unique identifier is generated to correlate all subsequent events and data records for that specific workflow.

- **Action:** Generate a new `super_id`.
- **Service:** `Super ID Service`
- **Endpoint:** `POST /api/v1/super_ids`
- **Authentication:** `Authorization: Bearer <access_token_from_step_1>`
- **Request Payload (Optional):**
  ```json
  {
    "count": 1,
    "description": "Data capture for property 123456789"
  }
  ```
- **Successful Response (201 Created):**
  ```json
  {
    "super_id": "aedd5c2f-0df1-4f4b-b3a2-b22b2c41a197"
  }
  ```
  The returned `super_id` will be used to tag all data related to this specific data capture task.

### **Step 3: Initiate Data Capture**

With a valid access token and a `super_id`, the client can now request the property data capture.

- **Action:** Fetch and store all available data for a specific property.
- **Service:** `Data Capture Rightmove Service`
- **Endpoint:** `POST /api/v1/properties/fetch/combined`
- **Authentication:** `Authorization: Bearer <access_token_from_step_1>`
- **Request Payload:**
  ```json
  {
    "property_url": "https://www.rightmove.co.uk/properties/123456789",
    "super_id": "aedd5c2f-0df1-4f4b-b3a2-b22b2c41a197"
  }
  ```
- **Successful Response (200 OK):** A JSON object detailing the outcome of each internal API call and storage operation.
  ```json
  {
    "property_id": 123456789,
    "property_url": "https://www.rightmove.co.uk/properties/123456789",
    "results": [
      {
        "api_endpoint": "properties/details",
        "stored": true,
        "message": "Successfully stored property details."
      },
      {
        "api_endpoint": "buy/property-for-sale/detail",
        "stored": true,
        "message": "Successfully stored property for sale details."
      }
    ]
  }
  ```
