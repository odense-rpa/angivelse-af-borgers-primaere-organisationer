import asyncio
import logging
import sys

#import pandas as pd

from odk_tools.tracking import Tracker
from automation_server_client import (
    AutomationServer,
    Workqueue,
    WorkItemError,
    Credential,
)
from kmd_nexus_client import NexusClient, CitizensClient, OrganizationsClient

# temp fix since no Q:\
from organizations import approved_organizations

nexus_client = None
citizens_client = None
organizations_client = None
tracking_client = None


async def populate_queue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    all_organizations = organizations_client.get_organizations()

    for organization in all_organizations:
        if organization["name"] not in approved_organizations:
            continue

        citizens = organizations_client.get_citizens_by_organization(organization)

        logger.info(f"Adding {len(citizens)} citizens from {organization['name']}")

        for citizen in citizens:
            if citizen["patientIdentifier"]["type"] != "cpr":
                continue

            if citizen["patientIdentifier"]["identifier"] in ["221354-1242", "010858-9995", "131313-1313", "251248-9996", "050505-9996"]:
                continue

            data = {
                "cpr": citizen["patientIdentifier"]["identifier"],
                "organization": organization["name"],
            }

            try:
                # Add the item to the workqueue
                workqueue.add_item(data, data["cpr"])
            except Exception as e:
                logger.error(f"Error adding item to workqueue: {data}. Error: {e}")


async def process_workqueue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    for item in workqueue:
        with item:
            data = item.data
            try:
                citizen = citizens_client.get_citizen(data["cpr"])
                citizens_orgs = organizations_client.get_organizations_by_citizen(
                    citizen=citizen
                )

                # Find the organization that should be updated
                updateable_organization = next(
                    (
                        item
                        for item in citizens_orgs
                        if item["organization"]["name"] == data["organization"]
                    ),
                    None,
                )

                # Citizen no longer has the organization
                if not updateable_organization:
                    continue

                # If the organization is already the primary organization, skip it
                if updateable_organization["primaryOrganization"]:
                    continue

                # Process the item here
                organizations_client.update_citizen_organization_relationship(
                    organization_relation=updateable_organization,
                    endDate=None,
                    primary_organization=True,
                )

                # Track the item
                tracking_client.track_task("Angivelse af borgers primære organisation")

                # Log
                logger.info(
                    f"Sat {data['organization']} som primær organisation på {data["cpr"]}"
                )

            except ValueError as e:
                logger.error(f"Error processing item: {data}. Error: {e}")
                item.fail(str(e))
            except WorkItemError as e:
                logger.error(f"Error processing item: {data}. Error: {e}")
                item.fail(str(e))


if __name__ == "__main__":
    ats = AutomationServer.from_environment()

    workqueue = ats.workqueue()

    # Path to the file containing the list of approved organizations
    # file_path_approved_organizations = r"Q:\RPA\Leverancer\Visitering til Lysningen\Liste over organisationer som muligvis skal have besked.xlsx"
    # approved_organizations_raw = pd.read_excel(file_path_approved_organizations)
    # Convert only the first column to a dictionary
    # approved_organizations = [
    #     value for (_, value) in approved_organizations_raw.iloc[:, 0].to_dict().items()
    # ]

    # Initialize external systems
    credential = Credential.get_credential("KMD Nexus - produktion")
    tracking_credential = Credential.get_credential("Odense SQL Server")

    nexus_client = NexusClient(
        instance=credential.data["instance"],
        client_secret=credential.password,
        client_id=credential.username,
    )
    citizens_client = CitizensClient(nexus_client=nexus_client)
    organizations_client = OrganizationsClient(nexus_client=nexus_client)

    tracking_client = Tracker(
        username=tracking_credential.username, password=tracking_credential.password
    )

    # Queue management
    if "--queue" in sys.argv:
        workqueue.clear_workqueue("new")
        asyncio.run(populate_queue(workqueue))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue))
