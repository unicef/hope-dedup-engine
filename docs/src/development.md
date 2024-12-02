## Local Development

To develop the service locally, you can utilize the provided `compose.yml` file. This configuration file defines all the necessary services, including the primary application and its dependencies, to create a consistent development environment. By using **Docker Compose**, you can effortlessly spin up the entire application stack, ensuring that all components work seamlessly together.

To build and start the service, along with its dependencies, run the following command:

    docker compose up --build


## Running Tests
To ensure that the service is working correctly, a comprehensive suite of tests is available. You can run these tests execute the following command:

    docker compose run --rm backend pytest tests -v --create-db


## Viewing Coverage Report

After running the tests, a coverage report will be generated. This report helps in assessing how much of the code is covered by the tests, highlighting any areas that may need additional testing. You can find the coverage report in the `~build/coverage` directory.
