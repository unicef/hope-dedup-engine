### API Documentation

The application provides comprehensive API documentation to facilitate ease of use and integration. API documentation is available via two main interfaces:

#### Swagger UI
An interactive interface that allows users to explore and test the API endpoints. It provides detailed information about the available endpoints, their parameters, and response formats. Users can input data and execute requests directly from the interface.

URL: `http://localhost:8000/api/rest/swagger/`

#### Redoc
A static, beautifully rendered documentation interface that offers a more structured and user-friendly presentation of the API. It includes comprehensive details about each endpoint, including descriptions, parameters, and example requests and responses.

URL: `http://localhost:8000/api/rest/redoc/`


These interfaces ensure that developers have all the necessary information to effectively utilize the API, enabling seamless integration and interaction with the application’s features.

!!! warning "Environment-Specific URLs"
    The URLs will vary depending on the server where it is hosted. If the server is hosted elsewhere except for the local machine, replace **http://localhost:8000** with the server's domain URL.


---

### **Accessing the REST API**

To interact with the REST API, a valid authentication token is required. The token can be generated from the admin panel:

1. Navigate to:
```
Home › Api › Tokens
```

2. Create a new token for the desired user.

!!! warning "User Requirement for API Access"
    The user for whom the token is created **must be linked to an external system**.
    External systems are managed in:
    ```
    Home › Security › External systems
    ```
    Without this link, the token will not be valid for API authentication.
