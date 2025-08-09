import os
import time
import logging
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from supabase import create_client, Client

# --- Configuration & Setup ---

# Set up basic logging to print messages to the console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from the .env file
load_dotenv()

# Fetch configuration from environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
# Default to 60 seconds if not set
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL_SECONDS", "60"))

AIRCRAFT_FETCH_INTERVAL = int(os.getenv("AIRCRAFT_FETCH_INTERVAL_SECONDS", "300")) # 5 minutes

# --- Health Monitoring & Notifications ---

# A simple state variable to track the feeder's health to avoid sending duplicate alerts
# True = Healthy, False = Unhealthy/Down
feeder_is_healthy = True

def send_discord_notification(message: str, is_error: bool = False):
    """Sends a formatted message to the configured Discord webhook."""
    if not DISCORD_WEBHOOK_URL:
        logging.warning("DISCORD_WEBHOOK_URL not set. Skipping notification.")
        return

    # Set color based on message type (red for errors, green for recovery)
    color = 15158332 if is_error else 3066993
    title = "🚨 Feeder Health Alert" if is_error else "✅ Feeder Status Update"

    payload = {
        "embeds": [{
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except requests.RequestException as e:
        logging.error(f"Failed to send Discord notification: {e}")

# --- Database & API Functions ---

def get_all_aircraft(supabase: Client) -> dict[str, str]:
    """Fetches all aircraft from Supabase and returns a tail_number -> id mapping."""
    try:
        response = supabase.table("aircraft").select("id, tail_number").execute()
        # Create a dictionary for quick lookups: {'N12345': 'uuid-goes-here'}
        aircraft_map = {item['tail_number']: item['id'] for item in response.data if item['tail_number']}
        logging.info(f"Fetched {len(aircraft_map)} aircraft from the database.")
        return aircraft_map
    except Exception as e:
        logging.error(f"Failed to fetch aircraft from Supabase: {e}")
        return {}

def query_adsb_lol_api(tail_numbers: list[str]) -> list[dict] | None:
    """Queries the ADSB.lol re-api for a list of tail numbers."""
    global feeder_is_healthy
    if not tail_numbers:
        return []

    # The API is limited to ~1000 items and a certain URL length
    # For now, we assume the list is not excessively long.
    url = f"https://re-api.adsb.lol/?find_reg={','.join(tail_numbers)}"

    try:
        response = requests.get(url, timeout=15) # 15-second timeout
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)

        # If we get here, the request was successful. If the feeder was previously down, mark it as recovered.
        if not feeder_is_healthy:
            feeder_is_healthy = True
            send_discord_notification("Connection to ADSB.lol feeder has been restored.", is_error=False)
            logging.info("Feeder has recovered.")

        return response.json().get("aircraft", [])

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            # This is our primary health check failure indicator
            logging.error("Feeder check failed: 403 Forbidden. Is this script running on the feeder device?")
            if feeder_is_healthy: # Only send alert on the first failure
                send_discord_notification(
                    "**Feeder is DOWN!**\nReceived a `403 Forbidden` error from the re-api. "
                    "This means the server is not recognizing this IP as a valid feeder.",
                    is_error=True
                )
            feeder_is_healthy = False
        else:
            logging.error(f"HTTP error occurred while querying ADSB.lol: {e}")
        return None
    except requests.RequestException as e:
        logging.error(f"A network error occurred while querying ADSB.lol: {e}")
        return None

def map_adsb_to_track_points(adsb_data: list[dict], aircraft_map: dict[str, str]) -> list[dict]:
    """Maps the raw ADSB.lol data to the Supabase track_point schema."""
    track_points_to_insert = []
    for aircraft in adsb_data:
        # The 'r' key holds the registration/tail_number
        tail_number = aircraft.get('r')
        # We must have a position and a matching tail number in our database
        if tail_number in aircraft_map and aircraft.get('lat') and aircraft.get('lon'):
            
            track_point = {
                "aircraft_id": aircraft_map[tail_number],
                # ADSB.lol 'now' is a Unix timestamp in milliseconds. Postgres needs ISO 8601.
                "timestamp": datetime.fromtimestamp(aircraft.get('now', time.time()), tz=timezone.utc).isoformat(),
                "latitude": aircraft.get('lat'),
                "longitude": aircraft.get('lon'),
                "altitude_msl_ft": aircraft.get('alt_baro'),
                "ground_speed_kts": aircraft.get('gs'),
                "vertical_speed_fpm": aircraft.get('baro_rate'),
                "heading_deg": aircraft.get('track'), # 'track' is often used for heading
            }
            # Remove keys with None values to let the database use its defaults
            track_point_clean = {k: v for k, v in track_point.items() if v is not None}
            track_points_to_insert.append(track_point_clean)
    return track_points_to_insert

def insert_track_points(supabase: Client, track_points: list[dict]):
    """Batch-inserts a list of track points into the Supabase database."""
    if not track_points:
        logging.info("No new track points to insert.")
        return

    try:
        response = supabase.table("track_point").insert(track_points).execute()
        print(response)
        logging.info(f"Successfully inserted {len(track_points)} new track points.")
    except Exception as e:
        logging.error(f"Failed to insert track points into Supabase: {e}")
        

# --- Main Application Logic ---

def main():
    """Main execution loop."""
    logging.info("Starting aircraft tracking service...")

    # Validate that all required environment variables are set
    if not all([SUPABASE_URL, SUPABASE_KEY]):
        logging.error("FATAL: SUPABASE_URL or SUPABASE_KEY environment variables not set. Exiting.")
        return

    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        logging.error(f"FATAL: Could not connect to Supabase. Check URL and Key. Error: {e}")
        return

    
    last_aircraft_fetch_time = 0
    while True:
        logging.info("--- Running tracking cycle ---")

        # 1. Get all aircraft from our DB
        aircraft_map = get_all_aircraft(supabase)
        # 1. Refresh the aircraft list from the database if the cache is old
        time_since_last_fetch = time.time() - last_aircraft_fetch_time
        print("Time since last fetch: ", time_since_last_fetch)
        if time_since_last_fetch > AIRCRAFT_FETCH_INTERVAL:
            logging.info("Aircraft cache is stale (or empty). Refreshing from database...")
            aircraft_map = get_all_aircraft(supabase)
            last_aircraft_fetch_time = time.time()

        if aircraft_map:
            # 2. Query the ADSB API for those aircraft
            tail_numbers_to_find = list(aircraft_map.keys())
            live_adsb_data = query_adsb_lol_api(tail_numbers_to_find)

            # 3. If data is found, process and insert it
            if live_adsb_data is not None:
                track_points = map_adsb_to_track_points(live_adsb_data, aircraft_map)
                insert_track_points(supabase, track_points)
        else:
            logging.warning("No aircraft found in the database to track.")

        logging.info(f"--- Cycle complete. Waiting for {POLLING_INTERVAL} seconds... ---")
        time.sleep(POLLING_INTERVAL)


if __name__ == "__main__":
    main()

