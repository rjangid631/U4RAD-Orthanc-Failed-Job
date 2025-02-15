import requests
from django.http import JsonResponse
from django.shortcuts import render

ORTHANC_URL = "http://localhost:8042"
CLOUD_URL = "https://pacs.reportingbot.in"
ORTHANC_AUTH = ("admin", "phP@123!")  # Replace with actual credentials
CLOUD_AUTH = ("admin", "phP@123!")  # Replace with actual credentials

def fetch_failed_jobs(request):
    """
    Fetch job IDs and check for failed jobs after forcing Orthanc to refresh job statuses.
    """
    try:
        # Step 1: Force Orthanc to refresh its job list
        refresh_response = requests.post(f"{ORTHANC_URL}/jobs/reconstruct", auth=ORTHANC_AUTH)

        # Step 2: Get the updated list of job IDs
        response = requests.get(f"{ORTHANC_URL}/jobs", auth=ORTHANC_AUTH)
        response.raise_for_status()
        job_ids = response.json()

        failed_jobs = []  # Store failed jobs

        # Step 3: Fetch details of each job
        for job_id in job_ids:
            job_response = requests.get(f"{ORTHANC_URL}/jobs/{job_id}", auth=ORTHANC_AUTH)
            job_response.raise_for_status()
            job_details = job_response.json()

            job_state = job_details.get("State")  

            # Check if the job state is 'Failure'
            if job_state == "Failure":  
                failed_jobs.append({
                    "ID": job_id,
                    "DicomInstance": job_details.get("Content", {}).get("ParentResources", ["N/A"])[0],  # Extract first resource
                    "State": job_state,
                    "Description": job_details.get("ErrorDescription", "No description"),
                })

        return JsonResponse({"failed_jobs": failed_jobs})

    except requests.RequestException as e:
        return JsonResponse({"error": str(e)}, status=500)
    

def retry_failed_jobs(request):
    """
    Retry failed jobs by resending their DICOM instances to the cloud.
    """
    try:
        response = requests.get(f"{ORTHANC_URL}/jobs", auth=ORTHANC_AUTH)
        response.raise_for_status()
        job_ids = response.json()

        retried_jobs = []

        for job_id in job_ids:
            job_response = requests.get(f"{ORTHANC_URL}/jobs/{job_id}", auth=ORTHANC_AUTH)
            job_response.raise_for_status()
            job_details = job_response.json()

            job_state = job_details.get("State")

            if job_state == "Failure":
                parent_resources = job_details.get("Content", {}).get("ParentResources", [])
                if not parent_resources:
                    continue

                dicom_id = parent_resources[0]

                dicom_response = requests.get(f"{ORTHANC_URL}/instances/{dicom_id}/file", auth=ORTHANC_AUTH)
                if dicom_response.status_code == 200:
                    files = {"file": ("dicom.dcm", dicom_response.content)}

                    cloud_response = requests.post(f"{CLOUD_URL}/instances", files=files, auth=CLOUD_AUTH)

                    if cloud_response.status_code == 200:
                        retried_jobs.append(job_id)

                        # Delete old failed job after successful retry
                        requests.delete(f"{ORTHANC_URL}/jobs/{job_id}", auth=ORTHANC_AUTH)

        # Fetch updated failed jobs after retrying
        updated_failed_jobs_response = fetch_failed_jobs(request)
        updated_failed_jobs_data = updated_failed_jobs_response.content.decode("utf-8")

        return JsonResponse({
            "message": f"Retried {len(retried_jobs)} failed jobs.",
            "failed_jobs": updated_failed_jobs_data  # Return updated failed jobs list
        })

    except requests.RequestException as e:
        return JsonResponse({"error": str(e)}, status=500)

def home(request):
    return render(request, "index.html")