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
        # Open the JSON file and load the sample HRV data
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

    # Send the sample HRV data to the endpoint
    for i, record in enumerate(sample_data):
        try:
            logger.info(f"Sending record {i+1}: {record}")
            # Send the HRV data to the endpoint
            response = requests.post(endpoint_url, json=record)

            # Check if the response is successful
            response.raise_for_status() 

            # Log the response
            logger.info(f"-> Server response: {response.status_code} - {response.json()}")

        # If the response is not successful, log the error
        except requests.exceptions.RequestException as e:
            logger.error(f"!! Failed to send data for record {i+1}: {e}")

        logger.info("-" * 20)

        # Wait for 1 second before sending the next record (1Hz)
        time.sleep(1)

    logger.info("--- Simulation finished ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate a stream of HRV data to the main application.")

    # Add the --simulate flag to the parser
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run the script in simulation mode."
    )

    # Parse the arguments
    args = parser.parse_args()

    # If the --simulate flag is used, run the simulation
    if args.simulate:
        app_endpoint = "http://127.0.0.1:8000/breath-check-in"
        data_file = "tools/sample_hrv_data.json"

        run_simulation(data_file, app_endpoint)
    else:
        logger.info("To run the simulation, use the --simulate flag.")
        logger.info("Example: python tools/simulate_data.py --simulate")