import requests
import json
import time
import argparse
from src.logger import get_logger

logger = get_logger(__name__)

def run_simulation(file_path: str, endpoint_url: str):
    """
    Reads sample data from a file and sends it to the specified endpoint.
    """
    try:
        with open(file_path, 'r') as f:
            sample_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Error: The file '{file_path}' was not found.")
        return
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON from '{file_path}'.")
        return

    logger.info(f"--- Starting data simulation ---")
    logger.info(f"Target endpoint: {endpoint_url}\n")

    for i, record in enumerate(sample_data):
        try:
            logger.info(f"Sending record {i+1}: {record}")
            response = requests.post(endpoint_url, json=record)

            response.raise_for_status() 

            logger.info(f"-> Server response: {response.status_code} - {response.json()}")

        except requests.exceptions.RequestException as e:
            logger.error(f"!! Failed to send data for record {i+1}: {e}")

        logger.info("-" * 20)
        time.sleep(1)

    logger.info("--- Simulation finished ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate a stream of HRV data to the main application.")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run the script in simulation mode."
    )
    args = parser.parse_args()

    if args.simulate:
        app_endpoint = "http://127.0.0.1:8000/breath-check-in"
        data_file = "tools/sample_hrv_data.json"

        run_simulation(data_file, app_endpoint)
    else:
        logger.info("To run the simulation, use the --simulate flag.")
        logger.info("Example: python tools/simulate_data.py --simulate")