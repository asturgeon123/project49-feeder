# Project49-Feeder: Aircraft Tracking and Data Collection

**Project49-Feeder** is a robust and configurable Python application designed to track specific aircraft, fetch their live positional data, and store it in a Supabase database. It leverages the open-source, unfiltered flight data from ADSB.lol and provides real-time health monitoring with Discord notifications.

This application is ideal for aviation enthusiasts, researchers, or anyone interested in collecting and analyzing flight data for a specific set of aircraft.

## Key Features

*   **Targeted Aircraft Tracking:** Monitors a predefined list of aircraft based on their tail numbers.
*   **Real-time Data Fetching:** Queries the ADSB.lol API at a configurable interval to get the latest flight data.
*   **Data Storage:** Inserts clean and structured track point data into a Supabase `track_point` table.
*   **Health Monitoring:** Actively checks the connection to the ADSB.lol feeder and sends alerts if the connection is lost.
*   **Discord Notifications:** Provides instant alerts to a Discord channel for feeder status changes (down or recovered).
*   **Resilient and Configurable:** Handles network errors gracefully and allows for easy configuration through environment variables.
*   **Containerized:** Includes a `Dockerfile` for easy deployment and consistent execution environments.

## How It Works

The application operates in a continuous loop, performing the following steps:

1.  **Fetch Aircraft List:** Retrieves the list of aircraft to be tracked from your Supabase `aircraft` table. This list is cached to reduce database queries.
2.  **Query ADSB.lol API:** It sends a request to the ADSB.lol re-api with the tail numbers of the aircraft to be tracked. This API provides real-time data for aircraft detected by the ADSB.lol network of feeders.
3.  **Process and Map Data:** The raw JSON response from the API is parsed and mapped to the schema of the `track_point` table in your Supabase database.
4.  **Insert Data:** The processed track points are then batch-inserted into the database.
5.  **Health Check:** Each successful or failed API request to ADSB.lol serves as a health check. If the API returns a `403 Forbidden` error, it indicates that the script is not running on a recognized feeder's IP address, and a "Feeder is DOWN" alert is sent to Discord. A successful request after a failure will trigger a "Feeder has been restored" notification.
6.  **Wait and Repeat:** The application then pauses for a configurable polling interval before repeating the cycle.

## Getting Started

### Prerequisites

*   Python 3.12 or later
*   Docker
*   A Supabase account with a project set up
*   A Discord server with a webhook URL

### Setup

Download the docker compose file
```
wget -O docker-compose.yml https://raw.githubusercontent.com/asturgeon123/project49-feeder/refs/heads/main/docker-compose.yaml
```
Start the containers
```
docker compose up -d
```

## Health Monitoring and Notifications

The application provides a simple yet effective health monitoring system for the ADSB.lol feeder.

*   **Feeder Down:** If the script fails to connect to the ADSB.lol re-api with a `403 Forbidden` error, it assumes the feeder is down. An alert is immediately sent to the configured Discord webhook. This error typically occurs when the IP address of the machine running the script is not recognized as a valid ADSB.lol feeder.
*   **Feeder Recovered:** Once the connection to the API is re-established (a successful request is made after a failure), a recovery notification is sent to Discord.

This ensures that you are promptly informed of any disruptions in the data collection process.