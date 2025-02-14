import logging
import requests
from django.http import JsonResponse
from django.shortcuts import render

# Configure logging
logging.basicConfig(level=logging.INFO, filename="app.log", format="%(asctime)s - %(levelname)s - %(message)s")

ORTHANC_URL = "http://localhost:8042"
CLOUD_URL = "https://pacs.reportingbot.in"
ORTHANC_AUTH = ("admin", "phP@123!")  # Replace with actual credentials
CLOUD_AUTH = ("admin", "phP@123!")  # Replace with actual credentials

def fetch_failed_jobs(request):
    """
    Fetch job IDs and check for failed jobs.
    """
    try:
        # Step 1: Get the list of job IDs
        response = requests.get(f"{ORTHANC_URL}/jobs", auth=ORTHANC_AUTH)
        response.raise_for_status()
        job_ids = response.json()

        failed_jobs = []  # Store failed jobs

        logging.info(f"Fetched {len(job_ids)} job IDs from Orthanc.")  # ✅ Log number of jobs fetched

        # Step 2: Fetch details of each job
        for job_id in job_ids:
            job_response = requests.get(f"{ORTHANC_URL}/jobs/{job_id}", auth=ORTHANC_AUTH)
            job_response.raise_for_status()
            job_details = job_response.json()

            job_state = job_details.get("State")  # ✅ Fetch "State" instead of "Status"
            logging.info(f"Job {job_id}: State = {job_state}")  # ✅ Log each job state

            # Check if the job state is 'Failure'
            if job_state == "Failure":  
                failed_jobs.append({
                    "ID": job_id,
                    "DicomInstance": job_details.get("Content", {}).get("ParentResources", ["N/A"])[0],  # Extract first resource
                    "State": job_state,
                    "Description": job_details.get("ErrorDescription", "No description"),
                })

        logging.info(f"Total failed jobs found: {len(failed_jobs)}")  # ✅ Log number of failed jobs

        return JsonResponse({"failed_jobs": failed_jobs})

    except requests.RequestException as e:
        logging.error(f"Error fetching jobs: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)
    

def retry_failed_jobs(request):
    """
    Retry failed jobs by resending their DICOM instances to the cloud.
    """
    try:
        # Step 1: Get the list of job IDs from Orthanc
        response = requests.get(f"{ORTHANC_URL}/jobs", auth=ORTHANC_AUTH)
        response.raise_for_status()
        job_ids = response.json()

        logging.info(f"Fetched {len(job_ids)} job IDs from Orthanc for retry.")  # ✅ Log number of jobs fetched

        retried_jobs = []  # Store successfully retried jobs

        # Step 2: Fetch details for each job to find failed ones
        for job_id in job_ids:
            job_response = requests.get(f"{ORTHANC_URL}/jobs/{job_id}", auth=ORTHANC_AUTH)
            job_response.raise_for_status()
            job_details = job_response.json()

            job_state = job_details.get("State")  # ✅ Fetch "State"
            logging.info(f"Checking job {job_id}: State = {job_state}")  # ✅ Log job state

            if job_state == "Failure":
                # Extract DICOM ID from ParentResources
                parent_resources = job_details.get("Content", {}).get("ParentResources", [])
                if not parent_resources:
                    logging.error(f"Job {job_id} failed, but no DICOM instances found.")
                    continue

                dicom_id = parent_resources[0]  # Taking the first resource
                logging.info(f"Job {job_id} failed. Retrying DICOM ID: {dicom_id}")  # ✅ Log DICOM ID

                # Step 3: Fetch the DICOM file from Orthanc
                dicom_response = requests.get(f"{ORTHANC_URL}/instances/{dicom_id}/file", auth=ORTHANC_AUTH)
                if dicom_response.status_code == 200:
                    files = {"file": ("dicom.dcm", dicom_response.content)}

                    # Step 4: Upload to cloud PACS
                    cloud_response = requests.post(f"{CLOUD_URL}/instances", files=files, auth=CLOUD_AUTH)

                    if cloud_response.status_code == 200:
                        logging.info(f"Successfully retried job {job_id} for DICOM {dicom_id}")
                        retried_jobs.append(job_id)
                    else:
                        logging.error(f"Failed to upload DICOM {dicom_id} to cloud: {cloud_response.text}")
                else:
                    logging.error(f"Failed to fetch DICOM {dicom_id} from Orthanc")

        logging.info(f"Total retried jobs: {len(retried_jobs)}")  # ✅ Log number of jobs retried

        return JsonResponse({"message": f"Retried {len(retried_jobs)} failed jobs."})

    except requests.RequestException as e:
        logging.error(f"Error retrying jobs: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

def home(request):
    return render(request, "index.html")