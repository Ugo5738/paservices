# Property Analysis Services (PA Services)

This repository contains the microservices that power the Property Analysis platform. Our goal is to provide a reliable and scalable system for capturing and analyzing property data.

## 🚀 Getting Started: For New Developers

If you are new to the project, this is your starting point. Our "Paved Path" for development uses Docker to create a consistent local environment that mirrors our production setup.

➡️ **Start Here: [Development Guide](docs/development.md)**

## 🏛️ System Architecture

To understand how the services interact, refer to our core architecture documentation. These are "golden" documents that provide a trusted overview of the system.

- **[Project Structure Overview](PROJECT_STRUCTURE.md)**: A high-level view of the directories and services.
- **[System Workflow Guide](docs/system_workflow.md)**: A technical walkthrough of the API call sequence for a typical data capture task.

## 🛠️ Service-Specific Documentation

Dive into the details for each microservice. These READMEs provide service-specific context and link back to our central documentation for shared concepts.

- **[Auth Service](./auth_service/README.md)**: Manages users, clients, and permissions.
- **[Super ID Service](./super_id_service/README.md)**: Generates and records unique workflow IDs.
- **[Data Capture Rightmove Service](./data_capture_rightmove_service/README.md)**: Fetches and stores property data from Rightmove.

## 🚀 Deployment & Operations

This project is deployed on AWS EKS via an automated CI/CD pipeline. The "paved path" for deployment is to use our GitHub Actions workflows.

- **[Production Deployment Guide](docs/production_deployment.md)**: Detailed steps for the initial production environment setup.
- **[Deployment Checklist](deployment-checklist.md)**: Pre-flight checks for ensuring a smooth deployment.
- **[CI/CD Workflows](.github/workflows/)**: Our automated pipelines for testing and deployment. Manual deployments should only be performed for debugging or initial setup.

## ⁉️ Troubleshooting

Encountering an issue? Our troubleshooting guide contains solutions to common problems, from local development errors to deployment issues.

➡️ **[Troubleshooting Guide](docs/troubleshooting.md)**
