import asyncio
import logging
import sys

from automation_server_client import AutomationServer, Workqueue, WorkItemError, Credential
from kmd_nexus_client import NexusClient, CitizensClient, OrganizationsClient
import pandas as pd

nexus_client = None
citizens_client = None
organizations_client = None

# Path to the file containing the list of approved organizations
file_path_approved_organizations = r"Q:\RPA\Leverancer\Visitering til Lysningen\Liste over organisationer som muligvis skal have besked.xlsx"
approved_organizations = pd.read_excel(file_path_approved_organizations)
# Convert only the first column to a dictionary
tmp = [value for (_,value) in approved_organizations.iloc[:, 0].to_dict().items()]

async def populate_queue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    logger.info("Hello from populate workqueue!")

    all_organizations = organizations_client.get_organizations()

    for organization in all_organizations:
        if organization["name"] not in tmp:
            continue

        citizens = organizations_client.get_citizens_by_organization(organization)

        for citizen in citizens:
            data = {
                "cpr": citizen["patientIdentifier"]["identifier"],
                "organization": organization["name"]
            }

            try:
                # Add the item to the workqueue
                workqueue.add_item(data,data["cpr"])
            except Exception as e:
                logger.error(f"Error adding item to workqueue: {data}. Error: {e}")
    




async def process_workqueue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    logger.info("Hello from process workqueue!")



    for item in workqueue:
        with item:
            data = item.get_data_as_dict()
            citizen = citizens_client.get_citizen(data["cpr"])
            citizens_orgs = organizations_client.get_organizations_by_citizen(citizen=citizen)

            # Find the organization that should be updated
            updateable_organization = next((item for item in citizens_orgs if item["organization"]["name"] == data["organization"]), None)

            # If the organization is already the primary organization, skip it
            if updateable_organization["primaryOrganization"]:
                continue

            try:
                # Process the item here
                organizations_client.update_citizen_organization_relationship(organization_relation=updateable_organization,endDate=None, primary_organization=True)
                # Do some afregning eventually

                # Log
                logger.info(f"Opdateret organisation som primær: {data}")

                pass
            except WorkItemError as e:
                # A WorkItemError represents a soft error that indicates the item should be passed to manual processing or a business logic fault
                logger.error(f"Error processing item: {data}. Error: {e}")
                item.fail(str(e))


if __name__ == "__main__":
    ats = AutomationServer.from_environment()

    workqueue = ats.workqueue()

    # Initialize external systems for automation here..
    credential = Credential.get_credential("KMD Nexus - produktion")

    nexus_client = NexusClient(
        instance= credential.get_data_as_dict()["instance"],
        client_secret=credential.password,
        client_id=credential.username
    )
    citizens_client = CitizensClient(nexus_client=nexus_client)
    organizations_client = OrganizationsClient(nexus_client=nexus_client)

    # Queue management
    if "--queue" in sys.argv:
        workqueue.clear_workqueue("new")
        asyncio.run(populate_queue(workqueue))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue))
