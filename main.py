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
from kmd_nexus_client import NexusClientManager

# temp fix since no Q:\
from organizations import godkendte_organisationer

nexus_client_manager = None
tracking_client = None


async def populate_queue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)
    
    organisationer = nexus_client_manager.organisationer.hent_organisationer()

    for organisation in organisationer:
        if organisation["name"] not in godkendte_organisationer:
            continue

        borgere = nexus_client_manager.organisationer.hent_borgere_for_organisation(organisation)

        logger.info(f"Adding {len(borgere)} citizens from {organisation['name']}")

        for borger in borgere:
            if borger["patientIdentifier"]["type"] != "cpr":
                continue

            if borger["patientIdentifier"]["identifier"] in ["221354-1242", "010858-9995", "131313-1313", "251248-9996", "050505-9996"]:
                continue

            data = {
                "cpr": borger["patientIdentifier"]["identifier"],
                "organization": organisation["name"],
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
                borger = nexus_client_manager.borgere.hent_borger(data["cpr"])
                borger_organisationer = nexus_client_manager.organisationer.hent_organisationer_for_borger(
                    borger
                )

                # Find the organization that should be updated
                organisation_til_opdatering = next(
                    (
                        item
                        for item in borger_organisationer
                        if item["organization"]["name"] == data["organization"]
                    ),
                    None,
                )

                # Citizen no longer has the organization
                if not organisation_til_opdatering:
                    continue

                # If the organization is already the primary organization, skip it
                if organisation_til_opdatering["primaryOrganization"]:
                    continue

                # Process the item here
                nexus_client_manager.organisationer.opdater_borger_organisations_relation(
                    organization_relation=organisation_til_opdatering,
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

    nexus_client_manager = NexusClientManager(
        instance=credential.data["instance"],
        client_secret=credential.password,
        client_id=credential.username,
    )    

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
