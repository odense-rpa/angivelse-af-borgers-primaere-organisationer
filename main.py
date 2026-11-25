import argparse
import asyncio
import logging
import os

from odk_tools.tracking import Tracker
from automation_server_client import (
    AutomationServer,
    Workqueue,
    WorkItemError,
    Credential,
)
from kmd_nexus_client import NexusClientManager

from process.config import get_godkendte_organisationer, load_godkendte_organisationer

nexus: NexusClientManager
tracking_client: Tracker

async def populate_queue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    godkendte_organisationer = get_godkendte_organisationer()
    organisationer = nexus.organisationer.hent_organisationer()

    for organisation in organisationer:
        if organisation["name"] not in godkendte_organisationer:
            continue

        borgere = nexus.organisationer.hent_borgere_for_organisation(organisation)

        logger.info(f"Tilføjer {len(borgere)} borgere fra {organisation['name']}")

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
                workqueue.add_item(data, data["cpr"])
            except Exception as e:
                logger.error(f"Fejl ved tilføjelse af item til kø: {data}. Fejlbesked: {e}")


async def process_workqueue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    for item in workqueue:
        with item:
            data = item.data
            try:
                borger = nexus.borgere.hent_borger(data["cpr"])

                if not borger:
                    raise ValueError(f"Borger med CPR {data['cpr']} ikke fundet.")

                borger_organisationer = nexus.organisationer.hent_organisationer_for_borger(
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
                nexus.organisationer.opdater_borger_organisations_relation(
                    relation=organisation_til_opdatering,
                    slut_dato=None,
                    primær_organisation=True,
                )

                # Track the item
                tracking_client.track_task("Angivelse af borgers primære organisation")

                # Log
                logger.info(
                    f"Sat {data['organization']} som primær organisation på {data["cpr"]}"
                )

            except (ValueError, WorkItemError) as e:
                logger.error(f"Fejl ved behandling af item: {data}. Fejl: {e}")
                item.fail(str(e))

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO
    )

    parser = argparse.ArgumentParser(
        description="Angivelse af borgers primære organisationer"
    )
    parser.add_argument(
        "--excel-file",
        default="./godkendte_organisationer.xlsx",
        help="Path to the Excel file containing approved organizations (default: ./godkendte_organisationer.xlsx)",
    )
    parser.add_argument(
        "--queue",
        action="store_true",
        help="Populate the workqueue and exit (no processing)",
    )
    args = parser.parse_args()

    # Validate Excel file exists
    if not os.path.isfile(args.excel_file):
        raise FileNotFoundError(f"Excel file not found: {args.excel_file}")

    # Load approved organizations once on startup
    load_godkendte_organisationer(args.excel_file)

    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    # Initialize external systems
    credential = Credential.get_credential("KMD Nexus - produktion")
    tracking_credential = Credential.get_credential("Odense SQL Server")

    nexus = NexusClientManager(
        instance=credential.data["instance"],
        client_secret=credential.password,
        client_id=credential.username,
    )    

    tracking_client = Tracker(
        username=tracking_credential.username, password=tracking_credential.password
    )

    # Queue management
    if args.queue:
        workqueue.clear_workqueue("new")
        asyncio.run(populate_queue(workqueue))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue))
