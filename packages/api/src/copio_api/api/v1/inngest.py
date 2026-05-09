from fastapi import APIRouter

from copio_api.workers.inngest_app import inngest_client, register_functions

router = APIRouter()
inngest_app = register_functions(router, client=inngest_client)
