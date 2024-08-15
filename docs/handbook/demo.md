---
layout: default
title: Demo
nav_order: 2
---

### Instructions to Run the Demo Application

To run the demo application locally using Docker Compose, follow these steps:

- Navigate to the root directory of the repository.

- Execute the following command:

    ```docker compose -f tests/extras/demoapp/compose.yml up```

### Accessing the HDE application

- **Admin Panel**: http://localhost:8000/ (username: `adm@hde.org`, password: `adm`)

- **API Documentation**:

Swagger UI: http://localhost:8000/api/rest/swagger/


Redoc: http://localhost:8000/api/rest/redoc/